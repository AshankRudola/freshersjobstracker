import sqlite3
conn = sqlite3.connect('jobs.db')
c = conn.cursor()
c.execute("SELECT value FROM view_config WHERE view_id=1 AND key='scrapers_enabled'")
row = c.fetchone()
print(f"Row: {row}")
