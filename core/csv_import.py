import csv
import datetime
import sqlite3
import re
from typing import BinaryIO

DAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado"]


def normalize_name(name: str) -> str:
    """
    Worker names come from human-edited CSVs and may contain numbering,
    spacing inconsistencies, or casing differences. We normalize to ensure
    we can reliably identify the same worker across multiple imports.
    """
    name = re.sub(r"^\d+\.\s*", "", name)
    return name.strip().upper()


def parse_money(value: str | None) -> int | None:
    """
    Payroll values may include currency symbols, separators, or text.
    We extract digits only so formatting differences don't break imports.
    """
    if not value:
        return None
    digits = re.findall(r"\d+", value)
    return int("".join(digits)) if digits else None


def read_csv(file: BinaryIO) -> list[list[str]]:
    """
    CSV files may come from Excel with inconsistent encodings.
    We decode defensively and split lines ourselves to avoid crashes.
    """
    raw = file.read()
    text = raw.decode("utf-8", errors="replace")
    return list(csv.reader(text.splitlines(), delimiter=";"))


def extract_week_info(rows: list[list[str]]) -> tuple[int, int]:
    """
    The week number is encoded in the CSV header instead of the filename.
    We trust the CSV over external metadata to avoid mismatches.
    """
    try:
        kw = int(rows[0][1])
    except (IndexError, ValueError):
        raise ValueError("Could not parse week number from first row")

    year = datetime.date.today().year
    return kw, year


def detect_columns(
    header: list[str],
) -> tuple[dict[int, list[int]], dict[str, int | None]]:
    """
    CSV column order is not guaranteed. We detect columns by name
    instead of hardcoding indices to keep imports robust to layout changes.
    """
    header = [h.strip().lower() for h in header]

    day_columns = {}
    col_idx = 1
    for day_idx, _ in enumerate(DAYS):
        day_columns[day_idx] = [col_idx, col_idx + 1]  # AM, PM
        col_idx += 2

    def find(name):
        return header.index(name) if name in header else None

    payroll_cols = {
        "salario": find("salario"),
        "bonus": find("bonus"),
        "total": find("total"),
        "comment": find("comentario") or (col_idx + 5),
    }

    return day_columns, payroll_cols


def prepare_week(conn, year: int, kw: int) -> tuple[int, bool]:
    """
    Weeks are unique per (year, week_number).
    If the week exists, we overwrite *only dependent data* instead of
    deleting the week itself to preserve foreign key stability.
    """
    cur = conn.cursor()
    cur.execute("SELECT id FROM weeks WHERE year=? AND week_number=?", (year, kw))
    existing = cur.fetchone()

    if existing:
        week_id = existing["id"]
        conn.execute("DELETE FROM attendance WHERE week_id=?", (week_id,))
        conn.execute("DELETE FROM payroll_reference WHERE week_id=?", (week_id,))
        return week_id, True

    cur.execute("INSERT INTO weeks (year, week_number) VALUES (?, ?)", (year, kw))
    return cur.lastrowid, False


def upsert_worker(cur, display_name: str) -> int:
    """
    Workers are identified by normalized names, not IDs,
    because IDs are DB-internal and CSVs don't contain them.
    """
    normalized = normalize_name(display_name)

    cur.execute(
        """
        INSERT OR IGNORE INTO workers (display_name, normalized_name, active)
        VALUES (?, ?, 1)
        """,
        (display_name, normalized),
    )
    cur.execute("SELECT id FROM workers WHERE normalized_name=?", (normalized,))
    return cur.fetchone()["id"]


def upsert_site(cur, site_code: str) -> int:
    """
    Construction sites may appear in attendance before metadata exists.
    We create them lazily to keep imports single-pass.
    """
    cur.execute("SELECT id FROM construction_sites WHERE code=?", (site_code,))
    row = cur.fetchone()
    if row:
        return row["id"]

    cur.execute(
        """
        INSERT INTO construction_sites (code, name, active)
        VALUES (?, NULL, 1)
        """,
        (site_code,),
    )
    return cur.lastrowid


def insert_attendance(cur, worker_id, week_id, day, half, site_id, sort_order):
    """
    Attendance is uniquely defined per worker/day/half/week.
    We use UPSERT to allow safe re-imports.
    """
    cur.execute(
        """
        INSERT INTO attendance
        (worker_id, week_id, day, half, code, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(worker_id, week_id, day, half)
        DO UPDATE SET code=excluded.code
        """,
        (worker_id, week_id, day, half, site_id, sort_order),
    )


def insert_payroll(cur, worker_id, week_id, salario, bonus, total, comment):
    """
    Payroll is recalculated externally and treated as authoritative.
    We replace existing rows instead of diffing values.
    """
    cur.execute(
        """
        INSERT OR REPLACE INTO payroll_reference
        (worker_id, week_id, salario, bonus, total, comment)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (worker_id, week_id, salario, bonus, total, comment),
    )


def import_csv(file, db_path="instance/app.db"):
    rows = read_csv(file)
    kw, year = extract_week_info(rows)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    week_id, existed_before = prepare_week(conn, year, kw)

    day_columns, payroll_cols = detect_columns(rows[1])
    cur = conn.cursor()

    for sort_order, row in enumerate(rows[2:]):
        if not row or not any(c.strip() for c in row):
            continue

        display_name = re.sub(r"^\s*\d+[\.\-\s]*", "", row[0].strip())
        if not any(c.isalpha() for c in display_name):
            continue

        worker_id = upsert_worker(cur, display_name)

        # Attendance
        for day_idx, cols in day_columns.items():
            for half, col_idx in enumerate(cols, start=1):
                if col_idx >= len(row):
                    continue
                site_code = row[col_idx].strip()
                if not site_code or site_code == "0":
                    continue

                site_id = upsert_site(cur, site_code)
                insert_attendance(
                    cur, worker_id, week_id, day_idx, half, site_id, sort_order
                )

        # Payroll
        insert_payroll(
            cur,
            worker_id,
            week_id,
            (
                parse_money(row[payroll_cols["salario"]])
                if payroll_cols["salario"] is not None
                else None
            ),
            (
                parse_money(row[payroll_cols["bonus"]])
                if payroll_cols["bonus"] is not None
                else None
            ),
            (
                parse_money(row[payroll_cols["total"]])
                if payroll_cols["total"] is not None
                else None
            ),
            (
                row[payroll_cols["comment"]].strip()
                if payroll_cols["comment"] and payroll_cols["comment"] < len(row)
                else None
            ),
        )

    conn.commit()
    conn.close()

    return kw, year, existed_before
