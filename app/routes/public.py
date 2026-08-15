"""Landing page, statistics dashboard and the container health check."""

import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, url_for

from app import repository
from app.constants import MESSAGES_AR

logger = logging.getLogger(__name__)

bp = Blueprint("public", __name__)


@bp.route("/")
def index():
    """Landing page linking to the employee and admin portals."""
    return render_template("index.html")


@bp.route("/statistics")
def statistics():
    """Aggregate counts plus the chart underneath them."""
    try:
        stats = repository.get_statistics()
        return render_template(
            "statistics.html",
            total_hajj=repository.get_total_hajj(),
            **stats,
        )
    except Exception:
        logger.exception("Failed to render statistics")
        flash(MESSAGES_AR["system_error"], "error")
        return redirect(url_for("public.index"))


@bp.route("/healthz")
def healthz():
    """Liveness probe for Coolify. Touches the database so a broken volume fails."""
    try:
        repository.get_setting("__healthcheck__")
        return jsonify({"status": "ok"})
    except Exception:
        logger.exception("Health check failed")
        return jsonify({"status": "error"}), 503
