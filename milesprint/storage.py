import json
import sqlite3
from contextlib import contextmanager
from time import time_ns


class Fault(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def now_ms():
    return time_ns() // 1_000_000


class Store:
    def __init__(self, path):
        self.path = path
        with self.transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY, alias TEXT NOT NULL UNIQUE,
                identity TEXT NOT NULL UNIQUE, observation TEXT NOT NULL,
                ceiling TEXT NOT NULL, overrides TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
                revision INTEGER NOT NULL DEFAULT 1)""")
            db.execute("""CREATE TABLE IF NOT EXISTS leases (
                id TEXT PRIMARY KEY, device_id TEXT NOT NULL REFERENCES devices(id),
                holder TEXT NOT NULL, task TEXT NOT NULL, worktree TEXT,
                intent TEXT NOT NULL, policy_revision INTEGER NOT NULL,
                credential TEXT NOT NULL, expires_at_ms INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('held','released','expired')),
                handoff TEXT)""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_held_per_device
                       ON leases(device_id) WHERE state = 'held'""")

            db.execute("""CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, at_ms INTEGER NOT NULL,
                event TEXT NOT NULL, subject TEXT, details TEXT NOT NULL)""")

    @contextmanager
    def transaction(self, *, read_only=False):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=2)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            if read_only:
                db.execute("PRAGMA query_only = ON")
            db.execute("BEGIN" if read_only else "BEGIN IMMEDIATE")
            yield db
            db.commit()
        except sqlite3.Error as exc:
            busy = getattr(exc, "sqlite_errorcode", 0) & 255 in (
                sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
            raise Fault("STORE_BUSY" if busy else "STORE_ERROR", "SQLite operation failed") from exc
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def device(db, target):
        row = db.execute("SELECT * FROM devices WHERE id = ? OR alias = ?", (target, target)).fetchall()
        if len(row) != 1:
            raise Fault("DEVICE_NOT_FOUND", "Provide an unambiguous device ID or alias")
        return row[0]


def audit(db, event, subject=None, **details):
    db.execute("INSERT INTO audit(at_ms, event, subject, details) VALUES (?, ?, ?, ?)",
               (now_ms(), event, subject, json.dumps(details)))
