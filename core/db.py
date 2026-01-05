import sqlite3
from pathlib import Path

DB_PATH = Path("instance/app.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    with open("schema.sql", "rb") as f:
        sql = f.read().decode("utf-8", errors="replace")
        conn.executescript(sql)

    conn.commit()
    conn.close()
