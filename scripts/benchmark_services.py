from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sme.services.analytics import day_explorer_payload, summarize_day  # noqa: E402
from sme.services.appliances import breakdown  # noqa: E402
from sme.services.detection import DETECTOR_VERSION, detect_events  # noqa: E402
from sme.services.narrative import create_story  # noqa: E402
from sme.services.synthetic import generate_meter_series  # noqa: E402


def measure(callable_, runs: int) -> dict:
    durations = []
    for _ in range(runs):
        started = time.perf_counter()
        callable_()
        durations.append((time.perf_counter() - started) * 1000)
    return {
        "runs": runs,
        "min_ms": round(min(durations), 3),
        "median_ms": round(statistics.median(durations), 3),
        "max_ms": round(max(durations), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline service microbenchmark using only synthetic meter data.")
    parser.add_argument("--runs", type=int, default=3, help="Repetitions per operation (default: 3).")
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--days", type=int, default=35)
    parser.add_argument("--output", type=Path, default=ROOT / "benchmarks" / "service-benchmark.json")
    args = parser.parse_args()
    if args.runs < 1 or args.runs > 20:
        parser.error("--runs must be between 1 and 20")
    if args.days < 18 or args.days > 120:
        parser.error("--days must be between 18 and 120")

    generated = generate_meter_series(args.seed, args.days)
    readings, labels, meta = generated
    latest_utc = max(row.interval_start_utc for row in readings)
    latest_day = latest_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date()
    day_rows = [row for row in readings if row.interval_start_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Manila")).date() == latest_day]
    summary = summarize_day(day_rows, latest_day)
    fake_appliances = [
        SimpleNamespace(id="ac", name="Air conditioner", category="air_conditioner", rated_power_w=Decimal("1550"), quantity=1, duty_pct=Decimal("100"), hours_per_day=Decimal("4.5"), days_per_week=7),
        SimpleNamespace(id="fridge", name="Refrigerator", category="refrigerator", rated_power_w=Decimal("150"), quantity=1, duty_pct=Decimal("40"), hours_per_day=Decimal("24"), days_per_week=7),
    ]
    facts = {
        "total_kwh": 100.0, "previous_total_kwh": 95.0, "change_pct": 5.3,
        "coverage_pct": 99.0, "top_share_pct": 35.0, "average_power_kw": 0.6,
        "declared_coverage_pct": 40.0, "driver": "Cooling", "top_category": "Cooling",
        "period_start": latest_day.isoformat(), "period_end": latest_day.isoformat(),
        "received_intervals": summary["received_intervals"], "expected_intervals": 96,
        "appliances_count": len(fake_appliances), "simulated": True, "interval_minutes": 15,
    }

    results = {
        "metadata": {
            "scope": "CPU-only synthetic service microbenchmark; not a database, browser, or end-to-end benchmark",
            "data_source": "synthetic",
            "seed": args.seed,
            "days": args.days,
            "reading_count": len(readings),
            "synthetic_label_types": sorted({item.anomaly_type for item in labels}),
            "detector_version": DETECTOR_VERSION,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or "not reported",
            "logical_cpu_count": __import__("os").cpu_count(),
        },
        "operations": {},
    }
    results["operations"]["synthetic_generation"] = measure(lambda: generate_meter_series(args.seed, args.days), args.runs)
    results["operations"]["detector_pipeline"] = measure(lambda: detect_events(readings, args.seed), args.runs)
    results["operations"]["day_interval_payload"] = measure(lambda: day_explorer_payload(day_rows, latest_day), args.runs)
    results["operations"]["appliance_estimate_breakdown"] = measure(lambda: breakdown(fake_appliances, Decimal("100")), args.runs)
    results["operations"]["deterministic_narrative"] = measure(lambda: create_story(facts, "en"), args.runs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nSaved benchmark report: {args.output.relative_to(ROOT) if args.output.is_relative_to(ROOT) else args.output}")


if __name__ == "__main__":
    main()
