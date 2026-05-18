import sqlite3
import threading
import json
import os
import sys
from typing import List, Dict, Any, Optional

# Resolve base directory — works whether run as a script or a PyInstaller exe
if getattr(sys, 'frozen', False):
    # If running in a PyInstaller bundle
    _exe_dir = os.path.dirname(sys.executable)
    # Check if it's inside a macOS .app bundle
    if sys.platform == 'darwin' and _exe_dir.endswith('Contents/MacOS'):
        _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(_exe_dir)))
    else:
        _BASE_DIR = _exe_dir
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(_BASE_DIR, 'jobs.db')
_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# DB INIT
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # ── Views table ──────────────────────────────────────────────────────
        c.execute('''
        CREATE TABLE IF NOT EXISTS views (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        # Ensure the Default view (id=1) always exists
        c.execute("INSERT OR IGNORE INTO views (id, name, description) VALUES (1, 'Default', 'Default view')")

        # ── Per-view config table ────────────────────────────────────────────
        c.execute('''
        CREATE TABLE IF NOT EXISTS view_config (
            view_id INTEGER NOT NULL,
            key     TEXT    NOT NULL,
            value   TEXT,
            PRIMARY KEY (view_id, key)
        )
        ''')

        # ── Jobs table ───────────────────────────────────────────────────────
        c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id           INTEGER PRIMARY KEY,
            view_id      INTEGER DEFAULT 1,
            title        TEXT,
            company      TEXT,
            location     TEXT,
            url          TEXT,
            posted_date  TEXT,
            experience   TEXT DEFAULT 'N/A',
            reviewed     INTEGER DEFAULT 0,
            interested   INTEGER DEFAULT 0,
            comment      TEXT DEFAULT '',
            keywords_tags TEXT DEFAULT '[]',
            source       TEXT DEFAULT 'unknown',
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(view_id, url)
        )
        ''')

        # ── Migrations for existing DBs ──────────────────────────────────────
        c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'")
        sql = c.fetchone()[0]
        if 'url          TEXT UNIQUE' in sql:
            # Fix global UNIQUE constraint to per-view UNIQUE constraint
            c.execute('ALTER TABLE jobs RENAME TO jobs_old')
            c.execute('''
            CREATE TABLE jobs (
                id           INTEGER PRIMARY KEY,
                view_id      INTEGER DEFAULT 1,
                title        TEXT,
                company      TEXT,
                location     TEXT,
                url          TEXT,
                posted_date  TEXT,
                experience   TEXT DEFAULT 'N/A',
                reviewed     INTEGER DEFAULT 0,
                interested   INTEGER DEFAULT 0,
                comment      TEXT DEFAULT '',
                keywords_tags TEXT DEFAULT '[]',
                source       TEXT DEFAULT 'unknown',
                created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(view_id, url)
            )
            ''')
            c.execute('''
            INSERT INTO jobs (id, view_id, title, company, location, url, posted_date, experience, reviewed, interested, comment, keywords_tags, source, created_at)
            SELECT id, view_id, title, company, location, url, posted_date, experience, reviewed, interested, comment, keywords_tags, source, created_at FROM jobs_old
            ''')
            c.execute('DROP TABLE jobs_old')
        c.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in c.fetchall()}

        if 'reviewed' not in columns:
            c.execute("ALTER TABLE jobs ADD COLUMN reviewed INTEGER DEFAULT 0")
        if 'interested' not in columns:
            c.execute("ALTER TABLE jobs ADD COLUMN interested INTEGER DEFAULT 0")
        if 'keywords_tags' not in columns:
            c.execute("ALTER TABLE jobs ADD COLUMN keywords_tags TEXT DEFAULT '[]'")
        if 'experience' not in columns:
            c.execute("ALTER TABLE jobs ADD COLUMN experience TEXT DEFAULT 'N/A'")
        if 'source' not in columns:
            c.execute("ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'unknown'")
        if 'view_id' not in columns:
            c.execute("ALTER TABLE jobs ADD COLUMN view_id INTEGER DEFAULT 1")

        # Migrate flag → interested
        if 'flag' in columns and 'interested' in columns:
            try:
                c.execute("UPDATE jobs SET interested = flag WHERE interested = 0 AND flag = 1")
            except Exception:
                pass

        # ── Global app_config (non-view-specific) ────────────────────────────
        c.execute('''
        CREATE TABLE IF NOT EXISTS app_config (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        ''')

        conn.commit()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONFIG (non-view-specific)
# ─────────────────────────────────────────────────────────────────────────────

def get_config(key: str, default=None):
    """Get a global config value from DB"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT value FROM app_config WHERE key = ?', (key,))
        row = c.fetchone()
        conn.close()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return default


def set_config(key: str, value):
    """Set a global config value in DB"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            'INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)',
            (key, json.dumps(value))
        )
        conn.commit()
        conn.close()


def get_all_config():
    """Get all global config"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT key, value FROM app_config')
        rows = c.fetchall()
        conn.close()
        result = {}
        for key, value in rows:
            try:
                result[key] = json.loads(value)
            except Exception:
                result[key] = value
        return result


# ─────────────────────────────────────────────────────────────────────────────
# VIEWS CRUD
# ─────────────────────────────────────────────────────────────────────────────

def list_views() -> List[Dict[str, Any]]:
    """Return all views ordered by id"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM views ORDER BY id')
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]


def create_view(name: str, description: str = '') -> Dict[str, Any]:
    """Create a new view. Returns the new view dict."""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            'INSERT INTO views (name, description) VALUES (?, ?)',
            (name.strip(), description.strip())
        )
        view_id = c.lastrowid
        conn.commit()
        c.execute('SELECT * FROM views WHERE id = ?', (view_id,))
        row = c.fetchone()
        conn.close()
        return dict(row)


def delete_view(view_id: int) -> bool:
    """Delete a view and all its jobs and config. Returns False if id==1 (Default protected)."""
    if int(view_id) == 1:
        return False  # Default view is protected
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM jobs WHERE view_id = ?', (view_id,))
        c.execute('DELETE FROM view_config WHERE view_id = ?', (view_id,))
        c.execute('DELETE FROM views WHERE id = ?', (view_id,))
        conn.commit()
        conn.close()
    return True


def rename_view(view_id: int, new_name: str) -> bool:
    """Rename a view."""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE views SET name = ? WHERE id = ?', (new_name.strip(), view_id))
        conn.commit()
        conn.close()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# PER-VIEW CONFIG
# ─────────────────────────────────────────────────────────────────────────────

def get_view_config(view_id: int, key: str, default=None):
    """Get a per-view config value"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT value FROM view_config WHERE view_id = ? AND key = ?', (view_id, key))
        row = c.fetchone()
        conn.close()
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return default


def set_view_config(view_id: int, key: str, value):
    """Set a per-view config value"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            'INSERT OR REPLACE INTO view_config (view_id, key, value) VALUES (?, ?, ?)',
            (view_id, key, json.dumps(value))
        )
        conn.commit()
        conn.close()


def get_all_view_config(view_id: int) -> Dict[str, Any]:
    """Get all config for a specific view"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT key, value FROM view_config WHERE view_id = ?', (view_id,))
        rows = c.fetchall()
        conn.close()
        result = {}
        for key, value in rows:
            try:
                result[key] = json.loads(value)
            except Exception:
                result[key] = value
        return result


# ─────────────────────────────────────────────────────────────────────────────
# JOBS
# ─────────────────────────────────────────────────────────────────────────────

def upsert_jobs(jobs: List[Dict[str, Any]], view_id: int = 1) -> int:
    """Insert jobs tagged with view_id, deduplicating by URL (unique constraint)."""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Existing fingerprints for this view (for tag merging)
        c.execute(
            'SELECT id, title, company, location, posted_date, keywords_tags, experience '
            'FROM jobs WHERE view_id = ?',
            (view_id,)
        )
        existing = {}
        for row in c.fetchall():
            fingerprint = (row[1], row[2], row[3], row[4])
            existing[fingerprint] = {'id': row[0], 'tags': row[5], 'experience': row[6]}

        inserted = 0
        for job in jobs:
            fingerprint = (
                job.get('title'), job.get('company'),
                job.get('location'), job.get('posted_date')
            )

            if fingerprint in existing:
                # Merge keyword tags
                existing_id = existing[fingerprint]['id']
                if job.get('keywords_tags'):
                    try:
                        existing_tags = json.loads(existing[fingerprint]['tags']) if existing[fingerprint]['tags'] else []
                    except Exception:
                        existing_tags = []
                    new_tags = job.get('keywords_tags')
                    if isinstance(new_tags, str):
                        new_tags = [new_tags]
                    for tag in new_tags:
                        if tag not in existing_tags:
                            existing_tags.append(tag)
                    c.execute('UPDATE jobs SET keywords_tags = ? WHERE id = ?',
                               (json.dumps(existing_tags), existing_id))
                continue

            try:
                tags = job.get('keywords_tags', [])
                if isinstance(tags, str):
                    tags = [tags]
                c.execute('''
                INSERT OR IGNORE INTO jobs
                    (view_id, title, company, location, url, posted_date,
                     experience, reviewed, interested, keywords_tags, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                ''', (
                    view_id,
                    job.get('title'), job.get('company'), job.get('location'),
                    job.get('url'), job.get('posted_date'),
                    str(job.get('experience', 'N/A')),
                    json.dumps(tags),
                    job.get('source', 'unknown')
                ))
                inserted += 1
                existing[fingerprint] = {
                    'id': None,
                    'tags': json.dumps(tags),
                    'experience': str(job.get('experience', 'N/A'))
                }
            except Exception:
                pass

        conn.commit()
        conn.close()
        return inserted


def list_jobs(view_id: int = 1) -> List[Dict[str, Any]]:
    """Return all jobs for a specific view, newest first"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM jobs WHERE view_id = ? ORDER BY created_at DESC', (view_id,))
        rows = c.fetchall()
        conn.close()
        return [dict(r) for r in rows]


def get_existing_urls(view_id: int = 1) -> set:
    """Return set of URLs already in DB for a given view"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            'SELECT url FROM jobs WHERE view_id = ? AND url IS NOT NULL AND url != "N/D"',
            (view_id,)
        )
        rows = c.fetchall()
        conn.close()
        return set(row[0] for row in rows)


def enforce_job_limit(limit: int = 1000, view_id: int = 1) -> int:
    """Keep only the most recent 'limit' jobs for a view"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
        DELETE FROM jobs
        WHERE view_id = ? AND id NOT IN (
            SELECT id FROM jobs WHERE view_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        )
        ''', (view_id, view_id, limit))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        return deleted


# ─────────────────────────────────────────────────────────────────────────────
# JOB ACTIONS (view-agnostic, by id)
# ─────────────────────────────────────────────────────────────────────────────

def set_reviewed(job_id: int, reviewed: int):
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE jobs SET reviewed = ? WHERE id = ?', (reviewed, job_id))
        conn.commit()
        conn.close()


def set_interested(job_id: int, interested: int):
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE jobs SET interested = ? WHERE id = ?', (interested, job_id))
        conn.commit()
        conn.close()


def set_comment(job_id: int, comment: str):
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE jobs SET comment = ? WHERE id = ?', (comment, job_id))
        conn.commit()
        conn.close()


def set_flag(job_id: int, flag: int):
    """Legacy — kept for compatibility"""
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE jobs SET interested = ? WHERE id = ?', (flag, job_id))
        conn.commit()
        conn.close()


def add_keywords_tag(job_id: int, keyword: str):
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT keywords_tags FROM jobs WHERE id = ?', (job_id,))
        row = c.fetchone()
        if row:
            try:
                tags = json.loads(row[0]) if row[0] else []
            except Exception:
                tags = []
            if keyword not in tags:
                tags.append(keyword)
                c.execute('UPDATE jobs SET keywords_tags = ? WHERE id = ?',
                           (json.dumps(tags), job_id))
        conn.commit()
        conn.close()


def set_keywords_tags(job_id: int, tags: List[str]):
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE jobs SET keywords_tags = ? WHERE id = ?', (json.dumps(tags), job_id))
        conn.commit()
        conn.close()
