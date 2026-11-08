# Security review — V2 implementation notes

This is a design and code-review record, not a certification or independent security assessment.

## Controls implemented in code

| Area | Implementation | Remaining caveat |
|---|---|---|
| Network scope | Uvicorn binds to `127.0.0.1`; Host allowlist defaults to loopback only | The operator must not reverse-proxy or expose the port externally |
| Transport/request origin | Exact local Origin/Referer allowlist; Fetch Metadata cross-site rejection | Defaults assume the browser uses the configured local address and port |
| CSRF | Session-bound token on authenticated mutations; pre-auth challenge for login | Cookie `Secure` is false for local plain-HTTP loopback; do not use this design for a public deployment |
| Session secrets | Opaque random token in HttpOnly/SameSite=Strict cookie; only SHA-256 digest stored | No enterprise SSO, device management, or distributed session store |
| Password storage | Argon2id with fixed parameters; minimum 15-character passphrases; timing dummy hash | Operator-generated bootstrap credentials must be protected and rotated |
| Staff MFA | Terminal-delivered one-time code with expiry, source binding, and five-attempt cap | Terminal OTP is not a production authenticator or remote-safe MFA |
| Authorization | Explicit customer/reviewer/administrator dependency checks | All future routes must reuse the dependencies and receive role-specific tests |
| Consent | Version/hash binding, append-only decisions, idempotency key, current-consent gating, withdrawal | Consent text and retention assumptions require legal/privacy review before real data |
| Audit | HMAC-linked append-only audit events; chain check at application startup; read-only safe mode on detected tampering | The HMAC key and database are on the same host; an attacker with both may rewrite history |
| Input | Pydantic validation, bounded fields, JSON-only mutation requests, body-size cap | Review new endpoints for query complexity and resource exhaustion |
| Headers | CSP, frame denial, `nosniff`, referrer and permissions policies, no-store | Any new UI feature must remain compatible with restrictive CSP |
| Dependencies | Pinned Python and npm package versions; no CDN | Refresh pins and review advisories before an external release |
| Database privileges | Separate runtime DML account and migration account; launcher verifies both accounts and MySQL version | Validate SQL grants on an actual local MySQL installation |
| Setup automation | Launcher preserves `.env`, uses pinned dependencies, binds Docker MySQL to loopback, and asks before system installs | Review package-manager actions and secrets on each target OS |
| Path handling | Project assets resolve under the installed project root; runtime data paths may be redirected | Path registry is diagnostic only and must never be treated as executable trust configuration |
| Local model | Ollama loopback-only endpoint, installed manifest SHA-256 check, bounded prompts, fact validation and deterministic fallback | Model output remains untrusted; test each model/version and do not expose Ollama remotely |
| Learning workspace | Synthetic-only model training artifacts are checksummed and require human promotion | Do not enable self-modifying source code or auto-promote unvalidated models |

## Explicit non-goals

The implementation is not hardened for internet exposure, multi-tenant hosting, multiple workers, real customer data, utility integrations, production staff identity, billing decisions, theft determinations, or legally operative consent capture. The launcher is a local developer convenience, not an enterprise endpoint-management agent.

## Required before a real-data pilot

1. Independent security review and penetration test.
2. Formal privacy impact assessment, retention schedule, deletion rules, and reviewed consent text.
3. TLS and cookie design review if any non-loopback access is ever approved.
4. Secret-management and key-rotation design, audit-key separation, and tested encrypted backups.
5. Account lifecycle, recovery, staff offboarding, and production MFA.
6. Database migration, restore, least-privilege, and concurrency tests on supported MySQL versions.
7. Detection validation on representative consented field data with documented false-positive/false-negative rates and human review process.
8. Load, accessibility, browser compatibility, and operational monitoring tests.


## Gaps found in the 2026-11-03 re-audit

- **Automated graduated auto-lock is not implemented.** Request rate limiting and failed-login throttling exist; manual administrator safe-mode locking and startup audit-chain verification exist. The L1-L4 per-source escalation, cooldown, and persistent trigger design in `project-spec/references/security-hardening.md` is not complete.
- **Request-size cap updated.** `RequestBodyLimitMiddleware` now counts and bounds actual streamed bytes for state-changing API requests, including when `Content-Length` is absent or inaccurate; an isolated regression test covers this path. Verify it on the target ASGI server before any network exposure.
- **Periodic tamper verification is not implemented.** The application checks the audit chain at startup; it does not periodically verify code/config/model file hashes or comprehensively monitor protected-setting changes.
- **MySQL grants and transport binding are not verified on the target machine.** The review must be completed with the actual MySQL service and runtime/migration accounts.

These gaps are tracked in `docs/SKILL_INTEGRATION_AUDIT.md`. Do not claim automated auto-lock, full tamper detection, penetration testing, or production security.
