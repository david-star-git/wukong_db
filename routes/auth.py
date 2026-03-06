import os
from flask import Blueprint, render_template, request, session, redirect, url_for, flash

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        valid_user = os.environ.get("WUKOND_USER", "admin")
        valid_pass = os.environ.get("WUKOND_PASS", "")

        if not valid_pass:
            error = "Server is not configured (WUKOND_PASS not set)."
        elif username == valid_user and password == valid_pass:
            session.permanent = True
            session["logged_in"] = True
            next_url = request.args.get("next") or url_for("dashboard.dashboard")
            return redirect(next_url)
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
