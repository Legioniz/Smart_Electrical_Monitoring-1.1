# Design prototype: landing page and portal

Contents: 1 Status; 2 Landing page; 3 App shell and navigation; 4 Screens; 5 Sample data and tie-outs; 6 Visual tokens and contrast; 7 Technique and limits; 8 Revising; 9 From prototype to build; 10 Gaps and Optional additions

## 1. Status
A static, front-end-only design prototype made as a Claude design artifact. Last known link (private to the user, may change): https://claude.ai/artifact/1e2vxpSb4zHuTGLR5TnDPB. Nothing runs behind it: no detection, database, or AI. Only navigation works; other buttons are visual. Claude has not opened it in a browser, so layout and tab switching are unverified until the user reports; contrast ratios below were calculated, not seen on a screen. It is allowed-mode work (design sketch with static sample values). If the hackathon rules restrict front-end files before the event, treat it as a design reference only.

## 2. Landing page (opens first)
- Header: product name and an "Open sample portal" button.
- Hero: kicker "Plain-language smart meter insight"; headline "Your smart meter already knows what happened. We make it explain." (the proposal's value proposition, second sentence highlighted); one lead sentence about seeing 15-minute usage in simple sentences before the bill; buttons "Open sample portal" (opens the consent screen first) and "See an alert example"; a sample-day line chart with 6 PM to 9 PM highlighted and a small Watch alert card (2.4 times usual, 3 days in a row).
- See, Understand, Act: three cards from the proposal.
- How it works: three steps (the meter reports every 15 minutes; Guardian compares it with your own usual patterns; Storyteller explains what changed with checked numbers).
- Explore every screen: seven tiles that open the seven screens.
- Built to be trusted: "Numbers are checked"; "Mobile first"; "You stay in control" (alerts planned to be opt-in, English first, Filipino to follow).
- Footer: "Hackathon design prototype with sample data. Not an official Meralco site and not endorsed by Meralco. Nothing here is live or real." plus links to the sample Consent, Settings, Safe mode, and Admin sign-in screens
Rules: no unbuilt feature is stated as available (use "planned"); no Meralco logo; no endorsement; no invented statistics or customer counts; the disclaimer stays.

## 3. App shell and navigation
- Phone and tablet: fixed bottom bar with seven icon-and-label items: Overview, Day, Heatmap, Breakdown, Appliances, Alerts, Story (the bar scrolls sideways if they do not fit). Desktop (1024 px and up): dark left sidebar of 240 px with the product name.
- The Dashboard screen is labeled "Overview" in navigation so it does not clash with "Back to home", which returns to the landing page.
- Top bar: "Back to home", "Settings", and a "Sample data" chip. A banner on every screen: "SAMPLE DATA: Design prototype with simulated values. Only the navigation works. Nothing here is live or real."
- Active item: filled background and yellow text. Content is capped near 1120 px wide. Icons are inline strokes marked decorative; no emoji.

## 4. Screens (expected design)
| Screen | Expected design | Sample content |
|---|---|---|
| Dashboard (nav: Overview) | Dark summary card; Watch alert card with "See this evening" (goes to Day Explorer) and "This is normal"; "Your appliances" card (count, share explained, biggest) with a Manage appliances button; Pulse Ring (today by hour, with a table view); weekly bar chart | 118.4 kWh; up 39.8% from 84.7 kWh; Wed to Fri bars flagged; note that projected bill needs a tariff |
| Day Explorer | Title; Today, Yesterday, Same day last week buttons (visual only); 24 hourly bars with 6 PM to 9 PM flagged and 7 PM selected; selected-interval card (names appliances you listed that could explain it); flagged-today card | Today is Friday; 7:00 to 7:15 PM is 0.65 kWh, an average of 2.6 kW, usual 0.27 kWh, about 2.4 times |
| Heatmap | Grid of four time blocks by seven days with letters L, M, H, P plus a legend and caption | Heaviest hours 6 to 9 PM |
| Breakdown | Estimated-share bars from the appliances the customer listed and the meter total, a "likely biggest user" line, an estimate disclaimer, and an Edit my appliances button | Aircon 41.2%, refrigerator 8.5%, lighting 2.4%, TV and computer 4.7%, everything else 43.2% |
| Appliances | List of the customer's appliances with type, rated power, hours, estimated weekly kWh and share, Edit and Delete buttons, an Add appliance button, a "what your list explains" card, and a change-history card | Aircon 48.8, refrigerator 10.1, lighting 2.8, TV and computer 5.6 kWh a week; 67.3 of 118.4 kWh explained (56.8%) |
| Edit appliance | Form with name, type, rated power in watts, how many, percent of the time at full power, hours per day, days per week, and optional notes; an impact preview (before and after); Save and Cancel | Aircon hours 4.5 to 6: 48.8 to 65.1 kWh a week (41.2% to 55.0%); coverage 56.8% to 70.6% |
| Remove appliance | Two choices, "I no longer have it" (past weeks keep it) and "I added it by mistake" (removed from every week), plus Keep it; readings not affected | Danger-colored mistake button |
| Add appliance | Blank form with placeholders and rules, a prompt to fill it in for the impact preview, Add and Cancel | Nothing is saved |
| Alerts | Inbox of cards with tier pills and "This is normal" | Watch (appliance left running, today); Info (lower usage, Sunday); Info (2 missing readings, Thursday); Info (still learning your usual pattern, about 14 days of readings needed) |
| Story | Narrative paragraph; English button and a dimmed "Filipino (planned)" button; Biggest drivers card; How this was checked card | Text uses only fact-sheet numbers |
| Consent (first run) | Plain explanation; one required checkbox for usage and alerts in the app; SMS or push and neighborhood comparison shown as planned and disabled; retention note; "Agree and continue" and "Not now" | Nothing is saved |
| Settings | In-app alerts toggle; SMS or push and quiet hours planned; language; sounds and motion; Download my data, Delete my sample data and appliances, Withdraw consent | Opened from the top bar |
| Safe mode (customer view) | Dark card "Temporarily paused for safety", read-only last saved usage, no technical detail | 118.4 kWh sample |
| Sign in (User tab) | Username and password, generic error line, consent on first sign-in, Back to home; "Open sample portal" on the landing page leads here | Sample credentials only |
| Sign in (Admin tab) | Same page design with a one-time code field and a "reviewers and administrators only" notice | Sample credentials only |
| Review queue (admin) | Banner "Never shown to customers"; Lead A and Lead B in "pattern consistent with" wording with confidence and status; protection status card; sign out | Admin only |

## 5. Sample data and tie-outs (single source of truth)
| Item | Values | Check |
|---|---|---|
| Daily kWh Mon to Sun | 15.2, 16.0, 17.1, 18.4, 19.9, 16.4, 15.4 | Sum 118.4 |
| Week change | 118.4 vs 84.7 | (118.4 - 84.7) / 84.7 = 39.8% |
| Hourly kWh for Friday | 0.2, 0.3, 0.3, 0.3, 0.3, 0.4, 0.6, 0.8, 0.7, 0.5, 0.5, 0.6, 0.7, 0.7, 0.8, 0.8, 0.9, 1.2, 2.4, 2.6, 2.3, 1.0, 0.6, 0.4 | Sum 19.9 = Friday's daily value |
| Interval | 0.65 kWh in 15 minutes | 0.65 / 0.25 = 2.6 kW; 0.65 / 0.27 = about 2.4 times usual |
| Declared appliances | Aircon 1.55 kW x 1 x 100% x 4.5 h x 7 days = 48.825 kWh; Refrigerator 0.15 kW x 40% x 24 h x 7 = 10.08; Lighting 0.008 kW x 10 x 5 h x 7 = 2.8; TV and computer 0.2 kW x 4 h x 7 = 5.6 | Sum 67.305 kWh; 67.305 / 118.4 = 56.8% explained |
| Shares | 41.2, 8.5, 2.4, 4.7, and 43.2 for everything else (118.4 - 67.305 = 51.095) | Sum 100.0 |
| What-if checks | Aircon 6 h: 65.1 kWh, 55.0%, coverage 70.6%; Thursday change: 58.125 kWh, 49.1%; add a washing machine: 1.5 kWh, 1.3%; remove the aircon: 84.4% unexplained | appliances-and-mysql.md section 4 |
| Temperatures | 34.6 and 31.2 degrees C | Difference 3.4 (the story shows both, not the difference) |
| Alert counts | 2.4 times, 3 days in a row, 2 missing readings | Placeholders; any change must also change the fact sheet |
| Admin samples | Lead A: lower night usage for 3 weeks, confidence medium; Lead B: drifting from comparable homes, confidence low; protection level Normal; 3 throttled requests, 0 blocked sources, 0 integrity alerts | Placeholders; admin only |
Bar heights: 6 px per kWh for daily bars; 44 px per kWh for hourly bars. After any number changes, update every place it appears and rerun these checks.

## 6. Visual tokens and measured contrast
| Role | Color | Notes |
|---|---|---|
| Ink (text, dark surfaces) | #10213a | 16.15 to 1 on white |
| Page background | #eef2f7 | Ink on it 14.36 to 1; secondary text #475569 on it 6.74 to 1 |
| Accent (buttons, active nav, highlights) | #fbbf24 | Ink on it 9.67 to 1; on ink 9.67 to 1 |
| Active nav fill | #24456f | Yellow on it 5.84 to 1 |
| Flagged bars | #c2410c with cap #7c2d12 | 5.18 to 1 on white; 1.65 to 1 against normal bars; cap against bar 1.81 to 1 |
| Normal bars | #7c93b5 | 3.14 to 1 on white |
| Heatmap cells | L #e2e8f0, M #bfd0e8, H #7c93b5, P #f97316 | Ink letters on them: 13.10, 10.30, 5.15, 5.76 to 1 |
| Sample note and chip | text #6b4200 on #fff4d6 | 7.97 to 1 |
| Pills | #8a3a07 on #ffedd5; ink on #e2e8f0 | 6.82 and 13.10 to 1 |
| Footer text | #b8c5da on #0b1830 | 10.14 to 1 |
Known limits: the heatmap orange cell and blue cell differ mostly by hue (1.12 to 1), so the letters L, M, H, P carry the meaning; bottom-nav labels are 11 px, below the 12 px guideline, so use 12 px in the real build. Type: system font stack; landing headline fluid from 32 to 56 px; screen titles 26 px; body 15 to 17 px.

## 7. Technique and limits
Screens switch with hidden radio inputs and labels, and panels appear through the checked-sibling selector; no script runs. Keyboard: arrow keys move between screens. Limits: labels are not tab stops, there are no deep links, no state, no loading or error states; it exists to show design, not to be production code. Icons are inline strokes; there are no external fonts or images. Motion is CSS only (screen enter, staggered bars and ring segments, a flagged pulse twice, a line draw, press and hover feedback, a reduced-motion rule); no sound or script runs (experience.md section 9).

## 8. Revising
Make small edits for text and colors; keep the sample banner and disclaimers; keep the tie-outs in section 5 true after any number change; add a screen as a panel plus a navigation item plus a tile. Ask the user to report any tab that does not switch; do not claim it works unseen.

## 9. From prototype to build
| Screen | Real data source (model-spec.md) | Notes |
|---|---|---|
| Landing | None (public entry route) | Real links and buttons instead of label tricks |
| Dashboard | Weekly rollups; latest alert | Compare with the customer's own history |
| Day Explorer | Interval readings by day; flagged windows | 15-minute detail on tap; units kWh and kW labeled |
| Heatmap | Hour-by-day rollups | Text alternative |
| Breakdown | Appliance estimates from the customer's own entries and the meter total (appliances-and-mysql.md section 4) | Labeled estimate; no disaggregation claim |
| Appliances | The appliances registry and its effective-dated versions (appliances-and-mysql.md sections 2 to 4) | Add, edit, retire or remove with validation, preview, history, and audit |
| Alerts | Alert records for the customer audience only | Never theft language; "This is normal" feeds customer alerts only |
| Story | Fact sheet and validated narrative | Template fallback; English first |
Missing in the prototype and needed in the build: routing, authentication or access control, consent capture, loading, empty and error states, language switching, real charts, accessibility testing, and tests.

## 10. Gaps and Optional additions
Remaining gaps: tariff entry for the projected bill; a "same hour last week" overlay; 15-minute zoom; a help page; Filipino text reviewed by a fluent speaker; larger nav labels; empty, loading, and error states. Suggest at most three at a time and add only when the user asks.
