from flask import Flask, render_template, request, redirect, url_for
from db import get_db, init_db
import datetime
import csv
import os
from csv_import import import_csv

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"


@app.before_request
def setup():
    init_db()


@app.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            return render_template("upload.html", error="No file uploaded.")

        # --- Read CSV for preliminary validation ---
        raw = file.read()
        text = raw.decode("utf-8", errors="replace")
        rows = list(csv.reader(text.splitlines()))

        if not rows or len(rows[0]) < 2:
            return render_template(
                "upload.html", error="CSV file is empty or malformed."
            )

        # Extract KW and year from CSV
        try:
            kw = int(rows[0][1])
        except ValueError:
            return render_template("upload.html", error="Invalid KW value in CSV.")
        year = datetime.date.today().year

        # --- Save uploaded file ---
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file_path = f"{app.config['UPLOAD_FOLDER']}/week_{year}_{kw}.csv"

        # Reset file pointer and save
        file.stream.seek(0)
        file.save(file_path)

        # --- Import CSV into database ---
        with open(file_path, "rb") as f:
            kw, year, exists = import_csv(f, db_path="instance/app.db")

        # --- Handle existing week in web ---
        if exists:
            # Redirect to a confirmation page in the web UI
            return render_template(
                "confirm_overwrite.html", kw=kw, year=year, file_name=file_path
            )

        # Successfully imported, redirect to week view
        return redirect(url_for("view_week", year=year, kw=kw))

    # GET request -> show upload form
    return render_template("upload.html")


@app.route("/map-codes", methods=["POST"])
def map_codes():
    conn = get_db()
    for code, label in request.form.items():
        conn.execute(
            "INSERT OR IGNORE INTO day_codes (code, label) VALUES (?, ?)", (code, label)
        )
    conn.commit()
    return redirect(url_for("upload"))


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


@app.route("/week/<int:year>/<int:kw>")
def view_week(year, kw):
    conn = get_db()
    # Spanish display names only
    day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

    # Get week id
    week = conn.execute(
        "SELECT id FROM weeks WHERE year=? AND kalenderwoche=?", (year, kw)
    ).fetchone()
    if not week:
        return f"No hay datos para KW {kw}, {year}", 404
    week_id = week["id"]

    # Fetch workers in CSV order
    workers_db = conn.execute("SELECT id, display_name FROM workers").fetchall()

    # Fetch attendance and payroll
    attendance_db = conn.execute(
        "SELECT worker_id, day, half, code FROM attendance WHERE week_id=?", (week_id,)
    ).fetchall()
    payroll_db = conn.execute(
        "SELECT worker_id, salario, bonus, total, comment FROM payroll_reference WHERE week_id=?",
        (week_id,),
    ).fetchall()

    # Build data in CSV order
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

    for a in attendance_db:
        data[a["worker_id"]].setdefault("attendance", {})
        data[a["worker_id"]]["attendance"].setdefault(a["day"], {})
        data[a["worker_id"]]["attendance"][a["day"]][a["half"]] = a["code"]

    for p in payroll_db:
        data[p["worker_id"]]["salario"] = p["salario"]
        data[p["worker_id"]]["bonus"] = p["bonus"]
        data[p["worker_id"]]["total"] = p["total"]
        data[p["worker_id"]]["comment"] = p["comment"]

    return render_template(
        "week_view.html",
        year=year,
        kw=kw,
        workers=data.values(),
        day_names=day_names,  # just for display
    )


if __name__ == "__main__":
    app.run(debug=True)
