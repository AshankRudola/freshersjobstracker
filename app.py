import yaml
import importlib
import os
import sys
import time as _time
import io

# Force webdriver-manager to use the local folder instead of user home

# Disable WDM progress bar and logging to keep stdout clean
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

# Robust stream handling for windowed environments (PyInstaller)
class DummyStream:
    def write(self, data): pass
    def flush(self): pass
    def isatty(self): return False
    @property
    def encoding(self): return 'utf-8'

if sys.stdout is None:
    sys.stdout = DummyStream()
if sys.stderr is None:
    sys.stderr = DummyStream()

# Force UTF-8 encoding for stdout/stderr if they are actual streams
if hasattr(sys.stdout, 'buffer') and getattr(sys.stdout, 'encoding', '') != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except (AttributeError, io.UnsupportedOperation):
        pass
if hasattr(sys.stderr, 'buffer') and getattr(sys.stderr, 'encoding', '') != 'utf-8':
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, io.UnsupportedOperation):
        pass

# Resolve base directory — works for both script and PyInstaller frozen exe
if getattr(sys, 'frozen', False):
    _exe_dir = os.path.dirname(sys.executable)
    if sys.platform == 'darwin' and _exe_dir.endswith('Contents/MacOS'):
        _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_exe_dir)))
    else:
        _BASE_DIR = _exe_dir
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import threading
from flask import Flask, render_template, jsonify, request, Response, stream_with_context
from apscheduler.schedulers.background import BackgroundScheduler

# Explicitly import scrapers so PyInstaller bundles them automatically
import scrapers.linkedin
import scrapers.naukri
import scrapers.indeed
import scrapers.unstop
import scrapers.shine

# Explicitly import Selenium internal modules for PyInstaller bundling
import selenium.webdriver.chrome.webdriver
import selenium.webdriver.chrome.options
import selenium.webdriver.chrome.service
import webdriver_manager.chrome
import selenium.webdriver.common.by
import selenium.webdriver.support.ui
import selenium.webdriver.support.expected_conditions
from storage import (
    init_db, upsert_jobs, list_jobs, set_reviewed, set_interested, set_comment,
    get_config, set_config, get_all_config,
    list_views, create_view, delete_view, rename_view,
    get_view_config, set_view_config, get_all_view_config,
    get_existing_urls, enforce_job_limit
)

# ── Global scrape state (for real-time progress modal) ────────────────────────
_scrape_lock = threading.Lock()
_scrape_state = {
    'running': False,
    'view_id': None,
    'view_name': '',
    'log': [],           # list of log-line strings
    'scraped': 0,        # raw jobs found
    'inserted': 0,       # new jobs inserted into DB
    'finished': False,
}

# File logger for debugging frozen EXE issues
_LOG_FILE = os.path.join(_BASE_DIR, 'debug_scrape.log')

def _push_log(msg: str):
    """Append a line to the live scrape log and write to file."""
    with _scrape_lock:
        _scrape_state['log'].append(msg)
    
    # Write to local debug file
    try:
        with open(_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{_time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass

    # Safely print to stderr if it exists
    try:
        if sys.stderr:
            print(msg, file=sys.stderr)
            sys.stderr.flush()
    except Exception:
        pass

app = Flask(__name__,
    template_folder=os.path.join(_BASE_DIR, 'templates'))

# Initialize database
init_db()

# Load YAML config (scrapers list + debug level — global, not per-view)
_CONFIG_PATH = os.path.join(_BASE_DIR, 'config.yaml')
yaml_cfg = yaml.safe_load(open(_CONFIG_PATH, 'r', encoding='utf-8'))

# ── Remote / Internship filter keyword sets ───────────────────────────────────
REMOTE_KEYWORDS = {
    'remote', 'wfh', 'work from home', 'work-from-home',
    'anywhere', 'virtual', 'telecommute', 'telecommuting',
    'fully remote', 'hybrid remote',
}
INTERNSHIP_KEYWORDS = {
    'intern', 'internship', 'trainee', 'apprentice',
    'graduate trainee', 'fresher',
}

# Debug level: 0=silent, 1=normal, 2=verbose, 3=debug
DEBUG_LEVEL = yaml_cfg.get('debug_level', 1)


def debug_print(level, msg):
    if DEBUG_LEVEL >= level:
        print(f"[DEBUG-{level}] {msg}", file=sys.stderr)


def write_scrapers_to_yaml(scrapers_list):
    """Update only the 'scrapers' section in config.yaml"""
    global yaml_cfg
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            full = yaml.safe_load(f) or {}
    except Exception:
        full = {}
    full['scrapers'] = scrapers_list
    tmp = _CONFIG_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        yaml.safe_dump(full, f, sort_keys=False, allow_unicode=True)
    os.replace(tmp, _CONFIG_PATH)
    yaml_cfg = yaml.safe_load(open(_CONFIG_PATH, 'r', encoding='utf-8'))


def load_scrapers(enabled_names: list = None):
    """
    Load scraper instances.
    If enabled_names is provided, only load scrapers whose name is in that list.
    Otherwise load all enabled scrapers from config.yaml.
    """
    instances = []
    infos = []
    for s in yaml_cfg.get('scrapers', []):
        # Global enabled flag from yaml
        if not s.get('enabled', True):
            continue
        # Per-view override: if caller specified which scrapers to use
        if enabled_names is not None and s['name'] not in enabled_names:
            continue
        try:
            mod = importlib.import_module(s['module'])
            cls = getattr(mod, s['class'])
            instances.append(cls())
            infos.append(s)
        except Exception as e:
            print(f"  ⚠️  Could not load scraper {s['name']}: {e}")
    if DEBUG_LEVEL >= 2:
        print(f"✓ Loaded {len(instances)} scraper(s)")
    return instances, infos


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    views = list_views()
    # Default to view 1; view switching is done client-side via JS + localStorage
    jobs = list_jobs(view_id=1)
    return render_template('index.html', jobs=jobs, views=views)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Jobs API
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/jobs')
def api_jobs():
    view_id = int(request.args.get('view', 1))
    jobs = list_jobs(view_id=view_id)
    return jsonify(jobs)


@app.route('/api/set_reviewed', methods=['POST'])
def api_set_reviewed():
    data = request.json
    set_reviewed(data['id'], 1 if data.get('reviewed') else 0)
    return jsonify({'ok': True})


@app.route('/api/set_interested', methods=['POST'])
def api_set_interested():
    data = request.json
    set_interested(data['id'], 1 if data.get('interested') else 0)
    return jsonify({'ok': True})


@app.route('/api/set_comment', methods=['POST'])
def api_set_comment():
    data = request.json
    set_comment(data['id'], data.get('comment', ''))
    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Views API
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/views', methods=['GET'])
def api_list_views():
    return jsonify(list_views())


@app.route('/api/views', methods=['POST'])
def api_create_view():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'ok': False, 'error': 'Name is required'}), 400
    try:
        view = create_view(name, data.get('description', ''))
        return jsonify({'ok': True, 'view': view})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400


@app.route('/api/views/<int:view_id>', methods=['DELETE'])
def api_delete_view(view_id):
    if view_id == 1:
        return jsonify({'ok': False, 'error': 'Cannot delete Default view'}), 400
    ok = delete_view(view_id)
    return jsonify({'ok': ok})


@app.route('/api/views/<int:view_id>', methods=['PATCH'])
def api_rename_view(view_id):
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'ok': False, 'error': 'Name is required'}), 400
    rename_view(view_id, name)
    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES — Settings / Config API
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/settings')
def settings():
    view_id = int(request.args.get('view', 1))
    views = list_views()
    view_cfg = _build_view_config(view_id)
    # Attach global scrapers list (with per-view enabled state overlay)
    view_cfg['scrapers'] = _get_per_view_scrapers(view_id)
    return render_template('settings.html', config=view_cfg, views=views, active_view_id=view_id)


def _build_view_config(view_id: int) -> dict:
    """Assemble the config dict for a given view."""
    return {
        'debug_level': yaml_cfg.get('debug_level', 1),
        'keywords': get_view_config(view_id, 'keywords', []),
        'locations': get_view_config(view_id, 'locations', []),
        'poll_interval_minutes': get_view_config(view_id, 'poll_interval_minutes', 60),
        'auto_scrape_enabled': get_view_config(view_id, 'auto_scrape_enabled', False),
        'remote_only': get_view_config(view_id, 'remote_only', False),
        'internship_only': get_view_config(view_id, 'internship_only', False),
    }


def _get_per_view_scrapers(view_id: int) -> list:
    """
    Return the scrapers list from config.yaml, with per-view enabled state.
    Per-view enabled state is stored in view_config as 'scrapers_enabled' (list of names).
    If not set, default to all globally-enabled scrapers being enabled for this view.
    """
    global_scrapers = yaml_cfg.get('scrapers', [])
    # Per-view override: which scraper names are enabled for this view
    per_view_enabled = get_view_config(view_id, 'scrapers_enabled', None)

    result = []
    for s in global_scrapers:
        s_copy = dict(s)
        if per_view_enabled is None:
            # No override yet — inherit global enabled state
            s_copy['view_enabled'] = s.get('enabled', True)
        else:
            s_copy['view_enabled'] = s['name'] in per_view_enabled
        result.append(s_copy)
    return result


@app.route('/api/config', methods=['GET'])
def api_get_config():
    view_id = int(request.args.get('view', 1))
    cfg = _build_view_config(view_id)
    cfg['scrapers'] = _get_per_view_scrapers(view_id)
    return jsonify(cfg)


@app.route('/api/config', methods=['POST'])
def api_update_config():
    view_id = int(request.args.get('view', 1))
    data = request.json or {}

    # Save per-view settings
    set_view_config(view_id, 'keywords', data.get('keywords', []))
    set_view_config(view_id, 'locations', data.get('locations', []))
    set_view_config(view_id, 'poll_interval_minutes', data.get('poll_interval_minutes', 60))
    set_view_config(view_id, 'auto_scrape_enabled', bool(data.get('auto_scrape_enabled', False)))
    set_view_config(view_id, 'remote_only', bool(data.get('remote_only', False)))
    set_view_config(view_id, 'internship_only', bool(data.get('internship_only', False)))

    # Save per-view scraper enabled state (list of enabled names)
    scrapers_data = data.get('scrapers', [])
    enabled_names = [s['name'] for s in scrapers_data if s.get('view_enabled', True)]
    set_view_config(view_id, 'scrapers_enabled', enabled_names)

    # Also update global enabled flag in config.yaml if changed
    # (global flag = enabled in ANY view — so only disable globally if ALL views disabled it)
    write_scrapers_to_yaml(
        [{k: v for k, v in s.items() if k != 'view_enabled'} for s in scrapers_data]
        if scrapers_data else yaml_cfg.get('scrapers', [])
    )

    if DEBUG_LEVEL >= 1:
        print(f"✓ View {view_id} config updated: "
              f"keywords={data.get('keywords', [])}, "
              f"remote_only={data.get('remote_only')}, "
              f"internship_only={data.get('internship_only')}")

    return jsonify({'ok': True})


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────────────────────────────────────

def _is_remote(job: dict) -> bool:
    combined = ((job.get('title') or '') + ' ' + (job.get('location') or '')).lower()
    return any(kw in combined for kw in REMOTE_KEYWORDS)


def _is_internship(job: dict) -> bool:
    title = (job.get('title') or '').lower()
    return any(kw in title for kw in INTERNSHIP_KEYWORDS)


def run_scrapers(view_id: int = None):
    """
    Run scrapers for a specific view (or all views if view_id is None).
    Each view uses its own keywords, locations, and mode filters.
    """
    if view_id is None:
        views_to_scrape = list_views()
    else:
        v = next((v for v in list_views() if v['id'] == view_id), None)
        views_to_scrape = [v] if v else [{'id': view_id, 'name': f'View {view_id}'}]

    for view in views_to_scrape:
        vid = view['id']
        vname = view.get('name', str(vid))
        _run_scrapers_for_view(vid, vname)


def _run_scrapers_for_view(view_id: int, view_name: str):
    _push_log(f'Scraping view "{view_name}"...')

    keywords = get_view_config(view_id, 'keywords', [])
    locations = get_view_config(view_id, 'locations', [])
    remote_only = get_view_config(view_id, 'remote_only', False)
    internship_only = get_view_config(view_id, 'internship_only', False)

    if not keywords:
        _push_log(f'No keywords configured for this view. Please add keywords in Settings.')
        return

    # If no locations provided, use an empty string to allow broad search
    effective_locations = locations if locations else [""]

    # Determine which scrapers to use for this view
    per_view_enabled = get_view_config(view_id, 'scrapers_enabled', None)
    scraper_instances, scraper_infos = load_scrapers(enabled_names=per_view_enabled)

    if not scraper_instances:
        _push_log('No scrapers enabled for this view.')
        return

    existing_urls = get_existing_urls(view_id=view_id)
    all_found = []

    search_count = 0
    for original_kw in keywords:
        for loc in effective_locations:
            search_kw = original_kw
            if internship_only and 'intern' not in search_kw.lower():
                search_kw += ' Internship'
            if remote_only and 'remote' not in search_kw.lower():
                search_kw += ' Remote'

            for i, s in enumerate(scraper_instances):
                scraper_name = 'unknown'
                try:
                    scraper_cfg = scraper_infos[i]
                    scraper_name = scraper_cfg.get('name', 'unknown')
                    total_max = scraper_cfg.get('max_results_per_search', 100)
                    max_results = total_max // max(len(keywords), 1)

                    search_count += 1
                    loc_label = loc if loc else 'All India'
                    _push_log(f'[{scraper_name.upper()}] Searching "{search_kw}" in {loc_label}...')

                    jobs = s.search(search_kw, loc, max_results=max_results, existing_urls=existing_urls)
                    for job in jobs:
                        job['keywords_tags'] = original_kw
                    all_found.extend(jobs)
                    for job in jobs:
                        existing_urls.add(job['url'])

                    with _scrape_lock:
                        _scrape_state['scraped'] += len(jobs)

                    _push_log(f'[{scraper_name.upper()}] Done — {len(jobs)} jobs found.')

                except Exception as e:
                    _push_log(f'[{scraper_name.upper()}] Error: {e}')

    if all_found:
        inserted = upsert_jobs(all_found, view_id=view_id)
        enforce_job_limit(1000, view_id=view_id)
        with _scrape_lock:
            _scrape_state['inserted'] += inserted
        _push_log(f'Done! {inserted} new jobs added to "{view_name}".')
    else:
        _push_log(f'No new jobs found for "{view_name}".')


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    data = request.json or {}
    view_id = data.get('view_id')
    if view_id is not None:
        view_id = int(view_id)

    with _scrape_lock:
        if _scrape_state['running']:
            return jsonify({'ok': False, 'message': 'Scraping already in progress'}), 409
        _scrape_state.update({
            'running': True,
            'view_id': view_id,
            'view_name': '',
            'log': ['Starting scrape...'],
            'scraped': 0,
            'inserted': 0,
            'finished': False,
        })

    def _run_and_finish(vid):
        try:
            run_scrapers(vid)
        finally:
            with _scrape_lock:
                _scrape_state['running'] = False
                _scrape_state['finished'] = True

    threading.Thread(target=_run_and_finish, args=(view_id,), daemon=True).start()
    return jsonify({'ok': True, 'message': 'Scraping started'})


@app.route('/api/scrape_status')
def api_scrape_status():
    """SSE endpoint — streams log lines to the browser in real time."""
    def event_stream():
        import time
        sent = 0
        while True:
            with _scrape_lock:
                log = _scrape_state['log']
                finished = _scrape_state['finished']
                scraped = _scrape_state['scraped']
                inserted = _scrape_state['inserted']

            # Send any new log lines
            while sent < len(log):
                line = log[sent].replace('\n', ' ')
                yield f'data: {line}\n\n'
                sent += 1

            if finished and sent >= len(log):
                # Send final summary event and close stream
                yield f'event: done\ndata: {{"scraped": {scraped}, "inserted": {inserted}}}\n\n'
                return

            time.sleep(0.4)

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/api/scrape_state')
def api_scrape_state():
    """JSON polling fallback for scrape state."""
    with _scrape_lock:
        return jsonify(dict(_scrape_state))


@app.route('/api/clear_jobs', methods=['POST'])
def api_clear_jobs():
    """
    Clear jobs in a view.
    Body: { view_id: int, mode: 'all' | 'selected', ids: [int, ...] }
    """
    data = request.json or {}
    view_id = int(data.get('view_id', 1))
    mode = data.get('mode', 'all')

    import sqlite3 as _sqlite3
    from storage import _lock
    with _lock:
        conn = _sqlite3.connect('jobs.db')
        c = conn.cursor()
        if mode == 'selected':
            ids = data.get('ids', [])
            if not ids:
                conn.close()
                return jsonify({'ok': False, 'error': 'No IDs provided'}), 400
            placeholders = ','.join('?' * len(ids))
            c.execute(
                f'DELETE FROM jobs WHERE view_id = ? AND id IN ({placeholders})',
                [view_id] + [int(i) for i in ids]
            )
        else:  # 'all'
            c.execute('DELETE FROM jobs WHERE view_id = ?', (view_id,))
        deleted = c.rowcount
        conn.commit()
        conn.close()

    print(f'🗑️  Cleared {deleted} job(s) from view {view_id} (mode={mode})')
    return jsonify({'ok': True, 'deleted': deleted})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()

    if DEBUG_LEVEL >= 1:
        try:
            print(f"Debug level: {DEBUG_LEVEL}")
            views = list_views()
            print(f"Views: {[v['name'] for v in views]}")
        except Exception:
            pass

    # Check if DB has data in the default view
    existing_jobs = list_jobs(view_id=1)
    has_data = len(existing_jobs) > 0

    # Scheduler: tick every 60s; only runs a view when its interval has elapsed.
    # Initialize _last_ran to NOW so no view fires immediately at boot.
    import time as _time
    _last_ran: dict = {v['id']: _time.time() for v in list_views()}

    def scheduler_tick():
        """Check each view's poll interval and run scrapers only if due."""
        now = _time.time()
        for view in list_views():
            vid = view['id']
            # Only run if auto-scrape is enabled (default to True for backward compatibility)
            is_enabled = get_view_config(vid, 'auto_scrape_enabled', False)
            if not is_enabled:
                continue

            interval_seconds = get_view_config(vid, 'poll_interval_minutes', 60) * 60
            if now - _last_ran.get(vid, now) >= interval_seconds:
                _last_ran[vid] = now
                _run_scrapers_for_view(vid, view['name'])

    scheduler = BackgroundScheduler()
    # misfire_grace_time=60 prevents harmless warnings if the 60s tick is delayed by a few seconds
    scheduler.add_job(scheduler_tick, 'interval', id='scheduler_tick', seconds=60, misfire_grace_time=60)
    scheduler.start()

    try:
        print("\n" + "=" * 60)
        print("Freshers Jobs Tracker is RUNNING")
        print("=" * 60)
        print("Web UI: http://127.0.0.1:5001")
        print("=" * 60)
        print(f"{len(existing_jobs)} existing job(s) in Default view")
        print("Click 'Scrape Now' in the UI to start scraping")
        print()
    except Exception:
        pass

    if DEBUG_LEVEL <= 1:
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

    app.run(host='0.0.0.0', port=5001, debug=False)
