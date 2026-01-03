import csv
import datetime
import sqlite3
import re

DAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado"]


def normalize_name(name: str) -> str:
    # Remove leading numbers + dot
    name = re.sub(r"^\d+\.\s*", "", name)
    return name.strip().upper()


def parse_money(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.findall(r"\d+", value)
    return int("".join(digits)) if digits else None


def import_csv(file, db_path="instance/app.db"):
    """
    Imports a CSV file into the database.
    If overwrite=False and the week exists, returns (kw, year, exists=True)
    instead of overwriting.
    """
    raw = file.read()
    text = raw.decode("utf-8", errors="replace")
    rows = list(csv.reader(text.splitlines()))

    kw = int(rows[0][1])
    year = datetime.date.today().year

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- check existing week ---
    cur.execute("SELECT id FROM weeks WHERE year=? AND kalenderwoche=?", (year, kw))
    existing = cur.fetchone()
    existed_before = bool(existing)

    if existing:
        week_id = existing["id"]
        exists = True
        # Delete old data if overwriting
        conn.execute("DELETE FROM attendance WHERE week_id=?", (week_id,))
        conn.execute("DELETE FROM payroll_reference WHERE week_id=?", (week_id,))
    else:
        conn.execute(
            "INSERT INTO weeks (year, kalenderwoche) VALUES (?, ?)", (year, kw)
        )
        week_id = conn.lastrowid
        exists = False

    # --- parse workers in CSV order ---
    for sort_order, row in enumerate(rows[2:]):
        if not row or not row[0].strip():
            continue

        display_name = re.sub(r"^\d+\.\s*", "", row[0]).strip()
        if not any(c.isalpha() for c in display_name):
            continue

        normalized = normalize_name(display_name)

        # Insert worker if not exists
        cur.execute(
            "INSERT OR IGNORE INTO workers (display_name, normalized_name, active) VALUES (?, ?, 1)",
            (display_name, normalized),
        )
        cur.execute("SELECT id FROM workers WHERE normalized_name=?", (normalized,))
        worker_id = cur.fetchone()["id"]

        # Insert attendance
        for day_idx in range(6):
            base_col = 1 + day_idx * 2
            for half in (1, 2):
                if len(row) <= base_col + (half - 1):
                    continue
                code = row[base_col + (half - 1)].strip()
                if not code or code == "0":
                    continue
                cur.execute(
                    """
                    INSERT OR REPLACE INTO attendance
                    (worker_id, week_id, day, half, code, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (worker_id, week_id, day_idx, half, code, sort_order),
                )

        # Insert payroll reference
        salario = parse_money(row[14] if len(row) > 14 else None)
        bonus = parse_money(row[15] if len(row) > 15 else None)
        total = parse_money(row[17] if len(row) > 17 else None)
        comment = row[18].strip() if len(row) > 18 else None

        cur.execute(
            """
            INSERT OR REPLACE INTO payroll_reference
            (worker_id, week_id, salario, bonus, total, comment)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (worker_id, week_id, salario, bonus, total, comment),
        )

    conn.commit()
    conn.close()
    return kw, year, existed_before
