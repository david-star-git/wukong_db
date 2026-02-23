from flask import Blueprint, render_template
from core.db import get_db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def dashboard():
    db = get_db()
    workers = db.execute(
        """
        SELECT id, display_name, active
        FROM workers
        ORDER BY id
        """
    ).fetchall()

    selected_worker_id = workers[0]["id"] if workers else None

    return render_template(
        "dashboard.html",
        workers=workers,
        selected_worker_id=selected_worker_id,
    )
