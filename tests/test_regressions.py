"""Regressions for defects found in adversarial review of the SQLite migration.

Each test names the failure it locks down.
"""

import logging
import sqlite3

import pytest

from app import create_app, db, repository
from app.config import DEFAULT_SECRET_KEY
from app.repository import DuplicateActiveRequestError


def _seed_duplicate_open_reports(path: str) -> None:
    """Build a database that violates the one-open-report-per-passport rule.

    This is what the old check-then-insert logic could leave behind, and what
    the migration script produces when it finds legacy duplicates.
    """
    connection = db.connect(path)
    try:
        connection.executescript(db.SCHEMA)
        for index in (1, 2):
            connection.execute(
                """
                INSERT INTO card_requests (
                    employee_name, employee_number, hajj_name, passport_number,
                    visa_number, request_reason, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"موظف {index}",
                    "0512345678",
                    f"حاج {index}",
                    "DUP00001",
                    f"V{index}",
                    "Lost Card",
                    "New",
                    "2025-01-01T00:00:00+00:00",
                    "2025-01-01T00:00:00+00:00",
                ),
            )
    finally:
        connection.close()


def test_app_still_boots_against_a_database_with_duplicate_open_reports(tmp_path, caplog):
    """The index cannot be built, but refusing to boot would strand the operator.

    /admin is the only place to resolve the duplicates, so the app must start
    without the index and say so loudly rather than crash-looping.
    """
    path = str(tmp_path / "dupes.db")
    _seed_duplicate_open_reports(path)

    with caplog.at_level(logging.ERROR):
        app = create_app({"TESTING": True, "DATABASE_PATH": path})

    assert "DUP00001" in caplog.text
    assert "NOT being blocked" in caplog.text

    # And the admin portal that fixes them is reachable.
    assert app.test_client().get("/admin").status_code == 200


def test_index_is_created_once_the_duplicates_are_resolved(tmp_path):
    path = str(tmp_path / "dupes.db")
    _seed_duplicate_open_reports(path)

    connection = db.connect(path)
    try:
        assert db.ensure_active_passport_index(connection) is False

        connection.execute(
            "UPDATE card_requests SET status = 'card delivered' WHERE id = 1"
        )
        assert db.ensure_active_passport_index(connection) is True

        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        ]
        assert db.ACTIVE_PASSPORT_INDEX in names
    finally:
        connection.close()


def test_init_schema_is_idempotent_across_repeated_boots(tmp_path):
    path = str(tmp_path / "repeat.db")
    for _ in range(3):
        connection = db.connect(path)
        try:
            assert db.init_schema(connection) is True
        finally:
            connection.close()


def test_reopening_a_report_conflicts_instead_of_500ing(client, app):
    """An admin correcting a mis-clicked status must get a real explanation."""
    form = {
        "employee_name": "عبدالعزيز",
        "employee_number": "0512345678",
        "hajj_name": "حاج اختبار",
        "passport_number": "REOPEN01",
        "visa_number": "V1",
        "request_reason": "Lost Card",
    }
    client.post("/submit_request", data=form)
    with app.app_context():
        first_id = repository.list_requests()[0]["id"]

    # Close it, then let the passport be reported again.
    client.post(f"/update_status/{first_id}", data={"status": "card delivered"})
    client.post("/submit_request", data={**form, "visa_number": "V2"})

    response = client.post(f"/update_status/{first_id}", data={"status": "New"})

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["success"] is False
    assert "REOPEN01" in payload["error"]


def test_reopening_still_works_when_there_is_no_conflict(client, app):
    form = {
        "employee_name": "عبدالعزيز",
        "employee_number": "0512345678",
        "hajj_name": "حاج اختبار",
        "passport_number": "REOPEN02",
        "visa_number": "V1",
        "request_reason": "Lost Card",
    }
    client.post("/submit_request", data=form)
    with app.app_context():
        request_id = repository.list_requests()[0]["id"]

    client.post(f"/update_status/{request_id}", data={"status": "found"})
    response = client.post(f"/update_status/{request_id}", data={"status": "New"})

    assert response.status_code == 200
    with app.app_context():
        assert repository.get_request(request_id)["status"] == "New"


@pytest.mark.parametrize("variant", ["a1234567", "A123 4567", " a123 4567 ", "A1234567"])
def test_passport_variants_cannot_open_a_second_report(make_request, variant):
    """Case and spacing must not create a second open report for one pilgrim."""
    make_request(passport_number="A1234567")
    with pytest.raises(DuplicateActiveRequestError):
        make_request(passport_number=variant)


def test_passport_is_stored_in_canonical_form(make_request):
    request_id = make_request(passport_number=" a123 4567 ")
    assert repository.get_request(request_id)["passport_number"] == "A1234567"


def test_has_active_request_matches_across_variants(make_request):
    make_request(passport_number="A1234567")
    assert repository.has_active_request("a123 4567") is True
    assert repository.has_active_request("B7654321") is False


def test_blank_session_secret_falls_back_instead_of_producing_an_empty_key(monkeypatch):
    """An empty SESSION_SECRET used to yield "", which 500s every flash()."""
    monkeypatch.setenv("SESSION_SECRET", "   ")

    import importlib

    from app import config as config_module

    importlib.reload(config_module)
    assert config_module.Config.SECRET_KEY == DEFAULT_SECRET_KEY

    monkeypatch.delenv("SESSION_SECRET", raising=False)
    importlib.reload(config_module)


def test_flashing_works_under_the_fallback_secret(tmp_path):
    """The whole point of the fallback: submissions must not 500."""
    app = create_app(
        {"TESTING": True, "DATABASE_PATH": str(tmp_path / "secret.db")}
    )
    app.config["SECRET_KEY"] = DEFAULT_SECRET_KEY

    response = app.test_client().post(
        "/submit_request",
        data={
            "employee_name": "عبدالعزيز",
            "employee_number": "0512345678",
            "hajj_name": "حاج اختبار",
            "passport_number": "FLASH001",
            "visa_number": "V1",
            "request_reason": "Lost Card",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "number",
    ["05١٢٣٤٥٦٧٨", "٠٥123456 78"],
)
def test_arabic_indic_digits_are_rejected_in_employee_numbers(client, app, number):
    """Python's \\d matches Arabic-Indic digits; the stored value would be undialable."""
    client.post(
        "/submit_request",
        data={
            "employee_name": "عبدالعزيز",
            "employee_number": number,
            "hajj_name": "حاج اختبار",
            "passport_number": "ARDIGIT1",
            "visa_number": "V1",
            "request_reason": "Lost Card",
        },
        follow_redirects=True,
    )
    with app.app_context():
        assert repository.list_requests() == []


def test_admin_status_cell_carries_a_sort_key_matching_the_status(client, app):
    """The sort key and the filter key must agree, or sorting uses stale values."""
    client.post(
        "/submit_request",
        data={
            "employee_name": "عبدالعزيز",
            "employee_number": "0512345678",
            "hajj_name": "حاج اختبار",
            "passport_number": "SORTKEY1",
            "visa_number": "V1",
            "request_reason": "Lost Card",
        },
    )
    body = client.get("/admin").get_data(as_text=True)

    # The rendered status cell exposes data-sort, and the JS keeps it in step.
    assert 'data-sort="New"' in body
    assert "cell.dataset.sort = data.status;" in body


def test_statistics_survive_a_database_without_the_uniqueness_index(tmp_path):
    path = str(tmp_path / "dupes.db")
    _seed_duplicate_open_reports(path)

    app = create_app({"TESTING": True, "DATABASE_PATH": path})
    client = app.test_client()

    assert client.get("/statistics").status_code == 200
    with app.app_context():
        assert repository.get_statistics()["total_new"] == 2


def test_invalid_reason_still_raises_rather_than_being_mistaken_for_a_duplicate(
    make_request,
):
    """create_request must only translate passport conflicts, not CHECK failures."""
    with pytest.raises(sqlite3.IntegrityError):
        make_request(request_reason="Eaten By Camel")
