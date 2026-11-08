#!/usr/bin/env python3
"""Dependency-free static verification for the Brief v11 browser experience.

Checks both the no-CDN fallback and optional React source for animation,
reduced-motion, sound-safety, and accessible chart alternatives.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_MOTION_PROPERTIES = {"transform", "opacity"}


def _strip_comments(source: str) -> str:
    return re.sub(r"/\*.*?\*/", "", source, flags=re.S)


def _balanced_block(source: str, open_at: int) -> tuple[str, int]:
    """Return content within the brace at open_at and position after its close."""
    if open_at >= len(source) or source[open_at] != "{":
        raise ValueError("Expected opening brace")
    depth = 0
    for index in range(open_at, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_at + 1:index], index + 1
    raise ValueError("Unclosed CSS block")


def _keyframes(css: str) -> tuple[dict[str, list[set[str]]], list[str]]:
    found: dict[str, list[set[str]]] = {}
    errors: list[str] = []
    for match in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", css):
        name = match.group(1)
        block, _ = _balanced_block(css, match.end() - 1)
        if name in found:
            errors.append(f"duplicate @keyframes definition: {name}")
        frame_props: list[set[str]] = []
        for frame_match in re.finditer(r"(?:from|to|\d+(?:\.\d+)?%|(?:\d+(?:\.\d+)?%\s*,\s*)+\d+(?:\.\d+)?%)\s*\{", block):
            frame, _ = _balanced_block(block, frame_match.end() - 1)
            props = {m.group(1).strip().lower() for m in re.finditer(r"(?:^|;)\s*([a-z-]+)\s*:", frame)}
            frame_props.append(props)
            disallowed = props - ALLOWED_MOTION_PROPERTIES
            if disallowed:
                errors.append(f"{name} animates unsupported properties: {', '.join(sorted(disallowed))}")
        found[name] = frame_props
    return found, errors


def _css_errors(path: Path) -> list[str]:
    css = _strip_comments(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    keyframes, keyframe_errors = _keyframes(css)
    errors.extend(keyframe_errors)
    for match in re.finditer(r"(?<![\w-])animation\s*:\s*([^;}]+)", css):
        value = match.group(1).strip().replace("!important", "").strip()
        if not value or value == "none":
            continue
        animation_name = value.split()[0]
        if animation_name not in keyframes:
            errors.append(f"animation '{animation_name}' has no @keyframes definition")
    for match in re.finditer(r"(?<![\w-])transition\s*:\s*([^;}]+)", css):
        value = match.group(1).strip().replace("!important", "").strip()
        if value == "none":
            continue
        for item in value.split(","):
            animated_property = item.strip().split()[0].lower()
            if animated_property not in ALLOWED_MOTION_PROPERTIES:
                errors.append(f"transition animates unsupported property: {animated_property}")
    reduced = re.search(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{", css)
    if not reduced:
        errors.append("missing prefers-reduced-motion media query")
    else:
        block, _ = _balanced_block(css, reduced.end() - 1)
        if not re.search(r"animation(?:-duration)?\s*:", block):
            errors.append("prefers-reduced-motion does not suppress animation")
        if not re.search(r"transition(?:-duration)?\s*:", block):
            errors.append("prefers-reduced-motion does not suppress transitions")
    if ".reduced-motion" not in css or ".calm-mode" not in css:
        errors.append("missing app-level reduced-motion or Calm Mode selectors")
    if not re.search(r"\.reduced-motion[^{}]*\{[^}]*animation\s*:\s*none", css, re.S):
        errors.append("app-level reduced-motion class does not disable animation")
    if not re.search(r"\.calm-mode[^{}]*\{[^}]*animation\s*:\s*none", css, re.S):
        errors.append("Calm Mode class does not disable animation")
    return errors


def verify() -> list[str]:
    errors: list[str] = []
    frontend_css = ROOT / "frontend/src/index.css"
    fallback_css = ROOT / "web/styles.css"
    frontend_jsx = ROOT / "frontend/src/App.jsx"
    fallback_js = ROOT / "web/app.js"
    for path in (frontend_css, fallback_css, frontend_jsx, fallback_js):
        if not path.exists():
            errors.append(f"missing frontend asset: {path.relative_to(ROOT)}")
    if errors:
        return errors

    for css_path in (frontend_css, fallback_css):
        errors.extend(f"{css_path.relative_to(ROOT)}: {error}" for error in _css_errors(css_path))

    react = frontend_jsx.read_text(encoding="utf-8")
    fallback = fallback_js.read_text(encoding="utf-8")
    optional_defaults = ("soundEnabled", "interactionSounds", "alertChimes", "energyRibbon", "whatIfMorph", "sharedTransitions", "scrollReveals", "countUpNumbers", "haptics", "undoToast")
    settings_options = (*optional_defaults, "reducedMotion", "calmMode")
    react_settings = react[react.find("function SettingsPanel"):] if "function SettingsPanel" in react else ""
    fallback_settings = fallback[fallback.find("async function renderSettings"):] if "async function renderSettings" in fallback else ""
    for name, source, settings_source in (("React", react, react_settings), ("fallback", fallback, fallback_settings)):
        if not settings_source:
            errors.append(f"{name}: Settings component/function was not found")
        for option in optional_defaults:
            if not re.search(rf"{option}\s*:\s*true", source):
                errors.append(f"{name}: optional feature {option} is not enabled by default")
        for option in settings_options:
            if not re.search(rf"toggle\(\s*['\"]{option}['\"]", settings_source):
                errors.append(f"{name}: Settings control for {option} is missing")
        if "visibilitychange" not in source or "document.hidden" not in source or ".suspend()" not in source:
            errors.append(f"{name}: hidden-tab audio suspension is incomplete")
        if "interactionSounds" not in source or "alertChimes" not in source:
            errors.append(f"{name}: sound channels are not independently controlled")
        if not re.search(r"Math\.min\(\s*\.5\s*,\s*Math\.max\(0", source):
            errors.append(f"{name}: audio gain is not clamped to 0–50%")
        if "calmMode" not in source or "reduced-motion" not in source or "calm-mode" not in source:
            errors.append(f"{name}: Calm Mode/reduced-motion preference wiring is missing")
        if "calmMode" not in source or "currentPrefs.calmMode" not in source and "prefs.calmMode" not in source:
            errors.append(f"{name}: Calm Mode does not suppress sound output")
        if re.search(r"if\s*\(\s*(?:merged|next)\.calmMode\s*\)\s*\{[^}]*soundEnabled\s*=\s*false", source):
            errors.append(f"{name}: Calm Mode destructively overwrites the user's saved sound preference")
        if "role=\"group\"" not in source and "role:'group'" not in source:
            errors.append(f"{name}: Pulse Ring lacks a semantic group")
        if "aria-label" not in source or "pulse-segment" not in source:
            errors.append(f"{name}: Pulse Ring hour labels are not exposed")
        if name == "React" and "startViewTransition" not in source:
            errors.append("React: shared transitions are not feature-detected")
        if name == "fallback" and "shared-transitions" not in source:
            errors.append("fallback: shared transition CSS preference is not wired")
        if "navigator.vibrate" not in source:
            errors.append(f"{name}: haptic preference has no capability-gated implementation")
        if "undoToast" not in source or "/restore" not in source:
            errors.append(f"{name}: undo is not connected to the version-checked restore route")
        if "scrollReveals" not in source or "countUpNumbers" not in source:
            errors.append(f"{name}: scroll reveal/count-up preferences are not wired")
        if "soundEnabled" in source and "new Ctx()" not in source and "new Ctx" not in source:
            errors.append(f"{name}: Web Audio context creation is missing")
        if "ensureAudioFromGesture" not in source:
            errors.append(f"{name}: audio is not guarded by a real user gesture")
        if "localStorage" not in source or "PREF_KEY" not in source:
            errors.append(f"{name}: local preference persistence/migration is missing")
        if "volume" not in settings_source or "50" not in settings_source:
            errors.append(f"{name}: 0–50% volume setting is missing")

    if "EnergyRibbon intervals={pulseDay?.intervals || []}" not in react:
        errors.append("React: Energy Ribbon is not integrated into the overview")
    if "getPrefs().energyRibbon?energyRibbon(day)" not in fallback:
        errors.append("fallback: Energy Ribbon is not integrated into both overview/day flow")
    if "document.startViewTransition(paint)" in fallback:
        errors.append("fallback: asynchronous View Transition update can race synchronous event binding")

    # The React charts and fallback charts must each offer non-visual data alternatives.
    for name, source in (("React", react), ("fallback", fallback)):
        if "Show as a table" not in source and "Show hourly table" not in source:
            errors.append(f"{name}: chart table disclosure controls are missing")
        if "aria-expanded" not in source:
            errors.append(f"{name}: chart table controls do not expose expanded state")
        if "caption>" not in source and "<caption>" not in source:
            errors.append(f"{name}: data tables are missing captions")
        if "aria-live" not in source and "role=\"status\"" not in source:
            errors.append(f"{name}: no live region/status feedback found")

    # Every synthesized note is brief; delays must not create a long sound sequence.
    duration_values = [int(v) for v in re.findall(r"(?:duration|ms)\s*:\s*(\d+)", react + "\n" + fallback)]
    if not duration_values:
        errors.append("no explicit synthesized tone durations found")
    elif max(duration_values) >= 3000:
        errors.append(f"synthesized tone duration is too long: {max(duration_values)} ms")

    # Both layouts should include narrow viewport rules and a visible keyboard focus state.
    for path in (frontend_css, fallback_css):
        css = path.read_text(encoding="utf-8")
        if not re.search(r"@media\s*\(max-width\s*:\s*680px\)", css):
            errors.append(f"{path.relative_to(ROOT)}: missing mobile breakpoint")
        if ":focus-visible" not in css:
            errors.append(f"{path.relative_to(ROOT)}: missing visible keyboard focus styles")
    if "tabIndex=\"0\"" not in react and "tabindex=\"0\"" not in fallback:
        errors.append("Pulse Ring segments are not keyboard-focusable")
    return errors


def main() -> int:
    errors = verify()
    if errors:
        print("FRONTEND EXPERIENCE VERIFICATION: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1
    print("FRONTEND EXPERIENCE VERIFICATION: PASS")
    print(" - CSS keyframes and transitions only animate transform/opacity")
    print(" - No duplicate/missing keyframes")
    print(" - OS reduced-motion and app Calm Mode are wired")
    print(" - Optional experience features default on; sound is gesture-gated, bounded, channelled, and suspended in hidden tabs")
    print(" - Pulse Ring and charts expose keyboard/text/table alternatives")
    print(" - Mobile breakpoints and visible keyboard focus styles are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
