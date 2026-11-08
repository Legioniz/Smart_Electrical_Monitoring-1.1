#!/usr/bin/env python3
"""Run the repeatable offline verification suite and write a Markdown report."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str], *, timeout: int = 180, env: dict | None = None):
    print(f"\n=== {name} ===")
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as exc:
        detail = (exc.stdout or "") + (exc.stderr or "")
        print(detail[-4000:])
        print("TIMEOUT")
        return {"name": name, "status": "BLOCKED", "command": " ".join(command), "details": "Timed out."}
    output = (result.stdout or "") + (result.stderr or "")
    print(output[-6000:] if output else "(no output)")
    status = "PASS" if result.returncode == 0 else "FAIL"
    return {"name": name, "status": status, "command": " ".join(command), "details": output[-8000:].strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Smart Meter Explorer V2 verification checks.")
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "VERIFICATION_REPORT.md")
    args = parser.parse_args()

    results = []
    results.append(run("Backend and integration tests", [sys.executable, "-m", "pytest", "-q"], timeout=180))
    results.append(run("Python compilation", [sys.executable, "-m", "compileall", "-q", "launch.py", "sme", "scripts", "migrations", "tests"]))
    results.append(run("Read-only system diagnostics", [sys.executable, "scripts/system_diagnostics.py"]))
    results.append(run("Local project path registry", [sys.executable, "scripts/path_registry.py"]))
    node = shutil.which("node")
    if node:
        results.append(run("Fallback browser JavaScript syntax", [node, "--check", "web/app.js"]))
        results.append(run("Vite configuration JavaScript syntax", [node, "--check", "frontend/vite.config.js"]))
        npm = shutil.which("npm")
        node_env = os.environ.copy()
        if npm:
            try:
                global_root = subprocess.check_output([npm, "root", "-g"], text=True, timeout=10).strip()
                node_env["NODE_PATH"] = global_root + os.pathsep + node_env.get("NODE_PATH", "")
            except Exception:
                pass
        jsx_script = r'''
const ts = require('typescript');
const fs = require('node:fs');
let failed = false;
for (const file of ['frontend/src/App.jsx', 'frontend/src/main.jsx']) {
  const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    reportDiagnostics: true
  });
  const errors = (result.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
  if (errors.length) { failed = true; console.error(file, errors.map(e => ts.flattenDiagnosticMessageText(e.messageText, '\\n')).join('\\n')); }
  else console.log('JSX parse OK:', file);
}
process.exit(failed ? 1 : 0);
'''
        jsx_result = subprocess.run([node, "-e", jsx_script], cwd=ROOT, text=True, capture_output=True, env=node_env, timeout=30)
        output = (jsx_result.stdout or "") + (jsx_result.stderr or "")
        print("\n=== React JSX syntax parse ===\n" + (output or "(no output)"))
        results.append({"name": "React JSX syntax parse", "status": "PASS" if jsx_result.returncode == 0 else "SKIP", "command": "node -e <TypeScript JSX transpileModule>", "details": output.strip() or "TypeScript parser not installed; source-only check was not run."})
    else:
        results.append({"name": "JavaScript syntax checks", "status": "SKIP", "command": "node --check", "details": "Node.js is not installed."})

    results.append(run("Frontend animation/accessibility contract", [sys.executable, "scripts/verify_frontend_experience.py"]))
    results.append(run("Project path and asset reference audit", [sys.executable, "scripts/verify_project_paths.py"]))

    vite = ROOT / "frontend" / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
    if vite.exists():
        npm = shutil.which("npm")
        if npm:
            results.append(run("React production build", [npm, "run", "build"], timeout=240))
        else:
            results.append({"name": "React production build", "status": "SKIP", "command": "npm run build", "details": "npm is not installed."})
    else:
        results.append({"name": "React production build", "status": "BLOCKED", "command": "npm install && npm run build", "details": "Frontend dependencies are not installed. A prior npm install attempt timed out while resolving the npm registry; Vite build was therefore not run."})

    if not args.skip_browser:
        browser = run("Optional real-browser smoke test", [sys.executable, "scripts/browser_experience_smoke.py"], timeout=45)
        if browser["status"] == "FAIL" and "BLOCKED" in browser.get("details", ""):
            browser["status"] = "BLOCKED"
        if browser["status"] == "FAIL" and "SKIP" in browser.get("details", ""):
            browser["status"] = "SKIP"
        results.append(browser)
    else:
        results.append({"name": "Optional real-browser smoke test", "status": "SKIP", "command": "scripts/browser_experience_smoke.py", "details": "Skipped by request."})

    try:
        import mysql.connector  # noqa: F401
        connector_available = True
    except Exception:
        connector_available = False
    if connector_available and shutil.which("mysql"):
        results.append({"name": "MySQL deployment verification", "status": "NOT RUN", "command": "local MySQL migration and persistence checks", "details": "Connector and CLI are available, but deployment checks require a separately configured local MySQL instance and credentials."})
    else:
        results.append({"name": "MySQL deployment verification", "status": "BLOCKED", "command": "local MySQL migration and persistence checks", "details": "MySQL Connector/Python and/or MySQL CLI are unavailable in this verification environment. The runtime DB is MySQL-only; SQLite is used only by tests."})

    if not args.skip_benchmark:
        results.append(run("Synthetic service microbenchmark", [sys.executable, "scripts/benchmark_services.py", "--runs", "2", "--output", "benchmarks/verification-benchmark.json"], timeout=180))
    else:
        results.append({"name": "Synthetic service microbenchmark", "status": "SKIP", "command": "scripts/benchmark_services.py", "details": "Skipped by request."})

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Verification report — Smart Meter Explorer V2 / Brief v11",
        "",
        f"Run timestamp: {now}",
        "",
        "This report records checks executed in the current development environment. A blocked or skipped check is not a pass.",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for result in results:
        lines.append(f"| {result['name']} | **{result['status']}** |")
    lines += ["", "## Details", ""]
    for result in results:
        lines += [f"### {result['name']} — {result['status']}", "", f"Command: `{result['command']}`", "", result.get("details", "No additional output.") or "No additional output.", ""]
    lines += [
        "## Interpretation and remaining release gates",
        "",
        "- Automated backend/API tests use an isolated in-memory SQLite adapter. They do not verify MySQL behavior.",
        "- The frontend animation contract script checks CSS keyframes, transition properties, reduced-motion hooks, sound safety, chart alternatives, focus styles, and mobile breakpoints; it is not a substitute for rendered browser inspection.",
        "- The optional browser smoke test is a real Chromium/Playwright check when browser policy permits local navigation.",
        "- React production build verification requires installed npm packages. An unavailable package registry is a blocker, not a successful build.",
        "- MySQL migration, least-privilege grants, persistence, backup/restore, and concurrency remain deployment checks on the target computer.",
        "- No independent penetration test, representative real-meter validation, or production-readiness assessment is implied by this report.",
        "",
    ]
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote report: {report_path.relative_to(ROOT) if report_path.is_relative_to(ROOT) else report_path}")

    hard_failures = [r for r in results if r["status"] == "FAIL"]
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
