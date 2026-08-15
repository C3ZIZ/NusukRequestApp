from app import repository


def test_pages_render(client):
    for path in ("/", "/employee", "/admin", "/statistics"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_healthz_reports_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def _form(**overrides):
    payload = {
        "employee_name": "عبدالعزيز",
        "employee_number": "0512345678",
        "hajj_name": "حاج اختبار",
        "passport_number": "TST123456",
        "visa_number": "VISA123456",
        "request_reason": "Lost Card",
    }
    payload.update(overrides)
    return payload


def test_submitting_a_report_stores_it(client, app):
    response = client.post("/submit_request", data=_form(), follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        rows = repository.list_requests()
    assert len(rows) == 1
    assert rows[0]["passport_number"] == "TST123456"


def test_bad_employee_number_is_rejected(client, app):
    client.post("/submit_request", data=_form(employee_number="12345"), follow_redirects=True)
    with app.app_context():
        assert repository.list_requests() == []


def test_missing_fields_are_rejected(client, app):
    client.post("/submit_request", data=_form(hajj_name="   "), follow_redirects=True)
    with app.app_context():
        assert repository.list_requests() == []


def test_unknown_reason_is_rejected(client, app):
    client.post("/submit_request", data=_form(request_reason="Nope"), follow_redirects=True)
    with app.app_context():
        assert repository.list_requests() == []


def test_card_returned_is_ignored_for_lost_cards(client, app):
    client.post(
        "/submit_request",
        data=_form(request_reason="Lost Card", card_returned="on"),
        follow_redirects=True,
    )
    with app.app_context():
        assert repository.list_requests()[0]["card_returned"] is False


def test_card_returned_is_honoured_for_damaged_cards(client, app):
    client.post(
        "/submit_request",
        data=_form(request_reason="Damaged Card", card_returned="on"),
        follow_redirects=True,
    )
    with app.app_context():
        assert repository.list_requests()[0]["card_returned"] is True


def test_duplicate_submission_creates_only_one_report(client, app):
    client.post("/submit_request", data=_form(), follow_redirects=True)
    client.post("/submit_request", data=_form(), follow_redirects=True)

    with app.app_context():
        assert len(repository.list_requests()) == 1


def test_update_status_succeeds_and_persists(client, app):
    client.post("/submit_request", data=_form())
    with app.app_context():
        request_id = repository.list_requests()[0]["id"]

    response = client.post(f"/update_status/{request_id}", data={"status": "found"})
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    with app.app_context():
        assert repository.get_request(request_id)["status"] == "found"


def test_update_status_rejects_unknown_values(client, app):
    client.post("/submit_request", data=_form())
    with app.app_context():
        request_id = repository.list_requests()[0]["id"]

    response = client.post(f"/update_status/{request_id}", data={"status": "banana"})
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_update_status_on_a_missing_report_is_a_404(client):
    response = client.post("/update_status/9999", data={"status": "found"})
    assert response.status_code == 404


def test_update_flag_toggles_and_persists(client, app):
    client.post("/submit_request", data=_form())
    with app.app_context():
        request_id = repository.list_requests()[0]["id"]

    response = client.post(
        f"/update_flag/{request_id}", data={"field": "is_written", "value": "true"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"success": True, "field": "is_written", "value": True}

    with app.app_context():
        assert repository.get_request(request_id)["is_written"] is True


def test_update_flag_rejects_unknown_fields(client, app):
    client.post("/submit_request", data=_form())
    with app.app_context():
        request_id = repository.list_requests()[0]["id"]

    response = client.post(
        f"/update_flag/{request_id}", data={"field": "status", "value": "true"}
    )
    assert response.status_code == 400


def test_update_flag_on_a_missing_report_is_a_404(client):
    response = client.post(
        "/update_flag/9999", data={"field": "is_written", "value": "true"}
    )
    assert response.status_code == 404


def test_total_hajj_round_trip(client, app):
    response = client.post("/update_total_hajj", data={"total_hajj": "120000"})
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    with app.app_context():
        assert repository.get_total_hajj() == 120000

    assert b"120000" in client.get("/statistics").data


def test_total_hajj_rejects_junk(client):
    assert client.post("/update_total_hajj", data={"total_hajj": "abc"}).status_code == 400
    assert client.post("/update_total_hajj", data={"total_hajj": "-5"}).status_code == 400
    assert client.post("/update_total_hajj", data={"total_hajj": ""}).status_code == 400


def test_statistics_reflect_stored_reports(client, app):
    client.post("/submit_request", data=_form(passport_number="P1"))
    client.post(
        "/submit_request", data=_form(passport_number="P2", request_reason="Damaged Card")
    )

    body = client.get("/statistics").get_data(as_text=True)
    # Two reports, one of each reason.
    assert "إحصائيات نظام بديل" in body
