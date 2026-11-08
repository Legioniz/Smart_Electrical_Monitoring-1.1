# Model spec: data, detection, fact sheet, narrative, simulation, metrics

Contents: 1 Data and units; 2 Features; 3 Detection and tiers; 4 False-positive controls; 5 Fact sheet; 6 Narrative and validator; 7 Synthetic data; 8 Metrics; 9 Hand-checkable examples; 10 Tuning detection settings; 11 Notification delivery; 12 Consumption calculations

All thresholds below are tunable settings with defaults the team chooses and documents. Defaults shown are illustrative unless the proposal states them.

## 1. Data and units
- Reading: pseudonymous meter ID, interval start time, energy in kWh for the 15-minute interval, quality flag (ok, missing, estimated).
- Average power over an interval in kW is kWh divided by 0.25. Never label interval energy as kW.
- 96 intervals per day. Store timestamps in UTC and show local time; the local zone for the Philippines is Asia/Manila (Likely UTC+8 with no daylight saving; verify).
- Customer profile: pseudonymous ID, language (English or Filipino), notification consent flags (mocked in the MVP), optional tariff (never invented).
- Alert: ID, meter, tier, type, window, score, reason code, fact sheet ID, status, audience (customer or internal).
- Fact sheet and narrative records are versioned and cached per period.
- Reject or flag: duplicate timestamps, out-of-order readings, negative energy, impossible values, gaps.

## 2. Features (computed only from past data at scoring time)
| Feature | Definition | Edge cases |
|---|---|---|
| Rolling baseline ratio | Current interval energy divided by the median of the same hour over the last 7 days, and again over 28 days | Fewer than the required days means cold start |
| Same-hour yesterday | Current interval minus the same interval yesterday | Missing yesterday gives no value |
| Day-of-week profile | Typical curve per weekday and weekend | Needs several weeks; use priors early |
| Temperature delta | Current temperature minus the recent average for that hour; used to explain weather-driven change | Simulated and labeled in the MVP |
| Night-time floor | Lowest sustained consumption during quiet hours (for example 01:00 to 05:00, tunable) | Compare to the customer's own history |
| Neighbor divergence | Household trend relative to the median of a comparable cohort on the same feeder | Cohort simulated in the MVP; pseudonymized |
Cold start: until the required history exists (the proposal says 14 days), use population-level priors and lower the confidence tier.
Never include the interval being scored inside its own baseline.

## 3. Detection and tiers
- Isolation Forest scores individual intervals on engineered features (point anomalies).
- Autoencoder learns the customer's normal daily shape and flags high reconstruction error over a window (pattern anomalies).
- Rule-based theft and tampering signatures from the proposal: sudden sustained drop with no weather or season change; night-time floor collapse to near zero; neighbor divergence over weeks; communication gaps correlated with consumption changes.
- Tiers: INFO is a mild deviation shown in the portal only. WATCH is a sustained deviation across several intervals and sends a customer notification with an explanation. CRITICAL is a strong score or a theft signature: a customer alert for non-theft causes, and an internal ticket.
- Persistence: an anomaly must repeat for a minimum number of intervals (tunable) before it escalates.
- Cooldown: a minimum quiet period before the same alert type can notify again.
- Different confidence thresholds for customer-facing and internal alerts.
- Theft-related signals create internal leads only. The customer sees at most a neutral message about unusual usage, with no theft language.
- Feedback ("this is normal") adjusts customer-facing alerts only. It must not change theft-lead criteria.
- Alerts are created only by the detection pipeline from stored readings and carry provenance (detection-methods.md section 9); none is inserted by hand outside labeled sample data.

## 4. False-positive controls and sources
Persistence, cooldown, tiered thresholds, weather adjustment, and cold-start caution. Legitimate causes to consider: vacancy or travel, outages, solar or net-metering changes, appliance replacement, seasonal change, new occupants, holidays, meter replacement.

## 5. Fact sheet (the only input to narration)
Fields (from the proposal's example): period, total energy (kWh), prior-period energy (kWh), change in percent, driver (labeled estimate), driver share (percent of total, estimate), average temperature and prior average temperature, peak window, anomaly flag. Add any derived value the text will mention (for example temperature difference), computed upstream.
Rules: every number is computed in code or SQL; rounding is defined (for example percent to one decimal in the sheet); no raw interval data leaves the secure boundary; the sheet is versioned and logged without personal identifiers.

## 6. Narrative and validator
- Generate the template narrative first; a local LLM may rephrase from the fact sheet under the rules in llm.md.
- Validator: extract every number from the text; each must equal a sheet value after allowed transformations only: the documented rounding, percent or unit formatting, 24-hour to 12-hour time conversion, and pre-approved advice constants. Any other number rejects the text.
- Also check: no theft or accusation terms in customer text; length cap per channel; language matches the customer's setting; no medical, legal, or financial claims.
- On failure or LLM unavailability, use the deterministic template built from the same sheet. The customer should not see an error message.
- Generate once per period and cache.

## 7. Synthetic data (labeled simulated)
- A seeded generator produces the same series for the same seed and settings.
- Baseline: a daily shape that differs on weekdays and weekends, plus noise; a temperature series that affects an aircon-like load; known appliance shares to support the estimated breakdown.
- Injected anomalies with ground-truth labels: single spike; sustained evening rise (appliance fault); gradual drift; sudden sustained drop; night-floor collapse; communication gap.
- Cohort of neighbor meters for divergence.
- Never present generated values as real consumption, real customers, or real weather.

## 8. Metrics (always label the data source)
- Precision = true positives divided by (true positives plus false positives) over reviewed alerts. On synthetic data, a true positive is an alert whose window overlaps an injected anomaly of a matching type.
- Recall = detected injected anomalies divided by all injected anomalies (synthetic only).
- Mean time to alert = alert time minus anomaly onset.
- False alerts per meter per week.
- Narrative number-match rate = narratives passing the validator divided by all narratives. Passing the validator is not proof of truth, so also check a sample by hand against the sheet.
- Report seeds, settings, and counts. Never present synthetic results as real-world performance.

## 9. Hand-checkable examples
| Case | Working | Result |
|---|---|---|
| Readings per day | 24 x 4 | 96 |
| Readings per year (non-leap) | 96 x 365 | 35,040 |
| Fleet readings per day (proposal's 12,000,000 meters) | 12,000,000 x 96 | 1,152,000,000 |
| Interval energy to average power | 0.30 kWh / 0.25 h | 1.2 kW |
| Evening window 18:00 to 21:00 | 3 hours x 4 | 12 intervals |
| Week-over-week change | (118.4 - 84.7) / 84.7 x 100 = 33.7 / 84.7 x 100 | 39.8% |
| Temperature difference | 34.6 - 31.2 | 3.4 degrees C |
| Evening ratio | 7.2 kWh observed / 3.0 kWh usual (12 intervals) | 2.4 times |
| Number-match, "about 40%" | Sheet has 39.8; rounds to 40 under a nearest-integer rule | Accept only if that rule is documented |
| Number-match, "about 3 degrees warmer" | Sheet has 34.6 and 31.2 only | Reject unless the difference 3.4 (and its rounding) is in the sheet |
| Number-match, "6 PM to 9 PM" | Sheet has 18:00 to 21:00 | Accept as a time-format conversion |
| Number-match, "one degree warmer" advice | Not in the sheet | Reject unless it is a pre-approved advice constant |
| Persistence example | Rule: 3 consecutive evenings | Third evening triggers WATCH (illustrative setting) |

## 10. Tuning detection settings
- Settings to tune: persistence length, cooldown, tier thresholds, score threshold, baseline window lengths, night-floor hours, autoencoder window and error threshold.
- Method: use the seeded synthetic benchmark; split by time into a tuning period and a test period; try a small documented grid or random search; choose by a stated objective (for example the highest precision at a minimum recall, with false alerts per meter-week capped); save every run (settings, seed, metrics) as a benchmark run in the database.
- Guard against overfitting: never tune on the test period, report test results once, vary seeds, and note that settings tuned on synthetic data may not transfer to real data.
- Label all results synthetic. Real-world tuning needs authorized data and human-reviewed labels.
- Keep tuned settings in one versioned place so changes are traceable and reversible.

## 11. Notification delivery (local mode)
- Channels: the in-app inbox is built; SMS, push, and email are planned and mocked. Real channels, providers, costs, and rules are Unknown.
- Consent gate: no analytics are shown before first-run consent; a notification on a channel is created only if the customer consented to that channel.
- Outbox: every notification is recorded locally with channel, audience, tier, text, language, and status "not sent (mock)"; no network call happens in local mode.
- Tier mapping: INFO in-app only; WATCH in-app, plus a mocked push or SMS if consented; CRITICAL non-theft alert to the customer plus an internal ticket in the admin queue; theft signals go to admin only and never create customer text.
- Suppression: persistence and cooldown apply first; quiet hours (planned); the validator must pass; channel length caps; language from the profile.
- Delivery log: created, shown, or suppressed with a reason (no consent, cooldown, quiet hours, validator failed). It feeds the false-alerts-per-week metric.
- "This is normal" feedback links to the alert ID and affects customer alerts only.

## 12. Consumption calculations (dashboard accuracy)
- One source: every dashboard number comes from the interval readings (kWh per 15-minute interval) through one calculation module. Tiles, charts, exports, and fact sheets use the same results.
- Periods are half-open [start, end) in local time (Asia/Manila) mapped to UTC ranges: a day is 00:00 to 24:00 local, a week is Monday to Sunday (configurable), a month is a calendar month.
- Totals reconcile exactly: day total = sum of its intervals; week total = sum of its day totals. Use exact decimals and round only for display.
- Missing data is never filled silently. Coverage = received intervals / expected intervals (96 a day). Totals below full coverage are labeled partial; compare periods only when coverage meets a tunable minimum (default Unknown), otherwise show "not comparable".
- Average power in kW = kWh / 0.25 per interval; the average kW of a full day = day kWh / 24.
- Change % = (current - previous) / previous x 100 when previous is above 0; otherwise "not available".
- Heatmap blocks cover all 96 intervals with no overlap: 00:00 to 06:00, 06:00 to 12:00, 12:00 to 18:00, 18:00 to 24:00 (24 intervals each).
- Worked check (prototype sample): daily totals 15.2, 16.0, 17.1, 18.4, 19.9, 16.4, 15.4 sum to 118.4; (118.4 - 84.7) / 84.7 x 100 = 39.8%.
- Tests: reconciliation of intervals to day to week; heatmap cells sum to the period total; chart data equals tile data; partial-day labeling; readings exactly at midnight; no daylight-saving handling is needed (Likely: Asia/Manila has none).
- Insight rule: an insight or narrative states the period and coverage it used and says "not enough data" below the minimum.
