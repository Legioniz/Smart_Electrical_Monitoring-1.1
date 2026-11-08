from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Account, AppSession, AuditEvent, AuthChallenge, LockState, SecurityEvent

UTC = timezone.utc
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1, hash_len=32, salt_len=16)
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("not-a-valid-user-passphrase-for-timing-only")


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid4())


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    if len(password) < 15:
        raise ValueError("Use a passphrase of at least 15 characters.")
    if len(password.encode("utf-8")) > 1024:
        raise ValueError("Passphrase is too long.")
    return PASSWORD_HASHER.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        # Keep malformed/missing-user verification work close to a valid Argon2 check.
        if stored_hash != DUMMY_PASSWORD_HASH:
            try:
                PASSWORD_HASHER.verify(DUMMY_PASSWORD_HASH, password)
            except Exception:
                pass
        return False


def write_audit(
    db: Session,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    safe_meta = metadata or {}
    previous = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
    previous_hash = previous.event_hash if previous else "0" * 64
    occurred = utcnow()
    payload = json.dumps(
        {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": safe_meta,
            "occurred_at": occurred.isoformat(),
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    audit_key = (settings.app_secret_key or "test-only-audit-key").encode("utf-8")
    event_hash = hmac.new(audit_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=safe_meta,
        occurred_at=occurred,
        previous_hash=previous_hash,
        event_hash=event_hash,
    )
    db.add(event)
    db.flush()
    return event


def verify_audit_chain(db: Session) -> bool:
    previous_hash = "0" * 64
    for event in db.scalars(select(AuditEvent).order_by(AuditEvent.id.asc())):
        payload = json.dumps(
            {
                "actor_id": event.actor_id,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "metadata": event.metadata_json or {},
                "occurred_at": event.occurred_at.isoformat(),
                "previous_hash": event.previous_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        audit_key = (settings.app_secret_key or "test-only-audit-key").encode("utf-8")
        expected = hmac.new(audit_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if event.previous_hash != previous_hash or event.event_hash != expected:
            return False
        previous_hash = event.event_hash
    return True


def record_security_event(
    db: Session,
    source_hash: str,
    reason_code: str,
    severity: str = "L1",
    account_id: str | None = None,
) -> None:
    db.add(
        SecurityEvent(
            account_id=account_id,
            source_hash=source_hash,
            reason_code=reason_code,
            severity=severity,
            occurred_at=utcnow(),
        )
    )


def get_lock_state(db: Session) -> LockState:
    state = db.get(LockState, 1)
    if state is None:
        state = LockState(id=1, mode="normal", reason_code="normal", changed_at=utcnow())
        db.add(state)
        db.flush()
    return state


def request_source_hash(request: Request) -> str:
    # In the local-only app the source is normally loopback. Store only a hash.
    source = request.client.host if request.client else "unknown"
    return digest(source)


def check_mutation_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in settings.app_origins:
        raise HTTPException(status_code=403, detail={"code": "origin_mismatch", "message": "This request did not come from the local application."})
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site and fetch_site not in {"same-origin", "none"}:
        raise HTTPException(status_code=403, detail={"code": "origin_mismatch", "message": "Cross-site requests are not accepted."})


def validate_host(request: Request) -> None:
    host = request.headers.get("host", "").lower().strip()
    if host not in settings.app_hosts:
        raise HTTPException(status_code=403, detail={"code": "host_not_allowed", "message": "This host is not enabled for local access."})


class SlidingRateLimiter:
    def __init__(self, max_events: int = 120, window_seconds: int = 60):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self.events[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_events:
            return False
        bucket.append(now)
        return True


def create_preauth_challenge(db: Session, source_hash: str) -> tuple[str, str]:
    challenge = random_token(32)
    csrf = random_token(32)
    record = AuthChallenge(
        challenge_hash=digest(challenge),
        csrf_token=csrf,
        challenge_type="preauth",
        expires_at=utcnow() + timedelta(minutes=10),
        source_hash=source_hash,
    )
    db.add(record)
    db.commit()
    return challenge, csrf


def get_preauth_challenge(db: Session, request: Request) -> AuthChallenge:
    raw = request.cookies.get(settings.preauth_cookie, "")
    if not raw:
        raise HTTPException(status_code=403, detail={"code": "csrf_failed", "message": "Reload the sign-in page and try again."})
    challenge = db.get(AuthChallenge, digest(raw))
    if not challenge or challenge.challenge_type != "preauth" or challenge.consumed_at or challenge.expires_at <= utcnow():
        raise HTTPException(status_code=403, detail={"code": "csrf_failed", "message": "Your sign-in form expired. Reload it and try again."})
    token = request.headers.get("x-csrf-token", "")
    if not secrets.compare_digest(token, challenge.csrf_token):
        raise HTTPException(status_code=403, detail={"code": "csrf_failed", "message": "The security token did not match. Reload the form."})
    return challenge


def get_session_and_account(db: Session, request: Request) -> tuple[AppSession, Account]:
    raw = request.cookies.get(settings.session_cookie, "")
    if not raw:
        raise HTTPException(status_code=401, detail={"code": "session_expired", "message": "Please sign in again."})
    session = db.get(AppSession, digest(raw))
    now = utcnow()
    if not session or session.expires_at <= now:
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=401, detail={"code": "session_expired", "message": "Please sign in again."})
    idle_minutes = settings.admin_idle_minutes if session.role in {"reviewer", "administrator"} else settings.customer_idle_minutes
    if session.last_seen_at + timedelta(minutes=idle_minutes) <= now:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail={"code": "session_expired", "message": "Your session timed out. Please sign in again."})
    account = db.get(Account, session.account_id)
    if not account or account.status != "active" or session.role != account.role:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail={"code": "session_expired", "message": "Please sign in again."})
    return session, account


def require_session_csrf(request: Request, session: AppSession) -> None:
    token = request.headers.get("x-csrf-token", "")
    if not token or not secrets.compare_digest(token, session.csrf_token):
        raise HTTPException(status_code=403, detail={"code": "csrf_failed", "message": "The security token did not match. Reload the page and try again."})
