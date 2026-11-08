# Security and privacy guide

Contents: 1 Data classes; 2 Minimization and real data; 3 Consent; 4 LLM data boundary; 5 Theft leads; 6 Access and audit; 7 API and code checklist; 8 Compliance wording; 9 Review output; 10 Online database; 11 Retention and deletion

Firewall, connection security, DNS, bot and SQL protections, auto-lock, and tamper detection are in security-hardening.md. Claude is not a lawyer. This guide helps the team build carefully and describe things honestly; it does not certify compliance. The proposal names the Data Privacy Act of 2012 (RA 10173) and the National Privacy Commission; legal or data-protection-officer review is needed before real use.

## 1. Data classes
Consumption series tied to a meter can reveal when people are home and what they do, so treat it as personal data even when IDs are pseudonymous. Also sensitive: appliance lists (they reveal routines), location, contact details, notification preferences, theft leads. Cohort benchmarks must be pseudonymized so no customer sees another's data.

## 2. Minimization and real data
- Use simulated data for the MVP and label it.
- Real or anonymized meter data only with written authorization and agreed terms; keep it out of the repository and out of logs.
- Collect only fields a feature needs; no real names, addresses, phone numbers, or account numbers in sample data.
- State a retention and deletion approach before real use.

## 3. Consent and notifications
Consent submission, persistence, tracking, enforcement, and withdrawal are specified once, in consent.md. Notification channels are mocked in local mode (model-spec.md section 11).

## 4. LLM data boundary
In local mode the LLM runs on the same machine (llm.md) and nothing leaves it. Send only the fact sheet: no identifiers, no raw intervals, no customer free text. A per-customer fact sheet is still personal data, so it never goes to a hosted or cloud service. Do not log prompts or outputs that contain personal data.

## 5. Theft leads
Internal audience only; reviewed by authorized admin through standard procedures; never an accusation to the customer; never an automatic disconnection or penalty; every access audited. Customer feedback does not alter theft-lead criteria. Keep wording of internal tickets factual ("pattern consistent with") and not conclusive.

## 6. Access and audit (planned in the proposal; label as not implemented unless built)
Role-based access with least privilege; audit log of data access; encryption in transit and at rest. If the MVP mocks any of these, say so.

## 7. API and code checklist
API, input, secrets, and transport rules are in security-hardening.md sections 4, 7, 8, and 9; sign-in and sessions are in login-portal.md. Also: no stack traces, internal paths, or secrets in responses or logs; do not render user or model text as raw HTML; pin dependencies and add no telemetry without a stated need; treat any committed credential as leaked and rotate it.

## 8. Compliance wording
Say: "designed with data-privacy principles in mind; pending legal and data-protection review". Do not say: "compliant", "certified", "audited", or "legally defensible".

## 9. Review output
Table: Check, Status (Pass, Fail, Not reviewed), Evidence, Fix. End with: "This is a checklist pass, not an audit or legal advice."

## 10. Online database
Out of scope in local-only mode (decision 15); this section applies only if the user later changes the mode.
- Use simulated data only unless real data is authorized in writing. An online database is a third party holding the data: where it is hosted, who can access it, retention, and cost are Unknown until checked.
- Connection strings and credentials live in environment variables or a secret manager, never in source or the repository; rotate them if leaked.
- Use TLS in transit, restrict network access where the service allows it, and give the app a least-privilege database user (it should not be able to drop tables).
- Only the API talks to the database; never expose it directly to the browser.
- Know how to restore from a backup, and test it once.
- Free or demo tiers may pause, limit storage, or expire: Unknown; verify, and keep a working local fallback.
- State honestly in the README and demo that data is stored in an online database. Claim encryption at rest or compliance only if verified.

## 11. Retention and deletion (local mode)
The proposal requires a documented retention and deletion schedule before real use. Real periods are Unknown: the data owner sets them with legal and data-protection review. Prototype defaults below are for simulated data only and are not policy.
| Data | Prototype default | Real use |
|---|---|---|
| Readings | Until reset or deletion | Unknown; set by the data owner |
| Alerts and notification outbox | Until reset or deletion | Unknown |
| Appliance entries | Until the customer deletes them or resets | Unknown |
| Fact sheets and narratives | Replaced per period | Unknown |
| Feedback | Until reset or deletion | Unknown |
| Consent records | Kept as long as the data they cover, so consent can be shown | Unknown |
| Security and audit logs | Kept through the event and retrospective, then deleted; no personal data in them | Unknown |
| Admin review notes | Until reset | Unknown |
| Backups and exports | Deleted after the event | Unknown |
Deletion actions: "Delete my sample data" removes a customer's simulated readings, alerts, narratives, feedback, and appliances; withdrawing consent stops analytics and notifications; caches and backups are cleared on their next cycle (state this limit). After the event, delete all local copies and exports and archive only the code. Never present a retention period as a policy.
