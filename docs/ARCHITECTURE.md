# Architecture and request flows

## Deployment boundary

The API and UI are served from one local FastAPI process bound to `127.0.0.1`. Static assets are local files; no remote script, analytics, fonts, or image CDN is used. The application database is MySQL. Automated tests use an isolated in-memory SQLite database through the test-only app factory.

## Components

- `launch.py`: single-file, cross-platform setup/diagnostics/launcher; reuses existing tools, provisions MySQL only after approval, and coordinates the local app startup.
- `sme/paths.py`: central project-root and runtime-data path resolver. Project assets cannot escape the install root; only runtime data paths are configurable.
- `sme/main.py`: route handlers, role checks, request middleware, error mapping, static file hosting.
- `sme/security.py`: Argon2id password hashes, session token hashing, CSRF validation, HMAC audit-chain writing and verification, one-time challenges, and rate limiter.
- `sme/models.py`: SQLAlchemy schema.
- `sme/services/analytics.py`: Manila-time date boundaries, coverage-aware daily/interval series, and fact sheets.
- `sme/services/detection.py`: deterministic pattern rules plus optional scikit-learn scoring.
- `sme/services/intelligence.py`: robust MAD baseline, EWMA, CUSUM, candidate regime-change scan, assumption-explicit Bayesian evidence estimate, ensemble evidence score, and short-range weekday-aware forecast.
- `sme/services/appliances.py`: input validation and appliance usage estimates.
- `sme/services/narrative.py`: bounded deterministic explanations and fact-validated local Ollama story/suggestion adapter with manifest-hash verification.
- `scripts/path_registry.py` and `scripts/system_diagnostics.py`: local inventory of required files and installed support tools; the registry is diagnostic, not executable configuration.
- `scripts/train_synthetic_baseline.py`: isolated synthetic-only ML training with checksummed, review-required artifacts under `var/learning/`.
- `migrations/`: Alembic migration configuration and initial schema.
- `web/`: same-origin no-CDN fallback UI.
- `frontend/`: optional React source to build into `web/dist/`.

## Authentication

1. The browser requests `/api/auth/preflight`; the server creates a short-lived pre-auth challenge and CSRF token and sets an HttpOnly, SameSite=Strict pre-auth cookie.
2. Customer password authentication consumes the pre-auth challenge. Staff authentication first validates username/password, then creates a one-time code printed only in the local server terminal; verification consumes the pre-auth challenge.
3. The server creates a random opaque session token, stores only its SHA-256 digest, and sets the raw token in an HttpOnly, SameSite=Strict cookie. Session records include role, source hash, CSRF token, idle/absolute expiry timestamps.
4. A new account must change its generated temporary passphrase. Password change rotates the session and CSRF token.
5. Staff actions additionally require the relevant role. Safe-mode unlock requires a different active administrator's approval and OTP.

## Consent

- The consent notice has a version and SHA-256 digest. The browser submits the version, a UUID request ID, the required analytics decision, and independent optional mock-channel decisions.
- The required purpose must be granted to access customer analytics. Notification preferences do not activate an external notification provider.
- Each purpose decision is stored as an append-only record. A uniqueness constraint on account, purpose, and request ID prevents duplicate decisions. A reused request ID with different values returns a conflict.
- Repeated same-request submissions are idempotent. Withdrawal appends `withdrawn` decisions and blocks analytics on the next protected request.
- Consent reads are available to an authenticated customer even when no current consent exists. Customer analytics routes enforce current consent. Staff cannot submit customer consent.

## Request protections

- Request Host is allowlisted; the default allowlist contains loopback hosts only.
- Mutating `/api/` requests require an allowlisted Origin, or a same-origin Referer fallback, and same-origin Fetch Metadata when supplied.
- Mutating requests must be JSON and are subject to a body-size limit.
- Session-changing actions require the session CSRF token. Authentication endpoints use their one-time pre-auth CSRF challenge.
- Response headers include CSP, frame denial, `nosniff`, referrer policy, permissions policy, cache-control, and a request ID. Same-origin geolocation is allowed only after the customer explicitly chooses it; CSP permits the Open-Meteo weather API as an optional external connection.
- API errors use stable error codes and request IDs. Security failures are stored as source-hashed security events when the database is available.

## Analytics and model boundaries

- The demo generator produces 35 days of 15-minute readings and synthetic labels, with an intentionally omitted communication-gap window.
- Missing or invalid readings are excluded from totals and coverage calculations; they are not imputed as zero.
- Pattern rules have human-readable reasons and distinguish customer-facing alerts from internal-only review leads.
- Isolation Forest and a daily profile reconstruction model are supplementary scores. The daily model trains/scores only complete days; gaps are not filled with fabricated zeros.
- The synthetic benchmark is a controlled demonstration using generated labels. It is not a validation study and must not be described as field accuracy.
- Customer stories and suggestions use computed facts and deterministic templates by default. Optional local Ollama is disabled by default; `scripts/configure_local_llm.py` selects an installed local model and records its local manifest SHA-256. Model output is validated and falls back to templates.
- The daily reconstruction detector is a PCA linear autoencoder trained only on complete days, avoiding iterative MLP convergence and never filling missing intervals with zeros.
- Learning artifacts are synthetic-only by default, checksummed, versioned, and not auto-promoted. Runtime code cannot rewrite its own source, security policy, migrations, or dependencies.

## Data lifecycle and deletion

The customer export endpoint returns that customer's account metadata, meter readings, alerts, appliance records, and consent status. The sample-data deletion endpoint removes simulated readings, alerts, story/fact-sheet, and appliance records while retaining the account and consent history for this demonstration. Audit history remains append-only in ordinary flows. Database administrators remain responsible for database backup and secure media deletion.

## Optional weather enrichment and adaptive intelligence

See `docs/INTELLIGENCE_AND_WEATHER.md` for algorithms, assumptions, privacy boundaries, and intentionally unimplemented data-dependent methods. Location coordinates are handled client-side and are not persisted or sent to the FastAPI backend. Weather context never changes security/theft alert severity.
