# Quality guide: tests, ML evaluation, review, debugging

Contents: 1 Test plan; 2 ML evaluation; 3 Running and reporting; 4 Code review; 5 Debugging; 6 After a change; 7 Prototype review; 8 Critical workflows and UX completeness

Expected values come from hand calculation, never from running the code and copying its output.

## 1. Test plan (name each case, inputs, expected result)
| Area | Cases |
|---|---|
| Ingestion | Valid reading accepted; negative energy, duplicate timestamp, unknown meter, bad timestamp rejected; gap flagged |
| Features | Baseline ratio and same-hour values match hand calculations; the scored interval is excluded from its own baseline; cold start lowers confidence |
| Signatures | Sudden drop, night-floor collapse, neighbor divergence, and communication gap each fire on a constructed series and stay quiet on a normal one |
| Isolation Forest and autoencoder | Injected spike and drift detected on synthetic data at documented settings; results reproducible with a seed |
| Tiers | Persistence, cooldown, and threshold behavior; theft signals route to internal audience only |
| Fact sheet | Every number equals a hand-computed value; derived values present |
| Validator | Accepts documented rounding and time conversions; rejects an unknown number, a theft term, an over-length text |
| Fallback | LLM off or invalid output gives template text with no error |
| LLM layer | The tests in llm.md section 11: a fake local model for unit tests (no network), the evaluation set, injection and output-handling cases, switches, caching, provenance |
| API | Valid and invalid requests; consistent error shape; no stack traces |
| Privacy | No theft language in customer text; no personal data in logs |
| Storage | The same storage contract tests pass on every configured backend; reloading the same readings creates no duplicates; migrations apply cleanly from empty; reset-to-demo restores data; a database failure gives a friendly message |
| Performance | Baseline and after timings recorded with machine and data size; outputs identical before and after each optimization |
| Security | The tests in security-hardening.md section 14: bound queries with hostile-looking input, database rights, rate limits, auto-lock and unlock, lock abuse, tamper alarm, headers and transport, cross-origin rules, meter ingestion, error leaks, logging |
| Appliances and MySQL | The tests in appliances-and-mysql.md section 11: CRUD validation, estimates, tab outputs, integrity, authorization, MySQL constraints and privileges |
| Login and sessions | The tests in login-portal.md section 10: sign-in, throttling and lockout, sessions, authorization, admin second step, password storage, audit, cross-site request forgery |
| UI | Screens at 360, 768, 1280 px; no sideways page scroll; text alternatives present; red never the only signal |
| Localization | English and Filipino templates render; Filipino reviewed by a fluent speaker |

## 2. ML evaluation protocol
- Use the synthetic benchmark with labeled injected anomalies; report precision, recall, mean time to alert, and false alerts per meter-week, with seeds and settings.
- Split by time; keep the test period unseen during tuning.
- Compare against a simple threshold baseline.
- Label every figure "synthetic". Never present it as real-world performance or as the proposal's KPI.
- If real anonymized data is later authorized, evaluate separately and require human review labels for precision.

## 3. Running and reporting
- Run the tests and report the real output: passed, failed, skipped, and failing test names with messages. If not run, say "Not run" and why.
- When a test fails, redo the hand calculation to decide whether the code or the expected value is wrong. Do not edit a test just to pass it.
- Check that tests can fail: break the logic briefly (for example drop the persistence rule) and confirm a test catches it, then restore.
- While iterating, run the tests for the code touched; run the whole suite once at the end of the slice and before any claim of done.
- Check the app starts with the documented command before claiming the interface works.
- Report as: Area, Tests run, Passed, Failed, Notes. End with what is verified, what is not, and which acceptance items are unmet.

## 4. Code review checklist
1. Nothing hardcoded that should come from data; settings in one place.
2. Units correct: kWh per interval versus kW average; no mixing.
3. No data leakage; baselines use past data only.
4. Theft signals never reach customer-facing output.
5. Every generated number passes through the validator; fallback works.
6. Timestamps handled consistently (UTC storage, local display).
7. Seeds fixed; results reproducible; model and settings versions recorded.
8. Errors handled without stack traces; secrets absent.
9. Core code independent of web and database code.
10. Tests exist for each behavior above and were run.
Output a table: Finding, Severity (Blocker, Should fix, Nice), Location, Suggested fix. Lead with blockers and say what was not reviewed.

## 5. Debugging
1. Reproduce with the smallest series that shows the problem and calculate the expected answer by hand.
2. Locate the layer: ingestion, features, scoring, tiers, fact sheet, validator, API, or UI.
3. Test one hypothesis at a time; read the full error.
4. Fix the cause, add a regression test, run the suite.
Root cause first: when a protection blocks a feature, diagnose and fix the cause (token, session, Origin, Host, validation); never switch the protection off, loosen it to a wildcard, or add a bypass flag. Common causes: off-by-one at interval boundaries; time zone or daylight-saving mix-ups; kWh and kW mixed; rolling windows that include the current value; leakage across the train and test split; unseeded randomness; stale cached narratives; flaky tests that use the network; units missing from chart axes.

## 6. After a change
- If a requirement changed on purpose, update the affected tests first with new hand-calculated values, note the reason in the changelog, then change the code.
- Add a test for each new rule; keep old tests that still apply.
- After a detection change, rerun the synthetic benchmark and compare with the previous run.
- After a fact-sheet or template change, rerun the validator cases.
- After an interface change, recheck 360, 768, and 1280 px.
- Report "Not run" for anything not executed.

## 7. Prototype review checklist
- The landing page and all portal screens are reachable; tiles, buttons, and Back to home go to the right place.
- Numbers tie out as in prototype.md section 5 after any change.
- The sample-data label is visible on every screen and in the landing footer.
- No theft or accusation language; nothing described as live, real, or compliant; opt-in alerts marked planned.
- Text contrast is at least 4.5 to 1 and meaningful graphics at least 3 to 1; recompute after color changes.
- Touch targets are at least 44 px; arrow keys move between screens; charts have text alternatives; icons are decorative.
- Layout holds at 360, 768, and 1280 px with no sideways scroll.
- If Claude has not opened the prototype, say "Not opened" and ask the user to report any tab that fails.

## 8. Critical workflows and UX completeness
Every critical workflow needs automated tests that were run.
| Workflow | Tests |
|---|---|
| Sign-in and sign-out (customer, reviewer, administrator) | login-portal.md section 10 |
| Consent submit, persist, withdraw | consent.md section 8 |
| Authorization | Every role against every route and action, allowed and denied; cross-customer denial; the matrix in login-portal.md section 8 |
| Request integrity | security-hardening.md section 18 |
| Appliance add, edit, delete, estimates | appliances-and-mysql.md section 11 |
| Ingestion and validation | Section 1 rows |
| Consumption calculations | model-spec.md section 12 |
| Detection and alert creation with provenance | detection-methods.md sections 8 and 9 |
| Narratives and the validator | Section 1 rows |
| Review queue and safe-mode unlock | login-portal.md section 10; security-hardening.md section 14 |
| Migration, backup, restore | appliances-and-mysql.md section 13 drills |
| Experience (motion, sound, charts) | experience.md section 8 |
UX completeness audit:
- Dead controls: every button and link activates a handler or route; a control that is not built is removed or disabled with a visible reason. A browser test enumerates the interactive elements and activates each (tool Unknown).
- Navigation: every route is reachable from the interface; Sign out and back links work; an unknown route shows a 404 page; an unauthorized request goes to sign-in and returns to the page afterward.
- States: empty, loading, and error states exist for every screen.
- Accessibility: keyboard-only pass, focus order, labels and names, contrast at least 4.5 to 1, screen-reader names for charts and icons.
- Layout: 360, 768, and 1280 px with no sideways page scroll.
