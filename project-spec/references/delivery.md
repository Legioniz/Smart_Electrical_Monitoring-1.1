# Delivery guide: gates, Definition of Done, scope, risks, team

Contents: 1 Phase gates; 2 Definition of Done; 3 Scope control; 4 Risk register; 5 Team workflow; 6 Decision log

## 1. Phase gates
Do not start a phase until the previous exit criteria are met, and name unmet criteria instead of rounding up.
| Phase | Entry | Exit (evidence) |
|---|---|---|
| 0 Gate | Proposal read | The user confirmed coding is allowed, or planning-only mode is stated; the event and rules are identified |
| 1 Architecture | Phase 0 | S0: architecture notes, threat model, decisions logged, traceability table accepted |
| 2 Database | Phase 1 | S1 and S2: migrations build the schema from empty; restore drill recorded; generator and validated ingestion pass tests that were run |
| 3 Authentication and consent | Phase 2 | S3 and S4: sign-in, sign-out, sessions, and consent submission with persistence and tracking pass their tests |
| 4 Permissions and security tests | Phase 3 | S5: permission matrix and request-integrity tests pass; lock drill passes; no feature work starts before this |
| 5 Dashboard | Phase 4 | S6 to S8: calculations reconcile; screens work with real data at 360, 768, and 1280 px; no dead controls; appliances feed the tabs |
| 6 Anomaly detection | Phase 5 | S9 and S10: the detector runs on synthetic data; alerts carry provenance; benchmark reported as synthetic |
| 7 AI explanations | Phase 6 | S11 and S12: validator, fallback, and LLM-off path proven; the evaluation set run; insights cite their fact sheet and coverage |
| 8 Acceptance | Phase 7 | S13 and S14: optimization recorded; UX completeness audit done; full suite rerun; every acceptance item marked; the go or no-go in foolproof.md completed |
Scale gates to the change class (change-management.md): a tweak needs no gate, a pivot restarts at Phase 0. After each phase report in 10 lines or fewer: what was built, changed files, tests run with counts, remaining issues. Never sacrifice security to make a feature work.

## 2. Definition of Done
A feature is done when: it works from current data; it has tests that were run; invalid input is handled; units are shown; it is explained in plain words; no control on its screens is dead; its security checks stayed on; a teammate can explain it. The project is done when every acceptance item in the current Brief is Met with evidence. Allowed marks: Met (with evidence), Not met, Not yet tested.

## 3. Scope control
| Class | Items |
|---|---|
| Required (MVP, baseline Brief) | Architecture notes and threat model; MySQL store with migrations, backup, and restore; synthetic generator and validated ingestion; login portal (customer, reviewer, administrator); consent with persistence and tracking; permission matrix and request-integrity checks (CSRF, Origin, Host, validation); security layer (bound queries, rate limits, headers, firewall rules, auto-lock, tamper checks); consumption calculations; landing page and portal screens; appliance add, edit, retire or remove with tab outputs; detection with alert provenance; alert tiers, notification settings, and mocked delivery; reviewer queue and administrator unlock; fact sheet, template narrative, validator, and fallback; local LLM layer with validation, fallback, and switches; optimization pass with recorded measurements; UX completeness audit; motion and sound system (opt-in sound, reduced-motion support); tests; README; demo script |
| Optional (added only when the user asks) | Heatmap; model-written Filipino text; deeper performance tuning; real weather; real notification channels; fleet-scale benchmark; signed releases; the customer-alert feedback loop; "ask about my usage"; password reset and self-registration; matrix-profile or forecast-interval detectors |
| Out of scope (local-only mode, decision 15) | Hosted link; online database; hosted LLM provider; web application firewall, bot-management service, managed DNS and DNSSEC, hosted edge and cloud firewall services (revisit only if the user changes the mode) |
| Not allowed | Theft accusations to customers; automatic disconnection; real data without authorization; compliance or performance claims without evidence; Meralco endorsement claims |
Do not build what the user did not ask for; suggest at most three Optional ideas. A user instruction counts as approval.

## 4. Risk register
Risks, prevention, detection, and fallbacks are in foolproof.md section 2.

## 5. Team workflow (the team decides roles)
Proposal roles: Team Lead and PM; ML Engineer; Backend Engineer; Frontend Engineer; LLM and Prompt Engineer. Team size is Unknown; ask. Review each other's work kindly and specifically; commit under your own name; every member rehearses the Q&A. Ask for the schedule before proposing a timeline; do not assume dates.

## 6. Decision log
| Date | Decision | Options considered | Reason | Who agreed |
Fill it for the open decisions in project-brief.md and every later choice.
