from flask import Blueprint, render_template, request, redirect, url_for
from services.upload_service import handle_upload, overwrite_existing_week

upload_bp = Blueprint("upload", __name__)

@upload_bp.route("/upload", methods=["GET", "POST"])
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

        return redirect(url_for("weeks.view_week", **result))

    return render_template("upload.html")


@upload_bp.route("/overwrite-week", methods=["POST"])
def overwrite_week():
    year, kw = overwrite_existing_week(request)
    return redirect(url_for("weeks.view_week", year=year, kw=kw))
