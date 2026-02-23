import math
from flask import Blueprint, jsonify
from core.db import get_db

api_workers_bp = Blueprint("api_workers", __name__, url_prefix="/api/worker")


def _compute_stats(db, worker_id):
    """Compute all derived stats for a worker."""

    # ── Totals (all time) ────────────────────────────────────────────────────
    totals = db.execute(
        """
        SELECT
            COALESCE(SUM(p.salario * att.halves), 0) AS total_salary,
            COALESCE(SUM(p.bonus), 0) AS total_bonus
        FROM payroll_reference p
        JOIN (
            SELECT week_id, COUNT(*) AS halves
            FROM attendance
            WHERE worker_id = ?
            GROUP BY week_id
        ) att ON att.week_id = p.week_id
        WHERE p.worker_id = ?
        """,
        (worker_id, worker_id),
    ).fetchone()

    total_halves = db.execute(
        "SELECT COUNT(*) AS h FROM attendance WHERE worker_id = ?",
        (worker_id,),
    ).fetchone()["h"]

    # ── Seniority – first week on record ────────────────────────────────────
    first_week = db.execute(
        """
        SELECT w.year, w.week_number
        FROM attendance a
        JOIN weeks w ON w.id = a.week_id
        WHERE a.worker_id = ?
        ORDER BY w.year ASC, w.week_number ASC
        LIMIT 1
        """,
        (worker_id,),
    ).fetchone()

    total_weeks_count = db.execute(
        """
        SELECT COUNT(DISTINCT w.id) AS cnt
        FROM attendance a
        JOIN weeks w ON w.id = a.week_id
        WHERE a.worker_id = ?
        """,
        (worker_id,),
    ).fetchone()["cnt"]

    # ── Last-month window (up to 4 most-recent weeks with data) ─────────────
    recent_weeks = db.execute(
        """
        SELECT w.id, w.year, w.week_number
        FROM attendance a
        JOIN weeks w ON w.id = a.week_id
        WHERE a.worker_id = ?
        GROUP BY w.id
        ORDER BY w.year DESC, w.week_number DESC
        LIMIT 4
        """,
        (worker_id,),
    ).fetchall()

    window_size = len(recent_weeks)

    # Days worked per week in window
    recent_days = []
    for rw in recent_weeks:
        halves = db.execute(
            "SELECT COUNT(*) AS h FROM attendance WHERE worker_id = ? AND week_id = ?",
            (worker_id, rw["id"]),
        ).fetchone()["h"]
        recent_days.append(halves / 2.0)

    avg_days = sum(recent_days) / window_size if window_size else 0
    # Max possible days in a week = 6 (Mon–Sat, 2 halves each)
    attendance_score = min(avg_days / 6.0, 1.0)

    # Bonus info in window
    week_ids = [rw["id"] for rw in recent_weeks]
    placeholders = ",".join("?" * len(week_ids)) if week_ids else "NULL"

    bonus_rows = db.execute(
        f"""
        SELECT COALESCE(bonus, 0) AS bonus, COALESCE(salario, 0) AS salario
        FROM payroll_reference
        WHERE worker_id = ? AND week_id IN ({placeholders})
        """,
        [worker_id] + week_ids,
    ).fetchall() if week_ids else []

    weeks_with_bonus = sum(1 for r in bonus_rows if r["bonus"] > 0)
    bonus_week_pct   = weeks_with_bonus / window_size if window_size else 0

    avg_bonus  = sum(r["bonus"]  for r in bonus_rows) / len(bonus_rows) if bonus_rows else 0
    avg_salary = sum(r["salario"] for r in bonus_rows) / len(bonus_rows) if bonus_rows else 0
    bonus_ratio = min(avg_bonus / avg_salary, 1.0) if avg_salary > 0 else 0

    # Bonus likelihood 0–100
    bonus_likelihood = round((0.6 * bonus_week_pct + 0.4 * bonus_ratio) * 100)

    # Star rating 1–5
    combined = 0.55 * attendance_score + 0.45 * (0.6 * bonus_week_pct + 0.4 * bonus_ratio)
    stars = max(1, min(5, math.ceil(combined * 5))) if (window_size or total_halves) else 1

    first_label = (
        f"{first_week['year']}-W{first_week['week_number']:02d}" if first_week else None
    )

    return {
        "total_days":       total_halves / 2.0,
        "total_salary":     totals["total_salary"],
        "total_bonus":      totals["total_bonus"],
        "total_weeks":      total_weeks_count,
        "first_week":       first_label,
        "stars":            stars,
        "bonus_likelihood": bonus_likelihood,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────────────────────
@api_workers_bp.route("/<int:worker_id>/profile")
def worker_profile(worker_id):
    db = get_db()

    worker = db.execute(
        "SELECT id, display_name, cedula, active FROM workers WHERE id = ?",
        (worker_id,),
    ).fetchone()

    if not worker:
        return jsonify({"error": "Worker not found"}), 404

    stats = _compute_stats(db, worker_id)

    return jsonify({
        "worker": {
            "id":           worker["id"],
            "display_name": worker["display_name"],
            "cedula":       worker["cedula"],
            "active":       worker["active"],
        },
        "stats": stats,
    })


# ─────────────────────────────────────────────────────────────────────────────
# CHART DATA
# ─────────────────────────────────────────────────────────────────────────────
@api_workers_bp.route("/<int:worker_id>/charts")
def worker_charts(worker_id):
    db = get_db()

    # Days worked per week (last 12 weeks with attendance)
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
    ).fetchall()[::-1]

    # Bonus per week (last 12 payroll entries)
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
    ).fetchall()[::-1]

    # Days per construction site – all sites with ≥ 1 day, sorted by days desc
    site_days = db.execute(
        """
        SELECT
            a.code                          AS site_code,
            COALESCE(cs.name, cs.code)      AS site_label,
            COUNT(a.id) / 2.0               AS days_worked
        FROM attendance a
        LEFT JOIN construction_sites cs ON cs.id = a.code
        WHERE a.worker_id = ?
        GROUP BY a.code
        HAVING days_worked >= 0.5
        ORDER BY days_worked DESC
        LIMIT 5
        """,
        (worker_id,),
    ).fetchall()

    return jsonify({
        "labels":      [f"{r['year']}-W{r['week_number']:02d}" for r in weekly_days],
        "days":        [r["days_worked"] for r in weekly_days],
        "bonus_labels":[f"{r['year']}-W{r['week_number']:02d}" for r in weekly_bonus],
        "bonus":       [r["bonus"] for r in weekly_bonus],
        "sites":       [{"code": r["site_code"], "label": r["site_label"], "value": r["days_worked"]} for r in site_days],
    })
