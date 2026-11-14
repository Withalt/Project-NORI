import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT);
CREATE TABLE IF NOT EXISTS memories(
  id INTEGER PRIMARY KEY, ts REAL, kind TEXT, content TEXT, importance INTEGER DEFAULT 1);
-- External-content FTS table: triggers below must keep it in sync with memories
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
  content, content='memories', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
END;
CREATE TABLE IF NOT EXISTS llm_log(
  id INTEGER PRIMARY KEY, ts REAL, backend TEXT, ok INTEGER,
  first_token_s REAL, total_s REAL, error TEXT);
-- Reserved for emotion/motivation state in a later version
CREATE TABLE IF NOT EXISTS state(
  key TEXT PRIMARY KEY, value REAL);
"""


class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.executescript(SCHEMA)
        # Migration for databases created before the model column existed
        try:
            self.c.execute("ALTER TABLE llm_log ADD COLUMN model TEXT")
        except sqlite3.OperationalError:
            pass

    def add_message(self, role, content):
        self.c.execute("INSERT INTO messages(ts,role,content) VALUES(?,?,?)",
                       (time.time(), role, content))
        self.c.commit()

    def recent_messages(self, n):
        rows = self.c.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def log_llm(self, backend, ok, first_token_s=None, total_s=None, error=None, model=None):
        self.c.execute(
            "INSERT INTO llm_log(ts,backend,ok,first_token_s,total_s,error,model) "
            "VALUES(?,?,?,?,?,?,?)",
            (time.time(), backend, int(ok), first_token_s, total_s, error, model))
        self.c.commit()

    def llm_stats(self):
        rows = self.c.execute(
            "SELECT backend, ok, first_token_s FROM llm_log").fetchall()
        by = {}
        for backend, ok, first in rows:
            s = by.setdefault(backend, {"n": 0, "fail": 0, "empty": 0, "first": []})
            s["n"] += 1
            if not ok:
                s["fail"] += 1
            elif first is None:
                s["empty"] += 1
            else:
                s["first"].append(first)
        return by