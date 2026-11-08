# Smart Meter Explorer V2.13 — Brief v11 experience update

A local-only smart-meter analytics demonstration. It uses **synthetic electricity readings only** and is not connected to Meralco, a utility, a real smart meter, billing systems, outage systems, or external notification providers.

## V2.13 intelligence and weather hardening

See `docs/INTELLIGENCE_AND_WEATHER.md` for calendar-aware anomaly intelligence, two-sided drift detection, forecast uncertainty, data-quality diagnostics, and optional GPS/weather context. See `docs/INTEGRATION_VERIFICATION.md` for the current verification boundaries.

## Brief v11 Pulse experience update

This revision retains the V2 backend, consent workflow, database design, and security controls while updating both browser interfaces to the Brief v11 experience requirements:

- Pulse identity across sign-in, home, navigation, and customer overview, including the 24-hour Pulse Ring.
- Keyboard-focusable hourly ring segments with text labels, a 24-row hourly table, and text/table alternatives for the weekly and heatmap visualizations.
- Optional Pulse enhancements are enabled by default on new installations and can be changed in Privacy & settings: Energy Ribbon, what-if appliance preview, shared transitions, scroll reveals, count-up metrics, haptics, and undo toast. Interface sounds start enabled at a low volume, but Web Audio is created/resumed only after a real user gesture; it never autoplays, has separate interaction/alert channels, is suspended while the tab is hidden, and is never the only confirmation.
- Transform/opacity-only interface motion with Reduce Motion and Calm Mode support. All optional motion features start enabled on a new installation, but system/app reduced-motion settings always take precedence; navigation keeps the app shell mounted and restores scroll/focus on screen changes.
- A persistent home shortcut, settings shortcut, sound control, and visible simulated-data label.

The offline fallback in `web/` is the runnable no-CDN interface. The optional React source in `frontend/` mirrors the same experience, including the Energy Ribbon on the overview and day explorer. Preferences are stored in the current browser; saved user choices override defaults. The React production bundle was not rebuilt in this environment because npm registry access timed out; see `docs/VALIDATION_LOG.md`.

## What is included

- Optional per-launch location consent and Open-Meteo weather context. Coordinates stay in page memory and are sent directly from the browser to the weather provider; they are not stored by this app. Temperature/usage comparison is exploratory, not causal. See `docs/INTELLIGENCE_AND_WEATHER.md` for details and limits.

- Customer workspace with a 7-day usage overview, 15-minute day explorer, 7-day usage heatmap, alerts, fact-based energy story, appliance estimates, and privacy controls.
- Customer consent flow with a versioned text hash, required analytics purpose, separately optional mock notification purposes, append-only decisions, request-ID idempotency, and withdrawal.
- Reviewer and administrator access. Staff login requires a one-time code printed to the local server terminal. Safe-mode unlock requires a different administrator to approve.
- Explainable pattern detection for spikes, sustained evening rises, gradual drift, sustained drops, night-floor changes, and communications gaps. Internal-only patterns stay out of the customer alert feed. Adaptive intelligence adds robust MAD baselines, EWMA, CUSUM, a candidate change-point scan, an explicitly assumption-based Bayesian evidence estimate, a transparent evidence score, and a short-range weekday-aware forecast.
- Optional local model scoring through scikit-learn. The primary explanations and energy-use suggestions are deterministic and tied to computed facts. A verified loopback-only Ollama model can optionally rephrase the energy story and suggestions; output is validated and falls back to templates. Ollama remains opt-in and requires a configured local endpoint and model SHA-256.
- A review-only synthetic learning workspace can train and checksum local ML artifacts under `var/learning/`. Artifacts are not automatically promoted or loaded into the live detector.
- MySQL storage for the application. SQLite is used only by the automated test suite.
- A no-CDN fallback browser interface in `web/`, plus React/Vite/Recharts/Tailwind source in `frontend/`. Core meter analysis works offline; optional weather context needs internet access.
- Alembic schema migration, bootstrap/demo seed, access controls, audit chain, security event log, API request IDs, and regression tests.

## System requirements

- Python 3.11 or newer.
- MySQL 8.0.16 or newer, running on the same computer. MySQL must support enforced `CHECK` constraints and JSON columns.
- Windows, macOS, or Linux.
- Optional for rebuilding the React interface: Node.js 22 and npm.

The default service binds to `127.0.0.1`; it is not designed to be exposed to a LAN or the public internet.

## One-file setup and launcher (recommended)

The recommended entry point is the root-level `launch.py`. It checks the computer before making changes, reuses existing software, and coordinates setup:

1. Detects the operating system, Python, Node/npm, MySQL, Docker Compose, Ollama, and required project files.
2. Creates `.venv` only if it is missing, then installs only Python packages whose exact pinned versions are missing or mismatched. Existing system Python packages are not changed.
3. Creates `.env` with a unique local secret only when `.env` does not already exist; existing credentials and settings are preserved.
4. Checks both MySQL application and migration accounts. If no server is running, it can offer to start a MySQL 8.4 container bound only to `127.0.0.1` when Docker Compose exists, or offer a native MySQL Server installation through a supported OS package manager. It creates separate least-privilege accounts and preserves database files. System software is never installed silently.
5. Detects Node.js 22+ and reuses installed React packages. If Node is missing, the launcher can offer a supported package-manager install where available. React is optional because the no-CDN `web/` interface works without Node.
6. Builds React when dependencies are available, runs Alembic/demo bootstrap, opens the local app, and keeps the server process attached to the launcher.

Run from the extracted project folder:

```bash
python launch.py
```

Windows users can also run `launch.py` from PowerShell using `py -3.11 launch.py`. The launcher asks before starting a Docker database or installing optional Node.js. Use `--yes` only if you approve starting the local Docker MySQL container automatically. Useful modes:

```bash
python launch.py --diagnose       # read-only system inspection
python launch.py --setup-only     # prepare dependencies/database, do not serve
python launch.py --no-react       # use the offline fallback even if Node is installed
python launch.py --skip-db        # diagnostics/dependency setup only; app cannot fully run
```

Logs are written to `.local/logs/launcher.log`; the generated path inventory is `.local/path-registry.json`. Runtime learning/model artifacts are stored under `var/learning/`. Both folders are excluded from version control. The path registry records installed tool paths and required project assets; source files are always resolved inside the project root, while only runtime data folders can be redirected with `SME_DATA_DIR`. The launcher never rewrites source code or security policy.

To train an isolated baseline artifact from generated data only:

```bash
python scripts/train_synthetic_baseline.py --confirm-synthetic-only
```

The script saves a versioned model, SHA-256 manifest, and synthetic holdout metrics under `var/learning/`. This is a review artifact, not an automatically promoted production model.

### Manual installation (alternative)

Requirements: Python 3.11+, MySQL 8.0.16+, and optionally Node.js 22+ with npm for the React build. Extract the project to a folder you control, then create the environment and install pinned dependencies:

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start MySQL, review `database/create_users.sql`, replace both placeholder passwords, and execute it as a MySQL administrator. Run `python scripts/create_env.py`, edit `.env` with the runtime and migration database URLs, then run:

```bash
python -m sme.cli bootstrap
python -m sme.cli serve
```

Open `http://127.0.0.1:8000/`. Do not expose the service to a LAN or public internet.

## Tests and verification

Run the repeatable verification suite from the project root while the Python environment is active:

```bash
python scripts/run_verification.py
```

This runs the backend/API tests, Python compilation, JavaScript syntax checks, the React JSX parser when TypeScript is available, the frontend animation/accessibility contract checks, an optional browser smoke test, and a small synthetic service microbenchmark. Results are written to `docs/VERIFICATION_REPORT.md`. To skip the optional browser smoke and benchmark:

```bash
python scripts/run_verification.py --skip-browser --skip-benchmark
```

The frontend experience checker and project path/asset auditor can also be run independently:

```bash
python scripts/verify_frontend_experience.py
python scripts/verify_project_paths.py
```

The experience check verifies CSS animation/transition properties, keyframe references, reduced-motion and Calm Mode behavior, all optional default-on settings, gesture-gated sound, Pulse Ring alternatives, focus styles, and mobile breakpoints. The path auditor checks local Markdown links, frontend imports, npm script paths, fallback assets, and API static-file wiring. From `frontend/`, the experience and path checks are also exposed as `npm run verify:experience` and `npm run verify:paths`.

For a real Chromium smoke test, install the optional browser dependency and browser binary:

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python scripts/browser_experience_smoke.py
```

The test server uses a temporary in-memory SQLite database and does not touch the configured MySQL database. A browser-policy block means the test is not verified, not that it passed.

The core test suite uses an in-memory SQLite database only for isolated automated tests. It does not replace the MySQL installation check. The synthetic service microbenchmark is CPU-only and does not model MySQL, HTTP, browser rendering, concurrency, or production workloads. Before a release, complete the pending MySQL/browser checks listed in `docs/ACCEPTANCE.md`.

## React interface (optional build step)

The project includes two local browser interfaces:

- **Fallback interface:** already provided in `web/`, requires no Node install, no external CDN, and no build step.
- **React interface:** source code in `frontend/`, with React, Recharts, Tailwind CSS, and Vite. Build it to `web/dist/` to make FastAPI serve it in place of the fallback.

To build the React interface when npm packages can be installed:

```bash
cd frontend
npm install
npm run build
cd ..
```

Then restart the Python server. The built interface is served from the same local origin as the API. The package lockfile should be generated and committed by the maintainer when npm install is performed in a network-enabled build environment.

The Vite development server is optional and not the recommended workflow. The default security allowlist is for the FastAPI origin on port 8000. If developing via Vite on port 5173, add only `http://127.0.0.1:5173` to `APP_ALLOWED_ORIGINS`; the provided Vite proxy rewrites the forwarded Host to the API loopback address. Keep the API bound to loopback. Do not disable Origin, Host, or CSRF checks to make the dev server work.

## Database commands

```bash
python -m sme.cli check       # validate configuration and connect to MySQL
python -m sme.cli migrate     # apply schema migrations
python -m sme.cli seed-demo   # seed demo data only if it does not already exist
```

Database backups are an operator responsibility. Before applying a new schema revision to any database with data, take and verify a backup. Never use the initial migration's downgrade operation on a database containing data; it drops the schema.

## Important limitations

- Every meter reading is generated and labeled by the demo generator. No real customer, utility, or smart-meter data is ingested.
- Detection benchmarks are measured against synthetic injected pattern labels. They are not evidence of real-world accuracy, fraud, theft, equipment failure, or billing correctness.
- Appliance energy allocation is an estimate from user-entered rated power and usage assumptions. A household meter does not measure each appliance separately.
- No SMS, push, email, payment, outage, restoration, or utility action is transmitted. Optional notifications create local mock records only.
- Staff access and terminal OTPs are for a single-computer demonstration, not enterprise identity management.
- The application has not undergone independent security testing, production penetration testing, formal privacy/legal review, or load testing. Do not deploy it for real customer data or decisions.

## Project layout

```text
sme/                 FastAPI application, data models, security, services
migrations/          Alembic schema migration
frontend/            React + Vite + Recharts + Tailwind source
web/                 Local browser app and fallback interface
scripts/              Environment setup, verification, browser smoke, and benchmark tools
database/             MySQL least-privilege user SQL
tests/                SQLite-backed automated tests
project-spec/         Uploaded project skill and source references
docs/                 Architecture, security, acceptance, validation
```

## Optional local LLM for stories and energy suggestions

The customer Energy Story includes fact-grounded suggestions. Deterministic templates always work. If Ollama and a local model are installed, configure them explicitly:

```bash
ollama list
python scripts/configure_local_llm.py
```

If no model is installed, run `ollama pull <model>` yourself, then rerun the configuration script. It computes the SHA-256 of the installed local model manifest and writes the verified model name/path/hash to `.env`. The app checks that hash before each local model call, only accepts loopback Ollama URLs, validates generated numbers against the computed fact sheet, and falls back to templates on any failure. No meter data is sent to a hosted LLM.

## Windows one-click dependency setup

For Windows 10/11, double-click `START-SME-WINDOWS.bat`. It detects the existing MySQL 8.4 installation, starts its service when configured, downloads and verifies Node.js LTS only when missing, installs missing React dependencies, builds the frontend, and then invokes the main launcher. See [Windows setup guide](docs/WINDOWS_SETUP.md).


## Project operating rules
The active project brief and complete Smart Meter Explorer build/security/quality skill are maintained in `project-spec/SKILL.md` and `project-spec/references/`. Read the skill before making project changes. The coding gate was confirmed by the user on 2026-11-03; detailed hackathon rules and event identity remain to be documented. Security protections, local-only mode, synthetic-data labeling, human review of theft leads, and test honesty are non-negotiable.
