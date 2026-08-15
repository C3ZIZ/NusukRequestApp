import sqlite3

import pytest

from app import repository
from app.repository import DuplicateActiveRequestError


def test_create_and_read_back(make_request, sample_request):
    request_id = make_request()

    stored = repository.get_request(request_id)
    assert stored["hajj_name"] == sample_request["hajj_name"]
    assert stored["status"] == "New"
    # Flags come back as booleans, not the 0/1 stored on disk.
    assert stored["card_returned"] is False
    assert stored["request_upload"] is False
    assert stored["is_written"] is False
    assert stored["created_at"] is not None


def test_second_open_report_for_same_passport_is_rejected(make_request):
    make_request()
    with pytest.raises(DuplicateActiveRequestError):
        make_request()


def test_passport_can_be_reported_again_once_the_first_is_closed(make_request):
    first = make_request()
    repository.update_status(first, "card delivered")

    second = make_request()
    assert second != first


def test_invalid_reason_is_rejected_by_the_schema(make_request):
    with pytest.raises(sqlite3.IntegrityError):
        make_request(request_reason="Eaten By Camel")


def test_invalid_status_is_rejected_by_the_schema(make_request):
    request_id = make_request()
    with pytest.raises(sqlite3.IntegrityError):
        repository.update_status(request_id, "totally made up")


def test_update_status_reports_missing_rows(ctx):
    assert repository.update_status(9999, "found") is False


def test_update_flag_round_trips(make_request):
    request_id = make_request()

    assert repository.update_flag(request_id, "is_written", True) is True
    assert repository.get_request(request_id)["is_written"] is True

    assert repository.update_flag(request_id, "request_upload", True) is True
    assert repository.get_request(request_id)["request_upload"] is True

    assert repository.update_flag(request_id, "is_written", False) is True
    assert repository.get_request(request_id)["is_written"] is False


def test_update_flag_rejects_unknown_columns(make_request):
    request_id = make_request()
    with pytest.raises(ValueError):
        repository.update_flag(request_id, "status; DROP TABLE card_requests", True)


def test_update_flag_reports_missing_rows(ctx):
    assert repository.update_flag(9999, "is_written", True) is False


def test_statistics_on_an_empty_table_are_zero_not_null(ctx):
    stats = repository.get_statistics()
    assert stats["total_requests"] == 0
    assert stats["total_lost"] == 0
    assert stats["total_uploaded"] == 0


def test_statistics_count_each_dimension(make_request):
    lost = make_request(passport_number="P1")
    make_request(passport_number="P2", request_reason="Damaged Card")
    delivered = make_request(passport_number="P3")

    repository.update_flag(lost, "request_upload", True)
    repository.update_flag(lost, "is_written", True)
    repository.update_status(delivered, "card delivered")

    stats = repository.get_statistics()
    assert stats["total_requests"] == 3
    assert stats["total_lost"] == 2
    assert stats["total_damaged"] == 1
    assert stats["total_uploaded"] == 1
    assert stats["total_written"] == 1
    assert stats["total_delivered"] == 1
    assert stats["total_new"] == 2


def test_requests_are_listed_newest_first(make_request):
    older = make_request(passport_number="P1")
    newer = make_request(passport_number="P2")

    ids = [row["id"] for row in repository.list_requests()]
    assert ids.index(newer) < ids.index(older)


def test_total_hajj_defaults_to_zero_and_survives_a_round_trip(ctx):
    assert repository.get_total_hajj() == 0

    repository.set_total_hajj(120000)
    assert repository.get_total_hajj() == 120000

    # A non-numeric value stored by hand must not crash the dashboard.
    repository.set_setting("total_hajj", "not a number")
    assert repository.get_total_hajj() == 0


def test_setting_writes_are_upserts(ctx):
    repository.set_setting("colour", "green")
    repository.set_setting("colour", "blue")
    assert repository.get_setting("colour") == "blue"
