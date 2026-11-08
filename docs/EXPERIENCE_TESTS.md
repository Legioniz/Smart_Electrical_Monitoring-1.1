# Brief v11 experience verification

This checklist is deliberately separate from code-level tests. Do not mark an item complete until it has been exercised in a real browser on the target computer.

| Test | Procedure | Expected result | Status in this build environment |
|---|---|---|---|
| Default sound state | Clear both `sme.pulse.preferences.v1` and `.v2` local-storage keys and sign in | Interface sound is enabled at 22% default volume, but no sound plays until an explicit user gesture | Source/static checks passed; browser audio test not run |
| Direct-gesture audio | With default sound enabled, perform a user interaction; then reload without interaction | AudioContext is created/resumed only from the real gesture; no sound plays on load | Source/static checks passed; browser audio test not run |
| Master mute | Turn Sound off in the persistent topbar control | Interaction and alert sounds stop immediately; visible confirmation remains | Code reviewed; browser audio test not run |
| Separate channels | Disable interaction sounds, then trigger an interaction and a new-alert event; repeat with alert chimes disabled | Each preference controls only its own channel | Code reviewed; browser audio test not run |
| Hidden tab | Enable sound, switch to another tab, then return | AudioContext is suspended while hidden; no hidden-tab chime is played | Code reviewed; browser audio test not run |
| Volume | Test at 0%, 25%, and 50% | 0% is silent; higher values remain modest; UI volume cannot exceed 50% | Code reviewed; acoustic test not run |
| Tone length | Trigger each tone and measure/observe its duration | Every synthesized tone sequence is below 3 seconds | Code reviewed; acoustic test not run |
| Server-confirmed feedback | Trigger consent, settings save, data deletion, and sign-out | Visible status changes only after successful server response; sound never blocks or substitutes for it | Code reviewed; end-to-end test not run |
| Reduced motion OS setting | Enable `prefers-reduced-motion` in the browser/OS | Screen/card/ring/line/alert animations stop; all data remains visible | CSS implementation reviewed; browser test blocked |
| Reduced motion app setting | Enable Reduce motion in Settings | App suppresses movement and transitions on subsequent views | Code reviewed; browser test blocked |
| Calm Mode | Enable Calm Mode | Motion, interface sound, and haptics switch off together; saved volume/channel values remain available when Calm Mode is disabled | Source/static checks passed; browser test blocked |
| Input during animation | Change fields, submit forms, and navigate immediately after a screen appears | Inputs respond without waiting for the 280 ms transition | Timing/code review only; browser test not run |
| Pulse Ring keyboard | Tab through hourly segments; use a screen reader to inspect labels | Each hour is focusable and announces hour, kWh, coverage, and alert status; table presents the same values | Markup review only; browser test blocked |
| Chart alternatives | Open weekly, day, heatmap, and Pulse Ring table alternatives | Data is available without relying on color/visual perception | Markup review only; browser test blocked |
| Responsive layout | Check 360, 390, 768, and 1280 px viewports | No page-level horizontal overflow; tables may scroll within their own wrappers | Browser test blocked |
| Navigation restore | Scroll a screen, navigate away, return, then use Back to home | Main shell remains mounted; scroll and focus return to the destination heading/position | Code review only; browser test blocked |

## Environment limitation

An automated Chromium smoke test was attempted during this update. The container's browser policy rejected both local HTTP and `file://` navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`, so the interactive browser checks could not be completed here. This is an environment restriction, not evidence of an application failure or a passing test.


## Automated checks added in the V11 verification pass

Run `python scripts/verify_frontend_experience.py` to validate the source-level contract for both the React interface and no-CDN fallback. It checks unique and resolvable keyframes, transform/opacity-only motion, reduced-motion and Calm Mode selectors, sound defaults and channel/suspension guards, hourly ring labels, chart table alternatives, live feedback regions, focus visibility, and narrow-screen breakpoints. This is static verification; it cannot prove the actual animation timing, audio output, visual contrast, or assistive-technology behavior.

Run `python scripts/browser_experience_smoke.py` after installing `requirements-browser.txt` and the Playwright Chromium binary to exercise the fallback UI at desktop and mobile viewport widths and verify OS/app reduced-motion behavior. It uses a separate in-memory test database. Complete the full customer journey and screen-reader checks manually on the target computer.


| Optional enhancements default on | Clear both preference keys in a fresh browser profile and inspect overview, day, and appliance pages | Energy Ribbon, what-if preview, shared transitions, scroll reveals, count-up metrics, haptics, and undo toast start enabled and are individually controllable in Settings | Source/static checks passed; browser test not run |
| Energy Ribbon on overview | Sign in with a customer account and open Overview | The 24-hour ribbon uses the same day's 96 intervals shown in the Pulse Ring | Source check passed; browser test not run |
| Rapid navigation | Navigate Day → Heatmap → Appliances rapidly under slow network throttling | An older response never replaces the most recently requested page; loading state remains valid | Request-token code reviewed; browser test not run |
| Fallback navigation with transitions | In no-CDN fallback, enable shared transitions and navigate to Day/Settings/Appliances | Controls bind immediately and remain functional; transition preference gates only the CSS entry motion | Static check passed; browser test not run |
