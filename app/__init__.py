from flask import Flask

from .config import Config
from .logging_config import configure as configure_logging


def create_app():
    configure_logging()
    app = Flask(__name__)
    app.config.from_object(Config)

    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app
