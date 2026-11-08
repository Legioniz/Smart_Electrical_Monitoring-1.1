from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sme.main import create_app
from sme.models import Account, Customer, Meter, Reading, Base, LockState
from sme.security import hash_password, new_id, utcnow


@pytest.fixture()
def app_and_db():
    app = create_app(testing=True, database_url="sqlite+pysqlite:///:memory:")
    factory = app.state.session_factory
    with factory() as db:
        customer_id = new_id()
        customer = Customer(id=customer_id, display_label="Test household", language="en", push_opt_in=False, sms_opt_in=False, created_at=utcnow())
        user = Account(id=new_id(), customer_id=customer_id, username="test.customer", password_hash=hash_password("Temporary test passphrase 2026!"), role="customer", status="active", must_change_password=True, created_at=utcnow())
        reviewer = Account(id=new_id(), customer_id=None, username="test.reviewer", password_hash=hash_password("Temporary reviewer passphrase 2026!"), role="reviewer", status="active", must_change_password=False, created_at=utcnow())
        admin1 = Account(id=new_id(), customer_id=None, username="test.admin.one", password_hash=hash_password("Temporary administrator passphrase 2026!"), role="administrator", status="active", must_change_password=False, created_at=utcnow())
        admin2 = Account(id=new_id(), customer_id=None, username="test.admin.two", password_hash=hash_password("Second administrator passphrase 2026!"), role="administrator", status="active", must_change_password=False, created_at=utcnow())
        meter = Meter(id=new_id(), customer_id=customer_id, pseudonymous_label="TEST-METER", created_at=utcnow())
        db.add_all([customer, user, reviewer, admin1, admin2, meter])
        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(days=8)
        rows = []
        for i in range(8 * 96):
            rows.append(Reading(meter_id=meter.id, interval_start_utc=(start + timedelta(minutes=15*i)).replace(tzinfo=None), energy_kwh=Decimal("0.0350"), quality="ok", label_type=None))
        db.add_all(rows)
        db.add(LockState(id=1, mode="normal", reason_code="normal", changed_at=utcnow()))
        db.commit()
        ids = {"customer_id": customer_id, "user_id": user.id, "reviewer_id": reviewer.id, "admin1_id": admin1.id, "admin2_id": admin2.id, "meter_id": meter.id}
    yield app, ids
    app.state.engine.dispose()


@pytest.fixture()
def client(app_and_db):
    app, _ids = app_and_db
    with TestClient(app) as test_client:
        yield test_client


def login_customer(client: TestClient, password: str = "Temporary test passphrase 2026!") -> tuple[str, dict]:
    pre = client.get("/api/auth/preflight")
    assert pre.status_code == 200
    csrf = pre.json()["csrf_token"]
    login = client.post("/api/auth/customer/login", headers={"Origin": "http://testserver", "X-CSRF-Token": csrf}, json={"username": "test.customer", "password": password})
    assert login.status_code == 200, login.text
    result = login.json()
    return result["csrf_token"], result


def login_admin(client: TestClient, username: str = "test.admin.one", password: str = "Temporary administrator passphrase 2026!") -> tuple[str, dict, str]:
    pre = client.get("/api/auth/preflight")
    csrf = pre.json()["csrf_token"]
    started = client.post("/api/auth/admin/start", headers={"Origin": "http://testserver", "X-CSRF-Token": csrf}, json={"username": username, "password": password})
    assert started.status_code == 200, started.text
    challenge = started.json()["challenge_id"]
    return csrf, started.json(), challenge


def change_customer_password(client: TestClient, csrf: str) -> str:
    response = client.post("/api/auth/password/change", headers={"Origin": "http://testserver", "X-CSRF-Token": csrf}, json={"current_password": "Temporary test passphrase 2026!", "new_password": "My new local test passphrase 2026!"})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]
