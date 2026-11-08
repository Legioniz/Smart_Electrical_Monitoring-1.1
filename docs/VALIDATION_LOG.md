# Validation log

Build: Smart Meter Explorer V2 — Brief v11 experience update

## Automated checks completed

Commands executed in the authoring environment:

```text
pytest -q
23 passed

python -m compileall -q sme scripts migrations
passed

node --check web/app.js
passed

node --check frontend/vite.config.js
passed

TypeScript transpileModule JSX parse of frontend/src/App.jsx and frontend/src/main.jsx
passed
```

The 23 tests use a fresh SQLAlchemy in-memory SQLite database for integration tests. SQLite is only a test adapter; it is not accepted as the configured runtime database. Coverage includes customer sign-in/password rotation/consent, consent idempotency and conflict behavior, withdrawal and re-consent, missing-CSRF and cross-origin rejection, staff OTP, role boundaries, safe mode and two-administrator approval, login throttling, audit-chain tamper detection, interval-gap handling, detector routing, appliance validation/estimates, narrative validation, and MySQL DDL engine/charset compilation.

A fixed-seed synthetic scenario test asserts that the six seeded pattern classes (spike, sustained evening rise, gradual drift, sudden sustained drop, night-floor collapse, and communications gap) all produce detector events. The internal-only night-floor pattern is checked for internal audience routing. This is a reproducible synthetic test, not evidence of real-world precision or recall.


## Brief v11 experience update validation

The v11 update adds the Pulse Ring to the customer overview, hourly energy labels and table alternative, weekly and heatmap table/text alternatives, persistent application-shell navigation, page focus and scroll restoration, optional Web Audio preferences, first-sign-in sound prompt, one-tap master mute, hidden-tab sound suspension, safe-mode visual-only feedback, and reduced-motion/Calm Mode behavior. The same experience layer is present in the no-CDN fallback and the optional React source.

Checks rerun for this update:

```text
python -m pytest -q
23 passed (3 warnings from the optional scikit-learn synthetic detector scenario)

python -m compileall -q sme scripts migrations
passed

node --check web/app.js
passed

node --check frontend/vite.config.js
passed

TypeScript JSX parser/transpiler check of frontend/src/App.jsx and frontend/src/main.jsx
passed

ZIP integrity
passed after final packaging
```

The pinned frontend dependency installation was attempted but npm registry access timed out with a network resolution error (`EAI_AGAIN`). No React production bundle was generated. An interactive Chromium smoke test was attempted, but the environment blocked navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`; no browser workflow is claimed as passed. The v11 experience checklist is in `docs/EXPERIENCE_TESTS.md`.

## Synthetic service microbenchmark

`scripts/benchmark_services.py` was run for two repetitions using 35 days of synthetic readings (3,356 stored intervals, fixed seed 20261031) in the authoring container (Python 3.13.5, Linux x86_64, 3 logical CPUs). The saved result is `benchmarks/service-benchmark.json`.

| Operation | Median | Runs |
|---|---:|---:|
| Synthetic generation | 11.690 ms | 2 |
| Detector pipeline | 651.769 ms | 2 |
| Day interval payload | 0.308 ms | 2 |
| Appliance estimate breakdown | 0.053 ms | 2 |
| Deterministic narrative | 0.048 ms | 2 |

This is a small CPU-only microbenchmark. It does not include MySQL, HTTP, browser rendering, concurrency, or end-to-end latency. It has no before/after optimization baseline and does not prove that an optimized implementation is equivalent to an unoptimized one.

## Not yet verified

- No local MySQL server was available in the authoring container. MySQL migration from empty, least-privilege grants, transaction behavior, restart persistence, schema drift, backup, and restore still need to be exercised on the target computer.
- npm package installation was unavailable. React/Vite/Recharts/Tailwind source is included and JSX parsing passed, but a production `web/dist` React bundle is not included. The same-origin no-CDN fallback UI in `web/` is the runnable interface once the API and MySQL are configured.
- Browser navigation was attempted with Chromium but blocked by the authoring environment (`ERR_BLOCKED_BY_ADMINISTRATOR`). Mobile/tablet/desktop layout, keyboard navigation, screen-reader behavior, color contrast, and full user journeys remain manual checks.
- No independent penetration test, formal privacy review, concurrency/load test, or representative field-data detector validation has been performed.
- The local Ollama adapter is optional and disabled by default. No model was installed or exercised. Full structured-output/source-field validation, circuit breaker, prompt-injection evaluation, model-hash verification against the actual model file, and LLM evaluation metrics remain incomplete.
- Automatic graduated/time-bound safe-mode triggers are not complete; safe mode is manually lockable and audit-chain tampering at startup is detected. A single-source lockout-isolation drill is not complete.
- Appliance version history is stored, but full effective-date impact calculations across all historical dashboard/story outputs and preview-versus-saved equivalence are not complete.

## Correct interpretation

Passing unit/API tests, syntax checks, and the synthetic microbenchmark proves only that selected code paths passed in the authoring environment. It does not prove that MySQL deployment, the optional React bundle, every browser workflow, automatic lock triggers, LLM behavior, or real-world anomaly accuracy has been verified. Consult `docs/ACCEPTANCE.md` before describing the project as complete or accepted against Brief v11.

## Full verification pass — 2026-11-03

Command: `python scripts/run_verification.py`

Results from this verification environment:

- `pytest -q`: **26 passed, 0 failed, 0 warnings**. This includes the pre-existing backend/authentication/consent/security/service tests, FastAPI static-shell/security-header checks, and the V11 frontend experience contract test.
- Python compilation: passed for `sme`, `scripts`, `migrations`, and `tests`.
- `node --check web/app.js` and `node --check frontend/vite.config.js`: passed.
- TypeScript `transpileModule` JSX parse: passed for `frontend/src/App.jsx` and `frontend/src/main.jsx`.
- Frontend experience contract: passed for both CSS/JS interfaces. The verifier rejects duplicate/missing keyframes, non-`transform`/`opacity` keyframe or transition properties, incomplete reduced-motion/Calm Mode wiring, missing sound guards, missing chart alternatives, missing focus styles, and missing mobile breakpoints.
- `web/styles.css`: removed a duplicate `pulse-draw` keyframe declaration discovered by the new verifier.
- Synthetic daily-profile reconstruction now uses a PCA linear autoencoder rather than iterative MLP training. It trains only on complete baseline days and scores complete holdout days; this avoids iterative convergence warnings and substantially reduces runtime.
- Synthetic service microbenchmark: rerun; results are in `benchmarks/verification-benchmark.json`. The benchmark remains CPU-only and is not an end-to-end performance result.

Blocked release checks (not passes):

- React production bundle: npm dependency installation timed out resolving the npm registry; Vite build could not run.
- Real browser/Chromium smoke: blocked by the execution environment's browser navigation policy (`ERR_BLOCKED_BY_ADMINISTRATOR`). `scripts/browser_experience_smoke.py` is included for execution on the target computer.
- MySQL migration/runtime: MySQL Connector/Python and MySQL CLI/server were unavailable here. SQLite was used only through the isolated automated test profile.
- Mobile and assistive-technology verification: responsive breakpoints and ARIA/focus source contracts were checked statically, but rendered browser and screen-reader checks remain outstanding.

The machine-readable/expanded check output is recorded in `docs/VERIFICATION_REPORT.md`.


## Follow-up settings integration and code audit — 2026-11-03

The optional Pulse experience settings are now enabled by default on a new browser installation and exposed individually in Privacy & settings. A previously saved browser preference intentionally overrides the new-install defaults. Sound preference is on at a low level, but Web Audio remains gesture-gated and never autoplays. Calm Mode temporarily suppresses motion, audio, and haptics without overwriting the saved per-feature values.

Additional code fixes: React page rendering now waits for all required page data; stale overlapping navigation requests cannot replace a newer page; Energy Ribbon is present on the React overview; count-up settings are passed explicitly to metric components; fallback painting is synchronous to avoid View Transition/event-binding races; audio resume errors and browser storage failures are handled; appliance restore stale-version requests reach the handler and return the intended HTTP 409; duplicate keyframes were removed.

The project path audit is available as `python scripts/verify_project_paths.py` and checks local Markdown links, required assets, frontend relative imports, npm script targets, Vite paths, and the FastAPI fallback mount.

Latest full test result: **29 passed**. Python compilation, fallback and Vite JavaScript syntax, React JSX parse, frontend animation/accessibility contract, and project path/asset audit passed. The latest detailed results and blocked release gates are in `docs/VERIFICATION_REPORT.md`.

The React production build remains blocked by npm registry access; real Chromium interaction remains blocked by browser policy; MySQL deployment checks remain blocked by the absence of a configured MySQL server/CLI/connector in the authoring environment. These are not counted as passes.


## One-file launcher and local learning additions

- Added `launch.py` with read-only diagnostics, Python virtual-environment reuse, exact-pinned dependency checks, safe `.env` preservation, dual MySQL-role verification, optional Docker Compose MySQL provisioning, optional Node/React build, migrations/demo bootstrap, and local server launch.
- Added `compose.yaml` with MySQL port bound to loopback only and a persistent named volume. Docker/system software is not installed silently.
- Added path registry and system diagnostics; path manifests are diagnostic only and cannot redirect or replace source code.
- Added synthetic-only review artifact training and a local learning workspace; no model artifact can self-promote or rewrite source files.
- Added validated local-LLM energy suggestions with deterministic templates as fallback.
- Appliance records remain in MySQL with version/audit history; loose per-appliance text files are not used as live state because they can diverge from the database.

- Added an Ollama setup helper that selects only an already-installed local model, computes its manifest digest, and writes the opt-in settings to `.env`. Inference now checks the actual manifest file against the configured digest before calling the loopback endpoint.

## Final launcher, learning, and suggestion verification — 2026-11-03

- Automated suite: **42 passed**. Added coverage for launcher requirement parsing, URL-encoded MySQL credentials, separate DB grants, MySQL version gate (rejects MariaDB/old MySQL), custom-port loopback allowlist alignment, project-root path escape rejection, Ollama manifest digest, safe LLM suggestion fallback, and customer story/recommendation API output.
- Python compilation passed for the launcher, application, migrations, scripts, and tests. Fallback JavaScript and Vite configuration syntax checks passed; React JSX parser passed for both source entry points.
- Frontend experience contract passed: transform/opacity-only motion, unique keyframes, reduced-motion/Calm Mode, default-on feature settings, gesture-gated audio, chart alternatives, focus styles, and mobile breakpoints.
- Project path audit passed. The generated registry found all **21/21** required project files and recorded Python/pip/Node/npm/MySQL/Docker/Ollama tool paths where present.
- The one-file `launch.py` now creates/reuses a virtual environment, installs only missing/mismatched pinned Python dependencies, preserves `.env`, detects existing MySQL clients/services before offering installation, can offer loopback-only Docker MySQL, checks both DB roles and MySQL 8.0.16+ compatibility, optionally builds React, bootstraps the schema, and starts the server. No system software is installed without confirmation.
- The PCA daily-profile reconstruction model replaced the slow iterative MLP reconstruction. Latest two-run synthetic detector median: **810.021 ms**. This benchmark is CPU-only and not a production load test.
- Synthetic-only learning artifact training completed. The holdout precision/recall were 0.4107/0.0639; the artifact is explicitly review-only and must not be promoted. No customer data is used by the offline training script.
- Energy story now includes fact-grounded suggestions. Deterministic templates are always available; optional local Ollama can phrase suggestions only after loopback endpoint and installed manifest SHA-256 checks. No live Ollama model was available here.
- React `npm install` timed out; production bundle remains blocked. Chromium smoke test was blocked by the environment's browser-navigation policy. MySQL deployment was blocked because no MySQL server, CLI, connector, or Docker was available. These are not passes.
