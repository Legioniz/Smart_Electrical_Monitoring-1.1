# Consent system: submission, persistence, tracking, and enforcement

Contents: 1 Scope; 2 Purposes and text; 3 Consent record; 4 Submission flow; 5 Enforcement; 6 Withdrawal and deletion; 7 Failure handling; 8 Tests

## 1. Scope
V2 priority 1: reliable consent submission, persistence across sessions, and acceptance tracking. The proposal requires explicit consent before customer-facing analytics. This guide describes engineering behavior, not legal compliance; legal and data-protection review is needed before real use. Local mode.

## 2. Purposes and text
- Required purpose: show my usage and unusual-use alerts in the app (needed to continue).
- Optional purposes, planned and mocked: SMS or push alerts; anonymous neighborhood comparison. Never pre-ticked.
- Plain language, with a retention note ("set before real use").
- Each version of the text has a version number and a hash. Changing the text or the purposes requires fresh consent.

## 3. Consent record (MySQL, in words)
consent_records: ID, account, purpose, status (granted or withdrawn), text version, text hash, decided_at in UTC, source screen, request ID. Append-only: a withdrawal adds a row and nothing is edited in place. The current state is the latest row per account and purpose. A unique key on account, purpose, and request ID makes retries idempotent. Every change also writes an audit event. Keep IP addresses out unless a reason is documented.

## 4. Submission flow
1. The user is signed in and sees the current text version with a CSRF token bound to the session.
2. Submit goes through the same protected path as every state-changing request (security-hardening.md section 18): token, Origin, Host, and validation checks all stay on.
3. The server checks: valid session, customer role, text version equals the current one, purposes are on the allow-list, the required purpose is present.
4. It writes the consent rows and the audit event in one transaction, so there is no partial state.
5. A retry with the same request ID returns the same result; a double click is safe.
6. On success the app confirms and moves on. On failure it shows a clear message and the user can retry.
Persistence: the consent state is read from the database on every request, not only from the session, so it survives new sessions, restarts, and other devices.

## 5. Enforcement
- Before any analytics endpoint or screen the server checks for a current grant of the required purpose; without one it redirects to the consent screen. Never trust the client for this.
- Optional purposes gate their own features (for example creating outbox entries).
- With real data, ingestion and analytics for an account stay blocked until consent exists; the legal basis is Unknown and needs counsel.

## 6. Withdrawal and deletion
- Withdrawal is as easy as giving consent (Settings). Effects are immediate: analytics screens are blocked and notifications stop.
- The consent history is kept as proof of the decisions; other personal data follows security-privacy.md section 11. Whether any proof must be kept after deletion is Unknown.
- Export includes the consent history.

## 7. Failure handling
Log a reason code for each failure: csrf_failed, origin_mismatch, host_not_allowed, session_expired, version_mismatch, validation_failed, db_error. Diagnose with the playbook in security-hardening.md section 18. Never continue as if consent was recorded, and never weaken a protection to make submission work.

## 8. Tests
| Case | Expected |
|---|---|
| Submit in a fresh session | Recorded; analytics unlock |
| Restart the app, sign in again | Consent still in force |
| Expired session during submit | Redirect to sign-in, then resume the consent screen |
| Double submit and retry | One result; no duplicate rows |
| Missing or wrong CSRF token | Refused with a clear message and a log entry |
| Wrong Origin or Host | Refused and logged |
| Stale text version | Asks the user to review the new text |
| Withdrawal | Analytics and notifications stop at once |
| Text changes | Re-consent required |
| Two tabs | No conflict or partial state |
| Database error mid-submit | Nothing saved; clear message |
| Keyboard and screen reader | Every control reachable and labeled |
