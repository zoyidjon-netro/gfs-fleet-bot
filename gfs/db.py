import json
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT);
        CREATE TABLE IF NOT EXISTS groups(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, photo INTEGER NOT NULL,
          present INTEGER NOT NULL DEFAULT 1, unit TEXT, manual_unit TEXT);
        CREATE TABLE IF NOT EXISTS jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER NOT NULL,
          payload TEXT NOT NULL, due REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
          last_error TEXT);
        CREATE TABLE IF NOT EXISTS deliveries(
          job INTEGER NOT NULL, occurrence REAL NOT NULL, chat INTEGER NOT NULL,
          state TEXT NOT NULL, error TEXT, PRIMARY KEY(job, occurrence, chat));
        CREATE TABLE IF NOT EXISTS audits(id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER NOT NULL,
          created REAL NOT NULL, filename TEXT, state TEXT NOT NULL, result TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY, owner INTEGER NOT NULL, kind TEXT NOT NULL);
        ''')
        if "details" not in {row[1] for row in self.conn.execute("PRAGMA table_info(audits)")}:
            self.conn.execute("ALTER TABLE audits ADD COLUMN details TEXT")
        self.conn.commit()

    def execute(self, sql, args=()):
        cur = self.conn.execute(sql, args)
        self.conn.commit()
        return cur

    def rows(self, sql, args=()):
        return [dict(x) for x in self.conn.execute(sql, args).fetchall()]

    def is_admin(self, uid):
        return bool(self.rows("SELECT id FROM admins WHERE id=?", (uid,)))

    def groups(self):
        return self.rows("SELECT * FROM groups ORDER BY title")

    def save_group(self, chat, present=True):
        self.execute('''INSERT INTO groups(id,title,photo,present) VALUES(?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET title=excluded.title,photo=excluded.photo,present=excluded.present''',
          (chat.id, chat.title or "", bool(chat.photo), present))

    def remap(self, trucks):
        from .domain import resolve_unit
        units = {t["unit"] for t in trucks}
        for group in self.groups():
            self.execute("UPDATE groups SET unit=? WHERE id=?", (resolve_unit(group["title"], units), group["id"]))

    def jobs(self):
        jobs = self.rows("SELECT * FROM jobs ORDER BY id DESC LIMIT 200")
        for job in jobs:
            job["payload"] = json.loads(job["payload"])
            job["deliveries"] = self.rows("SELECT occurrence,chat,state,error FROM deliveries WHERE job=? ORDER BY occurrence DESC LIMIT 500", (job["id"],))
        return jobs
