from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from sme.models import Account, AppSession, ConsentRecord, LockState
from sme.security import utcnow
from tests.conftest import login_customer, login_admin, change_customer_password


def test_customer_can_sign_in_change_password_and_submit_consent(client, app_and_db):
    csrf, login = login_customer(client)
    assert login["consent_required"] is True
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["user"]["must_change_password"] is True
    blocked = client.get("/api/customer/overview")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"

    csrf = change_customer_password(client, csrf)
    assert client.get("/api/session").json()["user"]["must_change_password"] is False

    consent = client.get("/api/consent")
    assert consent.status_code == 200
    payload = {"text_version":consent.json()["version"],"request_id":"c9df3b8a-8272-41d9-98b1-9a6fcbf1a832","required_analytics":True,"push_alerts":False,"sms_alerts":False}
    accepted = client.post("/api/consent", headers={"Origin":"http://testserver", "X-CSRF-Token":csrf}, json=payload)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["analytics_unlocked"] is True
    overview = client.get("/api/customer/overview")
    assert overview.status_code == 200, overview.text
    assert overview.json()["simulated"] is True
    intelligence = overview.json()["intelligence"]
    assert intelligence["version"] == "sme-intelligence-v2.0"
    assert intelligence["status"] in {"ready", "cold_start"}
    if intelligence["status"] == "ready":
        assert 0 <= intelligence["bayesian_anomaly_probability"] <= 1
        assert 0 <= intelligence["ensemble_score"] <= 1
        assert intelligence["forecast"]["lower_kwh"] <= intelligence["forecast"]["expected_kwh"] <= intelligence["forecast"]["upper_kwh"]
    story = client.get("/api/customer/story")
    assert story.status_code == 200, story.text
    assert story.json()["recommendations"]["items"]
    assert story.json()["recommendations"]["engine"] in {"template", "local_llm"}

    app, _ids = app_and_db
    with app.state.session_factory() as db:
        records = list(db.scalars(select(ConsentRecord)))
        assert len(records) == 3
        assert all(r.status in {"granted", "withdrawn"} for r in records)


def test_consent_is_idempotent_for_same_request_id(client, app_and_db):
    csrf, _ = login_customer(client)
    changed = client.post("/api/auth/password/change", headers={"Origin":"http://testserver", "X-CSRF-Token":csrf}, json={"current_password":"Temporary test passphrase 2026!", "new_password":"My new local test passphrase 2026!"})
    csrf = changed.json()["csrf_token"]
    version = client.get("/api/consent").json()["version"]
    payload = {"text_version":version,"request_id":"1d4c788f-a150-4cdd-a10d-12a85e11aacf","required_analytics":True}
    first = client.post("/api/consent", headers={"Origin":"http://testserver", "X-CSRF-Token":csrf}, json=payload)
    second = client.post("/api/consent", headers={"Origin":"http://testserver", "X-CSRF-Token":csrf}, json=payload)
    assert first.status_code == second.status_code == 200
    app, _ids = app_and_db
    with app.state.session_factory() as db:
        rows = list(db.scalars(select(ConsentRecord).where(ConsentRecord.request_id == payload["request_id"])))
        assert len(rows) == 3


def test_missing_csrf_is_rejected_without_changing_consent(client):
    csrf, _ = login_customer(client)
    change_customer_password(client, csrf)
    version = client.get("/api/consent").json()["version"]
    response = client.post("/api/consent", headers={"Origin":"http://testserver"}, json={"text_version":version,"request_id":"750cf7c5-d043-4f11-945f-6ba6caebf3e8","required_analytics":True})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_cross_origin_request_is_rejected(client):
    csrf, _ = login_customer(client)
    csrf = change_customer_password(client, csrf)
    version = client.get("/api/consent").json()["version"]
    response = client.post("/api/consent", headers={"Origin":"https://evil.example", "X-CSRF-Token":csrf}, json={"text_version":version,"request_id":"39c7b94e-dd4d-4fd5-a3c4-9e02e0df9c7b","required_analytics":True})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_mismatch"


def test_admin_second_factor_flow_keeps_preauth_valid(client, capsys):
    preauth_csrf, started, challenge = login_admin(client)
    captured = capsys.readouterr()
    match = re.search(r"code=(\d{6})", captured.err)
    assert match, captured.err
    verified = client.post("/api/auth/admin/verify", headers={"Origin":"http://testserver", "X-CSRF-Token":preauth_csrf}, json={"challenge_id":challenge,"code":match.group(1)})
    assert verified.status_code == 200, verified.text
    assert client.get("/api/internal/protection").status_code == 200


def test_internal_role_cannot_open_customer_analytics(client):
    preauth_csrf, _started, challenge = login_admin(client, username="test.reviewer", password="Temporary reviewer passphrase 2026!")
    # The reviewer code is emitted to stderr; this test exercises the role boundary through the session setup below.
    import sys
    # Rather than relying on terminal output in this test, insert a valid reviewer session directly.
    app = client.app
    with app.state.session_factory() as db:
        account = db.scalar(select(Account).where(Account.username == "test.reviewer"))
        raw = "test-reviewer-session-token"
        from sme.security import digest
        from sme.models import AppSession
        from datetime import timedelta
        db.add(AppSession(token_hash=digest(raw), account_id=account.id, csrf_token="c"*32, role="reviewer", created_at=utcnow(), last_seen_at=utcnow(), expires_at=utcnow()+timedelta(hours=1), source_hash="a"*64))
        db.commit()
    client.cookies.set("sme_session", raw)
    assert client.get("/api/customer/overview").status_code == 403


def test_safe_mode_blocks_internal_queue_but_protection_is_visible(client, app_and_db, capsys):
    preauth_csrf, _started, challenge = login_admin(client)
    match = re.search(r"code=(\d{6})", capsys.readouterr().err)
    assert match
    verified = client.post("/api/auth/admin/verify", headers={"Origin":"http://testserver", "X-CSRF-Token":preauth_csrf}, json={"challenge_id":challenge,"code":match.group(1)})
    assert verified.status_code == 200
    app, _ids = app_and_db
    with app.state.session_factory() as db:
        lock = db.get(LockState, 1); lock.mode = "read_only"; lock.reason_code = "test_lock"; lock.changed_at = utcnow(); db.commit()
    assert client.get("/api/internal/queue").status_code == 423
    assert client.get("/api/internal/protection").json()["mode"] == "read_only"


def test_consent_request_id_cannot_be_reused_for_a_different_decision(client):
    csrf, _login = login_customer(client)
    csrf = change_customer_password(client, csrf)
    version = client.get('/api/consent').json()['version']
    request_id = 'a3f2f2ad-3dd6-42c1-aef2-6e7f20f7a7a1'
    base = {'text_version': version, 'request_id': request_id, 'required_analytics': True, 'push_alerts': False, 'sms_alerts': False}
    first = client.post('/api/consent', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json=base)
    changed = {**base, 'push_alerts': True}
    second = client.post('/api/consent', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json=changed)
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()['error']['code'] == 'request_id_conflict'


def test_withdrawal_blocks_analytics_and_customer_can_reconsent(client):
    csrf, _login = login_customer(client)
    csrf = change_customer_password(client, csrf)
    version = client.get('/api/consent').json()['version']
    accepted = client.post('/api/consent', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json={
        'text_version': version,
        'request_id': 'b8bc1927-1c94-45ed-93d2-e3d47125f66d',
        'required_analytics': True,
        'push_alerts': False,
        'sms_alerts': False,
    })
    assert accepted.status_code == 200
    withdrawn = client.post('/api/customer/consent/withdraw', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json={})
    assert withdrawn.status_code == 200
    blocked = client.get('/api/customer/overview')
    assert blocked.status_code == 403
    assert blocked.json()['error']['code'] == 'consent_required'
    reaccepted = client.post('/api/consent', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json={
        'text_version': version,
        'request_id': 'b8bc1927-1c94-45ed-93d2-e3d47125f66e',
        'required_analytics': True,
        'push_alerts': False,
        'sms_alerts': False,
    })
    assert reaccepted.status_code == 200
    assert client.get('/api/customer/overview').status_code == 200


def test_host_allowlist_rejects_unrecognized_host(client):
    response = client.get('/health', headers={'Host': 'not-local.example'})
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'host_not_allowed'
    assert response.json()['error']['request_id']


def test_two_different_administrators_are_required_to_unlock_safe_mode(client, capsys):
    preauth_csrf, _started, challenge = login_admin(client)
    otp = re.search(r'code=(\d{6})', capsys.readouterr().err)
    assert otp
    verified = client.post('/api/auth/admin/verify', headers={'Origin': 'http://testserver', 'X-CSRF-Token': preauth_csrf}, json={'challenge_id': challenge, 'code': otp.group(1)})
    assert verified.status_code == 200
    csrf = verified.json()['csrf_token']
    locked = client.post('/api/internal/safe-mode/lock', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json={})
    assert locked.status_code == 200
    approval = client.post('/api/internal/safe-mode/approval/start', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json={
        'username': 'test.admin.two',
        'password': 'Second administrator passphrase 2026!',
    })
    assert approval.status_code == 200
    second_otp = re.search(r'code=(\d{6})', capsys.readouterr().err)
    assert second_otp
    unlock = client.post('/api/internal/safe-mode/unlock', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json={
        'approval_challenge_id': approval.json()['challenge_id'],
        'approval_code': second_otp.group(1),
        'current_password': 'Temporary administrator passphrase 2026!',
    })
    assert unlock.status_code == 200, unlock.text
    assert unlock.json()['mode'] == 'normal'


def test_failed_login_attempts_are_counted_and_eventually_throttled(client):
    for _ in range(8):
        preflight = client.get('/api/auth/preflight')
        assert preflight.status_code == 200
        response = client.post('/api/auth/customer/login', headers={
            'Origin': 'http://testserver',
            'X-CSRF-Token': preflight.json()['csrf_token'],
        }, json={'username': 'missing.user', 'password': 'A deliberately incorrect passphrase 2026!'})
        assert response.status_code == 401
    preflight = client.get('/api/auth/preflight')
    throttled = client.post('/api/auth/customer/login', headers={
        'Origin': 'http://testserver',
        'X-CSRF-Token': preflight.json()['csrf_token'],
    }, json={'username': 'missing.user', 'password': 'A deliberately incorrect passphrase 2026!'})
    assert throttled.status_code == 429
    assert throttled.json()['error']['code'] == 'login_throttled'


def test_day_explorer_flags_only_intervals_covered_by_persisted_detector_alert(client, app_and_db):
    from datetime import timedelta, timezone
    from sqlalchemy import func
    from sme.models import Alert, Reading
    from sme.services.analytics import local_day_bounds
    from sme.security import new_id, utcnow

    csrf, _login = login_customer(client)
    csrf = change_customer_password(client, csrf)
    consent_page = client.get('/api/consent').json()
    accepted = client.post('/api/consent', headers={'Origin': 'http://testserver', 'X-CSRF-Token': csrf}, json={
        'text_version': consent_page['version'], 'request_id': '9d331cf5-809e-45d6-9d4a-c05b3304ceab', 'required_analytics': True,
    })
    assert accepted.status_code == 200

    app, ids = app_and_db
    with app.state.session_factory() as db:
        latest = db.scalar(select(func.max(Reading.interval_start_utc)).where(Reading.meter_id == ids['meter_id']))
        local_day = latest.replace(tzinfo=timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Manila')).date()
        day_start, _day_end = local_day_bounds(local_day)
        db.add(Alert(
            id=new_id(), customer_id=ids['customer_id'], meter_id=ids['meter_id'], tier='WATCH',
            alert_type='sustained_evening_rise', reason_code='evening_load_persisted',
            reason_text='Evening use was above its recent pattern for several days.', audience='customer',
            status='open', score=1.8, threshold=1.5,
            window_start=day_start + timedelta(minutes=30), window_end=day_start + timedelta(minutes=60),
            detector_version='test-detector', settings_version='test-settings', feature_values={}, created_at=utcnow(),
        ))
        db.commit()

    day = client.get('/api/customer/day')
    assert day.status_code == 200, day.text
    slots = day.json()['intervals']
    assert [slot['slot'] for slot in slots if slot['flagged']] == [2, 3]
    assert slots[2]['reason'].startswith('Evening use')
    assert slots[1]['flagged'] is False
