# Appliances and MySQL: add, edit, delete, estimates, and tab outputs

Contents: 1 Scope and sources; 2 Appliance data model; 3 Add, edit, and delete rules; 4 Estimate method; 5 Data flow by tab; 6 Empty states; 7 Integrity and safety rules; 8 MySQL design; 9 Local MySQL setup and security; 10 Privacy; 11 Tests; 12 Unknowns; 13 Migrations, backup, and recovery

## 1. Scope and sources
Requirement (Brief v6, change C7): MySQL is the database; customers add, edit, and delete their own appliances; the entries feed the outputs of every relevant tab. Local mode only. Planning until the coding gate is confirmed.
Verified (MySQL documentation, checked 2026-10-27): CHECK constraints are enforced from MySQL 8.0.16 (earlier versions accept the syntax but ignore it); InnoDB does not support foreign keys on user-partitioned tables; MySQL's security options include local_infile, secure_file_priv, skip_networking, and skip_name_resolve. Likely: the default network binding differs by package, so check the installed one. Unknown: the MySQL version, the connector library, and whether the hackathon rules allow installing MySQL.

## 2. Appliance data model
| Field | Rule |
|---|---|
| appliance_id, customer_id | Internal IDs; customer_id comes from the session, never from the request |
| name | 1 to 60 characters, free text, untrusted; unique per customer among active appliances, ignoring case |
| category | Fixed list: air conditioner, refrigerator, lighting, water heater, washing machine, electronics, cooking, fan, other. Customer-facing text uses only this label |
| rated_power_w | Number above 0 up to a documented maximum (tunable); for lighting, per bulb |
| quantity | Whole number 1 to 99 |
| duty_pct | 1 to 100, default 100; a refrigerator might be set near 40 |
| hours_per_day | 0 to 24 in steps of 0.25 |
| days_per_week | Whole number 1 to 7 |
| notes | Optional, up to 200 characters, owner-only, never used in outputs, prompts, logs, or admin screens |
| status, retired_on | active; retired (the customer no longer has it, so past periods keep it); or removed (entered by mistake, so every period loses it) |
| created_at, updated_at, version | Times in UTC; version supports edit conflict checks |
| appliance_versions | Effective-dated history: each saved change closes the current version (valid_to) and opens a new one (valid_from, by default the save date); estimates use the version in effect on each day |
Computed values, never trusted input: average_kw = rated_power_w / 1000 x quantity x duty_pct / 100; declared_kwh_per_week = average_kw x hours_per_day x days_per_week. A maximum number of appliances per customer applies (tunable).

## 3. Add, edit, and delete rules
- Create: validate every field (type, range, length, category from the list); reject duplicate names; enforce the per-customer limit; rate limit the action; write an audit event; return the new estimate.
- Preview: before saving, show the effect on the appliance's weekly estimate, its share, and the list's coverage, computed by the same function that produces the saved result.
- Read: only the signed-in customer's active appliances, sorted by declared energy, largest first.
- Update: validate again; compare the version and, if it changed elsewhere, show a friendly message instead of overwriting; save it as a new effective-dated version (valid from the save date; an "applies from" date is Optional) so earlier days keep the details that were in effect; audit; recompute the affected periods.
- Delete: the screen asks for confirmation and offers two choices. "I no longer have it" retires the appliance: it stops counting from that day and past periods keep it. "I added it by mistake" removes it: it disappears from every period, output, export, and cache at once. Meter readings are never touched. Retired and removed rows are purged when the customer deletes their data or after a tunable period (default Unknown).
- Errors name the field and the fix in plain words; no database messages or stack traces.
- The audit event holds IDs and the action, never free text.

## 4. Estimate method
Use a daily basis with effective dating: on each day an appliance contributes average_kw x hours_per_day x days_per_week / 7, using the version in effect that day, and E_i is the sum over the days in the period. For a full week of one unchanged version this equals the weekly formula. M is the metered kWh for the period, E_i the declared kWh of appliance i, and S the sum of E_i.
- No appliances: show the empty state; fact-sheet appliance fields are "not available".
- S <= M: share_i = E_i / M; the remainder (M - S) / M is "Everything else (not listed)"; coverage = S / M.
- S > M (entries exceed the meter): share_i = E_i / S, remainder 0, coverage 100%, and a note that the shares are proportional.
- No meter total: show declared energy only, labeled "meter total not available".
- Rounding: percentages to one decimal and kWh to one decimal; use largest-remainder rounding so displayed percentages sum to 100.0.
- Always label the result "estimated from your entries and your meter total; not measured per appliance". Never claim appliance-level measurement or disaggregation.
Worked example (sample, M = 118.4 kWh):
| Appliance | Working | kWh per week | Share |
|---|---|---|---|
| Aircon | 1.55 kW x 1 x 100% x 4.5 h x 7 | 48.825 | 41.2% |
| Refrigerator | 0.15 kW x 1 x 40% x 24 h x 7 | 10.08 | 8.5% |
| Lighting | 0.008 kW x 10 x 100% x 5 h x 7 | 2.8 | 2.4% |
| TV and computer | 0.2 kW x 1 x 100% x 4 h x 7 | 5.6 | 4.7% |
| Everything else | 118.4 - 67.305 = 51.095 | 51.095 | 43.2% |
Coverage = 67.305 / 118.4 = 56.8%; shares sum to 100.0.
Over-declared example: add a space heater, 3 kW x 1 x 100% x 8 h x 7 = 168 kWh. S = 235.305, which is above 118.4, so shares are E_i / S: aircon 20.7%, refrigerator 4.3%, lighting 1.2%, TV and computer 2.4%, space heater 71.4% (sum 100.0), with the proportional-shares note.
What-if checks (base example above; every change is recomputed with the same method):
| Change | Working | Result |
|---|---|---|
| Aircon hours 4.5 to 6 for the whole week | 1.55 x 6 x 7 = 65.1 kWh; S = 65.1 + 10.08 + 2.8 + 5.6 = 83.58 | Shares 55.0, 8.5, 2.4, 4.7, everything else 29.4 (sum 100.0); coverage 70.6% |
| Aircon hours changed on Thursday (3 days at 4.5, 4 days at 6) | 3 x 6.975 + 4 x 9.3 = 20.925 + 37.2 = 58.125 kWh; S = 76.605 | Aircon 49.1%, 8.5, 2.4, 4.7, everything else 35.3; coverage 64.7% |
| Add a washing machine, 0.5 kW x 1 x 100% x 1 h x 3 days | 1.5 kWh; S = 68.805 | Washing machine 1.3%, the others unchanged, everything else 41.9; coverage 58.1% |
| Remove the aircon as a mistake | S = 67.305 - 48.825 = 18.48 | 8.5, 2.4, 4.7, everything else 84.4; coverage 15.6% |
| Retire the aircon today | Days before today keep it | Past weeks unchanged; later weeks exclude it |

## 5. Data flow by tab
| Tab | Uses | Output |
|---|---|---|
| Overview | Count, coverage, biggest appliance by category | "Your appliances" card: how many listed, share explained, biggest, Manage button |
| Day Explorer | Declared average power per appliance | For the selected interval, lists appliances that could explain the excess. Excess kW = observed average kW minus usual average kW. An appliance is a candidate if its average_kw is between 0.5 and 1.5 times the excess (tunable). Example: 2.6 kW observed, 1.08 usual, excess 1.52, so Aircon at 1.55 kW qualifies. If none qualify, say nothing about appliances |
| Heatmap | Nothing in the MVP | An overlay of typical hours needs start times, which are not collected (Optional) |
| Breakdown | Estimate method in section 4 | Share bars, coverage line, estimate label, Edit my appliances button |
| Appliances | CRUD in section 3 | List with each appliance's estimated weekly kWh and share, edit and delete, the coverage card |
| Alerts | The same candidate rule | The reason names the category, for example "could be an appliance you listed, such as your aircon"; the alert stores candidate IDs; without candidates the generic wording is used |
| Story | Fact sheet fields: appliances_count, declared_coverage_pct, top_category, top_share_pct, driver | The driver comes from the estimate only when coverage meets a tunable minimum; otherwise "not enough information"; every number is computed upstream and passes the validator |
| Settings | Consent, export, deletion | Export includes appliances; "Delete my sample data and appliances" removes them |
| Admin views and detection | Nothing by default; an Optional aggregate count by category needs a minimum group size (Unknown) | See section 7 |

On any create, update, retire, or removal: recompute the Appliances list, the Overview card, the Breakdown, and the Day Explorer candidates; invalidate cached estimates from the effective date onward (every period for a removal by mistake); regenerate the current period's fact sheet and narrative. Past narratives and stored alerts are not rewritten: an alert keeps the candidate IDs it had when it was created.

## 6. Empty states
No appliances: Overview card "Add your appliances to see where your electricity goes"; Breakdown "Add your appliances to see an estimate"; Alerts use generic wording; Story says the driver is not known yet; Day Explorer omits the appliance line. Loading and error states follow the portal's general design.

## 7. Integrity and safety rules
- Declared appliances are untrusted user input. They never change theft-lead criteria, thresholds, scores, or admin leads, and admin screens show no appliance details by default. A person could otherwise over-declare to explain away a pattern.
- Customer-facing text uses fixed category labels and computed numbers only. Names and notes never enter prompts, narratives, alerts, logs, or admin screens; the owner sees them escaped.
- Escape all output (stored cross-site scripting); bound parameters only; allow-list the category; reject control characters; enforce maximum lengths.
- Authorization comes from the session on every request; one customer can never read or change another's appliances.
- Rate limit the create, update, and delete actions; cap appliances per customer; audit every change.
- Estimates are always labeled estimates.
- A removal by mistake means gone from every period, output, export, and cache at once; a retired appliance stays only in the periods before its retirement date.

## 8. MySQL design (in words)
Tables: customers, meters, readings, hourly and daily summaries, appliances, appliance versions, alerts, notification outbox, fact sheets, narratives, feedback, consent records, settings versions, model runs, benchmark runs, audit events, admin users and roles, lock state, security events.
- Engine InnoDB; character set utf8mb4 (Likely best practice); times stored in UTC with the connection time zone set to UTC; the app shows Asia/Manila.
- Energy and power use exact decimal types; percentages are computed, not stored as free text.
- Keys: a primary key on every table; a unique key on meter plus interval start so reloading data is idempotent (an insert-or-update statement with bound parameters; Likely, verify on the chosen version); unique active appliance name per customer, enforced in a transaction and, if the version allows, by a unique index on a key that is empty for deleted rows (Unknown; verify).
- Constraints: CHECK constraints for ranges, which need MySQL 8.0.16 or later to be enforced (Verified); still validate in the app. Foreign keys with cascading delete from customers to appliances.
- Do not partition tables that need foreign keys, because InnoDB does not support foreign keys on user-partitioned tables (Verified). For one simulated meter, skip partitioning.
- Indexes: readings by meter and time; appliance versions by appliance and valid_from; appliances by customer and status; alerts by customer and time.
- No continuous aggregates exist in MySQL: keep hourly and daily summary tables updated in the same transaction as ingestion, recomputed idempotently, and cache narratives per period. The proposal's TimescaleDB features are not used.
- Transactions wrap multi-row writes (an ingestion batch plus its summaries; an appliance change plus its audit event).
- Migrations are tracked and apply from an empty database through a privileged migration user; the app user cannot change the schema.
- Bound parameters through the chosen connector (which one is Unknown; verify it supports them); identifiers only from fixed allow-lists.
- Backups: dump the demo database to the second device (Likely with MySQL's dump tool) and test a restore.
- Sample data is simulated and labeled.

## 9. Local MySQL setup and security
- Install a current supported MySQL Community Server on the demo machine, version 8.0.16 or later so CHECK constraints are enforced (exact version Unknown). Check that the hackathon rules allow installing it. MariaDB differs in places (Likely); do not substitute it silently.
- Network: the default binding varies by package; set the bind address to loopback or enable skip_networking and use the local socket, then confirm no other machine can reach the port. No inbound firewall rule for it.
- Accounts: set a root password; remove anonymous accounts and sample databases (Likely); create a migration user limited to the app database and an app user with only SELECT, INSERT, UPDATE, and DELETE on the app's tables; no file, grant, super, drop, alter, or create rights for the app user; both limited to localhost.
- Server options: turn off local_infile; set secure_file_priv; consider skip_name_resolve (the options exist per MySQL's documentation; recommended values are Likely).
- Credentials in environment variables, never in the repository; demo passwords labeled sample and deleted after the event.
- Check before the demo: the app starts with MySQL running; with MySQL stopped it shows a friendly message and does not crash.

## 10. Privacy
Appliance lists reveal household routines, so they are personal data: covered by consent, included in export and deletion, listed in the retention table, hidden from admin by default, and never sent to a hosted service (local mode has none). Fact sheets carry only categories and computed numbers.

## 11. Tests (plan; run with synthetic data)
| Area | Cases |
|---|---|
| CRUD | Valid create; each invalid field; duplicate name; per-customer limit; update; edit conflict; retire and remove then outputs follow the rules; delete never touches readings |
| Tracking | An update from Thursday changes only Thursday onward (the 58.125 kWh example); retiring keeps past weeks; removal by mistake erases every week; the preview equals the saved result; the change history lists each change; caches for the affected periods are recomputed |
| Estimates | The worked example; the over-declared example; no appliances; no meter total; percentages sum to 100.0 |
| Tab outputs | Add an appliance and Breakdown and Overview change; delete and they revert; Story fact-sheet fields; Day Explorer candidate rule on the 2.6 kW example; Alerts wording |
| Integrity | Same readings with different declared appliances give identical admin leads; free text never appears in customer text; hostile-looking input in name and notes is stored as plain data and escaped; no stack traces |
| Authorization | Customer A cannot read, edit, or delete customer B's appliances |
| MySQL | CHECK constraints reject bad rows on the chosen version; cascade delete; unique key keeps reloads idempotent; the app user cannot alter the schema; migrations apply from empty; backup and restore; MySQL stopped gives a friendly message; port not reachable from outside |
| Performance | Record timings for the list and the estimate with the machine and data size |

## 12. Unknowns
MySQL version and connector library; ID type; the unique-name implementation; whether the rules allow installing MySQL; the default binding on the team's install; the dump tool available; the default purge period for retired and removed appliances; whether an applies-from date is offered; the minimum group size for any aggregate view.

## 13. Migrations, backup, and recovery
- One tracked migration history is the only way the schema changes; no manual edits. Each migration is small, forward-only, and tested from an empty database and from the previous version. A schema-drift test compares the live schema with the migrations. Seed data is separate from migrations and labeled simulated.
- Consistency: keys, foreign keys, and CHECK constraints live in the database (8.0.16 or later) and the same rules run in the app; related writes share a transaction; a test looks for orphaned rows.
- Backups: dump the whole app database before each migration, before the demo, and after the final data load; keep the files on the second device; record file name, time, size, row counts per table, and a checksum; keep at least the last three.
- Recovery drill (record Pass or Fail and the time it took): restore a dump into a fresh database, run the app against it, compare row counts and checksums, and run the smoke test. Also drill MySQL stopped, a missing data directory, and a failed migration (restore from the pre-migration dump). Target recovery time is Unknown; measure it.
- Point-in-time recovery from binary logs is Unknown for this setup and not required for the MVP.
- Never edit the demo database by hand; use the app or a labeled script.
