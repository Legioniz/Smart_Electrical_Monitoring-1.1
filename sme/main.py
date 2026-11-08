from __future__ import annotations

import hashlib
import json
import secrets
import sys
import time
from datetime import date, datetime, timedelta, timezone
from contextlib import asynccontextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse

from .config import ROOT, settings
from .db import build_engine, build_session_factory, check_database
from .models import (
    Account, Alert, Appliance, ApplianceVersion, AppSession, AuditEvent,
    AuthChallenge, BenchmarkRun, ConsentRecord, Customer, FactSheet,
    Feedback, LockState, Meter, ModelRun, Narrative, NotificationOutbox,
    Reading, SecurityEvent, SettingsVersion, SyntheticLabel,
)
from .schemas import (
    AdminLogin, AdminVerify, ApplianceInput, ApplianceRemoval, ApplianceRestore, ConsentInput,
    CustomerLogin, NotificationSettings, PasswordChange, ReviewInput, SafeModeUnlock,
)
from .security import (
    check_mutation_origin, create_preauth_challenge, digest, get_lock_state,
    get_preauth_challenge, get_session_and_account, hash_password, new_id,
    random_token, record_security_event, request_source_hash,
    require_session_csrf, verify_audit_chain, verify_password, write_audit, DUMMY_PASSWORD_HASH,
    utcnow,
)
from .services.analytics import (
    day_explorer_payload, get_day_readings, get_period_readings, heatmap_payload,
    local_day_bounds, make_fact_sheet, summarize_day, weekly_series,
)
from .services.appliances import (
    CATEGORIES, appliance_candidates, average_kw, breakdown,
    validate_appliance, weekly_kwh,
)
from .services.detection import DETECTOR_VERSION, SETTINGS_VERSION, detect_events
from .services.intelligence import analyze_consumption
from .services.narrative import create_story, create_recommendations
from .services.synthetic import generate_meter_series

CONSENT_VERSION = "1.0"
CONSENT_TEXT = (
    "I agree to let this local demonstration show my simulated electricity usage and "
    "unusual-use alerts in the app. The data is synthetic and is stored on this computer. "
    "No SMS, push notification, or neighborhood comparison is enabled unless I separately opt in. "
    "A retention period must be set before any real customer data is used."
)
CONSENT_HASH = hashlib.sha256(CONSENT_TEXT.encode("utf-8")).hexdigest()
REQUIRED_PURPOSE = "usage_analytics"
OPTIONAL_PURPOSES = {"push_alerts", "sms_alerts"}


class RequestBodyLimitMiddleware:
    """Bound mutation request bodies even when Content-Length is absent or false.

    The body is buffered only up to the configured cap, then replayed once to
    the downstream ASGI app. This prevents chunked requests from bypassing the
    request-size check in LocalRequestMiddleware.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if (scope.get("type") != "http" or scope.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}
                or not scope.get("path", "").startswith("/api/")):
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                request_id = scope.get("state", {}).get("request_id")
                response = JSONResponse(
                    status_code=413,
                    content={"error": {"code": "request_too_large", "message": "The request is too large.", "request_id": request_id}},
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
                )
                await response(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)


class LocalRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = new_id()
        request.state.request_id = request_id
        host = request.headers.get("host", "").lower().strip()
        if host not in request.app.state.allowed_hosts:
            return self._reject(request, request_id, "host_not_allowed", "This host is not enabled for local access.")
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) < 0 or int(content_length) > settings.max_body_bytes:
                    return self._reject(request, request_id, "request_too_large", "The request is too large.", 413)
            except ValueError:
                return self._reject(request, request_id, "validation_failed", "The request could not be validated.", 400)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if not origin:
                referer = request.headers.get("referer")
                if referer:
                    parsed = urlsplit(referer)
                    origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in request.app.state.allowed_origins:
                return self._reject(request, request_id, "origin_mismatch", "This request did not come from the local application.")
            fetch_site = request.headers.get("sec-fetch-site")
            if fetch_site and fetch_site not in {"same-origin", "none"}:
                return self._reject(request, request_id, "origin_mismatch", "Cross-site requests are not accepted.")
            content_type = request.headers.get("content-type", "")
            if not content_type.lower().startswith("application/json"):
                return self._reject(request, request_id, "validation_failed", "This action requires a JSON request.", 415)
        key = (request.client.host if request.client else "unknown") + ":" + request.url.path
        if not request.app.state.rate_limiter.allow(key):
            self._log_failure(request, "rate_limited", "L1")
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited", "message": "Too many requests. Try again shortly.", "request_id": request_id}},
                headers={**self._security_headers(request_id), "Retry-After": "30"},
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        for name, value in self._security_headers(request_id).items():
            response.headers[name] = value
        return response

    @staticmethod
    def _security_headers(request_id: str) -> dict[str, str]:
        return {
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(self)",
            # Inline styles are needed for chart fills and responsive heatmap cells.
            # Script execution remains self-only with no unsafe-inline/eval allowance.
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://api.open-meteo.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
            "Cache-Control": "no-store",
        }

    def _reject(self, request: Request, request_id: str, code: str, message: str, status: int = 403):
        self._log_failure(request, code, "L1")
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message, "request_id": request_id}},
            headers=self._security_headers(request_id),
        )

    @staticmethod
    def _log_failure(request: Request, code: str, severity: str):
        factory = getattr(request.app.state, "session_factory", None)
        if not factory:
            return
        try:
            with factory() as db:
                record_security_event(db, request_source_hash(request), code, severity)
                db.commit()
        except Exception:
            # Security logging failure is not allowed to leak internal details to the client.
            pass


def create_app(*, testing: bool = False, database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(instance: FastAPI):
        if not instance.state.testing:
            from .config import validate_settings
            validate_settings()
        if instance.state.engine is not None:
            try:
                check_database(instance.state.engine)
                with instance.state.session_factory() as startup_db:
                    lock_state = get_lock_state(startup_db)
                    if not verify_audit_chain(startup_db):
                        lock_state.mode = "read_only"
                        lock_state.reason_code = "audit_chain_integrity_failed"
                        lock_state.changed_at = utcnow()
                        record_security_event(startup_db, digest("local-process"), "audit_chain_integrity_failed", "L4")
                        startup_db.commit()
            except Exception:
                # The application remains available for a clear /health and setup message.
                pass
        yield

    app = FastAPI(title="Smart Meter Explorer V2", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.testing = testing
    app.state.allowed_hosts = set(settings.app_hosts) | ({"testserver", "testserver:80"} if testing else set())
    app.state.allowed_origins = set(settings.app_origins) | ({"http://testserver"} if testing else set())
    app.state.rate_limiter = _make_limiter()
    app.state.engine = None
    app.state.session_factory = None
    url = database_url or settings.database_url
    if url:
        engine = build_engine(url, testing=testing)
        app.state.engine = engine
        app.state.session_factory = build_session_factory(engine)
        if testing:
            from .models import Base
            Base.metadata.create_all(engine)
    # Starlette wraps middleware in reverse registration order: LocalRequestMiddleware
    # is outermost so Host/Origin checks run before the bounded body buffer.
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(LocalRequestMiddleware)

    def get_db(request: Request):
        factory = request.app.state.session_factory
        if factory is None:
            raise HTTPException(503, detail={"code": "database_unavailable", "message": "The local database is not configured. Follow the MySQL setup in the README."})
        db = factory()
        try:
            yield db
        finally:
            db.close()

    def get_current_base(request: Request, db: Session = Depends(get_db)):
        session, account = get_session_and_account(db, request)
        session.last_seen_at = utcnow()
        db.commit()
        return session, account

    def get_current(current=Depends(get_current_base)):
        session, account = current
        if account.must_change_password:
            raise HTTPException(403, detail={"code": "password_change_required", "message": "Change your temporary passphrase before using the workspace."})
        return session, account

    def require_password_change(request: Request, current=Depends(get_current_base)):
        session, account = current
        require_session_csrf(request, session)
        if not account.must_change_password:
            raise HTTPException(409, detail={"code": "password_change_not_required", "message": "Your passphrase has already been changed."})
        return session, account

    def require_customer(current=Depends(get_current), db: Session = Depends(get_db)):
        session, account = current
        if account.role != "customer" or not account.customer_id:
            raise HTTPException(403, detail={"code": "role_not_allowed", "message": "This area is available to customer accounts only."})
        _require_current_consent(db, account)
        return session, account

    def require_internal(current=Depends(get_current)):
        session, account = current
        if account.role not in {"reviewer", "administrator"}:
            raise HTTPException(403, detail={"code": "role_not_allowed", "message": "This action is not available for your role."})
        return session, account

    def require_admin(current=Depends(get_current)):
        session, account = current
        if account.role != "administrator":
            raise HTTPException(403, detail={"code": "role_not_allowed", "message": "Administrator permission is required."})
        return session, account

    def require_write(request: Request, current=Depends(get_current), db: Session = Depends(get_db)):
        session, account = current
        require_session_csrf(request, session)
        lock = get_lock_state(db)
        if lock.mode == "read_only":
            raise HTTPException(423, detail={"code": "safe_mode_read_only", "message": "The application is in read-only safe mode. An administrator must review and unlock it."})
        return session, account

    def require_write_allow_safe_mode(request: Request, current=Depends(get_current), db: Session = Depends(get_db)):
        session, account = current
        require_session_csrf(request, session)
        return session, account

    def require_preauth(request: Request, db: Session = Depends(get_db)):
        return get_preauth_challenge(db, request)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            payload = detail
        else:
            payload = {"code": "request_rejected", "message": str(detail)}
        response = JSONResponse(
            status_code=exc.status_code,
            content={"error": {**payload, "request_id": getattr(request.state, "request_id", None)}},
        )
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(x) for x in first.get("loc", []) if x not in {"body", "query", "path"})
        message = f"Check the {field or 'submitted'} field and try again."
        return JSONResponse(status_code=422, content={"error": {"code": "validation_failed", "message": message, "request_id": getattr(request.state, "request_id", None)}})

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"error": {"code": "db_error", "message": "The local database could not complete that action. No partial change was saved; try again.", "request_id": getattr(request.state, "request_id", None)}})

    @app.get("/health")
    def health(request: Request):
        if request.app.state.engine is None:
            return {"status": "not_configured", "database": "not_configured", "mode": "local_only"}
        try:
            check_database(request.app.state.engine)
            return {"status": "ok", "database": "connected", "mode": "local_only", "simulated_data": True}
        except Exception:
            return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable", "mode": "local_only"})

    @app.get("/api/auth/preflight")
    def auth_preflight(request: Request, response: Response, db: Session = Depends(get_db)):
        challenge, csrf = create_preauth_challenge(db, request_source_hash(request))
        response.set_cookie(settings.preauth_cookie, challenge, httponly=True, secure=False, samesite="strict", path="/", max_age=600)
        return {"csrf_token": csrf, "expires_in_seconds": 600}

    @app.get("/api/session")
    def current_session(request: Request, db: Session = Depends(get_db)):
        try:
            session, account = get_session_and_account(db, request)
            session.last_seen_at = utcnow()
            db.commit()
            consented = has_current_consent(db, account)
            return {"authenticated": True, "user": {"id": account.id, "username": account.username, "role": account.role, "must_change_password": account.must_change_password}, "csrf_token": session.csrf_token, "consent_required": account.role == "customer" and not consented}
        except HTTPException as exc:
            if exc.status_code == 401:
                return {"authenticated": False}
            raise

    def _login_throttled(db: Session, username: str, source_hash: str) -> bool:
        ten_minutes_ago = utcnow() - timedelta(minutes=10)
        identifier_hash = digest(username.strip().casefold())
        count = db.scalar(select(func.count(LoginAttempt.id)).where(
            LoginAttempt.identifier_hash == identifier_hash,
            LoginAttempt.source_hash == source_hash,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.occurred_at >= ten_minutes_ago,
        ))
        return int(count or 0) >= settings.login_attempts_per_10m

    def _save_login_attempt(db: Session, username: str, source_hash: str, succeeded: bool):
        from .models import LoginAttempt
        db.add(LoginAttempt(identifier_hash=digest(username.strip().casefold()), source_hash=source_hash, succeeded=succeeded, occurred_at=utcnow()))

    def _new_session(db: Session, response: Response, account: Account, request: Request):
        raw_session = random_token(48)
        csrf = random_token(32)
        now = utcnow()
        is_internal = account.role in {"reviewer", "administrator"}
        absolute = timedelta(hours=settings.admin_absolute_hours if is_internal else settings.customer_absolute_hours)
        db.add(AppSession(
            token_hash=digest(raw_session), account_id=account.id, csrf_token=csrf,
            role=account.role, created_at=now, last_seen_at=now, expires_at=now + absolute,
            source_hash=request_source_hash(request),
        ))
        account.last_sign_in = now
        write_audit(db, account.id, "sign_in", "account", account.id, {"role": account.role})
        response.set_cookie(settings.session_cookie, raw_session, httponly=True, secure=False, samesite="strict", path="/", max_age=int(absolute.total_seconds()))
        response.delete_cookie(settings.preauth_cookie, path="/")
        return csrf

    @app.post("/api/auth/customer/login")
    def customer_login(payload: CustomerLogin, request: Request, response: Response, preauth=Depends(require_preauth), db: Session = Depends(get_db)):
        source_hash = request_source_hash(request)
        if _login_throttled(db, payload.username, source_hash):
            record_security_event(db, source_hash, "login_throttled", "L2")
            db.commit()
            raise HTTPException(429, detail={"code": "login_throttled", "message": "Sign-in is temporarily delayed. Try again later."})
        account = db.scalar(select(Account).where(Account.username == payload.username.strip().casefold()))
        password_ok = verify_password(account.password_hash if account else DUMMY_PASSWORD_HASH, payload.password)
        ok = bool(account and account.role == "customer" and account.status == "active" and password_ok)
        _save_login_attempt(db, payload.username, source_hash, ok)
        preauth.consumed_at = utcnow()
        if not ok:
            record_security_event(db, source_hash, "login_failed", "L1")
            db.commit()
            raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Incorrect username or password."})
        db.query(AppSession).filter(AppSession.account_id == account.id).delete(synchronize_session=False)
        csrf = _new_session(db, response, account, request)
        db.commit()
        return {"ok": True, "csrf_token": csrf, "user": {"username": account.username, "role": account.role}, "consent_required": not has_current_consent(db, account)}

    @app.post("/api/auth/admin/start")
    def admin_login_start(payload: AdminLogin, request: Request, preauth=Depends(require_preauth), db: Session = Depends(get_db)):
        source_hash = request_source_hash(request)
        if _login_throttled(db, payload.username, source_hash):
            record_security_event(db, source_hash, "admin_login_throttled", "L2")
            db.commit()
            raise HTTPException(429, detail={"code": "login_throttled", "message": "Sign-in is temporarily delayed. Try again later."})
        account = db.scalar(select(Account).where(Account.username == payload.username.strip().casefold()))
        password_ok = verify_password(account.password_hash if account else DUMMY_PASSWORD_HASH, payload.password)
        ok = bool(account and account.role in {"reviewer", "administrator"} and account.status == "active" and password_ok)
        _save_login_attempt(db, payload.username, source_hash, ok)
        if not ok:
            preauth.consumed_at = utcnow()
            record_security_event(db, source_hash, "admin_login_failed", "L2")
            db.commit()
            raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Incorrect username or password."})
        challenge_id = random_token(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(AuthChallenge(
            challenge_hash=digest(challenge_id), csrf_token="", challenge_type="admin_login",
            account_id=account.id, code_hash=digest(code), expires_at=utcnow() + timedelta(minutes=5),
            source_hash=source_hash,
        ))
        db.commit()
        print(f"\n[SME ADMIN CONSOLE CODE] account={account.username} code={code} expires=5m\n", file=sys.stderr, flush=True)
        return {"challenge_id": challenge_id, "message": "A one-time code was printed in the server terminal. Enter it to continue.", "expires_in_seconds": 300}

    @app.post("/api/auth/admin/verify")
    def admin_login_verify(payload: AdminVerify, request: Request, response: Response, preauth=Depends(require_preauth), db: Session = Depends(get_db)):
        challenge = db.get(AuthChallenge, digest(payload.challenge_id))
        if not challenge or challenge.challenge_type != "admin_login" or challenge.consumed_at or challenge.expires_at <= utcnow():
            raise HTTPException(403, detail={"code": "validation_failed", "message": "The one-time code expired. Sign in again."})
        if challenge.source_hash != request_source_hash(request) or not secrets.compare_digest(challenge.code_hash or "", digest(payload.code)):
            challenge.attempts += 1
            if challenge.attempts >= 5:
                challenge.consumed_at = utcnow()
            record_security_event(db, request_source_hash(request), "admin_code_failed", "L2", challenge.account_id)
            db.commit()
            if challenge.consumed_at:
                raise HTTPException(403, detail={"code": "validation_failed", "message": "Too many incorrect one-time codes. Start sign-in again."})
            raise HTTPException(401, detail={"code": "invalid_credentials", "message": "The one-time code is incorrect."})
        account = db.get(Account, challenge.account_id)
        if not account or account.role not in {"reviewer", "administrator"} or account.status != "active":
            raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Please sign in again."})
        challenge.consumed_at = utcnow()
        preauth.consumed_at = utcnow()
        db.query(AppSession).filter(AppSession.account_id == account.id).delete(synchronize_session=False)
        csrf = _new_session(db, response, account, request)
        db.commit()
        return {"ok": True, "csrf_token": csrf, "user": {"username": account.username, "role": account.role}}

    @app.post("/api/auth/password/change")
    def change_password(payload: PasswordChange, request: Request, response: Response, current=Depends(require_password_change), db: Session = Depends(get_db)):
        session, account = current
        if not verify_password(account.password_hash, payload.current_password):
            raise HTTPException(401, detail={"code": "reauthentication_failed", "message": "The current passphrase did not match."})
        if payload.current_password == payload.new_password:
            raise HTTPException(422, detail={"code": "validation_failed", "message": "Choose a new passphrase different from the current one."})
        account.password_hash = hash_password(payload.new_password)
        account.must_change_password = False
        raw_session = random_token(48)
        csrf = random_token(32)
        db.delete(session)
        now = utcnow()
        internal = account.role in {"reviewer", "administrator"}
        absolute = timedelta(hours=settings.admin_absolute_hours if internal else settings.customer_absolute_hours)
        db.add(AppSession(token_hash=digest(raw_session), account_id=account.id, csrf_token=csrf, role=account.role, created_at=now, last_seen_at=now, expires_at=now + absolute, source_hash=request_source_hash(request)))
        write_audit(db, account.id, "password_changed", "account", account.id, {"must_change_password": False})
        response.set_cookie(settings.session_cookie, raw_session, httponly=True, secure=False, samesite="strict", path="/", max_age=int(absolute.total_seconds()))
        db.commit()
        return {"ok": True, "csrf_token": csrf, "message": "Passphrase updated."}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, current=Depends(get_current), db: Session = Depends(get_db)):
        session, account = current
        require_session_csrf(request, session)
        db.delete(session)
        write_audit(db, account.id, "sign_out", "account", account.id, {"role": account.role})
        db.commit()
        response.delete_cookie(settings.session_cookie, path="/")
        response.delete_cookie(settings.preauth_cookie, path="/")
        return {"ok": True}

    @app.get("/api/consent")
    def get_consent(request: Request, current=Depends(get_current), db: Session = Depends(get_db)):
        _session, account = current
        if account.role != "customer":
            raise HTTPException(403, detail={"code": "role_not_allowed", "message": "Consent is for customer accounts."})
        return {
            "version": CONSENT_VERSION,
            "text": CONSENT_TEXT,
            "text_hash": CONSENT_HASH,
            "required": {"purpose": REQUIRED_PURPOSE, "label": "Show my usage and unusual-use alerts in the app", "required": True},
            "optional": [
                {"purpose": "push_alerts", "label": "Mock push notifications (not sent)", "required": False},
                {"purpose": "sms_alerts", "label": "Mock SMS notifications (not sent)", "required": False},
            ],
            "current": _consent_statuses(db, account.id),
        }

    @app.post("/api/consent")
    def submit_consent(payload: ConsentInput, request: Request, current=Depends(require_write), db: Session = Depends(get_db)):
        session, account = current
        if account.role != "customer":
            raise HTTPException(403, detail={"code": "role_not_allowed", "message": "Consent is for customer accounts."})
        if payload.text_version != CONSENT_VERSION:
            raise HTTPException(409, detail={"code": "version_mismatch", "message": "The consent text has changed. Review the current version and submit again."})
        if not payload.required_analytics:
            raise HTTPException(422, detail={"code": "validation_failed", "message": "The required usage purpose must be accepted to continue."})
        try:
            purpose_values = {
                REQUIRED_PURPOSE: True,
                "push_alerts": payload.push_alerts,
                "sms_alerts": payload.sms_alerts,
            }
            already_saved = True
            for purpose, granted in purpose_values.items():
                existing = db.scalar(select(ConsentRecord).where(
                    ConsentRecord.account_id == account.id,
                    ConsentRecord.purpose == purpose,
                    ConsentRecord.request_id == payload.request_id,
                ))
                if existing:
                    expected_status = "granted" if granted else "withdrawn"
                    if existing.status != expected_status:
                        raise HTTPException(409, detail={"code": "request_id_conflict", "message": "This consent request ID was already used for a different decision. Refresh and submit again."})
                    continue
                already_saved = False
                db.add(ConsentRecord(
                    id=new_id(), account_id=account.id, purpose=purpose,
                    status="granted" if granted else "withdrawn",
                    text_version=CONSENT_VERSION, text_hash=CONSENT_HASH,
                    request_id=payload.request_id, source_screen="consent",
                    decided_at=utcnow(),
                ))
            if not already_saved:
                write_audit(db, account.id, "consent_decided", "consent", payload.request_id, {"required": True, "push_alerts": payload.push_alerts, "sms_alerts": payload.sms_alerts, "text_version": CONSENT_VERSION})
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, detail={"code": "db_error", "message": "Consent was not saved. No partial change was committed; please retry."})
        return {"ok": True, "idempotent": already_saved, "analytics_unlocked": has_current_consent(db, account), "message": "Your consent decision was saved on this computer."}

    @app.post("/api/customer/consent/withdraw")
    def withdraw_consent(request: Request, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        now = utcnow()
        for purpose in (REQUIRED_PURPOSE, *OPTIONAL_PURPOSES):
            latest = db.scalar(select(ConsentRecord).where(ConsentRecord.account_id == account.id, ConsentRecord.purpose == purpose).order_by(ConsentRecord.decided_at.desc()).limit(1))
            if latest and latest.status == "granted":
                db.add(ConsentRecord(id=new_id(), account_id=account.id, purpose=purpose, status="withdrawn", text_version=CONSENT_VERSION, text_hash=CONSENT_HASH, request_id=new_id(), source_screen="settings", decided_at=now))
        db.query(Customer).filter(Customer.id == account.customer_id).update({Customer.push_opt_in: False, Customer.sms_opt_in: False})
        write_audit(db, account.id, "consent_withdrawn", "customer", account.customer_id, {"purposes": "all_current_grants"})
        db.commit()
        return {"ok": True, "analytics_unlocked": False, "message": "Consent was withdrawn. Analytics are now blocked."}

    @app.get("/api/customer/overview")
    def overview(current=Depends(require_customer), db: Session = Depends(get_db)):
        _session, account = current
        customer, meter = _customer_and_meter(db, account)
        latest = db.scalar(select(func.max(Reading.interval_start_utc)).where(Reading.meter_id == meter.id))
        if not latest:
            raise HTTPException(404, detail={"code": "no_meter_data", "message": "No readings are available for this simulated meter."})
        latest_day = latest.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date()
        series = weekly_series(db, meter.id, latest_day, 7)
        intelligence_series = weekly_series(db, meter.id, latest_day, 35)
        intelligence = analyze_consumption(intelligence_series)
        current_readings = get_period_readings(db, meter.id, latest_day - timedelta(days=6), 7)
        valid_current = [r for r in current_readings if r.quality != "missing"]
        total_decimal = sum((Decimal(r.energy_kwh) for r in valid_current), Decimal("0"))
        total = float(total_decimal)
        coverage = len(valid_current) / (7 * 96) * 100
        previous_readings = get_period_readings(db, meter.id, latest_day - timedelta(days=13), 7)
        valid_previous = [r for r in previous_readings if r.quality != "missing"]
        previous_decimal = sum((Decimal(r.energy_kwh) for r in valid_previous), Decimal("0"))
        prev_total = float(previous_decimal)
        change = ((total - prev_total) / prev_total * 100) if prev_total > 0 and len(valid_previous) >= 7 * 96 * 0.9 else None
        appliances = list(db.scalars(select(Appliance).where(Appliance.customer_id == account.customer_id, Appliance.status == "active")))
        app_data = breakdown(appliances, total_decimal)
        alerts = list(db.scalars(select(Alert).where(Alert.customer_id == account.customer_id, Alert.audience == "customer").order_by(Alert.created_at.desc()).limit(5)))
        return {
            "simulated": True,
            "period": {"start": series[0]["date"], "end": series[-1]["date"]},
            "total_kwh": round(total, 1),
            "previous_total_kwh": round(prev_total, 1),
            "change_pct": round(change, 1) if change is not None else None,
            "coverage_pct": round(coverage, 1),
            "average_power_kw": round(total / (7 * 24), 3),
            "weekly": [{"date": x["date"], "total_kwh": x["total_kwh"], "coverage_pct": x["coverage_pct"], "partial": x["partial"]} for x in series],
            "intelligence": intelligence,
            "appliances": {"count": len(appliances), "coverage_pct": app_data.get("coverage_pct"), "top_category": app_data["items"][0]["category_label"] if app_data.get("items") else None},
            "alerts": [_customer_alert_json(a) for a in alerts],
        }

    @app.get("/api/customer/day")
    def day_explorer(day: date | None = None, current=Depends(require_customer), db: Session = Depends(get_db)):
        _session, account = current
        _customer, meter = _customer_and_meter(db, account)
        latest = db.scalar(select(func.max(Reading.interval_start_utc)).where(Reading.meter_id == meter.id))
        latest_day = latest.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date() if latest else date.today()
        selected = day or latest_day
        if (latest_day - selected).days > 35 or (selected - latest_day).days > 0:
            raise HTTPException(422, detail={"code": "validation_failed", "message": "Choose a date inside the available simulated-data range."})
        readings = get_day_readings(db, meter.id, selected)
        payload = day_explorer_payload(readings, selected)
        # Mark intervals from persisted detector alerts. Synthetic injection labels
        # are deliberately not used as customer-visible detections.
        selected_start_utc, selected_end_utc = local_day_bounds(selected)
        detected_alerts = list(db.scalars(select(Alert).where(
            Alert.meter_id == meter.id,
            Alert.audience == "customer",
            Alert.window_start < selected_end_utc,
            Alert.window_end > selected_start_utc,
        )))
        for slot in payload["intervals"]:
            slot_start_utc = selected_start_utc + timedelta(minutes=15 * slot["slot"])
            matching = [a for a in detected_alerts if a.window_start <= slot_start_utc < a.window_end]
            if matching:
                first = sorted(matching, key=lambda a: (a.tier, a.created_at))[0]
                slot["flagged"] = True
                slot["alert_type"] = first.alert_type
                slot["alert_tier"] = first.tier
                slot["reason"] = first.reason_text
        appliances = list(db.scalars(select(Appliance).where(Appliance.customer_id == account.customer_id, Appliance.status == "active")))
        last_slot = next((i for i in reversed(payload["intervals"]) if i["energy_kwh"] is not None), None)
        candidates = []
        if last_slot:
            prior = get_period_readings(db, meter.id, selected - timedelta(days=7), 7)
            slot_number = int(last_slot["time"][:2]) * 4 + int(last_slot["time"][3:]) // 15
            prior_kw = []
            for row in prior:
                if row.quality == "missing":
                    continue
                local = row.interval_start_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila"))
                if local.hour * 4 + local.minute // 15 == slot_number:
                    prior_kw.append(float(row.energy_kwh) / 0.25)
            usual_kw = sorted(prior_kw)[len(prior_kw)//2] if prior_kw else 0.0
            candidates = appliance_candidates(appliances, last_slot["average_power_kw"], usual_kw)
        payload["appliance_candidates"] = candidates
        return payload

    @app.get("/api/customer/heatmap")
    def heatmap(days: int = 7, current=Depends(require_customer), db: Session = Depends(get_db)):
        if not 1 <= days <= 28:
            raise HTTPException(422, detail={"code": "validation_failed", "message": "Days must be between 1 and 28."})
        _session, account = current
        _customer, meter = _customer_and_meter(db, account)
        latest = db.scalar(select(func.max(Reading.interval_start_utc)).where(Reading.meter_id == meter.id))
        latest_day = latest.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date() if latest else date.today()
        return heatmap_payload(db, meter.id, latest_day, days)

    @app.get("/api/customer/alerts")
    def customer_alerts(current=Depends(require_customer), db: Session = Depends(get_db)):
        _session, account = current
        records = list(db.scalars(select(Alert).where(Alert.customer_id == account.customer_id, Alert.audience == "customer").order_by(Alert.created_at.desc()).limit(100)))
        return {"alerts": [_customer_alert_json(a) for a in records]}

    @app.get("/api/customer/story")
    def story(language: str = "en", current=Depends(require_customer), db: Session = Depends(get_db)):
        if language not in {"en", "fil"}:
            raise HTTPException(422, detail={"code": "validation_failed", "message": "Language must be en or fil."})
        _session, account = current
        _customer, meter = _customer_and_meter(db, account)
        latest = db.scalar(select(func.max(Reading.interval_start_utc)).where(Reading.meter_id == meter.id))
        latest_day = latest.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date() if latest else date.today()
        appliances = list(db.scalars(select(Appliance).where(Appliance.customer_id == account.customer_id, Appliance.status == "active")))
        built = make_fact_sheet(db, account.customer_id, meter.id, latest_day, appliances)
        sheet = db.scalar(select(FactSheet).where(FactSheet.customer_id == account.customer_id, FactSheet.fact_hash == built["fact_hash"]).order_by(FactSheet.created_at.desc()).limit(1))
        if sheet is None:
            sheet = FactSheet(id=new_id(), customer_id=account.customer_id, period_start=built["period_start_utc"], period_end=built["period_end_utc"], version="facts-v1", facts=built["facts"], fact_hash=built["fact_hash"], coverage_pct=Decimal(str(built["coverage_pct"])), created_at=utcnow())
            db.add(sheet)
            db.flush()
        narrative = db.scalar(select(Narrative).where(Narrative.fact_sheet_id == sheet.id, Narrative.language == language).order_by(Narrative.created_at.desc()).limit(1))
        if narrative is None:
            generated = create_story(sheet.facts, language)
            narrative = Narrative(
                id=new_id(), fact_sheet_id=sheet.id, language=language, text=generated["text"],
                engine=generated["engine"], model_name=generated["model_name"], model_hash=generated["model_hash"],
                prompt_version=generated["prompt_version"], validator_passed=generated["validator_passed"],
                provenance={"fact_sheet_id": sheet.id, "fact_hash": sheet.fact_hash, "reason": generated["reason"], "data_source": "synthetic"},
                latency_ms=generated["latency_ms"], created_at=utcnow(),
            )
            db.add(narrative)
            db.commit()
        recommendations = create_recommendations(sheet.facts, language)
        return {"fact_sheet": sheet.facts, "story": narrative.text, "engine": narrative.engine,
                "validator_passed": narrative.validator_passed, "recommendations": recommendations,
                "simulated": True}

    @app.get("/api/customer/appliances")
    def list_appliances(current=Depends(require_customer), db: Session = Depends(get_db)):
        _session, account = current
        records = list(db.scalars(select(Appliance).where(Appliance.customer_id == account.customer_id, Appliance.status == "active")))
        records.sort(key=weekly_kwh, reverse=True)
        latest = db.scalar(select(func.max(Reading.interval_start_utc)).join(Meter, Meter.id == Reading.meter_id).where(Meter.customer_id == account.customer_id))
        if latest:
            latest_day = latest.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date()
            week = get_period_readings(db, _customer_and_meter(db, account)[1].id, latest_day - timedelta(days=6), 7)
            total = sum((Decimal(r.energy_kwh) for r in week), Decimal("0"))
        else:
            total = None
        return {"appliances": [_appliance_json(a) for a in records], "breakdown": breakdown(records, total), "categories": CATEGORIES}

    @app.post("/api/customer/appliances/preview")
    def preview_appliance(payload: ApplianceInput, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        data = validate_appliance(payload.model_dump(exclude={"version"}))
        average = Decimal(str(data["rated_power_w"])) / Decimal(1000) * data["quantity"] * Decimal(str(data["duty_pct"])) / Decimal(100)
        weekly = average * Decimal(str(data["hours_per_day"])) * data["days_per_week"]
        return {"average_kw": float(average.quantize(Decimal("0.001"))), "declared_kwh_per_week": float(weekly.quantize(Decimal("0.1"))), "category_label": CATEGORIES[data["category"]], "note": "Estimate from your entries; not measured per appliance."}

    @app.post("/api/customer/appliances")
    def create_appliance(payload: ApplianceInput, request: Request, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        data = validate_appliance(payload.model_dump(exclude={"version"}))
        count = db.scalar(select(func.count(Appliance.id)).where(Appliance.customer_id == account.customer_id, Appliance.status == "active")) or 0
        if count >= 30:
            raise HTTPException(409, detail={"code": "limit_reached", "message": "You can list up to 30 active appliances."})
        if db.scalar(select(Appliance.id).where(Appliance.customer_id == account.customer_id, Appliance.active_name_key == data["active_name_key"])):
            raise HTTPException(409, detail={"code": "duplicate_appliance", "message": "An active appliance already uses that name."})
        now = utcnow()
        appliance = Appliance(id=new_id(), customer_id=account.customer_id, **data, status="active", version=1, created_at=now, updated_at=now)
        db.add(appliance)
        db.flush()
        _add_appliance_version(db, appliance, now)
        write_audit(db, account.id, "appliance_created", "appliance", appliance.id, {"category": appliance.category, "version": appliance.version})
        db.commit()
        return {"ok": True, "appliance": _appliance_json(appliance), "message": "Appliance saved. Dashboard estimates will use this entry."}

    @app.put("/api/customer/appliances/{appliance_id}")
    def update_appliance(appliance_id: str, payload: ApplianceInput, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        appliance = _owned_appliance(db, appliance_id, account.customer_id)
        if payload.version is None or payload.version != appliance.version:
            raise HTTPException(409, detail={"code": "version_conflict", "message": "This appliance changed in another tab. Reload the list before saving."})
        data = validate_appliance(payload.model_dump(exclude={"version"}))
        duplicate = db.scalar(select(Appliance.id).where(Appliance.customer_id == account.customer_id, Appliance.active_name_key == data["active_name_key"], Appliance.id != appliance.id))
        if duplicate:
            raise HTTPException(409, detail={"code": "duplicate_appliance", "message": "An active appliance already uses that name."})
        now = utcnow()
        previous = db.scalar(select(ApplianceVersion).where(ApplianceVersion.appliance_id == appliance.id, ApplianceVersion.valid_to.is_(None)).order_by(ApplianceVersion.version.desc()).limit(1))
        if previous:
            previous.valid_to = now
        for key, value in data.items():
            setattr(appliance, key, value)
        appliance.version += 1
        appliance.updated_at = now
        _add_appliance_version(db, appliance, now)
        write_audit(db, account.id, "appliance_updated", "appliance", appliance.id, {"version": appliance.version, "category": appliance.category})
        db.commit()
        return {"ok": True, "appliance": _appliance_json(appliance), "message": "Appliance updated. Related estimates use the new version from now on."}

    @app.delete("/api/customer/appliances/{appliance_id}")
    def remove_appliance(appliance_id: str, payload: ApplianceRemoval, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        appliance = _owned_appliance(db, appliance_id, account.customer_id)
        if payload.version != appliance.version:
            raise HTTPException(409, detail={"code": "version_conflict", "message": "This appliance changed in another tab. Reload the list before removing it."})
        now = utcnow()
        if payload.action == "retire":
            appliance.status = "retired"
            appliance.active_name_key = None
            appliance.retired_on = now
            appliance.version += 1
            appliance.updated_at = now
            previous = db.scalar(select(ApplianceVersion).where(ApplianceVersion.appliance_id == appliance.id, ApplianceVersion.valid_to.is_(None)).order_by(ApplianceVersion.version.desc()).limit(1))
            if previous:
                previous.valid_to = now
            write_audit(db, account.id, "appliance_retired", "appliance", appliance.id, {"version": appliance.version})
            msg = "Appliance retired. Earlier periods keep the estimate; future periods will exclude it."
        else:
            appliance_id_saved = appliance.id
            db.delete(appliance)
            write_audit(db, account.id, "appliance_removed_as_mistake", "appliance", appliance_id_saved, {"removed": True})
            msg = "Appliance removed from all estimates. Meter readings were not changed."
        db.commit()
        return {"ok": True, "message": msg, "version": appliance.version if payload.action == "retire" else None}

    @app.post("/api/customer/appliances/{appliance_id}/restore")
    def restore_appliance(appliance_id: str, payload: ApplianceRestore, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        appliance = _owned_appliance(db, appliance_id, account.customer_id)
        if appliance.status != "retired":
            raise HTTPException(409, detail={"code": "not_retired", "message": "Only a retired appliance can be restored."})
        if payload.version != appliance.version:
            raise HTTPException(409, detail={"code": "version_conflict", "message": "This appliance changed after it was retired. Reload before restoring it."})
        active_count = db.scalar(select(func.count(Appliance.id)).where(Appliance.customer_id == account.customer_id, Appliance.status == "active")) or 0
        if active_count >= 30:
            raise HTTPException(409, detail={"code": "limit_reached", "message": "The active appliance limit has been reached. Retire another item before restoring this one."})
        duplicate = db.scalar(select(Appliance.id).where(Appliance.customer_id == account.customer_id, Appliance.active_name_key == appliance.name.casefold(), Appliance.id != appliance.id))
        if duplicate:
            raise HTTPException(409, detail={"code": "duplicate_appliance", "message": "An active appliance already uses this name. Rename that item or edit the retired item after restoring is available."})
        now = utcnow()
        appliance.status = "active"
        appliance.active_name_key = appliance.name.casefold()
        appliance.retired_on = None
        appliance.version += 1
        appliance.updated_at = now
        _add_appliance_version(db, appliance, now)
        write_audit(db, account.id, "appliance_restored", "appliance", appliance.id, {"version": appliance.version})
        db.commit()
        return {"ok": True, "message": "Appliance restored. Future estimates will include it again.", "version": appliance.version, "appliance": _appliance_json(appliance)}

    @app.get("/api/customer/appliances/{appliance_id}/history")
    def appliance_history(appliance_id: str, current=Depends(require_customer), db: Session = Depends(get_db)):
        _session, account = current
        appliance = _owned_appliance(db, appliance_id, account.customer_id)
        versions = list(db.scalars(select(ApplianceVersion).where(ApplianceVersion.appliance_id == appliance.id).order_by(ApplianceVersion.version.asc())))
        return {"history": [{"version": v.version, "category": v.category, "rated_power_w": float(v.rated_power_w), "quantity": v.quantity, "duty_pct": float(v.duty_pct), "hours_per_day": float(v.hours_per_day), "days_per_week": v.days_per_week, "valid_from": v.valid_from.isoformat(), "valid_to": v.valid_to.isoformat() if v.valid_to else None} for v in versions]}

    @app.get("/api/customer/settings")
    def customer_settings(current=Depends(get_current), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        customer = db.get(Customer, account.customer_id)
        statuses = _consent_statuses(db, account.id)
        return {"language": customer.language, "push_alerts": customer.push_opt_in, "sms_alerts": customer.sms_opt_in, "consent": statuses, "data_source": "simulated"}

    @app.put("/api/customer/settings")
    def update_customer_settings(payload: NotificationSettings, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        if payload.push_alerts and not _has_purpose(db, account.id, "push_alerts"):
            raise HTTPException(403, detail={"code": "optional_consent_required", "message": "Grant optional push consent before enabling this setting."})
        if payload.sms_alerts and not _has_purpose(db, account.id, "sms_alerts"):
            raise HTTPException(403, detail={"code": "optional_consent_required", "message": "Grant optional SMS consent before enabling this setting."})
        customer = db.get(Customer, account.customer_id)
        customer.language = payload.language
        customer.push_opt_in = payload.push_alerts
        customer.sms_opt_in = payload.sms_alerts
        write_audit(db, account.id, "notification_settings_updated", "customer", account.customer_id, {"push_alerts": payload.push_alerts, "sms_alerts": payload.sms_alerts, "language": payload.language})
        db.commit()
        return {"ok": True, "message": "Settings saved. Notifications remain local mock entries and are not sent."}

    @app.get("/api/customer/export")
    def export_customer_data(current=Depends(get_current), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        customer_id = account.customer_id
        meter = db.scalar(select(Meter).where(Meter.customer_id == customer_id))
        appliances = list(db.scalars(select(Appliance).where(Appliance.customer_id == customer_id)))
        consents = list(db.scalars(select(ConsentRecord).where(ConsentRecord.account_id == account.id).order_by(ConsentRecord.decided_at.asc())))
        readings = list(db.scalars(select(Reading).where(Reading.meter_id == meter.id).order_by(Reading.interval_start_utc.asc()))) if meter else []
        alerts = list(db.scalars(select(Alert).where(Alert.customer_id == customer_id, Alert.audience == "customer")))
        payload = {
            "source": "synthetic demonstration data",
            "exported_at_utc": utcnow().isoformat(),
            "readings": [{"interval_start_utc": r.interval_start_utc.isoformat(), "energy_kwh": str(r.energy_kwh), "quality": r.quality} for r in readings],
            "appliances": [_appliance_json(a) for a in appliances],
            "consent_history": [{"purpose": c.purpose, "status": c.status, "text_version": c.text_version, "decided_at_utc": c.decided_at.isoformat()} for c in consents],
            "customer_alerts": [_customer_alert_json(a) for a in alerts],
        }
        return JSONResponse(content=payload, headers={"Content-Disposition": "attachment; filename=smart-meter-explorer-export.json"})

    @app.delete("/api/customer/sample-data")
    def delete_sample_data(request: Request, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        _customer_role(account)
        meter = db.scalar(select(Meter).where(Meter.customer_id == account.customer_id))
        customer_id = account.customer_id
        appliance_rows = list(db.scalars(select(Appliance).where(Appliance.customer_id == customer_id)))
        for appliance in appliance_rows:
            db.delete(appliance)
        if meter:
            db.query(Reading).filter(Reading.meter_id == meter.id).delete(synchronize_session=False)
            db.query(SyntheticLabel).filter(SyntheticLabel.meter_id == meter.id).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.customer_id == customer_id).delete(synchronize_session=False)
        db.query(NotificationOutbox).filter(NotificationOutbox.customer_id == customer_id).delete(synchronize_session=False)
        db.query(FactSheet).filter(FactSheet.customer_id == customer_id).delete(synchronize_session=False)
        write_audit(db, account.id, "sample_data_deleted", "customer", customer_id, {"readings": True, "appliances": True, "consent_history_retained": True})
        db.commit()
        return {"ok": True, "message": "Simulated readings, alerts, stories, and appliances were deleted. Consent history and the account were retained."}

    @app.get("/api/internal/queue")
    def internal_queue(current=Depends(require_internal), db: Session = Depends(get_db)):
        _session, account = current
        lock = get_lock_state(db)
        if lock.mode == "read_only":
            raise HTTPException(423, detail={"code": "safe_mode_read_only", "message": "Internal review is temporarily unavailable while safe mode is active."})
        leads = list(db.scalars(select(Alert).where(Alert.audience == "internal", Alert.status == "open").order_by(Alert.created_at.desc()).limit(100)))
        return {"safe_mode": lock.mode, "reason_code": lock.reason_code, "leads": [{"id": a.id, "tier": a.tier, "type": a.alert_type, "status": a.status, "reason": a.reason_text, "window_start": a.window_start.isoformat(), "window_end": a.window_end.isoformat(), "created_at": a.created_at.isoformat(), "provenance": a.feature_values} for a in leads]}

    @app.post("/api/internal/queue/{alert_id}/review")
    def review_lead(alert_id: str, payload: ReviewInput, current=Depends(require_write), db: Session = Depends(get_db)):
        _session, account = current
        if account.role not in {"reviewer", "administrator"}:
            raise HTTPException(403, detail={"code": "role_not_allowed", "message": "Reviewer permission is required."})
        alert = db.get(Alert, alert_id)
        if not alert or alert.audience != "internal":
            raise HTTPException(404, detail={"code": "not_found", "message": "Review item not found."})
        alert.status = payload.status
        alert.reviewed_by = account.id
        alert.reviewed_at = utcnow()
        write_audit(db, account.id, "internal_lead_reviewed", "alert", alert.id, {"status": payload.status})
        db.commit()
        return {"ok": True}

    @app.get("/api/internal/protection")
    def protection_status(current=Depends(require_internal), db: Session = Depends(get_db)):
        _session, account = current
        lock = get_lock_state(db)
        last_event = db.scalar(select(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(1))
        return {"mode": lock.mode, "reason_code": lock.reason_code, "changed_at": lock.changed_at.isoformat(), "last_security_event": {"reason_code": last_event.reason_code, "occurred_at": last_event.occurred_at.isoformat()} if last_event else None, "integrity": "audit_chain_checked_at_startup", "network_mode": "localhost_only"}

    @app.post("/api/internal/safe-mode/lock")
    def lock_safe_mode(request: Request, current=Depends(require_admin), db: Session = Depends(get_db)):
        session, account = current
        require_session_csrf(request, session)
        state = get_lock_state(db)
        state.mode = "read_only"
        state.reason_code = "admin_manual_lock"
        state.changed_at = utcnow()
        state.unlocked_by = None
        write_audit(db, account.id, "safe_mode_locked", "lock_state", "1", {"reason_code": state.reason_code})
        db.commit()
        return {"ok": True, "mode": state.mode}

    @app.post("/api/internal/safe-mode/approval/start")
    def start_safe_mode_approval(payload: AdminLogin, request: Request, current=Depends(require_admin), db: Session = Depends(get_db)):
        session, current_account = current
        require_session_csrf(request, session)
        second = db.scalar(select(Account).where(Account.username == payload.username.strip().casefold()))
        if not second or second.role != "administrator" or second.id == current_account.id or second.status != "active" or not verify_password(second.password_hash, payload.password):
            raise HTTPException(401, detail={"code": "approval_denied", "message": "A different active administrator must approve this action."})
        challenge_id = random_token(32)
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(AuthChallenge(challenge_hash=digest(challenge_id), csrf_token="", challenge_type="safe_mode_approval", account_id=second.id, code_hash=digest(code), expires_at=utcnow() + timedelta(minutes=5), source_hash=request_source_hash(request)))
        db.commit()
        print(f"\n[SME SECOND-ADMIN APPROVAL CODE] account={second.username} code={code} expires=5m\n", file=sys.stderr, flush=True)
        return {"challenge_id": challenge_id, "message": "The second administrator's one-time code was printed in the server terminal."}

    @app.post("/api/internal/safe-mode/unlock")
    def unlock_safe_mode(payload: SafeModeUnlock, request: Request, current=Depends(require_write_allow_safe_mode), db: Session = Depends(get_db)):
        session, account = current
        if account.role != "administrator":
            raise HTTPException(403, detail={"code": "role_not_allowed", "message": "Administrator permission is required."})
        if not verify_password(account.password_hash, payload.current_password):
            raise HTTPException(401, detail={"code": "reauthentication_failed", "message": "Re-enter your administrator passphrase."})
        challenge = db.get(AuthChallenge, digest(payload.approval_challenge_id))
        if not challenge or challenge.challenge_type != "safe_mode_approval" or challenge.consumed_at or challenge.expires_at <= utcnow() or challenge.source_hash != request_source_hash(request) or not secrets.compare_digest(challenge.code_hash or "", digest(payload.approval_code)):
            if challenge and challenge.challenge_type == "safe_mode_approval" and not challenge.consumed_at:
                challenge.attempts += 1
                if challenge.attempts >= 5:
                    challenge.consumed_at = utcnow()
                db.commit()
            raise HTTPException(403, detail={"code": "second_approval_failed", "message": "The second administrator approval is missing, invalid, expired, or has too many failed attempts."})
        second = db.get(Account, challenge.account_id)
        if not second or second.role != "administrator" or second.id == account.id or second.status != "active":
            raise HTTPException(403, detail={"code": "second_approval_failed", "message": "A different active administrator must approve this action."})
        challenge.consumed_at = utcnow()
        state = get_lock_state(db)
        state.mode = "normal"
        state.reason_code = "admin_two_person_unlock"
        state.changed_at = utcnow()
        state.unlocked_by = account.id
        write_audit(db, account.id, "safe_mode_unlocked", "lock_state", "1", {"second_approver_id": second.id})
        write_audit(db, second.id, "safe_mode_second_approval", "lock_state", "1", {"first_approver_id": account.id})
        db.commit()
        return {"ok": True, "mode": "normal", "message": "Safe mode was unlocked with two administrator approvals."}

    # Local front end: React build is served when present; the no-CDN fallback works offline.
    react_dist = ROOT / "web" / "dist"
    if react_dist.exists():
        app.mount("/assets", StaticFiles(directory=react_dist / "assets"), name="react-assets")

    @app.get("/", response_class=HTMLResponse)
    def home():
        built_index = react_dist / "index.html"
        return FileResponse(built_index if built_index.exists() else ROOT / "web" / "index.html")

    @app.get("/{asset_path:path}")
    def static_assets(asset_path: str):
        if asset_path.startswith("api/") or asset_path.startswith("internal/"):
            raise HTTPException(404, detail={"code": "not_found", "message": "Page not found."})
        built_asset = react_dist / asset_path
        if built_asset.exists() and built_asset.is_file():
            return FileResponse(built_asset)
        fallback_asset = ROOT / "web" / asset_path
        if fallback_asset.exists() and fallback_asset.is_file():
            return FileResponse(fallback_asset)
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})


    return app


def _make_limiter():
    from .security import SlidingRateLimiter
    return SlidingRateLimiter(max_events=settings.request_rate_per_minute, window_seconds=60)


def _customer_role(account: Account):
    if account.role != "customer" or not account.customer_id:
        raise HTTPException(403, detail={"code": "role_not_allowed", "message": "This action is available to customer accounts only."})


def _consent_statuses(db: Session, account_id: str) -> dict:
    statuses = {}
    for purpose in (REQUIRED_PURPOSE, *OPTIONAL_PURPOSES):
        record = db.scalar(select(ConsentRecord).where(ConsentRecord.account_id == account_id, ConsentRecord.purpose == purpose).order_by(ConsentRecord.decided_at.desc()).limit(1))
        statuses[purpose] = bool(record and record.status == "granted" and record.text_version == CONSENT_VERSION and record.text_hash == CONSENT_HASH)
    return statuses


def _has_purpose(db: Session, account_id: str, purpose: str) -> bool:
    record = db.scalar(select(ConsentRecord).where(ConsentRecord.account_id == account_id, ConsentRecord.purpose == purpose).order_by(ConsentRecord.decided_at.desc()).limit(1))
    return bool(record and record.status == "granted" and record.text_version == CONSENT_VERSION and record.text_hash == CONSENT_HASH)


def has_current_consent(db: Session, account: Account) -> bool:
    return account.role == "customer" and _has_purpose(db, account.id, REQUIRED_PURPOSE)


def _require_current_consent(db: Session, account: Account):
    if not has_current_consent(db, account):
        raise HTTPException(403, detail={"code": "consent_required", "message": "Review and accept the current consent notice before opening analytics."})


def _customer_and_meter(db: Session, account: Account) -> tuple[Customer, Meter]:
    customer = db.get(Customer, account.customer_id)
    meter = db.scalar(select(Meter).where(Meter.customer_id == account.customer_id).order_by(Meter.created_at.asc()).limit(1))
    if not customer or not meter:
        raise HTTPException(404, detail={"code": "meter_not_found", "message": "No simulated meter is configured for this account."})
    return customer, meter


def _owned_appliance(db: Session, appliance_id: str, customer_id: str) -> Appliance:
    try:
        UUID(appliance_id)
    except ValueError:
        raise HTTPException(404, detail={"code": "not_found", "message": "Appliance not found."})
    appliance = db.scalar(select(Appliance).where(Appliance.id == appliance_id, Appliance.customer_id == customer_id))
    if not appliance:
        raise HTTPException(404, detail={"code": "not_found", "message": "Appliance not found."})
    return appliance


def _add_appliance_version(db: Session, appliance: Appliance, now: datetime):
    db.add(ApplianceVersion(
        id=new_id(), appliance_id=appliance.id, version=appliance.version, category=appliance.category,
        rated_power_w=appliance.rated_power_w, quantity=appliance.quantity, duty_pct=appliance.duty_pct,
        hours_per_day=appliance.hours_per_day, days_per_week=appliance.days_per_week,
        valid_from=now, valid_to=None,
    ))


def _appliance_json(appliance: Appliance) -> dict:
    return {
        "id": appliance.id, "name": appliance.name, "category": appliance.category,
        "category_label": CATEGORIES.get(appliance.category, "Other"),
        "rated_power_w": float(appliance.rated_power_w), "quantity": appliance.quantity,
        "duty_pct": float(appliance.duty_pct), "hours_per_day": float(appliance.hours_per_day),
        "days_per_week": appliance.days_per_week, "notes": appliance.notes,
        "status": appliance.status, "version": appliance.version,
        "declared_kwh_per_week": round(float(weekly_kwh(appliance)), 1),
    }


def _customer_alert_json(alert: Alert) -> dict:
    # Audience routing prevents internal/theft-related leads from entering this serializer.
    return {
        "id": alert.id, "tier": alert.tier, "type": alert.alert_type,
        "reason": alert.reason_text, "status": alert.status,
        "window_start": alert.window_start.isoformat(), "window_end": alert.window_end.isoformat(),
        "created_at": alert.created_at.isoformat(),
    }


# LoginAttempt is referenced in the closure above. Import after models have been loaded.
from .models import LoginAttempt  # noqa: E402

app = create_app()
