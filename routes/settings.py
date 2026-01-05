from flask import Blueprint, render_template, request, redirect, url_for, flash
from core.db import get_db
import sqlite3


settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_db()

    if request.method == "POST":
        errors = []
        with conn:  # transaction (prevents locking issues)
            # ---- Workers: cedulas ----
            for key, value in request.form.items():
                if key.startswith("cedula_"):
                    worker_id = int(key.split("_", 1)[1])
                    cedula = value.strip() or None

                    try:
                        conn.execute(
                            """
                            UPDATE workers
                            SET cedula = ?
                            WHERE id = ? AND active = 1
                            """,
                            (cedula, worker_id),
                        )
                    except sqlite3.IntegrityError:
                        errors.append(f"Duplicate cedula for worker {worker_id}")

            # ---- Construction sites: names ----
            for key, value in request.form.items():
                if key.startswith("site_name_"):
                    site_id = int(key.split("_", 2)[2])
                    name = value.strip()

                    try:
                        conn.execute(
                            """
                            UPDATE construction_sites
                            SET name = ?
                            WHERE id = ? AND active = 1
                            """,
                            (name, site_id),
                        )
                    except sqlite3.IntegrityError:
                        errors.append(f"Duplicate site name for site {site_id}")

            # Flash errors if any
        for err in errors:
            flash(err, "error")

        conn.close()

        return redirect(url_for("settings.settings"))

    # ---- GET ----
    workers = conn.execute(
        """
        SELECT id, normalized_name, cedula
        FROM workers
        WHERE active = 1
        ORDER BY normalized_name
        """
    ).fetchall()

    sites = conn.execute(
        """
        SELECT id, UPPER(code) as code, name
        FROM construction_sites
        WHERE active = 1
        ORDER BY code
        """
    ).fetchall()

    return render_template(
        "settings.html",
        workers=workers,
        sites=sites,
    )
