"""Application factory for Badeel (بديل)."""

import logging
import os

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

logger = logging.getLogger(__name__)


def create_app(config_overrides: dict | None = None) -> Flask:
    """Build and configure the Flask application.

    `config_overrides` lets the tests point at a throwaway database without
    touching the environment.
    """
    from app.config import DEFAULT_SECRET_KEY, Config
    from app.constants import (
        REASON_LABELS_AR,
        STATUS_BADGE_CLASSES,
        STATUS_LABELS_AR,
        STATUSES,
    )
    from app import db
    from app.routes import admin, employee, public

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    # Coolify terminates TLS at its reverse proxy, so trust one hop of
    # X-Forwarded-* to keep url_for() generating https links.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Checked against the effective config, not the class attribute, so
    # overrides are covered too.
    if app.config["SECRET_KEY"] == DEFAULT_SECRET_KEY:
        logger.warning(
            "SESSION_SECRET is unset or blank; using the insecure default. "
            "Set it before deploying."
        )

    db.init_app(app)

    app.register_blueprint(public.bp)
    app.register_blueprint(employee.bp)
    app.register_blueprint(admin.bp)

    # Arabic labels and badge classes, so templates stop hardcoding the
    # status vocabulary in five different if/elif chains.
    app.jinja_env.globals.update(
        STATUSES=STATUSES,
        STATUS_LABELS_AR=STATUS_LABELS_AR,
        STATUS_BADGE_CLASSES=STATUS_BADGE_CLASSES,
        REASON_LABELS_AR=REASON_LABELS_AR,
    )

    return app
