# Deployment and demo-day guide

Contents: 1 Gate and honesty; 2 Targets; 3 Pre-run checklist; 4 Smoke test; 5 Demo-day runbook; 6 Rollback; 7 Troubleshooting; 8 Privacy of a public link; 9 Database options

Hosting facts for this stack were not researched for this skill. Anything about a specific host is Unknown until checked; research it when the team picks one.

## 1. Gate and honesty
Config files (container definitions, environment templates) count as coding. Before the gate is confirmed this guide is planning only. Never say the app is deployed or live unless the user opened the URL and shared the result. Never invent a URL.

## 2. Targets
| Target | Use | Risk |
|---|---|---|
| Local run on a team laptop (containers or direct processes) | Primary demo; development | Laptop failure; keep a second machine ready |
| Hosted link for judges | Out of scope (local-only decision) | Revisit only if the user changes the mode; hosting facts are Unknown |
| Recorded backup video and screenshots of the real running app | Backup if hardware or network fails | Label it a recording; never a substitute for the working app |
Decision (user): local mode only, no hosted link. Demo locally; keep the recording and a second device with its own working copy as backups.

## 3. Pre-run checklist
- [ ] Tests run and results seen; app starts with the documented command from a clean checkout.
- [ ] Only simulated data; no keys or real data in the repo or history; keys come from environment variables.
- [ ] The demo works with the LLM off, and with the network off (the LLM is local).
- [ ] The simulated-data label and synthetic-metric label are visible.
- [ ] Portal checked at 360, 768, and 1280 px.
- [ ] README commands were actually run; versions pinned; one Python version and one Node version used by the team.
- [ ] A tag marks the known-good commit.

## 4. Smoke test (record Pass or Fail and the date)
| # | Check | Expected |
|---|---|---|
| 1 | Portal loads on a phone-width screen | Simulated label visible |
| 2 | Day Explorer | 15-minute chart with flagged intervals and reasons |
| 3 | Each injected anomaly type | Flagged at the documented tier |
| 4 | Fact sheet and narrative | Numbers match the sheet |
| 5 | Validator with a bad number | Text rejected; template shown |
| 6 | LLM switched off | Template narrative, no error |
| 7 | Theft-pattern series | Internal lead only; no theft text for the customer |
| 8 | Bad input to the API | Friendly error, no stack trace |
| 9 | Filipino and English | Both render correctly |
| 10 | Accessibility spot check | Contrast, text alternatives, no sideways scroll |

## 5. Demo-day runbook
The full timeline, drills, and go or no-go are in foolproof.md. Fallback order: local run on the main laptop, local run on the second device, recording (say it is a recording).

## 6. Rollback
Prefer git revert or checking out the tagged version over rewriting history. Never force-push in the last two hours. Rebuild from the known-good commit.

## 7. Troubleshooting (Likely causes; verify)
| Symptom | Likely cause | Fix |
|---|---|---|
| A container exits at start | Missing environment variable or port conflict | Check logs; set the variable; change the port |
| Portal cannot reach the API | Cross-origin setting or wrong base URL | Fix the allowed origin and the URL setting |
| Charts empty on the phone view | Container width zero or data not loaded | Check layout and the data request |
| Narrative missing | LLM timeout with fallback disabled | Enable the template fallback; check that the local model runtime is running |
| Times off by hours | Time zone mix-up | Store UTC, convert for display |
| Works locally, fails elsewhere | Version or path differences | Pin versions; use relative paths with exact case |
| Slow scoring | Too much data per request | Batch off the request path; reduce data |

## 8. Privacy of a public link
A public link is open to anyone: simulated data only, the simulated label visible, no keys, no personal information, no utility logos.

## 9. Database options
| Option | Use | Watch for |
|---|---|---|
| Local MySQL server (chosen by the user) | All application data | Install and setup time; bind to localhost; least-privilege app user; version Unknown |
| Other local databases | Not chosen | The user chose MySQL; the proposal's TimescaleDB is not used |
| Online managed database | Out of scope (local-only decision) | Revisit only if the user changes the mode |
Recommendation: a local database behind one storage interface; the online option stays unbuilt.
Checklist: migrations apply from empty; demo data seeded; the app starts with no internet and shows a friendly message with MySQL stopped; a backup or export exists; the second device has its own working copy.
