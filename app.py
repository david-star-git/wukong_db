from flask import Flask, render_template, request, redirect, url_for, flash
from db import get_db, init_db
import datetime
import csv
import os
from csv_import import import_csv
from helpers import *
import sqlite3
from io import BytesIO
from dotenv import load_dotenv

# import logging
# logging.basicConfig(level=logging.DEBUG)
 
app = Flask(__name__)
load_dotenv()
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config["UPLOAD_FOLDER"] = "uploads"


@app.before_request
def setup():
    init_db()


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            return render_template("upload.html", error="No file uploaded.")

        try:
            raw = file.read()
            text = raw.decode("utf-8", errors="replace")
            rows = list(csv.reader(text.splitlines(), delimiter=";"))

            if not rows or len(rows[0]) < 2:
                return render_template(
                    "upload.html", error="CSV file is empty or malformed."
                )

            kw = int(rows[0][1])
            year = datetime.date.today().year

        except Exception as e:
            return render_template("upload.html", error=f"CSV read error: {e}")

        # Save a per-year backup
        backup_dir = os.path.join(app.config["UPLOAD_FOLDER"], str(year))
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"{kw}.csv")
        with open(backup_path, "wb") as f:
            f.write(raw)

        # Optional: save for archive/debug
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], f"week_{year}_{kw}.csv")
        with open(file_path, "wb") as f:
            f.write(raw)

        # Import directly from memory
        try:
            kw, year, exists = import_csv(BytesIO(raw), db_path="instance/app.db")
        except Exception as e:
            return render_template("upload.html", error=f"Import failed: {e}")

        if exists:
            return render_template(
                "confirm_overwrite.html",
                kw=kw,
                year=year,
                file_name=file_path,
            )

        return redirect(url_for("view_week", year=year, kw=kw))

    return render_template("upload.html")


@app.route("/overwrite-week", methods=["POST"])
def overwrite_week():
    kw = int(request.form["kw"])
    year = int(request.form["year"])
    overwrite = request.form["overwrite"] == "yes"

    if not overwrite:
        # User canceled
        return redirect(url_for("upload"))

    # Re-get the file from temporary storage
    file_path = f"uploads/week_{year}_{kw}.csv"
    with open(file_path, "rb") as f:
        kw, year, exists = import_csv(f, db_path="instance/app.db")

    return redirect(url_for("view_week", year=year, kw=kw))


@app.route("/weeks/<int:year>")
def week_overview(year):
    db = get_db()

    all_years = list(range(2026, 2061))
    existing_years = get_existing_years(db)
    existing_kws = get_existing_kws_for_year(db, year)

    return render_template(
        "week_overview.html",
        all_years=all_years,
        existing_years=existing_years,
        selected_year=year,
        existing_kws=existing_kws,
    )


@app.route("/week/<int:year>/<int:kw>")
def view_week(year, kw):
    conn = get_db()
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

    # Get week id
    week = conn.execute(
        "SELECT id FROM weeks WHERE year=? AND week_number=?", (year, kw)
    ).fetchone()
    if not week:
        return f"No hay datos para KW {kw}, {year}", 404
    week_id = week["id"]

    # Fetch workers in CSV order
    workers_db = conn.execute(
        "SELECT id, display_name FROM workers ORDER BY id"
    ).fetchall()

    # Fetch attendance with construction site info
    attendance_db = conn.execute(
        """
        SELECT a.worker_id, a.day, a.half, a.code AS site_id,
               cs.code AS site_code, cs.name AS site_name
        FROM attendance a
        LEFT JOIN construction_sites cs ON a.code = cs.id
        WHERE a.week_id=?
        """,
        (week_id,),
    ).fetchall()

    # Fetch payroll
    payroll_db = conn.execute(
        """
        SELECT worker_id, salario, bonus, total, comment
        FROM payroll_reference
        WHERE week_id=?
        """,
        (week_id,),
    ).fetchall()

    # Build data
    data = {}
    for w in workers_db:
        data[w["id"]] = {
            "name": w["display_name"],
            "attendance": {},
            "salario": None,
            "bonus": None,
            "total": None,
            "comment": None,
        }

    # Build attendance
    for a in attendance_db:
        wid = a["worker_id"]
        day = a["day"]
        half = a["half"]

        worker_att = data[wid]["attendance"]
        worker_att.setdefault(day, {})

        # Display site name if exists, otherwise fallback to site_code (upper), else code number
        if a["site_name"]:
            display = a["site_name"]
        elif a["site_code"]:
            display = a["site_code"].upper()
        else:
            display = str(a["site_id"]) if a["site_id"] else ""

        worker_att[day][half] = display

    # Build payroll
    for p in payroll_db:
        wid = p["worker_id"]
        if wid not in data:  # safety check
            continue

        # Ensure numbers are displayed as strings
        data[wid]["salario"] = str(p["salario"]) if p["salario"] is not None else ""
        data[wid]["bonus"] = str(p["bonus"]) if p["bonus"] is not None else ""
        data[wid]["total"] = str(p["total"]) if p["total"] is not None else ""
        data[wid]["comment"] = p["comment"] or ""

    return render_template(
        "week_view.html",
        year=year,
        kw=kw,
        workers=data.values(),
        day_names=day_names,
    )


@app.route("/settings", methods=["GET", "POST"])
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

        return redirect(url_for("settings"))

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


if __name__ == "__main__":
    app.run(debug=True)
