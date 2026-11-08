# Build guide (coding mode only for code)

Contents: 1 Principles; 2 Components; 3 Build order; 4 API in words; 5 Data layer and storage; 6 ML; 7 LLM; 8 Front end; 9 Errors; 10 Design for change; 11 Optimization

First apply the coding gate in SKILL.md. Before it is confirmed, use this guide to plan only.

## 1. Principles
- Inspect existing files before changing anything; never overwrite the team's work without reading it.
- Build a vertical slice first: simulated meter to chart, flag, and narrative on screen. Then widen.
- Keep the core logic (features, detection, fact sheet, validator) free of web and database code so it can be tested alone.
- Everything shown to a customer is computed from data; nothing is hardcoded. Settings live in one place.
- Prefer simple, reliable choices; add a component only when a current requirement needs it. Each extra service costs setup time.
- Explain each module and decision for student developers; they must be able to defend every part.
- Never put keys, passwords, or real data in source or the repository.

## 2. Components (from the proposal)
| Component | Job |
|---|---|
| Ingestion API | Accept and validate readings; reject bad data with a clear message |
| Time-series store | Hold intervals and rollups |
| Feature and rules pipeline | Compute features and theft signatures from past data |
| ML service | Isolation Forest and autoencoder scoring; asynchronous consumer |
| Alert service | Tiers, persistence, cooldown, audience routing |
| Fact-sheet builder and Storyteller | Build the sheet, produce and validate the narrative, fall back to templates |
| Portal | Customer screens (React) |
Slow models or the LLM must never block the portal from rendering.

## 3. Build order (exit evidence per slice)
The order follows the V2 development approach: architecture, database, authentication and consent, permissions and security tests, dashboard, anomaly detection, AI explanations, acceptance tests. Do not start feature slices (S6 and later) before S5 passes. Never sacrifice security to make a feature work.
| Slice | Content | Exit evidence |
|---|---|---|
| S0 | Architecture notes and threat model: module boundaries, settings, decisions logged, traceability table (project-brief.md section 7); documentation only | Accepted by the team; every V2 priority mapped to slices and tests |
| S1 | MySQL schema, constraints, tracked migrations, storage interface, backup and restore drill (appliances-and-mysql.md sections 8, 9, and 13) | Migrations build the schema from empty; schema-drift test passes; restore drill recorded |
| S2 | Synthetic generator with injected anomalies and labels; ingestion with validation and bound queries (security-hardening.md section 8) | Same seed gives identical data; labels present; bad rows rejected; reloading creates no duplicates |
| S3 | Login portal: accounts, sign-in, sign-out, sessions (login-portal.md) | Login tests pass; sessions expire; sign-out invalidates |
| S4 | Consent: submission, persistence, acceptance tracking, server-side enforcement (consent.md) | Consent tests pass in a fresh session, after a restart, and with every protection on |
| S5 | Authorization and request security: roles and permission matrix, CSRF, Origin, Host, request validation, rate limits, headers, auto-lock, audit log, integrity checks (security-hardening.md; login-portal.md section 8) | Permission and security test suites pass; lock drill passed; no feature work starts before this |
| S6 | Consumption calculations and summary tables (model-spec.md section 12) | Reconciliation tests pass; gaps shown, not filled |
| S7 | Landing route and portal screens with real data: Overview, Day Explorer, Alerts and Story shells (Heatmap if time allows) (prototype.md, design.md, experience.md) | Works at 360, 768, and 1280 px; every control works or is absent; numbers tie out; reduced motion and mute work |
| S8 | Appliances: registry with add, edit, retire or remove, impact preview, change history, effective-dated estimates, and outputs in every relevant tab (appliances-and-mysql.md) | Section 11 tests pass, including effective dating; changing an appliance changes the Breakdown, Overview, Story, and alerts |
| S9 | Features and detection following the complexity ladder in detection-methods.md (baseline and rules, Isolation Forest, one pattern model, calibration) | Detects injected anomalies on synthetic data; settings recorded; benchmark reported as synthetic |
| S10 | Alert tiers, persistence, cooldown, routing, and alert provenance; customer Alerts screen; mocked outbox; reviewer queue; safe-mode screen | No alert without provenance; theft signals stay internal; nothing is sent |
| S11 | Fact sheet, template narrative, validator, insight provenance (model-spec.md sections 5, 6, and 12) | Number-match cases pass; failing text falls back; every insight cites its fact sheet and coverage |
| S12 | Local LLM layer behind one interface, with grounding, validation, fallback, switches, and safety controls (llm.md) | Evaluation set run; LLM off and every failure case give template text; no customer free text reaches a prompt |
| S13 | Optimization pass: measure, tune, record (section 11; detection-methods.md section 6) | Baseline and after timings recorded; outputs identical; tuning runs saved |
| S14 | Integrate, UX completeness audit (quality.md section 8; experience.md section 8), acceptance tests, README, demo script | Acceptance list marked with evidence; no dead controls |
MVP means every slice; the customer-alert feedback loop is Optional unless the user asks. The app must work fully with the LLM off. Acceptance items map to slices in project-brief.md section 7.

## 4. API in words
Groups: readings in, anomalies and alerts out, fact sheet and story per period, customer feedback. Version the API. Validate every input. Return a consistent error shape with no stack traces or internal paths. Separate customer endpoints from internal ones (theft leads) and protect the internal ones. Keep contracts in one place.

## 5. Data layer and storage
Requirement (Brief v2, narrowed by v5): information is saved in a local database behind one storage interface; an online backend is possible later but is not built.
- One storage interface: a documented set of save and read operations for readings, alerts, fact sheets, narratives, feedback, settings versions, model runs, benchmark runs, and audit events. All other code uses only this interface, so the backend (local file, local server, online service) can change without touching the logic.
- One connection setting, read from an environment variable. No connection strings or credentials in source.
- Entities in words: meters (pseudonymous ID); appliances (appliances-and-mysql.md); readings (meter, interval start in UTC, kWh, quality flag); alerts; fact sheets (versioned); narratives (language, text, validator result, template or LLM, cached per period); feedback; settings versions; model runs (type, version, seed, settings); benchmark runs (synthetic, seed, metrics); audit events.
- Rules: parameterized queries only; schema changes through tracked migrations that apply cleanly from an empty database; a unique key on meter plus interval start so reloading data is idempotent; indexes on meter and time; transactions for multi-row writes; a reset-to-demo that restores simulated data; an export or backup of the demo database; tell the user when data is saved, reset, or deleted.
- Local mode only (decision 15): the database runs on the local machine and the app listens on localhost only. The storage interface keeps an online backend possible, but none is built or used; security-privacy.md section 10 applies only if the user changes the mode.
- Database: MySQL, local only (decision 12). The proposal's TimescaleDB features (hypertables, continuous aggregates) do not exist in MySQL; keep summary tables updated with ingestion instead. Schema, constraints, setup, and security rules are in appliances-and-mysql.md sections 8 and 9.
- Syncing between a local and an online database is Optional and complex; avoid it unless the user asks.
- If the database fails, show a friendly message and keep the app running from the last good data where possible.

## 6. ML
- Split data by time, never randomly; compute baselines from the past only (no leakage).
- Fix random seeds; save the model version and settings with every result.
- Keep thresholds in settings; log reason codes so every flag can be explained.
- Compare against a simple threshold baseline so the value of the models is measurable.
- Score in batches; keep scoring off the request path.

## 7. LLM
The LLM layer is specified once, in llm.md: local model only, grounded generation from the fact sheet, validation and fallback, safety controls, evaluation, and operations. Build it in S12 behind one interface; the app must work fully with the LLM off.

## 8. Front end
React with Recharts and Tailwind, mobile first. Follow the landing page and screens in prototype.md, with real routes, links, and buttons instead of the prototype's label technique. Flagged intervals use color plus shape or label. Every chart has a text alternative. Handle loading, empty, and error states. Keep logic out of components where practical. See design.md.

## 9. Errors
| Case | Behavior |
|---|---|
| Missing intervals | Flag gaps; do not fill silently; reduce confidence |
| Duplicate or out-of-order timestamps | Reject or reorder by documented rule, and log |
| Negative or impossible energy | Reject with the reason |
| Model or scoring failure | Keep the portal working; show the last good result with its time |
| LLM down or validator fails | Template narrative; no customer-facing error |
| Database down | Friendly message; no stack trace |
| Unknown meter | Reject; do not create silently |

## 10. Design for change
Keep tunable values (thresholds, persistence, cooldown, rounding rules, cold-start days, seed) in one settings place. Keep each module's inputs and outputs documented so a model or provider can be swapped. Keep tests as the executable specification: when a requirement changes on purpose, update the affected tests first, record why, then change the code. Prefer additive changes. Keep the Brief and changelog current.

## 11. Optimization (measure first)
- "Optimizable" means both speed and tunable accuracy by default (decision 13 in project-brief.md). Confirm the meaning with the user if it matters.
- Measure before changing anything. Record baseline timings (rows ingested per second, query time for one day and one month, scoring time per meter, narrative generation time, page load) with the machine and data size stated. Keep them in the changelog. Targets are Unknown until a baseline exists; set them with the user.
- Tactics, in order: read less data (time-range queries, pagination, indexes); batch writes; precomputed rollups such as daily and monthly summary tables updated with ingestion; cache narratives and stable results per period; score in batches off the request path; avoid recomputing features; downsample or paginate chart data for phones; load screens lazily.
- Change one thing at a time, rerun the same measurement, and keep the change only if it helps and the tests still pass.
- Correctness before speed: compare outputs before and after; they must be identical.
- Never claim speed or scale without measurements; label them with data size and machine.
- Detection tuning follows model-spec.md section 10.
