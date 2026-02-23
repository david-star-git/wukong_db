from flask import Blueprint, jsonify
from core.db import get_db

api_workers_bp = Blueprint("api_workers", __name__, url_prefix="/api/worker")


# -------------------------
# PROFILE
# -------------------------
@api_workers_bp.route("/<int:worker_id>/profile")
def worker_profile(worker_id):
    db = get_db()

    worker = db.execute(
        """
        SELECT id, display_name, cedula, active
        FROM workers
        WHERE id = ?
        """,
        (worker_id,),
    ).fetchone()

    if not worker:
        return jsonify({"error": "Worker not found"}), 404

    totals = db.execute(
        """
        SELECT
            COALESCE(SUM(salario), 0) AS total_salary,
            COALESCE(SUM(bonus), 0)   AS total_bonus
        FROM payroll_reference
        WHERE worker_id = ?
        """,
        (worker_id,),
    ).fetchone()

    total_halves = db.execute(
        """
        SELECT COUNT(*) AS halves
        FROM attendance
        WHERE worker_id = ?
        """,
        (worker_id,),
    ).fetchone()["halves"]

    return jsonify(
        {
            "id": worker["id"],
            "display_name": worker["display_name"],
            "cedula": worker["cedula"],
            "active": worker["active"],
            "total_days": total_halves / 2,
            "total_salary": totals["total_salary"],
            "total_bonus": totals["total_bonus"],
        }
    )


# -------------------------
# CHART DATA
# -------------------------
@api_workers_bp.route("/<int:worker_id>/charts")
def worker_charts(worker_id):
    db = get_db()

    # --- Days worked per week (last 12 weeks) ---
    weekly_days = db.execute(
        """
        SELECT
            w.year,
            w.week_number,
            COUNT(a.id) / 2.0 AS days_worked
        FROM attendance a
        JOIN weeks w ON w.id = a.week_id
        WHERE a.worker_id = ?
        GROUP BY w.id
        ORDER BY w.year DESC, w.week_number DESC
        LIMIT 12
        """,
        (worker_id,),
    ).fetchall()

    # --- Bonus per week (last 12 weeks) ---
    weekly_bonus = db.execute(
        """
        SELECT
            w.year,
            w.week_number,
            COALESCE(p.bonus, 0) AS bonus
        FROM payroll_reference p
        JOIN weeks w ON w.id = p.week_id
        WHERE p.worker_id = ?
        ORDER BY w.year DESC, w.week_number DESC
        LIMIT 12
        """,
        (worker_id,),
    ).fetchall()

    # --- Days per site (top 4, ≥ 1 day) ---
    site_days = db.execute(
        """
        SELECT
            cs.name AS site_name,
            COUNT(a.id) / 2.0 AS days_worked
        FROM attendance a
        JOIN construction_sites cs
            ON cs.code = a.code
        WHERE a.worker_id = ?
        GROUP BY cs.id
        HAVING days_worked >= 1
        ORDER BY days_worked DESC
        LIMIT 4
        """,
        (worker_id,),
    ).fetchall()

    return jsonify(
        {
            "weekly_days": [
                {
                    "label": f"{r['year']}-W{r['week_number']}",
                    "value": r["days_worked"],
                }
                for r in weekly_days[::-1]
            ],
            "weekly_bonus": [
                {
                    "label": f"{r['year']}-W{r['week_number']}",
                    "value": r["bonus"],
                }
                for r in weekly_bonus[::-1]
            ],
            "sites": [
                {
                    "label": r["site_name"],
                    "value": r["days_worked"],
                }
                for r in site_days
            ],
        }
    )
