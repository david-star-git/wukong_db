from flask import Flask, Blueprint
from dotenv import load_dotenv
import os

from core.db import init_db
from routes.upload import upload_bp
from routes.weeks import weeks_bp
from routes.settings import settings_bp
from routes.dashboard import dashboard_bp
from routes.api_workers import api_workers_bp

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not app.secret_key:
        raise RuntimeError("FLASK_SECRET_KEY is not set")

    app.config["UPLOAD_FOLDER"] = "uploads"

    @app.before_request
    def setup():
        init_db()

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_workers_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(weeks_bp)
    app.register_blueprint(settings_bp)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
