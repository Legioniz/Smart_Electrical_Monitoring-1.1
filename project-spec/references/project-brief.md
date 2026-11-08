# Project Brief v11: Smart Meter Data Explorer

Derived from the uploaded 10-page proposal (titled "Meralco Hackathon 2025 Proposal", marked Confidential Draft). Facts about the problem owner and Meralco's meter count are the proposal's own statements and are not verified here.

Contents: 1 Brief; 2 MVP slice; 3 Acceptance criteria; 4 Open decisions; 5 Team and roadmap; 6 Gate status; 7 V2 priorities and traceability; 8 Changelog

## 1. Brief
| Field | Value |
|---|---|
| Name | Smart Meter Data Explorer |
| Purpose | Turn 15-minute smart-meter readings into plain-language insight for customers, while an ML layer flags abnormal consumption, appliance faults, and possible illegal tapping for human review |
| Problem owner (per proposal) | Meralco, Customer Care and AMI |
| Users | Customers (mobile first); reviewers (review theft leads); administrators (safe mode and protected settings) |
| Modules | A Explorer (charts, heatmap, comparisons); B Guardian (anomaly and theft-signature detection); C Storyteller (fact sheet to narrative, with validation and fallback) |
| Stack (per proposal; database changed to MySQL by the user) | React, Recharts, Tailwind CSS; Python, FastAPI; MySQL (local server); scikit-learn, Isolation Forest, autoencoder; a local LLM behind one interface (LangChain optional); Docker, REST, webhooks |
| Data | Simulated only, 15-minute intervals (96 per day); real data only with written authorization |
| Storage (v2) | A database saves readings, alerts, fact sheets, narratives, feedback, settings, and run results. It is a local MySQL database (decisions 12, 15, and 17); the storage interface keeps an online option possible later, but none is built |
| Optimization (v2) | Optimizable in two ways: performance (measured, then tuned) and tunable detection settings (benchmarked on synthetic data) |
| Languages | English; Filipino variant from one template set |
| Devices | Mobile first (readable at 360 px), tablet, desktop |
| Delivery | Phase P0 MVP: one simulated meter, Explorer plus Guardian plus Storyteller, working end to end |
| Rules | Immutable core in SKILL.md; theft leads never reach customers; facts before language |
| Prototype | A static, clickable design prototype exists (references/prototype.md); it is a design reference, not the working app |
| Security (v4) | Layered protection: connection security, firewall rules, request filtering, DNS and bot defenses where possible, bound SQL queries, and an auto-lock safe mode on unusual activity or manipulation (references/security-hardening.md) |
| Accounts (v7) | A login portal with User and Admin sign-in; roles customer, reviewer, and administrator; sessions; a second step for internal accounts (references/login-portal.md) |
| Experience (v11) | Identity "Pulse": a signature ring chart, animations on interactions, and optional sound effects; motion follows reduced-motion settings and sound is user-controlled (references/experience.md) |
| Rule (V2) | Never sacrifice security to make a feature work; when a protection blocks a feature, fix the root cause instead of disabling the protection |
| Appliances (v6) | Customers add, edit, and delete their own appliances; the entries feed the Breakdown, Overview, Day Explorer, Alerts, and Story outputs (references/appliances-and-mysql.md) |
| Mode (v5) | Local mode only: the app runs on the team's own machine, listens on localhost, needs no internet, and has no hosted link, online database, or hosted LLM; the demo runs on a laptop with a backup copy on a second device |
| Version | v11 (history in section 8) |

## 2. MVP slice (P0, per the proposal: 48 hours, one simulated meter)
In scope: synthetic meter generator with injected anomalies; persistent local MySQL store behind one storage interface; appliance add, edit, and delete with estimates feeding every relevant tab; a local LLM layer that phrases validated insights (the app works fully with it off); an optimization pass with recorded timings and saved tuning runs; the security layer (bound queries, validation, rate limits, headers, firewall rules, auto-lock, tamper checks); features; point and pattern detection; alert tiers with persistence and cooldown; fact sheet; template narrative with validator; a landing page, a login portal for user and admin, and portal screens for Dashboard, Day Explorer, Alerts Inbox, Monthly Story (Heatmap if time allows; the Breakdown comes with appliances), following prototype.md; in-app alerts only.
Out of scope (proposal phases P1 and later, or local mode): real meters, real SMS or push delivery, fleet-wide scoring, real weather feeds, a hosted link, an online database, and a hosted LLM provider.
Built as local screens: first-run consent, notification settings, safe-mode screen, admin sign-in, and review queue with roles. Mocked and labeled: notification delivery (recorded in a local outbox as not sent), neighbor cohort, weather.

## 3. Acceptance criteria (MVP; each needs evidence)
1. The portal shows a 15-minute chart with flagged intervals and a plain-language reason.
2. Each injected anomaly type is detected on synthetic data (spike, sustained evening rise, gradual drift, sudden sustained drop, night-floor collapse, communication gap), with results reported honestly.
3. Alert tiers INFO, WATCH, CRITICAL follow the documented rules; persistence and cooldown work.
4. A fact sheet is built from computed values only.
5. The narrative passes number-match validation; a failing narrative falls back to the template.
6. With the LLM switched off, the portal still shows a template narrative and no error.
7. Theft-related signals never appear in customer-facing text.
8. Everything is labeled simulated; metrics from synthetic data are labeled synthetic.
9. The portal works at 360, 768, and 1280 px, with text alternatives for charts and red never the only signal.
10. Tests were run and results reported; README and setup commands were actually run.
11. No keys or real data in the repository.
12. A demo script exists and was rehearsed.
13. Data is saved in a database behind one storage interface; the app restarts with its data intact; reloading the same readings creates no duplicates.
14. The app runs entirely on the local machine with no internet; the storage interface keeps a future online backend possible, but none is built or used.
15. Baseline and after timings for the main operations are recorded with the machine and data size, and optimized results are identical to the unoptimized ones.
16. Detection settings are tuned on a time-split synthetic benchmark, versioned, and every run is saved; results are labeled synthetic.
17. A landing page opens first with the value proposition, a way into the portal, and the sample-data disclaimer; no unbuilt feature is described as available.
18. All portal screens are reachable from the navigation, and Back to home returns to the landing page.
19. Sample numbers on every screen tie out as in prototype.md section 5, and color contrast meets the stated ratios.
20. Every database query uses bound parameters; the runtime database user cannot change the schema; hostile-looking input changes no data and leaks no errors (tested on our own app).
21. API requests are validated, size limited, and rate limited with a clear throttle response; security headers and restricted cross-origin access are set.
22. The app listens on localhost only by default; nothing is exposed beyond the machine without the user's approval, TLS or an isolated network, and a decision-log entry; the database is not reachable from outside; the OS firewall is on; DNS, edge, and hosting protections are labeled not applicable in local mode and not claimed.
23. Unusual activity triggers graduated, time-bound responses up to a read-only safe mode; an authenticated admin can unlock it; lock state survives restart; one source cannot lock out others; the lock drill passed.
24. Integrity failures and unauthorized changes to protected settings are detected, logged, and trigger safe mode; all claims say layered defenses and not penetration-tested.
25. A first-run consent screen records the customer's choices before analytics are shown; notification settings gate delivery; delivery is mocked and labeled not sent; Settings offers withdraw consent, download, and delete for simulated data.
26. A retention and deletion approach is documented (security-privacy.md section 11); reset and delete work on simulated data; no real retention period is claimed.
27. Admin views (review queue, protection status, safe-mode unlock) require sign-in with the second step; a reviewer can view and mark leads but cannot unlock safe mode or change protected settings; only an administrator can, with a second approving administrator; demo credentials are labeled sample; the customer app has no path to admin views or lead text.
28. A customer can add, edit, and delete their own appliances with validation; delete asks for confirmation; every change is saved in MySQL and audited.
29. Appliance changes update the Breakdown, Overview, Day Explorer, Alerts, and Story outputs; with no appliances each tab shows a clear empty state; numbers tie out as in appliances-and-mysql.md section 4.
30. Declared appliances never change theft-lead criteria or admin leads; customer-facing text uses fixed category labels only, never free-text names or notes.
31. Data is stored in a local MySQL database following appliances-and-mysql.md sections 8 and 9: InnoDB, utf8mb4, bound queries, a least-privilege app user, localhost-only access; migrations apply from empty; backup and restore are tested.
32. Appliance data is covered by consent, export, deletion, and the retention table; "Delete my sample data and appliances" removes it.
33. A login portal offers User and Admin sign-in; unauthenticated requests reach only the landing and sign-in pages; every other route needs a valid session; roles are enforced on the server.
34. Passwords are stored as salted slow hashes; sign-in errors are generic; throttling and temporary lockout follow login-portal.md; Admin sign-in needs a second step; sessions expire and sign-out invalidates them.
35. Sign-in events are audited without passwords; repeated failures feed the auto-lock triggers; sample accounts are labeled sample and deleted after the event.
36. Consent submission works through the normal protected request path with no protection disabled; each decision is persisted with the text version, purposes, time, and account; it survives restarts and new sessions; analytics stay blocked until consent is recorded; withdrawal stops processing.
37. CSRF, Origin, Host, and request validation are enforced on every state-changing request; failures return a clear error and a log entry; no protection is disabled to make a feature work.
38. A permission matrix for customer, reviewer, and administrator is enforced on the server and covered by automated tests, including denial cases.
39. One migration history builds the schema from an empty database; the schema-drift test passes; backups are taken and a restore drill is recorded.
40. Daily, weekly, and period totals reconcile with the interval readings; gaps are shown and never filled; every chart uses the same numbers as the tiles.
41. Alerts come only from the detection pipeline run on stored readings, with provenance (detector and settings version, features, score, threshold, window); none is inserted by hand outside labeled sample data.
42. Every insight and narrative cites its fact sheet and data coverage; with insufficient data the app says so.
43. Every critical workflow in quality.md section 8 has automated tests that were run.
44. No dead controls: every button and link works, or is absent or disabled with a visible reason; every route is reachable; keyboard and screen-reader checks pass; 404 and error pages exist.
45. Appliance details are effective-dated: an update changes estimates only from its effective date; retiring keeps past periods and removing by mistake erases them; the impact preview equals the saved result; the change history lists each change.
46. A local LLM phrases insights from the fact sheet; no hosted API or cloud-model variant is used; the runtime listens on loopback only.
47. Every LLM text shown passed the validator (schema, numbers matched to cited fields, forbidden terms, length, language); failed text is never shown; the template fallback appears with no error; the LLM-off setting and circuit breaker work.
48. No customer free text (appliance names, notes) or identifiers reach a prompt; model output is escaped, never executed, and never used in queries.
49. Each narrative records the model name and hash, runtime and prompt versions, settings, fact-sheet ID, validator result, and latency.
50. The LLM evaluation set is run and reported (validator pass rate, faithfulness, forbidden terms, fallback rate, latency), labeled synthetic; the LLM stays on only if it meets the faithfulness bar the team set.
51. One design identity (Pulse) is applied to every screen using the tokens in prototype.md; every novel visual has a table or text alternative.
52. Motion follows experience.md section 4: transform and opacity only, durations in range, nothing blocks input, nothing flashes more than three times a second, no auto-start motion over 5 seconds without a pause control; with reduced motion on, nothing moves and all content and states stay visible.
53. Interface sounds are optional and user-controlled: off until enabled (or as decision 20 sets), started only after a user gesture, with always-reachable mute and volume, no autoplay, no sound over 3 seconds, no information carried by sound alone, and no sound while the tab is hidden.
54. Animations and sounds never delay or replace confirmation: consent, sign-in, deletion, and security actions show success only after the server confirms.
55. Every chart has a table view and a text summary; the Pulse Ring works by keyboard and screen reader.
56. The experience tests in experience.md section 8 were run, including reduced motion, mute, and input during animation.
Mark each Met, Not met, or Not yet tested. Never claim completion with any item unmarked.

## 4. Open decisions
| # | Decision | Options | Recommended |
|---|---|---|---|
| 1 | Event and rules that apply | Meralco Hackathon 2025, IDOL Hackathon 2026, other | Ask organizers; unknown now |
| 2 | MVP stack weight | A as proposed (React, FastAPI, with a database server); B React and FastAPI with a simpler store for MVP; C Python-only web app | B if time is tight, A if the team wants the full proposed architecture (with MySQL as the database); keep the proposal's design either way |
| 3 | Autoencoder implementation | scikit-learn-based; PyTorch; Keras | The one the team can explain; suitability of a scikit-learn approach is Likely but unverified |
| 4 | Narrative engine for MVP | Template only; LLM plus template; LLM only | Decided: LLM plus template (user, 2026-10-30): a local model phrases the fact sheet, the validator checks it, templates are the fallback |
| 5 | LLM hosting | Hosted API; local model; none | Local model only; hosted APIs and cloud-model variants are out of scope in local mode |
| 6 | Weather | Simulated; real feed | Simulated, labeled |
| 7 | Appliance breakdown | Skip; estimated from simulator shares; real disaggregation | Skip or "estimated" label; do not claim disaggregation |
| 8 | Projected bill | Skip; use a user-supplied tariff | Skip unless a tariff is supplied and labeled |
| 9 | Filipino text | English only; Filipino templates | Filipino templates reviewed by a fluent speaker |
| 10 | Hosting | Local containers; hosted | Decided: local only (user, 2026-10-27); hosting is out of scope |
| 11 | Demo length and judging criteria | Unknown | Ask organizers |
| 12 | Database | MySQL on the local machine (chosen); other local or online databases are not used | Decided: MySQL, local only (user, 2026-10-27), behind the storage interface; no online backend is built |
| 13 | Meaning of "optimizable" | Speed and resource use; tunable detection accuracy; both | Both, measured; targets are Unknown until a baseline exists |
| 14 | Next prototype additions | Keep the current screens plus landing; add a consent screen; add sign-in; add an internal ops view | Decided: add the consent screen, notification settings, safe-mode screen, and admin sign-in with a review queue (user, 2026-10-27); other items only on request |
| 15 | Exposure for the demo | Local only; local network or hotspot; hosted behind a provider's edge, firewall, and DNS | Decided: local only (user, 2026-10-27) |
| 16 | Auto-lock strictness and unlock policy | Strict early locks; graduated and time-bound; manual only | Graduated and time-bound with authenticated administrator unlock; thresholds tuned in rehearsal |
| 17 | MySQL version, connector library, and ID type | Current supported MySQL release (8.0.16 or later for enforced CHECK constraints); a maintained connector with bound parameters; integer or UUID IDs | Unknown until the team chooses; verify against the docs and the hackathon rules on installing software |
| 18 | Admin sign-in placement and second factor | Single portal with User and Admin tabs; a separate unlinked admin route; one-time code on the host console; authenticator-app code | Single portal with two tabs as requested; one-time code on the console for the demo; revisit before any real use (library Unknown) |
| 19 | Local LLM runtime and model | Ollama; a llama.cpp server; another local runtime | Unknown until hardware and the rules are known; choose by license, memory fit, structured-output support, and tested faithfulness; pin the exact version and hash; never a cloud-model variant |
| 20 | Default state of interface sounds | Off until enabled; on at low volume after the first gesture; asked once at first run | Asked once after first sign-in, default off, mute always reachable; the user may choose on-by-default |

Decided by the user: 4 (LLM plus template), 10, 12 (MySQL, local), 14, 15, and the single login portal for user and admin (change C8). Decision 5 follows from local mode (local model only). All others are recommended defaults, not yet confirmed.

## 5. Team and roadmap
Roles in the proposal: Team Lead and PM; ML Engineer; Backend Engineer; Frontend Engineer; LLM and Prompt Engineer. Actual team size is Unknown; ask.
Roadmap targets in the proposal (not commitments): P0 MVP at the hackathon; P1 pilot of about 1,000 meters; P2 about 1M meters; P3 about 12M meters.

## 6. Gate status
Coding permission: **user-confirmed** on 2026-11-03 (the user explicitly stated that the hackathon organizers confirmed coding is allowed). The exact event name, ruleset version, permitted external services, submission deadline, and written organizer evidence are not attached here; treat those details as **Unknown** until recorded. Coding mode is enabled on the user's confirmation; immutable safety, privacy, honesty, and verification rules remain in force.

## 7. V2 priorities and traceability
Rule for V2: never sacrifice security to make a feature work. For example, do not disable CSRF protection to fix consent submission; fix the session or token validation instead.
| # | Priority | Required improvement | Acceptance items | Slices |
|---|---|---|---|---|
| 1 | Consent system | Reliable consent submission, session persistence, acceptance tracking | 25, 36 | S4 |
| 2 | Authentication | Proper login, logout, session management | 33 to 35 | S3 |
| 3 | Authorization | Clear customer, reviewer, and administrator permissions | 27, 38 | S5 |
| 4 | Security | Correct CSRF, Origin, Host, and request validation | 20 to 24, 37 | S5 |
| 5 | Database | Consistent schema, migrations, backups, recovery | 13, 31, 39 | S1, S2 |
| 6 | Dashboard | Accurate consumption calculations and visualizations | 1, 29, 40, 45 | S6 to S8 |
| 7 | Anomaly detection | Working detection logic, not fabricated alerts | 2, 3, 41 | S9, S10 |
| 8 | AI integration | Explainable insights based on actual meter readings | 4 to 6, 42, 46 to 50 | S11, S12 |
| 9 | Testing | Automated tests for every critical workflow | 10, 43 | all (quality.md section 8) |
| 10 | User experience | No dead buttons, broken navigation, or inaccessible pages; a unique, friendly look with optional motion and sound | 9, 18, 44, 51 to 56 | S7, S14 |
Development order: architecture, database, authentication and consent, permissions and security tests, dashboard, anomaly detection, AI explanations, acceptance tests (delivery.md section 1). Advanced methods are allowed when they earn their place (detection-methods.md).

## 8. Changelog
| ID | Date | User instruction (short) | Class | Sections touched | Status |
|---|---|---|---|---|---|
| C1 | 2026-10-25 | The system should be optimizable and have a database for saving information, local or online | C2 | Brief, build.md sections 5 and 11, model-spec.md section 10, security-privacy.md section 10, deployment.md section 9, quality.md, delivery.md | Plan only; no code (coding unconfirmed) |
| C2 | 2026-10-27 | Make the prototype look functional, with all tabs viewable, static, no complex backend | C2 | design.md, prototype.md | Design prototype published; not opened or tested by Claude |
| C3 | 2026-10-27 | Redesign everything and add a landing page | C3 | design.md, prototype.md, Brief | Design prototype republished; not opened or tested by Claude |
| C4 | 2026-10-27 | Add the prototype work to the skill | C1 | prototype.md, design.md, quality.md, delivery.md, build.md, honesty-and-docs.md | Contrast measured; tie-outs fixed (hourly values now sum to Friday's 19.9) |
| C5 | 2026-10-27 | Add connection security, firewall, DNS, bot and SQL attack filtering, and auto-lock on unusual activity or manipulation | C3 | security-hardening.md, Brief v4, build.md, delivery.md, quality.md, foolproof.md, honesty-and-docs.md | Plan only; guidance checked against OWASP and DNS security sources on 2026-10-27; no code |
| C6 | 2026-10-27 | Local mode only, then add the rest (consent, settings, safe-mode, admin screens, notification delivery, retention, access control) | C3 | Brief v5, prototype.md, security-hardening.md sections 16 and 17, security-privacy.md section 11, model-spec.md section 11, build.md, delivery.md, deployment.md, foolproof.md | Plan and design prototype updated; no code; prototype not opened by Claude |
| C7 | 2026-10-28 | Add MySQL and let customers add, update, and delete appliances, with the data adjusting every relevant tab | C3 | appliances-and-mysql.md, Brief v6, build.md, prototype.md, delivery.md, security-privacy.md, security-hardening.md, quality.md, foolproof.md, deployment.md | Plan and prototype updated; MySQL facts checked against MySQL documentation on 2026-10-27; no code |
| C8 | 2026-10-28 | Remove the archived earlier project; add a login portal for user and admin | C3 | login-portal.md, Brief v7, build.md, prototype.md, security-hardening.md, quality.md, foolproof.md | Plan and prototype updated; password and session guidance checked against OWASP on 2026-10-28; no code |
| C9 | 2026-10-28 | Remove redundancy across guides; keep the app strict | C1 | change-management.md, delivery.md, security-privacy.md, security-hardening.md, foolproof.md | Duplicates replaced by single sources and pointers |
| C10 | 2026-10-30 | V2 priorities, development order, three roles, one rule: never sacrifice security to make a feature work; advanced methods allowed | C3 | Brief v8, build.md, delivery.md, consent.md, detection-methods.md, security-hardening.md section 18, login-portal.md, model-spec.md section 12, quality.md section 8, foolproof.md | Plan only; CSRF, literature, and conformal guidance checked 2026-10-30; no code |
| C11 | 2026-10-30 | Where to add, delete, and update appliances so the system registers, calculates, and tracks them everywhere | C2 | appliances-and-mysql.md, prototype.md, Brief v9, build.md, foolproof.md | Plan and prototype updated (Add form, preview, two removal choices, change history); what-if numbers hand-checked; no code |
| C12 | 2026-10-30 | Add an LLM | C3 | llm.md, Brief v10, build.md, model-spec.md, security-hardening.md, quality.md, foolproof.md, delivery.md | Plan only; OWASP LLM list and local runtime facts checked 2026-10-30; local mode kept; no code |
| C13 | 2026-10-30 | Complex but friendly front end with animations and sound effects; make it unique | C3 | experience.md, Brief v11, prototype.md, build.md, quality.md, foolproof.md | Plan and CSS-only prototype updated; WCAG, Web Audio, and browser support facts checked 2026-10-30; sound not demonstrable without code |


2026-11-03: Coding gate confirmation recorded from the user; imported the complete Smart Meter Explorer skill and reference set into project-spec. Event identity and detailed organizer rules remain Unknown pending documentation.
