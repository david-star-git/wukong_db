from flask import Flask, render_template
from dotenv import load_dotenv
import os
from datetime import timedelta

from core.db import init_db
from routes.upload import upload_bp
from routes.weeks import weeks_bp
from routes.settings import settings_bp
from routes.dashboard import dashboard_bp
from routes.api_workers import api_workers_bp
from routes.auth import auth_bp

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not app.secret_key:
        raise RuntimeError("FLASK_SECRET_KEY is not set")

    app.permanent_session_lifetime = timedelta(days=30)
    app.config["UPLOAD_FOLDER"] = "uploads"

    @app.before_request
    def setup():
        init_db()

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_workers_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(weeks_bp)
    app.register_blueprint(settings_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", code=500, message="Something went wrong on our end."), 500

    @app.errorhandler(ValueError)
    def value_error(e):
        return render_template("error.html", code=400, message=str(e)), 400

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
