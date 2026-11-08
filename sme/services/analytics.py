from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Appliance, FactSheet, Meter, Reading
from ..security import new_id, utcnow
from .appliances import breakdown

TZ = ZoneInfo("Asia/Manila")
UTC = timezone.utc


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, TZ)
    end = start + timedelta(days=1)
    return start.astimezone(UTC).replace(tzinfo=None), end.astimezone(UTC).replace(tzinfo=None)


def get_day_readings(db: Session, meter_id: str, day: date) -> list[Reading]:
    start, end = local_day_bounds(day)
    return list(db.scalars(
        select(Reading).where(
            Reading.meter_id == meter_id,
            Reading.interval_start_utc >= start,
            Reading.interval_start_utc < end,
        ).order_by(Reading.interval_start_utc.asc())
    ))


def summarize_day(readings: list[Reading], day: date) -> dict:
    valid_rows = [r for r in readings if r.quality != "missing"]
    total = sum((Decimal(r.energy_kwh) for r in valid_rows), Decimal("0"))
    count = len(valid_rows)
    coverage = Decimal(count) / Decimal(96) * 100
    return {
        "date": day.isoformat(),
        "total_kwh": float(total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        "total_kwh_exact": total,
        "received_intervals": count,
        "expected_intervals": 96,
        "coverage_pct": float(coverage.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        "average_power_kw": float((total / Decimal(24)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
        "partial": count < 96,
    }


def get_period_readings(db: Session, meter_id: str, start_day: date, days: int) -> list[Reading]:
    start, _ = local_day_bounds(start_day)
    _, end = local_day_bounds(start_day + timedelta(days=days))
    return list(db.scalars(
        select(Reading).where(
            Reading.meter_id == meter_id,
            Reading.interval_start_utc >= start,
            Reading.interval_start_utc < end,
        ).order_by(Reading.interval_start_utc.asc())
    ))


def day_explorer_payload(readings: list[Reading], day: date) -> dict:
    by_slot = {((r.interval_start_utc.replace(tzinfo=UTC).astimezone(TZ).hour * 60 + r.interval_start_utc.replace(tzinfo=UTC).astimezone(TZ).minute) // 15): r for r in readings}
    intervals = []
    for slot in range(96):
        row = by_slot.get(slot)
        intervals.append({
            "slot": slot,
            "time": f"{slot // 4:02d}:{(slot % 4) * 15:02d}",
            "energy_kwh": float(row.energy_kwh) if row and row.quality != "missing" else None,
            "average_power_kw": round(float(row.energy_kwh) / 0.25, 3) if row and row.quality != "missing" else None,
            "quality": row.quality if row else "missing",
            # Filled by the API from persisted detector alerts, not generator labels.
            "flagged": False,
            "alert_type": None,
            "alert_tier": None,
            "reason": None,
        })
    summary = summarize_day(readings, day)
    summary.pop("total_kwh_exact", None)
    return {"date": day.isoformat(), "summary": summary, "intervals": intervals, "simulated": True}


def weekly_series(db: Session, meter_id: str, end_day: date, days: int = 7) -> list[dict]:
    start = end_day - timedelta(days=days - 1)
    output = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        output.append(summarize_day(get_day_readings(db, meter_id, day), day))
    return output


def heatmap_payload(db: Session, meter_id: str, end_day: date, days: int = 7) -> dict:
    output = []
    for item in weekly_series(db, meter_id, end_day, days):
        day = date.fromisoformat(item["date"])
        readings = get_day_readings(db, meter_id, day)
        blocks = [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")]
        for row in readings:
            local = row.interval_start_utc.replace(tzinfo=UTC).astimezone(TZ)
            block = min(3, local.hour // 6)
            if row.quality != "missing":
                blocks[block] += Decimal(row.energy_kwh)
        output.append({
            "date": item["date"],
            "coverage_pct": item["coverage_pct"],
            "blocks": [float(v.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) for v in blocks],
        })
    return {"labels": ["00:00–06:00", "06:00–12:00", "12:00–18:00", "18:00–24:00"], "days": output}


def make_fact_sheet(db: Session, customer_id: str, meter_id: str, end_day: date, appliances: list[Appliance]) -> dict:
    current_start = end_day - timedelta(days=6)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    current_readings = get_period_readings(db, meter_id, current_start, 7)
    previous_readings = get_period_readings(db, meter_id, previous_start, 7)
    current_valid = [r for r in current_readings if r.quality != "missing"]
    previous_valid = [r for r in previous_readings if r.quality != "missing"]
    total = sum((Decimal(r.energy_kwh) for r in current_valid), Decimal("0"))
    previous = sum((Decimal(r.energy_kwh) for r in previous_valid), Decimal("0"))
    expected = 7 * 96
    coverage = Decimal(len(current_valid)) / Decimal(expected) * Decimal(100)
    change = None
    if previous > 0 and Decimal(len(previous_valid)) / Decimal(expected) >= Decimal("0.9"):
        change = ((total - previous) / previous * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    app_breakdown = breakdown(appliances, total)
    sorted_by_energy = sorted(app_breakdown.get("items", []), key=lambda x: x.get("declared_kwh_week", 0), reverse=True)
    top = sorted_by_energy[0] if sorted_by_energy else None
    facts = {
        "period_start": current_start.isoformat(),
        "period_end": end_day.isoformat(),
        "total_kwh": float(total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        "previous_total_kwh": float(previous.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        "change_pct": float(change) if change is not None else None,
        "coverage_pct": float(coverage.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        "received_intervals": len(current_valid),
        "expected_intervals": expected,
        "average_power_kw": float((total / Decimal(168)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
        "appliances_count": len(appliances),
        "declared_coverage_pct": app_breakdown.get("coverage_pct"),
        "top_category": top.get("category_label") if top else None,
        "top_share_pct": top.get("share_pct") if top else None,
        "driver": top.get("category_label") if top and app_breakdown.get("coverage_pct", 0) >= 40 else "not enough information",
        "simulated": True,
        "interval_minutes": 15,
    }
    digest = hashlib.sha256(json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"facts": facts, "fact_hash": digest, "coverage_pct": float(coverage), "period_start_utc": local_day_bounds(current_start)[0], "period_end_utc": local_day_bounds(end_day + timedelta(days=1))[0]}


def persist_fact_sheet(db: Session, customer_id: str, built: dict) -> FactSheet:
    record = FactSheet(
        id=new_id(),
        customer_id=customer_id,
        period_start=built["period_start_utc"],
        period_end=built["period_end_utc"],
        version="facts-v1",
        facts=built["facts"],
        fact_hash=built["fact_hash"],
        coverage_pct=Decimal(str(built["coverage_pct"])),
        created_at=utcnow(),
    )
    db.add(record)
    db.flush()
    return record
