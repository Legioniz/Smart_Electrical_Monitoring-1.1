from __future__ import annotations

from sqlalchemy import select

from sme.models import AuditEvent
from sme.security import verify_audit_chain, write_audit


def test_audit_chain_detects_tampered_metadata(app_and_db):
    app, ids = app_and_db
    with app.state.session_factory() as db:
        write_audit(db, ids['user_id'], 'test_action', 'test_entity', 'record-1', {'value': 'original'})
        write_audit(db, ids['user_id'], 'test_action_two', 'test_entity', 'record-2', {'count': 2})
        db.commit()
        assert verify_audit_chain(db) is True
        first = db.scalar(select(AuditEvent).order_by(AuditEvent.id.asc()).limit(1))
        first.metadata_json = {'value': 'tampered'}
        db.commit()
        assert verify_audit_chain(db) is False


def test_streamed_mutation_body_without_content_length_is_capped():
    import asyncio
    import json
    from sme.main import RequestBodyLimitMiddleware

    app_called = False
    sent = []

    async def downstream(scope, receive, send):
        nonlocal app_called
        app_called = True

    messages = iter([
        {"type": "http.request", "body": b"123456", "more_body": True},
        {"type": "http.request", "body": b"78901", "more_body": False},
    ])

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "method": "POST", "path": "/api/customer/appliances",
        "headers": [], "state": {"request_id": "test-request-id"},
    }
    asyncio.run(RequestBodyLimitMiddleware(downstream, max_bytes=10)(scope, receive, send))

    assert app_called is False
    start = next(message for message in sent if message["type"] == "http.response.start")
    body = next(message for message in sent if message["type"] == "http.response.body")
    assert start["status"] == 413
    payload = json.loads(body["body"])
    assert payload["error"]["code"] == "request_too_large"
    assert payload["error"]["request_id"] == "test-request-id"
