# Changelog

## V2 — Project Brief v11 experience update (2026-11-03)

- Retained the V2 FastAPI/MySQL backend, authentication, consent, security controls, detection logic, and existing test suite.
- Completed the Pulse Ring visual on both the no-CDN fallback and React source: 24 hourly segments, dynamic scale, central daily total, 12 AM/6 AM/12 PM/6 PM anchors, accessible segment names, and hourly table.
- Added text summaries and explicit table views for the weekly, 15-minute day, heatmap, and hourly Pulse Ring visualizations. Zero-consumption hours now have zero-length ring segments. Heatmap cells use letters and values so status is not communicated by color alone.
- Added Web Audio interaction/alert tones, default-off behavior, local user preferences, volume control, separate sound channels, a persistent quick mute control for customer and internal roles, gesture-gated audio, and hidden-tab suspension. Mutation tones only follow the server response.
- Constrained interface motion to transform/opacity effects, with reduced-motion and Calm Mode overrides. The landing pulse-line draw uses scale/opacity only; loading skeleton animation is finite.
- Added persistent home navigation, visible active-page state, heading focus, scroll restoration, live status semantics, and stronger focus styling. The first-run sound dialog restores focus when dismissed, and safe-mode controls remain silent.
- Updated acceptance and experience-test documentation to identify browser-only work honestly.

## Verification caveats

- `pytest -q`: 23 passed (3 scikit-learn convergence warnings in a synthetic detector test).
- Python compilation, fallback JavaScript syntax, and TypeScript JSX parsing passed.
- npm package installation timed out while fetching the React package manifest because the registry connection returned `EAI_AGAIN`; no React production bundle was generated.
- Chromium browser navigation was blocked by the build environment policy (`ERR_BLOCKED_BY_ADMINISTRATOR`), so browser audio, responsive, focus, and reduced-motion interaction checks remain outstanding.
- MySQL deployment and backup/restore validation remain target-computer tasks.

## Verification hardening — 2026-11-03

- Added a repeatable frontend experience verifier for both the React source and no-CDN fallback, covering motion properties, keyframe integrity, reduced-motion/Calm Mode, optional audio controls, chart alternatives, keyboard focus, and mobile breakpoints.
- Added FastAPI tests confirming the fallback shell/assets are served with security headers and unknown assets return 404.
- Added an optional isolated Playwright/Chromium smoke script and documented its in-memory test server; it never connects to or mutates the configured MySQL database.
- Added a one-command verification runner and generated `docs/VERIFICATION_REPORT.md`.
- Removed a duplicate fallback `pulse-draw` keyframe.
- Replaced the slow iterative MLP reconstruction with a deterministic PCA linear autoencoder, reducing training time and removing convergence warnings while retaining complete-day-only training.


## Optional feature integration and code-path hardening (2026-11-03)

- Changed the agreed defaults for new installations: Pulse optional features, interface sound (low-volume), and haptics are enabled by default. Saved local preferences continue to override defaults. Reduce Motion and Calm Mode remain user/OS overrides.
- Made the Energy Ribbon available on both the React overview and day explorer, matching the no-CDN fallback.
- Fixed a fallback navigation race: the browser View Transitions API defers its update callback, while the fallback immediately binds controls. Fallback rendering is now synchronous and uses the preference-gated CSS screen-entry transition; React retains the native API with `flushSync`.
- Fixed React overview loading to wait for both overview and interval data before publishing the new page, avoiding a partial render with an empty Pulse Ring/Ribbon.
- Fixed React CountUpMetric to use explicit settings props instead of depending on parent `useEffect` timing, preventing default count-up effects from being skipped on first render and respecting Calm Mode/Reduce Motion.
- Fixed fallback requestAnimationFrame bookkeeping so completed count-up frames are removed instead of accumulating stale frame IDs.
- Added a path/asset audit for Markdown links, fallback assets, React entry points/imports, npm script paths, and API fallback routing.
- Expanded frontend experience verification to assert default-on options, Settings presence, Energy Ribbon coverage, gesture-gated audio, and synchronous fallback rendering.
- Fixed DELETE test calls to use raw JSON content, compatible with the installed Starlette TestClient.

## Launcher and learning workspace

- Added a single-file `launch.py` that detects host tools, creates/reuses `.venv`, installs only missing/mismatched pinned packages, preserves existing `.env`, verifies both MySQL roles, optionally provisions loopback-only Docker MySQL, builds React when available, bootstraps the schema, and starts the app.
- Added system diagnostics and a generated path registry. Project assets are resolved from the installed project root; only runtime data directories can be redirected.
- Added a synthetic-only, review-required model training workspace and fact-grounded local-LLM suggestions with deterministic fallback. Added a local Ollama setup helper that records the installed model manifest digest.
- Kept MySQL as the canonical appliance store; appliance versions and audit events preserve history rather than loose per-appliance text files.


## 2026-11-03 — Skill integration and coding gate
- Added an ASGI-level streamed request-body size cap (not dependent on `Content-Length`) and a regression test for oversized chunked input.
- Advanced detector version to `guardian-v2.2` for the calendar-contiguity correction.
- Corrected multi-day detector windows to require actual consecutive calendar dates and adequate daily coverage; added a regression test proving missing whole days do not create false persistence alerts.
- Added `docs/SKILL_INTEGRATION_AUDIT.md` with explicit implemented/partial/not-implemented findings, including the remaining auto-lock and tamper-detection gaps.
- Integrated the complete uploaded `smart-meter-explorer` skill as `project-spec/SKILL.md` and its 23 reference documents under `project-spec/references/`.
- Recorded the user's explicit confirmation that the hackathon organizers allow coding. Exact event identity and detailed rules remain Unknown until organizer evidence is attached.
- Updated the project Brief gate status and changelog; immutable security, privacy, honesty, local-only, and verification rules remain binding.
- Ran the existing Python/backend integration suite and static verification; see `docs/INTEGRATION_VERIFICATION.md`. Browser, MySQL, and actual Windows installer execution remain unverified in this environment.


## 2026-11-03 — Adaptive intelligence and weather context

- Added robust MAD household baselines, EWMA smoothing, one-sided CUSUM, chronological candidate change-point scan, an assumption-explicit Bayesian posterior, transparent evidence score, and weekday-aware short-range median forecast.
- Exposed adaptive intelligence through the customer overview API and dashboard.
- Added an explicit location-consent prompt on every authenticated customer app launch; location is requested only after a button press, held in page memory, and never posted to the backend or persisted by this app.
- Added optional Open-Meteo current/hourly weather context and exploratory temperature/usage comparison. Weather failures and denied location leave meter analytics operational.
- Updated detector version to `guardian-v2.3`; added regression and privacy-flow tests.
- NILM, grid graph/GNN, full Bayesian online change-point detection, and tariff/budget optimization remain unimplemented because the current data/configuration cannot support defensible outputs.

## 2026-11-04 — V2.13 deeper intelligence and weather hardening

- Reworked adaptive intelligence as `sme-intelligence-v2.0`: stricter daily-row validation, duplicate-date diagnostics, low-coverage exclusions, calendar-gap reporting, and contiguous-window baselines.
- Hardened candidate change-point detection to require calendar continuity across the entire pre/post comparison, not merely within each side.
- Added two-sided CUSUM with gap resets and pre-change reference calibration, plus standardized EWMA shift reporting.
- Added explicit ensemble components, direction-aware recommendations, data-quality diagnostics, and a clearly qualified empirical forecast-error envelope.
- Added Spearman rank correlation to the backend weather comparison and explicit confounder warnings.
- Hardened browser weather handling with coordinate bounds validation, full-day hourly coverage checks, temperature plausibility checks, exploratory cooling-degree-day context, and coarse GPS accuracy warnings. Coordinates remain browser-only and are not sent to the application backend.
- Added regression tests for calendar gaps, downward regime shifts, duplicate/non-finite input, and rank-correlation behavior.
- Verification: 59 backend/API tests passed; Python compilation, JavaScript syntax, frontend experience contract, and project path audit passed. The real browser smoke test remains blocked by the container's local-navigation policy; React production build and MySQL deployment remain unverified because required environment services/dependencies are unavailable.
