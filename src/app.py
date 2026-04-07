"""
Slack OffBoarding — Flask application factory.
"""

import sentry_sdk
from flask import Flask
from src.config import Config
from src.services.job_manager import JobManager


def create_app() -> Flask:
    config = Config()

    # Initialize Sentry if DSN is set
    if config.SENTRY_DSN:
        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config)

    # Initialize job manager
    app.job_manager = JobManager(app.config["REDIS_URL"])

    # Register blueprints
    from src.routes.auth import auth_bp
    from src.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
