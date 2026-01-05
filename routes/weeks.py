from flask import Blueprint, render_template
from services.week_service import (
    get_week_overview_data,
    get_week_view_data,
)

weeks_bp = Blueprint("weeks", __name__)

@weeks_bp.route("/weeks/<int:year>")
def week_overview(year):
    return render_template(
        "week_overview.html",
        **get_week_overview_data(year),
    )


@weeks_bp.route("/week/<int:year>/<int:kw>")
def view_week(year, kw):
    return render_template(
        "week_view.html",
        **get_week_view_data(year, kw),
    )
