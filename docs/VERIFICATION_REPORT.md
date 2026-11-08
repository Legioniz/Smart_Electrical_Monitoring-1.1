# Verification report — Smart Meter Explorer V2 / Brief v11 + launcher/learning update

Run timestamp: 2026-11-03 04:28 UTC

This report distinguishes automated checks from environment-blocked checks. A blocked check is not a pass.

| Check | Result |
|---|---|
| Backend/API/regression suite | **PASS — 42 tests** |
| Python compilation | **PASS** |
| JavaScript syntax | **PASS** |
| React JSX syntax parse | **PASS** |
| Frontend animation/accessibility contract | **PASS** |
| Project path and required-file audit | **PASS — 21/21 required files** |
| Launcher read-only diagnostics | **PASS** |
| Launcher helper tests (DB URL decoding, grants, port allowlist, version gate) | **PASS** |
| Synthetic ML artifact generation | **PASS — review-only artifact generated** |
| Synthetic service benchmark | **PASS — detector median 810.021 ms** |
| React production bundle | **BLOCKED — npm install timed out** |
| Real Chromium browser smoke test | **BLOCKED — local browser navigation policy** |
| MySQL migration/persistence | **BLOCKED — no MySQL server, CLI, connector, or Docker in environment** |
| Live Ollama inference | **NOT RUN — Ollama/model unavailable** |

## Automated checks

### Backend/API/regression tests — PASS

Command: `python -m pytest -q`

Result: **42 passed**. Coverage includes authentication, consent, role checks, appliance versioning/restore, detector behavior, fact-grounded suggestions, Ollama manifest path/hash handling, launcher parsing, MySQL role grants/version gate, port allowlist alignment, and project path safety.

### Python and frontend syntax — PASS

- `python -m py_compile launch.py sme/paths.py sme/config.py sme/services/detection.py sme/services/narrative.py sme/main.py scripts/*.py tests/*.py`
- `node --check web/app.js`
- `node --check frontend/vite.config.js`
- TypeScript JSX parser accepted `frontend/src/App.jsx` and `frontend/src/main.jsx`.

### Frontend experience contract — PASS

Command: `python scripts/verify_frontend_experience.py`

- Animation/transition properties limited to transform and opacity.
- No duplicate or missing keyframes.
- OS reduced-motion and app Calm Mode wiring checked.
- Default-on optional settings and gesture-gated audio checked.
- Pulse Ring keyboard/text alternatives and chart tables checked.
- Mobile breakpoints and keyboard focus styles checked.

This is a source-level contract check, not rendered browser verification.

### Project paths and system inventory — PASS

Commands:

- `python scripts/verify_project_paths.py`
- `python scripts/path_registry.py`
- `python scripts/system_diagnostics.py`
- `python launch.py --diagnose`

All **21/21 required project files** were present. The path registry records absolute paths and tool discovery for diagnostics; it cannot redirect source imports or replace project files. Only runtime data directories may be redirected through `SME_DATA_DIR`.

### Synthetic ML workspace — PASS, not production-validated

Command: `python scripts/train_synthetic_baseline.py --confirm-synthetic-only --seed 20261103`

- 1,344 synthetic training rows across the first 14 days.
- 2,012 synthetic holdout rows across the remaining 21 days.
- 112 holdout rows flagged.
- Synthetic-label precision: **0.4107**.
- Synthetic-label recall: **0.0639**.
- Artifact SHA-256: `671f60d9e86de48ce6d30ea46af2f8b1189cff787c6a01072b04cd4ad14a77bf`.

The weak synthetic precision/recall means this artifact is **not approved for promotion**. It is stored only in the local `var/learning/` workspace and is not loaded by the running application.

### Synthetic service microbenchmark — PASS

Command: `python scripts/benchmark_services.py --runs 2 --output benchmarks/verification-benchmark.json`

35-day / 3,356-reading synthetic CPU-only run:

| Operation | Median |
|---|---:|
| Detector pipeline | 810.021 ms |
| Day interval payload | 0.561 ms |
| Appliance estimate breakdown | 0.077 ms |
| Deterministic narrative | 0.051 ms |
| Synthetic generation | 21.815 ms |

Two runs are a small smoke benchmark, not a load/performance claim.

## Blocked or unverified checks

### React production build — BLOCKED

Node.js 22.16.0 and npm were detected. `npm install --no-audit --no-fund` timed out while resolving the registry; no `node_modules` or partial lockfile was retained. React source parses, and the no-CDN fallback remains the runnable UI.

### Real browser — BLOCKED

`python scripts/browser_experience_smoke.py` returned `BROWSER SMOKE: BLOCKED — container browser policy prevented local page navigation`. Real animation, sound, haptic, focus, responsive, and screen-reader behavior must be tested on the target computer.

### MySQL — BLOCKED

No MySQL TCP listener, MySQL CLI, MySQL Connector/Python, or Docker Compose was available in this environment. The 42 tests use isolated in-memory SQLite through the test-only app factory. They do not verify MySQL 8.0.16+ migrations, grants, restart persistence, backup/restore, or concurrency.

### Ollama — NOT RUN

No Ollama executable or local model was available. The adapter is opt-in, loopback-only, checks the installed model manifest SHA-256, validates outputs against computed facts, and falls back to deterministic templates. Live model quality remains untested.

## Release assessment

The launcher, path inventory, offline UI, source-level frontend checks, and automated test suite are implemented and verified. This is **not production-ready**. Before calling the release complete, run the launcher on the target OS, verify the actual MySQL server and account grants, complete the React build/browser checks, and evaluate any selected local LLM model. Do not use real customer data or operational decisions until privacy, security, detection, and retention requirements are independently reviewed.

### Release archive verification — PASS

The final ZIP was extracted into a clean directory. From the extracted project root, `launch.py --diagnose`, `scripts/verify_project_paths.py`, `scripts/verify_frontend_experience.py`, Python compilation, and the full test suite all completed successfully (**42 passed**). The release archive contains no `.env`, virtual environment, generated local secrets, `.local/` path registry, `var/` model artifacts, `node_modules`, or generated React bundle.
