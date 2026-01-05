import csv
import datetime
import sqlite3
import re

DAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado"]


def normalize_name(name: str) -> str:
    name = re.sub(r"^\d+\.\s*", "", name)
    return name.strip().upper()


def parse_money(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.findall(r"\d+", value)
    return int("".join(digits)) if digits else None


def import_csv(file, db_path="instance/app.db"):
    raw = file.read()
    text = raw.decode("utf-8", errors="replace")
    rows = list(csv.reader(text.splitlines(), delimiter=";"))
    header_row = rows[1]
    day_columns = {}
    col_idx = 1

    for day_idx, day in enumerate(DAYS):
        day_columns[day_idx] = [col_idx, col_idx + 1]  # AM, PM
        col_idx += 2

    salario_col = col_idx
    bonus_col = col_idx + 1
    total_col = col_idx + 3
    comment_col = col_idx + 5

    # --- extract week number ---
    try:
        kw = int(rows[0][1])
    except (IndexError, ValueError):
        raise ValueError("Could not parse week number from first row")
    year = datetime.date.today().year

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- check existing week ---
    cur.execute("SELECT id FROM weeks WHERE year=? AND week_number=?", (year, kw))
    existing = cur.fetchone()
    existed_before = bool(existing)

    if existing:
        week_id = existing["id"]
        # Delete old data if overwriting
        conn.execute("DELETE FROM attendance WHERE week_id=?", (week_id,))
        conn.execute("DELETE FROM payroll_reference WHERE week_id=?", (week_id,))
    else:
        cur.execute("INSERT INTO weeks (year, week_number) VALUES (?, ?)", (year, kw))
        week_id = cur.lastrowid

    # --- detect headers ---
    header = [h.strip().lower() for h in rows[1]]
    day_indices = {day: [] for day in DAYS}
    for i, h in enumerate(header):
        for day in DAYS:
            if h.startswith(day):
                day_indices[day].append(i)

    # Payroll columns
    try:
        salario_col = header.index("salario")
        bonus_col = header.index("bonus")
        total_col = header.index("total")
    except ValueError:
        salario_col = bonus_col = total_col = None

    # --- parse worker rows ---
    for sort_order, row in enumerate(rows[2:]):
        if not row or not any(c.strip() for c in row):
            continue

        display_name = re.sub(r'^\s*\d+[\.\-\s]*', '', row[0].strip())
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

        # --- attendance ---
        for day_idx, cols in day_columns.items():
            for half, col_idx in enumerate(cols, start=1):  # 1=AM, 2=PM
                if col_idx >= len(row):
                    continue
                site_code = row[col_idx].strip()
                if not site_code or site_code == "0":
                    continue

                # --- get or create construction site ---
                cur.execute(
                    "SELECT id FROM construction_sites WHERE code=?", (site_code,)
                )
                site = cur.fetchone()
                if site is not None:
                    site_id = site["id"]
                else:
                    cur.execute(
                        "INSERT INTO construction_sites (code, name, active) VALUES (?, ?, 1)",
                        (site_code, None),
                    )
                    site_id = cur.lastrowid

                # --- insert attendance using site_id ---
                cur.execute(
                    """
                    INSERT INTO attendance
                    (worker_id, week_id, day, half, code, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(worker_id, week_id, day, half) DO UPDATE SET code=excluded.code
                    """,
                    (worker_id, week_id, day_idx, half, site_id, sort_order),
                )

        # --- payroll ---
        salario = parse_money(
            row[salario_col]
            if salario_col is not None and salario_col < len(row)
            else None
        )
        bonus = parse_money(
            row[bonus_col] if bonus_col is not None and bonus_col < len(row) else None
        )
        total = parse_money(
            row[total_col] if total_col is not None and total_col < len(row) else None
        )

        comment = (
            row[comment_col].strip()
            if comment_col < len(row) and row[comment_col].strip()
            else None
        )

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
