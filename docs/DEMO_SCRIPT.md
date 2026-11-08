# Local demonstration script (draft; not yet rehearsed)

Target duration: 5–7 minutes. Use only the generated synthetic account and keep the local server terminal private because it prints demo credentials and staff one-time codes.

## Before the demo

1. Start the local MySQL service and confirm it is bound to loopback only.
2. Run `python -m sme.cli check` and open `/health`.
3. Start the app with `python -m sme.cli serve`; open `http://127.0.0.1:8000/`.
4. Verify the sample account passphrase is available and has been changed. Do not put passwords or OTPs in slides or recordings.
5. Confirm the UI displays the synthetic-data disclaimer and has no internet dependency.

## Walkthrough

1. **Landing and role selection (30 seconds).** Point out the customer/staff portal choice, the local-only design, and the synthetic-data disclaimer.
2. **Customer first sign-in and privacy (60 seconds).** Sign in with the generated demo customer, change its temporary passphrase, inspect the consent text/version/hash, accept required usage analytics, and leave optional mock notifications off.
3. **Explorer (90 seconds).** Show 7-day totals, coverage, day explorer, the 15-minute trace, any detector markers, missing intervals, and the persisted plain-language reason. Explain that flagged slots are joined from saved detector alert windows—not from the generator's hidden labels.
4. **Guardian and Storyteller (60 seconds).** Open customer-safe alerts and the generated fact-based story. Switch to Filipino template text. State that model results and generated data are synthetic and not field-validated.
5. **Appliances and controls (60 seconds).** Add or edit one example appliance, show its estimate label and data history, then export the demo account's data. Do not imply appliance-level energy is directly measured.
6. **Staff review (60 seconds).** Sign out, use a reviewer/admin account, enter the terminal OTP, and show the review queue. Explain that internal-only leads never appear in the customer area. A reviewer cannot unlock safe mode.
7. **Protection drill (optional, 60 seconds).** With two separate admin accounts, lock safe mode, request a second admin approval, and unlock using the second code. Do not perform this during a high-stakes presentation unless rehearsed and a database backup exists.

## Claims to avoid

- Do not say the model detects actual electricity theft, meter tampering, or appliance faults reliably.
- Do not call synthetic benchmark results real-world precision/recall.
- Do not say the application is integrated with Meralco or sends real SMS/push alerts.
- Do not call the app production-ready or independently penetration-tested.

## Rehearsal record

Status: **NOT REHEARSED**. Record the date, operator, device, elapsed time, and issues after the team performs a complete offline rehearsal.
