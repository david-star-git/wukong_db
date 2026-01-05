from core.db import get_db
from core.helpers import get_existing_years, get_existing_kws_for_year

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]


def get_week_overview_data(year):
    db = get_db()
    return {
        "all_years": list(range(2026, 2061)),
        "existing_years": get_existing_years(db),
        "existing_kws": get_existing_kws_for_year(db, year),
        "selected_year": year,
    }


def get_week_view_data(year, kw):
    conn = get_db()

    # ---- Get week id ----
    week = conn.execute(
        "SELECT id FROM weeks WHERE year=? AND week_number=?",
        (year, kw),
    ).fetchone()

    if not week:
        raise ValueError("Week not found")

    week_id = week["id"]

    # ---- Fetch workers (CSV order assumed by ID) ----
    workers_db = conn.execute(
        "SELECT id, display_name FROM workers ORDER BY id"
    ).fetchall()

    # ---- Fetch attendance with construction site info ----
    attendance_db = conn.execute(
        """
        SELECT
            a.worker_id,
            a.day,
            a.half,
            a.code AS site_id,
            cs.code AS site_code,
            cs.name AS site_name
        FROM attendance a
        LEFT JOIN construction_sites cs ON a.code = cs.id
        WHERE a.week_id=?
        """,
        (week_id,),
    ).fetchall()

    # ---- Fetch payroll ----
    payroll_db = conn.execute(
        """
        SELECT
            worker_id,
            salario,
            bonus,
            total,
            comment
        FROM payroll_reference
        WHERE week_id=?
        """,
        (week_id,),
    ).fetchall()

    # ---- Build base data structure ----
    data = {}
    for w in workers_db:
        data[w["id"]] = {
            "name": w["display_name"],
            "attendance": {},
            "salario": "",
            "bonus": "",
            "total": "",
            "comment": "",
        }

    # ---- Build attendance ----
    for a in attendance_db:
        wid = a["worker_id"]
        day = a["day"]
        half = a["half"]

        if wid not in data:
            continue

        worker_att = data[wid]["attendance"]
        worker_att.setdefault(day, {})

        # Display priority:
        # 1) site name
        # 2) site code (upper)
        # 3) numeric site id
        if a["site_name"]:
            display = a["site_name"]
        elif a["site_code"]:
            display = a["site_code"].upper()
        else:
            display = str(a["site_id"]) if a["site_id"] else ""

        worker_att[day][half] = display

    # ---- Build payroll ----
    for p in payroll_db:
        wid = p["worker_id"]
        if wid not in data:
            continue

        data[wid]["salario"] = str(p["salario"]) if p["salario"] is not None else ""
        data[wid]["bonus"] = str(p["bonus"]) if p["bonus"] is not None else ""
        data[wid]["total"] = str(p["total"]) if p["total"] is not None else ""
        data[wid]["comment"] = p["comment"] or ""

    return {
        "year": year,
        "kw": kw,
        "workers": data.values(),
        "day_names": DAY_NAMES,
    }
