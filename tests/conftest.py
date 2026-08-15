import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app import repository  # noqa: E402


@pytest.fixture
def app(tmp_path):
    """A Flask app backed by a fresh SQLite file per test."""
    application = create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "test.db"),
            "SECRET_KEY": "test-secret",
        }
    )
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def ctx(app):
    """An app context, so repository functions can reach flask.g."""
    with app.app_context():
        yield


@pytest.fixture
def sample_request():
    return {
        "employee_name": "عبدالعزيز",
        "employee_number": "0512345678",
        "hajj_name": "حاج اختبار",
        "passport_number": "TST123456",
        "visa_number": "VISA123456",
        "request_reason": "Lost Card",
    }


@pytest.fixture
def make_request(ctx, sample_request):
    """Insert a report, overriding any field."""

    def _make(**overrides):
        payload = {**sample_request, **overrides}
        return repository.create_request(**payload)

    return _make
