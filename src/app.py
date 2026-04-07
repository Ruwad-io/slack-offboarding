"""
Slack OffBoarding — Flask application factory.
"""

from flask import Flask
from src.config import Config


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    # Register blueprints
    from src.routes.auth import auth_bp
    from src.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
