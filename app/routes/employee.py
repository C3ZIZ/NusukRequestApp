"""Employee portal: submit a report and browse existing ones."""

import logging
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import repository
from app.constants import (
    EMPLOYEE_NUMBER_PATTERN,
    MESSAGES_AR,
    REASON_DAMAGED,
    REASONS,
)
from app.repository import DuplicateActiveRequestError

logger = logging.getLogger(__name__)

bp = Blueprint("employee", __name__)

REQUIRED_FIELDS = (
    "employee_name",
    "employee_number",
    "hajj_name",
    "passport_number",
    "visa_number",
    "request_reason",
)


@bp.route("/employee")
def index():
    try:
        return render_template("employee.html", requests=repository.list_requests())
    except Exception:
        logger.exception("Failed to render employee portal")
        flash(MESSAGES_AR["system_error"], "error")
        return redirect(url_for("public.index"))


@bp.route("/submit_request", methods=["POST"])
def submit_request():
    """Validate and store a new report."""
    fields = {
        name: (request.form.get(name) or "").strip() for name in REQUIRED_FIELDS
    }

    if not all(fields.values()):
        flash(MESSAGES_AR["all_fields_required"], "error")
        return redirect(url_for("employee.index"))

    if not re.match(EMPLOYEE_NUMBER_PATTERN, fields["employee_number"]):
        flash(MESSAGES_AR["employee_number_invalid"], "error")
        return redirect(url_for("employee.index"))

    if fields["request_reason"] not in REASONS:
        flash(MESSAGES_AR["reason_invalid"], "error")
        return redirect(url_for("employee.index"))

    # The checkbox only appears for damaged cards; ignore it otherwise so a
    # crafted form cannot mark a lost card as returned.
    card_returned = (
        fields["request_reason"] == REASON_DAMAGED and "card_returned" in request.form
    )

    try:
        repository.create_request(card_returned=card_returned, **fields)
    except DuplicateActiveRequestError:
        flash(
            MESSAGES_AR["duplicate_request"].format(passport=fields["passport_number"]),
            "error",
        )
        return redirect(url_for("employee.index"))
    except Exception:
        # Log the detail; show the user a message that leaks nothing.
        logger.exception("Failed to submit report")
        flash(MESSAGES_AR["request_error"], "error")
        return redirect(url_for("employee.index"))

    flash(MESSAGES_AR["request_submitted"], "success")
    return redirect(url_for("employee.index"))
