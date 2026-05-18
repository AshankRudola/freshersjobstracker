import re
import os
import sys
from datetime import datetime, timezone

def get_base_dir():
    """Resolve base directory — works whether run as a script or a PyInstaller exe"""
    if getattr(sys, 'frozen', False):
        _exe_dir = os.path.dirname(sys.executable)
        if sys.platform == 'darwin' and _exe_dir.endswith('Contents/MacOS'):
            return os.path.dirname(os.path.dirname(os.path.dirname(_exe_dir)))
        return _exe_dir
    return os.path.dirname(os.path.abspath(__file__))

def get_job_age_hours(date_str):
    if not date_str or date_str in ('N/D', 'N/A'):
        return 999999
    date_str_stripped = date_str.strip()
    s = date_str_stripped.lower()

    if 'today' in s or 'just now' in s:
        return 0

    match = re.search(r'\d+', s)
    num = int(match.group()) if match else 1

    if re.search(r'\b(sec|secs|second|seconds)\b', s): return num / 3600
    if re.search(r'\b(min|mins|minute|minutes)\b', s): return num / 60
    if re.search(r'\b(h|hr|hrs|hour|hours)\b', s): return num
    if re.search(r'\b(d|day|days)\b', s): return num * 24
    if re.search(r'\b(w|wk|wks|week|weeks)\b', s): return num * 24 * 7
    if re.search(r'\b(m|mo|mos|month|months)\b', s): return num * 24 * 30
    if re.search(r'\b(y|yr|yrs|year|years)\b', s): return num * 24 * 365

    # Fallback: try to parse as a calendar date (e.g. "May 1, 2025", "2025-05-01", "1 May 2025")
    formats = [
        '%B %d, %Y',   # May 1, 2025
        '%b %d, %Y',   # May 1, 2025 (abbreviated)
        '%d %B %Y',    # 1 May 2025
        '%d %b %Y',    # 1 May 2025 (abbreviated)
        '%Y-%m-%d',    # 2025-05-01
        '%d/%m/%Y',    # 01/05/2025
        '%m/%d/%Y',    # 05/01/2025
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str_stripped, fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return max((now - dt).total_seconds() / 3600, 0)
        except ValueError:
            continue

    return 999999
