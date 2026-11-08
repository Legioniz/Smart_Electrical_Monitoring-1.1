# Design guide: mobile-first customer portal

Contents: 1 Principles; 2 Screens; 3 Layout by device; 4 Charts; 5 Alerts and copy; 6 Accessibility; 7 Visual identity; 8 Review checklist

In allowed mode (coding unconfirmed) a design sketch may use static placeholder values, clearly labeled as sample, and must not be wired to logic.

## 1. Principles
- Most customers arrive from a notification on a phone, so every screen must make sense in one thumb-length scroll.
- Always answer what happened, why, and what to do. Compare against the customer's own history, never against strangers.
- Plain language: "usage", not "load profile". Never blame the customer.
- Show the simulated-data label wherever sample data appears.
- No Meralco logo and nothing implying endorsement or partnership.

## 2. Screens (from the proposal)
| Screen | Shows | Example plain-language line (illustrative) |
|---|---|---|
| Dashboard | This period's usage, change versus last period, projected bill only if a tariff is supplied | "You're on track to use about the same as last month." |
| Day Explorer | 15-minute chart with flagged intervals and an inline reason chip | "Something ran longer than usual this evening." |
| Heatmap | Hour by day grid | "Your heaviest hours are 6 to 9 PM." |
| Breakdown | Estimated share by appliance category, labeled estimate | "Aircon is likely your biggest user." |
| Alerts Inbox | Info, Watch, and customer-appropriate Critical items with reasons | "We noticed a spike on Tuesday. Here's why." |
| Monthly Story | Narrative plus the top drivers, English or Filipino | One short paragraph built from the fact sheet |
A landing page opens first and leads into these screens; the full specification, sample data, and tokens are in prototype.md, which also covers the Appliances, sign-in, consent, Settings, safe-mode, and admin screens.
An internal ops view for theft leads is Optional, access-controlled, and never shown to customers.

## 3. Layout by device
| Device | Width to test | Layout |
|---|---|---|
| Phone | 360 px minimum | One column; bottom tab bar with icons and short labels (one per main screen); metrics in 2 columns; charts full width with a day or zoom control; tap targets at least 44 px |
| Tablet | about 768 px | Two-column cards; wider chart; table-style alert list |
| Desktop | 1280 px and up | Left sidebar; dashboard cards in a grid; chart with side detail panel |
Use the framework's responsive utilities and fluid widths; no fixed pixel page widths. The page never scrolls sideways. Test at 360, 768, and 1280 px.

## 4. Charts
- 15-minute series (96 points per day): show one day at a time, with previous and next controls; offer "same hour last week" overlay as an optional comparison.
- Label axes with units: energy per 15-minute interval in kWh, or average power in kW; do not mix them on one axis.
- Bars or lines start from zero where comparing amounts.
- Flagged intervals use color plus a shape or label; hover or tap shows the plain-language reason.
- Heatmap: hour by day with a legend and values on tap; do not rely on color alone.
- Each chart has a text alternative summarizing what it shows.
- Empty, loading, and error states are designed, not blank.
- Sample data carries a visible simulated label.

## 5. Alerts and copy
Alert card: tier label (Info, Watch, Critical) in words, one plain sentence on what changed with numbers from the fact sheet, a short why, and one suggested action about energy use only. Never use theft or accusation language in customer-facing text. Offer a one-tap "this is normal" feedback on customer alerts. Keep SMS and push text within the channel's length cap. A safe-mode screen says "Temporarily paused for safety", shows existing data read-only, and gives no technical detail.

## 6. Accessibility
Contrast at least 4.5:1 for text and meaningful data colors (WCAG AA, per the proposal); a color-blind-safe palette; red never the only signal; readable at 360 px; text alternatives for charts; touch targets of at least 44 px; no hover-only information; language setting respected.

## 7. Visual identity
Default: the ink, yellow, and deep-orange palette in prototype.md section 6, with measured contrast ratios. Flagged and normal states must differ in lightness as well as hue, and carry a text label or shape. Use one system font stack and the type scale in prototype.md. The team may change the palette on request; recompute contrast after any change. The experience layer (identity, complex visuals, motion, sound) is in experience.md.

## 8. Review checklist
Can a customer grasp the main message in ten seconds? Are units correct? Does it hold at 360, 768, and 1280 px? Any sideways scroll? Any tap target under 44 px? Is sample data labeled? Is any number not from the fact sheet? Is any theft language visible to customers? Does every control work, or is it removed or disabled with a reason?
