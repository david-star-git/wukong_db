from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.upload_service import handle_upload, overwrite_existing_week
from core.auth import login_required

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        result = handle_upload(request)

        if result["status"] == "error":
            return render_template("upload.html", error=result["message"])

        if result["status"] == "confirm":
            return render_template(
                "confirm_overwrite.html",
                kw=result["kw"],
                year=result["year"],
                file_name=result["file_path"],
            )

        flash(
            f"Week {result['kw']} of {result['year']} imported successfully"
            f" — {result['worker_count']} worker(s), {result['attendance_count']} attendance record(s).",
            "success",
        )
        return redirect(url_for("weeks.view_week", year=result["year"], kw=result["kw"]))

    return render_template("upload.html")


@upload_bp.route("/overwrite-week", methods=["POST"])
@login_required
def overwrite_week():
    year, kw, result = overwrite_existing_week(request)
    flash(
        f"Week {kw} of {year} overwritten"
        f" — {result['worker_count']} worker(s), {result['attendance_count']} attendance record(s).",
        "success",
    )
    return redirect(url_for("weeks.view_week", year=year, kw=kw))
