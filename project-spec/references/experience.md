# Experience design: identity, complex visuals, motion, and sound

Contents: 1 Scope and sources; 2 Identity; 3 Complex visuals made friendly; 4 Motion system; 5 Sound system; 6 Seamless flow; 7 Accessibility and performance; 8 Tests; 9 Prototype coverage; 10 Optional and Unknown

## 1. Scope and sources
Requirement (Brief v11, change C13): a complex but friendly front end with animations and sound effects on interactions and actions, with a unique identity. Planning (and the CSS-only prototype) until the coding gate is confirmed.
Verified (checked 2026-10-30):
- WCAG 2.2: Audio Control 1.4.2 (Level A): audio that plays automatically for more than 3 seconds needs a way to pause, stop, or control its volume. Pause, Stop, Hide 2.2.2 (A): moving or auto-updating content that starts automatically, lasts more than 5 seconds, and sits beside other content needs a pause, stop, or hide control. Three Flashes 2.3.1 (A): no more than three flashes in any one second. Animation from Interactions 2.3.3 (AAA): interaction-triggered motion can be disabled unless essential. The prefers-reduced-motion media query exposes the user's setting.
- MDN, Web Audio: create or resume an AudioContext inside a user gesture; a context created outside one starts suspended; give users sound control (play or stop, volume, mute).
- Chrome for Developers: same-document View Transitions work in Chrome and Edge 111 and Safari 18, and Firefox 144; another source gives a different Firefox version, so check MDN or caniuse at build time. Reports on scroll-driven animations in non-Chromium browsers conflict (Unknown). Feature-detect and keep a fallback for every enhancement.
Likely: animate only transform and opacity for smooth, compositor-friendly motion; keep UI feedback near 100 ms.

## 2. Identity ("Pulse", a working name)
- Concept: a home's electricity as a heartbeat. Motifs: the Pulse Ring (24-hour radial chart), the pulse line that draws in on the landing hero, and a yellow glow used only for what needs attention.
- Surfaces: calm dark panels for focus, light surfaces for reading; tokens and contrast ratios are in prototype.md section 6.
- Voice: plain, warm, never blaming.
- Signature components: Pulse Ring (built in the prototype); Energy Ribbon, a horizontal day timeline with a scrubber (Optional); what-if morph, where an appliance control morphs the share bars (Optional); shared-element transition from an appliance card to its Breakdown bar (Optional, needs View Transitions with a fallback).
- Unique must not mean confusing: every novel visual has a plain table or text alternative, direct labels, and units.

## 3. Complex visuals made friendly
- Progressive disclosure: the default view is one big number and one sentence; details open on tap.
- One hero visual per screen; at most about 25 elements animate at once, staggered in three groups.
- Every chart has a "Show as a table" view and a text summary. The Pulse Ring starts at 12 AM at the top and runs clockwise; segment length is proportional to kWh with a maximum set from the data (never hardcoded); four anchor labels (12 AM, 6 AM, 12 PM, 6 PM); the centre states the period and total.
- Flagged and normal states differ in lightness, label, and shape, never color alone; yellow means attention and blue means normal everywhere.
- No gesture-only actions; marks reachable by keyboard focus with the value shown on focus (Optional).

## 4. Motion system
| Purpose | Duration | Notes |
|---|---|---|
| Press feedback | 80 to 120 ms | Scale to about 0.97 |
| Hover, focus, toggles | 120 to 200 ms | Hover effects only where hover exists |
| Screens and cards entering | 250 to 300 ms | Ease-out; small rise and fade |
| Data entering (bars, ring) | 500 to 700 ms | Stagger in three groups, 160 ms total offset at most |
| Emphasis pulse | 1.2 s, two cycles | Once per load; never repeating |
| Navigation icon pop | about 300 ms | Once when selected |
| Line draw | about 1.2 s | Landing hero only |
Rules:
- Animate transform and opacity only; never layout properties such as width, height, top, or left.
- Nothing blocks input: every animation is interruptible and controls stay clickable.
- Nothing flashes more than three times a second; no auto-start motion over 5 seconds without a pause control.
- Do not shake elements for errors (it can trigger vestibular symptoms); use a color change, an icon, and text.
- Run entry animations once per mount, not on every data refresh.
- Reduced motion: replace movement with no animation or an opacity fade of 150 ms or less; every state change stays visible through color, outline, or text.
- Loading: skeleton placeholders that match the final layout, with a shimmer that stops after 5 seconds; no layout shift when content arrives.
- Count-up numbers (Optional, needs script): the final value is always in the text for assistive technology; skip under reduced motion.

## 5. Sound system
Principles: sound is an optional enhancement; never the only signal; short, quiet, and consistent; controlled by the user; no autoplay; no external audio assets in local mode (synthesize with Web Audio, or bundle small local files).
Default (decision 20): off until the user turns it on, with a one-time question after first sign-in and a mute that is always one tap away. The user may choose on-by-default.
Start the audio context only after the first user gesture (Verified). Play nothing while the tab is hidden (Likely). Limit to one sound per 150 ms and merge bursts.
Controls: master mute (remembered), volume, and a test button; separate toggles for interaction sounds and alert chimes.
Sound set (indicative design targets, to be tuned by ear on real speakers; loudness standard Unknown):
| Event | Character | Indicative spec |
|---|---|---|
| Tap or toggle | Soft tick | Sine or triangle near 1.2 kHz, about 30 ms, gain 0.04 or less |
| Screen change | Short glide | Sine gliding 200 to 400 Hz over about 90 ms, gain 0.03 or less |
| Added or saved | Two rising notes | About 523 then 784 Hz, 80 ms each, gain 0.06 or less |
| Removed or retired | Soft falling pair | About 440 then 330 Hz, 80 ms each, gain 0.05 or less |
| Error or blocked | One low tone | Triangle near 180 Hz, about 120 ms, gain 0.06 or less, never a buzz |
| Alert arrives (Watch) | Gentle two-tone chime | About 880 then 660 Hz, under 0.3 s, gain 0.07 or less; at most twice for a Critical customer alert |
| Safe mode | No sound | Visual only, to avoid alarm |
No sound lasts over 3 seconds. No sound is ever triggered by untrusted text, and no user-supplied audio is played. No microphone use.

## 6. Seamless flow
- A persistent shell: navigation and the top bar stay mounted; screens transition in 300 ms or less; scroll position and focus return when going back.
- Optimistic updates only for low-risk, reversible actions such as switching a tab. For consent, sign-in, deletion, and security actions show "saving", then success feedback only after the server confirms.
- Errors appear inline with a retry; focus moves to the error or dialog and returns afterward.
- An Undo toast for retiring an appliance is Optional.
- No dead controls: every control works, or is removed or disabled with a reason.

## 7. Accessibility and performance
- All contrast, target-size, keyboard, and text-alternative rules in design.md and prototype.md apply to every animated or sound-enabled element.
- A "calm mode" setting turns motion and sound off together.
- Performance targets are Unknown until measured: record interaction latency, frame rate on the demo laptop and a mid-range phone, and layout shift, using the browser's performance tools.

## 8. Tests
| Area | Cases |
|---|---|
| Reduced motion | With the device setting on, nothing moves and all content and states stay visible |
| Flashing | No element flashes more than three times a second |
| Input during animation | A click during any animation still works |
| Sound defaults | Off by default; starts only after a user gesture; mute persists across reloads; volume cap holds; rate limit holds; nothing plays while the tab is hidden |
| No autoplay | Nothing plays on load |
| Alternatives | Every chart has a table view and text summary; the Pulse Ring is readable by keyboard and screen reader |
| Confirmation | Consent, sign-in, deletion, and security actions show success only after the server confirms |
| Layout shift | No layout shift when skeletons are replaced |
| Visual regression | Screenshots at 360, 768, and 1280 px with animations disabled |
| Performance | A trace shows only transform and opacity animating |

## 9. Prototype coverage (CSS only; not opened by Claude)
Included: screen enter animation; staggered bar and ring growth; a flagged pulse twice; the landing line draw; press and hover feedback; a navigation icon pop; a reduced-motion rule; the ring with a table view; Settings rows for interface sounds (off, disabled) and reduced motion. Not included: sound, count-up, view transitions, skeleton loaders, and anything that needs script; those wait for coding to be allowed.

## 10. Optional and Unknown
Optional: Energy Ribbon, what-if morph, shared-element transitions, scroll-driven reveals, count-up numbers, haptics (off by default), an Undo toast. Unknown: animation and audio library choices, browser support at build time, the default sound state, the sound loudness standard, and performance targets.
