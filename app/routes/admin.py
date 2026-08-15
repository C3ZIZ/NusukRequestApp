"""Admin portal: triage reports and edit the pilgrim total.

These endpoints are unauthenticated, matching the previous behaviour. Anyone who
can reach the URL can change report state, so keep the deployment private.
"""

import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app import repository
from app.constants import MESSAGES_AR, STATUSES
from app.repository import DuplicateActiveRequestError

logger = logging.getLogger(__name__)

bp = Blueprint("admin", __name__)

# Query-string/form flag name -> database column.
FLAG_FIELDS = {
    "is_written": "is_written",
    "request_upload": "request_upload",
}


def _parse_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"true", "1", "yes", "on"}


@bp.route("/admin")
def index():
    try:
        return render_template(
            "admin.html",
            requests=repository.list_requests(),
            total_hajj=repository.get_total_hajj(),
        )
    except Exception:
        logger.exception("Failed to render admin portal")
        flash(MESSAGES_AR["system_error"], "error")
        return redirect(url_for("public.index"))


@bp.route("/update_status/<int:request_id>", methods=["POST"])
def update_status(request_id: int):
    new_status = request.form.get("status")
    if new_status not in STATUSES:
        return jsonify({"success": False, "error": MESSAGES_AR["status_invalid"]}), 400

    try:
        if not repository.update_status(request_id, new_status):
            return (
                jsonify({"success": False, "error": MESSAGES_AR["request_not_found"]}),
                404,
            )
    except DuplicateActiveRequestError as exc:
        # Reopening a report whose passport already has another open one.
        # Tell the admin exactly that instead of a generic failure.
        return (
            jsonify(
                {
                    "success": False,
                    "error": MESSAGES_AR["duplicate_request"].format(
                        passport=exc.passport_number
                    ),
                }
            ),
            409,
        )
    except Exception:
        logger.exception("Failed to update status for report %s", request_id)
        return jsonify({"success": False, "error": MESSAGES_AR["system_error"]}), 500

    return jsonify({"success": True, "status": new_status})


@bp.route("/update_flag/<int:request_id>", methods=["POST"])
def update_flag(request_id: int):
    """Toggle `is_written` or `request_upload` on a single report."""
    field = request.form.get("field")
    if field not in FLAG_FIELDS:
        return jsonify({"success": False, "error": MESSAGES_AR["status_invalid"]}), 400

    value = _parse_bool(request.form.get("value"))

    try:
        if not repository.update_flag(request_id, FLAG_FIELDS[field], value):
            return (
                jsonify({"success": False, "error": MESSAGES_AR["request_not_found"]}),
                404,
            )
    except Exception:
        logger.exception("Failed to update %s for report %s", field, request_id)
        return jsonify({"success": False, "error": MESSAGES_AR["system_error"]}), 500

    return jsonify({"success": True, "field": field, "value": value})


@bp.route("/update_total_hajj", methods=["POST"])
def update_total_hajj():
    raw = request.form.get("total_hajj")
    if raw is None or not raw.strip():
        return (
            jsonify({"success": False, "error": MESSAGES_AR["total_hajj_required"]}),
            400,
        )

    try:
        total_hajj = int(raw)
    except ValueError:
        return (
            jsonify({"success": False, "error": MESSAGES_AR["total_hajj_invalid"]}),
            400,
        )

    if total_hajj < 0:
        return (
            jsonify({"success": False, "error": MESSAGES_AR["total_hajj_invalid"]}),
            400,
        )

    try:
        repository.set_total_hajj(total_hajj)
    except Exception:
        logger.exception("Failed to update total_hajj")
        return jsonify({"success": False, "error": MESSAGES_AR["system_error"]}), 500

    return jsonify({"success": True, "message": MESSAGES_AR["total_hajj_updated"]})
