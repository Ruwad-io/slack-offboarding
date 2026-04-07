"""
Slack OffBoarding — Flask application factory.
"""

from flask import Flask
from src.config import Config
from src.services.job_manager import JobManager


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    # Initialize job manager
    app.job_manager = JobManager(app.config["REDIS_URL"])

    # Register blueprints
    from src.routes.auth import auth_bp
    from src.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
