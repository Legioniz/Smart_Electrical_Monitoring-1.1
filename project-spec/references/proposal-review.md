# Proposal review

Contents: 1 Strengths to keep; 2 Findings; 3 Claims register; 4 Fill-ins; 5 Questions for organizers

## 1. Strengths to keep
- Facts before language, with a deterministic fallback and a number-match check.
- Theft signals are leads for human review, never accusations or automatic actions.
- Alert tiers, a persistence requirement, a cooldown, and separate thresholds for customer and internal alerts.
- Mobile first, accessibility goals, and plain-language copy principles.
- Phased roadmap with a small MVP; independent modules.

## 2. Findings (ID, severity, issue, fix)
| ID | Sev | Issue | Fix |
|---|---|---|---|
| F1 | High | The example narrative breaks the proposal's own number-match rule. It says "40%" (fact sheet 39.8), "3 degrees C higher" (the sheet holds two temperatures, 34.6 and 31.2, whose difference is 3.4), and "one degree warmer" (not in the sheet). Times read "6 PM and 9 PM" while the sheet says 18:00 to 21:00 | Define allowed transformations: a stated rounding rule, derived values computed upstream and included in the sheet, time-format conversion, and approved advice constants. Implement them in the validator and fix the example text |
| F2 | High | The narrative says the aircon used 40% more, but the sheet says total usage rose 39.8% and the aircon share is 41.2% of total. These are different quantities | Reword to total usage and estimated share, or add a driver-specific change to the sheet |
| F3 | High | Appliance driver and breakdown from one whole-home meter has no stated method | State the method; label it an estimate; in the MVP derive it from known simulator shares; use "likely" wording |
| F4 | High | "Aligned with the Data Privacy Act" is a compliance claim; per-customer facts sent to a hosted LLM are still personal data | Reword to "designed to support privacy principles, pending legal and DPO review"; make the LLM data boundary an explicit decision |
| F5 | Med | Unsourced figures: "about 12M meters", "<1% can interpret them", "LLMs are cheap and safe enough" | Cite a source or label as an assumption; remove if unsupported |
| F6 | Med | The "Evidence of impact" column lists expected outcomes, not evidence | Rename to "Expected impact" |
| F7 | Med | KPIs (precision at least 70%, inquiries down 20%) are targets; precision needs reviewer-labeled alerts | In the MVP report only synthetic-benchmark results, labeled synthetic |
| F8 | Med | "Score the full fleet nightly" implies about 1.152 billion readings per day (12,000,000 x 96), unbenchmarked | Mark as a projection; no performance claims until measured |
| F9 | Med | Six pipeline components for one simulated meter in 48 hours is a schedule risk | Build a vertical slice first; see decision 2 in project-brief.md |
| F10 | Med | The autoencoder is listed under scikit-learn, which is not a dedicated deep-learning library; implementation is undefined | Choose and document an implementation |
| F11 | Med | "Customers never see an error" is an overclaim | Use "designed to fall back to template text" |
| F12 | Med | Persistence length, cooldown, confidence thresholds, and the 14-day cold start are unspecified | Make them tunable settings with documented defaults |
| F13 | Med | "This has happened 3 days in a row" and similar rules depend on unspecified definitions | Define each rule precisely in the model spec |
| F14 | Med | The "this is normal" feedback retrains the baseline, which could teach the system that tampering is normal | Let feedback affect customer-facing alerts only; keep theft-lead criteria fixed and reviewed by admin |
| F15 | Low | Projected bill needs a tariff; the mock shows a blank | Do not invent rates |
| F16 | Low | Event name and dates (Hackathon 2025) differ from earlier materials (2026); team fields are placeholders | Confirm the event and rules; fill the placeholders |
| F17 | Low | Neighbor divergence and temperature delta need cohort and weather data that the MVP lacks | Simulate and label |
| F18 | Low | Filipino text quality is unverified | Review by a fluent speaker |
| F19 | Low | Drops in usage can be legitimate (vacancy, travel, outage, solar installation, moving out) | Add these to false-positive controls; keep theft language internal |
| F20 | Low | Notification consent and opt-out are mentioned only as a future phase | Mock and label in the MVP; plan for real use |

## 3. Claims register
| Claim | Status | Safe wording |
|---|---|---|
| Meralco is heading toward about 12 million smart meters | Unverified | "The proposal assumes about 12 million meters" |
| 96 readings per meter per day, 35,040 per year | Checked arithmetic (96 x 365) | Fine; note that leap years differ |
| Fewer than 1% of customers can interpret interval data | Unsourced | Remove or cite |
| Isolation Forest is fast enough for nightly fleet scoring | Unverified | "Intended to scale; to be benchmarked" |
| Narrative accuracy 99% or better | Target | "Target; measured on synthetic text in the MVP" |
| Alert precision at least 70% | Target | "Target for the pilot; not measured" |
| Customers never see an error | Overclaim | "Falls back to template text" |
| Aligned with the Data Privacy Act of 2012 (RA 10173) | Compliance claim | "Designed with its principles in mind; needs legal review" |
| Theft detection is legally defensible | Overclaim | "Leads only, reviewed by humans" |

## 4. Fill-ins needed
Team name, team lead, contact email; the event name and date; demo length; judging criteria; allowed libraries and APIs; whether anonymized data will be provided.

## 5. Questions for organizers
1. Which event and rules apply, and when may coding start?
2. Will anonymized interval data be provided, and under what terms?
3. Are hosted LLM APIs allowed, and who pays?
4. Are there stack or library restrictions, and how is the work submitted?
5. How long is the demo, and what are the judging criteria?
6. May the team name Meralco as the problem owner in materials, and what branding rules apply?
