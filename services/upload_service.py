import csv
import datetime
import os
from io import BytesIO
from core.csv_import import import_csv

UPLOAD_DIR = "uploads"


def handle_upload(request):
    file = request.files.get("file")
    if not file or not file.filename:
        return {"status": "error", "message": "No file uploaded."}

    try:
        raw = file.read()
        text = raw.decode("utf-8", errors="replace")
        rows = list(csv.reader(text.splitlines(), delimiter=";"))

        if not rows or len(rows[0]) < 2:
            raise ValueError("CSV file is empty or malformed")

        kw = int(rows[0][1])
        year = datetime.date.today().year
    except Exception as e:
        return {"status": "error", "message": f"CSV read error: {e}"}

    os.makedirs(f"{UPLOAD_DIR}/{year}", exist_ok=True)

    backup_path = f"{UPLOAD_DIR}/{year}/{kw}.csv"
    archive_path = f"{UPLOAD_DIR}/week_{year}_{kw}.csv"

    for path in (backup_path, archive_path):
        with open(path, "wb") as f:
            f.write(raw)

    try:
        kw, year, exists = import_csv(BytesIO(raw), db_path="instance/app.db")
    except Exception as e:
        return {"status": "error", "message": f"Import failed: {e}"}

    if exists:
        return {
            "status": "confirm",
            "kw": kw,
            "year": year,
            "file_path": archive_path,
        }

    return {"status": "ok", "year": year, "kw": kw}


def overwrite_existing_week(request):
    kw = int(request.form["kw"])
    year = int(request.form["year"])

    path = f"{UPLOAD_DIR}/week_{year}_{kw}.csv"
    with open(path, "rb") as f:
        import_csv(f, db_path="instance/app.db")

    return year, kw
