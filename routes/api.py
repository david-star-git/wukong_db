from flask import Blueprint, jsonify
from db.db import get_db

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/worker/<int:worker_id>/profile")
def worker_profile(worker_id):
    conn = get_db()

    worker = conn.execute(
        """
        SELECT id, display_name, cedula, active
        FROM workers
        WHERE id=?
    """,
        (worker_id,),
    ).fetchone()

    stats = conn.execute(
        """
        SELECT
            COUNT(a.id) * 0.5 AS total_days,
            COALESCE(SUM(p.salario), 0) AS total_salary,
            COALESCE(SUM(p.bonus), 0) AS total_bonus
        FROM attendance a
        LEFT JOIN payroll_reference p
            ON p.worker_id = a.worker_id
           AND p.week_id = a.week_id
        WHERE a.worker_id = ?
    """,
        (worker_id,),
    ).fetchone()

    return jsonify(
        {
            "worker": dict(worker),
            "stats": dict(stats),
        }
    )


@api_bp.route("/api/worker/<int:worker_id>/charts")
def worker_charts(worker_id):
    conn = get_db()

    weeks = conn.execute(
        """
        SELECT id, year, week_number
        FROM weeks
        ORDER BY year DESC, week_number DESC
        LIMIT 12
    """
    ).fetchall()

    weeks = list(reversed(weeks))
    week_ids = [w["id"] for w in weeks]

    # --- days worked per week ---
    days = {w["id"]: 0 for w in weeks}
    rows = conn.execute(
        """
        SELECT week_id, COUNT(*) * 0.5 AS days
        FROM attendance
        WHERE worker_id=?
          AND week_id IN ({})
        GROUP BY week_id
    """.format(
            ",".join("?" * len(week_ids))
        ),
        [worker_id, *week_ids],
    ).fetchall()

    for r in rows:
        days[r["week_id"]] = r["days"]

    # --- bonus per week ---
    bonus = {w["id"]: 0 for w in weeks}
    rows = conn.execute(
        """
        SELECT week_id, bonus
        FROM payroll_reference
        WHERE worker_id=?
          AND week_id IN ({})
    """.format(
            ",".join("?" * len(week_ids))
        ),
        [worker_id, *week_ids],
    ).fetchall()

    for r in rows:
        bonus[r["week_id"]] = r["bonus"] or 0

    # --- site distribution (top 4, ≥ 1 day) ---
    sites = conn.execute(
        """
        SELECT cs.code, COUNT(a.id) * 0.5 AS days
        FROM attendance a
        JOIN construction_sites cs ON cs.id = a.code
        WHERE a.worker_id=?
        GROUP BY cs.id
        HAVING COUNT(a.id) >= 2
        ORDER BY days DESC
        LIMIT 4
    """,
        (worker_id,),
    ).fetchall()

    return jsonify(
        {
            "labels": [f"KW {w['week_number']}" for w in weeks],
            "days": [days[w["id"]] for w in weeks],
            "bonus": [bonus[w["id"]] for w in weeks],
            "sites": [dict(s) for s in sites],
        }
    )
