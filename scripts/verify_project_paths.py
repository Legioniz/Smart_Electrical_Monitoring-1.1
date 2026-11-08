#!/usr/bin/env python3
"""Check local documentation, HTML, JS imports, and frontend script paths."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def _inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def _check_file(errors: list[str], path: Path, source: str) -> None:
    if not path.is_file():
        errors.append(f"{source}: missing file: {path.relative_to(ROOT) if _inside_root(path) else path}")


def verify() -> list[str]:
    errors: list[str] = []

    # Markdown links must resolve relative to the document that contains them.
    for doc in [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md"), *ROOT.glob("project-spec/**/*.md")]:
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8")
        for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
            raw = match.group(1).strip().split()[0].strip("<>")
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc or raw.startswith(("#", "mailto:")):
                continue
            target_text = unquote(parsed.path)
            if not target_text:
                continue
            target = (doc.parent / target_text).resolve()
            if not _inside_root(target):
                errors.append(f"{doc.relative_to(ROOT)}: link escapes project root: {raw}")
            elif not target.exists():
                errors.append(f"{doc.relative_to(ROOT)}: broken local link: {raw}")

    # Exact HTML entry points and static assets.
    checks = [
        (ROOT / "web/index.html", r'href="/styles\.css"', ROOT / "web/styles.css"),
        (ROOT / "web/index.html", r'src="/app\.js"', ROOT / "web/app.js"),
        (ROOT / "frontend/index.html", r'src="/src/main\.jsx"', ROOT / "frontend/src/main.jsx"),
        (ROOT / "frontend/src/main.jsx", r"from ['\"]\./App\.jsx['\"]", ROOT / "frontend/src/App.jsx"),
        (ROOT / "frontend/src/main.jsx", r"import\s+['\"]\./index\.css['\"]", ROOT / "frontend/src/index.css"),
    ]
    for source_path, pattern, target in checks:
        source = source_path.read_text(encoding="utf-8") if source_path.is_file() else ""
        if not source_path.is_file():
            errors.append(f"Missing entry point: {source_path.relative_to(ROOT)}")
        elif not re.search(pattern, source):
            errors.append(f"{source_path.relative_to(ROOT)}: expected asset reference not found: {pattern}")
        _check_file(errors, target, source_path.relative_to(ROOT).as_posix())

    # Resolve explicit relative imports in frontend JavaScript/JSX modules.
    for source_path in [*ROOT.glob("frontend/**/*.js"), *ROOT.glob("frontend/**/*.jsx")]:
        source = source_path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?:from\s*|import\s*)['\"](\.[^'\"]+)['\"]", source):
            raw = match.group(1)
            target = (source_path.parent / raw).resolve()
            candidates = [target, target.with_suffix(".js"), target.with_suffix(".jsx"), target.with_suffix(".css"), target / "index.js", target / "index.jsx"]
            if not any(item.is_file() for item in candidates):
                errors.append(f"{source_path.relative_to(ROOT)}: unresolved local import: {raw}")

    # npm scripts that invoke project-owned scripts must resolve.
    package_path = ROOT / "frontend/package.json"
    if package_path.is_file():
        package = json.loads(package_path.read_text(encoding="utf-8"))
        scripts = package.get("scripts", {})
        for script_name, command in scripts.items():
            for relative in re.findall(r"(?:python|node)\s+(\.\.?/[^\s;&]+)", command):
                target = (package_path.parent / relative).resolve()
                if not target.is_file():
                    errors.append(f"frontend/package.json script '{script_name}' references missing path: {relative}")

    vite_config = ROOT / "frontend/vite.config.js"
    if vite_config.is_file():
        vite_source = vite_config.read_text(encoding="utf-8")
        if "../web/dist" not in vite_source:
            errors.append("frontend/vite.config.js: build output no longer targets web/dist")
        if "'/api'" not in vite_source and '"/api"' not in vite_source:
            errors.append("frontend/vite.config.js: development API proxy is missing")
    else:
        errors.append("Missing frontend build configuration: frontend/vite.config.js")

    # The API must serve the fallback assets that the fallback entry point requests.
    main_path = ROOT / "sme/main.py"
    main_source = main_path.read_text(encoding="utf-8") if main_path.is_file() else ""
    if 'ROOT / "web" / asset_path' not in main_source or 'ROOT / "web" / "index.html"' not in main_source:
        errors.append("sme/main.py: fallback asset FileResponse path is missing or changed; verify web/ is served")
    if not (ROOT / "sme/main.py").is_file():
        errors.append("Missing API entry point: sme/main.py")
    for required in ["launch.py", "compose.yaml", "sme/paths.py", "scripts/path_registry.py", "scripts/system_diagnostics.py", "scripts/train_synthetic_baseline.py", "scripts/configure_local_llm.py", "docs/DATA_STORAGE_DECISIONS.md", "learning/README.md"]:
        if not (ROOT / required).is_file():
            errors.append(f"Missing launcher/runtime support file: {required}")

    return errors


def main() -> int:
    errors = verify()
    if errors:
        print("PROJECT PATH VERIFICATION: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1
    print("PROJECT PATH VERIFICATION: PASS")
    print(" - Local Markdown links resolve")
    print(" - Fallback and React entry-point assets exist")
    print(" - Relative frontend imports resolve")
    print(" - npm scripts reference existing project scripts")
    print(" - API fallback static-file mount is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
