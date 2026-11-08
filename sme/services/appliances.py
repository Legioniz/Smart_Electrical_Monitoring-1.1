from __future__ import annotations

import re
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Iterable

from fastapi import HTTPException

CATEGORIES = {
    "air_conditioner": "Air conditioner",
    "refrigerator": "Refrigerator",
    "lighting": "Lighting",
    "water_heater": "Water heater",
    "washing_machine": "Washing machine",
    "electronics": "Electronics",
    "cooking": "Cooking",
    "fan": "Fan",
    "other": "Other",
}
MAX_APPLIANCES = 30


def validate_appliance(data: dict) -> dict:
    allowed = {"name", "category", "rated_power_w", "quantity", "duty_pct", "hours_per_day", "days_per_week", "notes"}
    unknown = set(data) - allowed
    if unknown:
        raise HTTPException(422, detail={"code": "validation_failed", "message": f"Unknown field: {sorted(unknown)[0]}"})
    name = str(data.get("name", "")).strip()
    if not 1 <= len(name) <= 60 or any(ord(ch) < 32 for ch in name):
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Appliance name must be 1–60 characters without control characters."})
    category = data.get("category")
    if category not in CATEGORIES:
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Choose a category from the supplied list."})
    try:
        rated = Decimal(str(data.get("rated_power_w")))
        duty = Decimal(str(data.get("duty_pct", 100)))
        hours = Decimal(str(data.get("hours_per_day")))
        quantity = int(data.get("quantity", 1))
        days = int(data.get("days_per_week", 7))
    except Exception:
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Enter valid numeric appliance values."})
    if not rated.is_finite() or not Decimal("0") < rated <= Decimal("20000"):
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Rated power must be above 0 and no more than 20,000 W."})
    if not 1 <= quantity <= 99:
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Quantity must be between 1 and 99."})
    if not duty.is_finite() or not 1 <= duty <= 100:
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Duty percentage must be between 1 and 100."})
    if not hours.is_finite() or not 0 <= hours <= 24 or (hours * 4) % 1 != 0:
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Hours per day must be from 0 to 24 in 15-minute steps."})
    if not 1 <= days <= 7:
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Days per week must be between 1 and 7."})
    notes = str(data.get("notes", ""))
    if len(notes) > 200 or any(ord(ch) < 32 and ch not in "\t\n\r" for ch in notes):
        raise HTTPException(422, detail={"code": "validation_failed", "message": "Notes must be 200 characters or fewer."})
    return {
        "name": name,
        "active_name_key": name.casefold(),
        "category": category,
        "rated_power_w": rated.quantize(Decimal("0.01")),
        "quantity": quantity,
        "duty_pct": duty.quantize(Decimal("0.01")),
        "hours_per_day": hours.quantize(Decimal("0.01")),
        "days_per_week": days,
        "notes": notes,
    }


def average_kw(appliance) -> Decimal:
    return (Decimal(appliance.rated_power_w) / Decimal(1000)) * Decimal(appliance.quantity) * (Decimal(appliance.duty_pct) / Decimal(100))


def weekly_kwh(appliance) -> Decimal:
    return average_kw(appliance) * Decimal(appliance.hours_per_day) * Decimal(appliance.days_per_week)


def _largest_remainder_percent(values: list[tuple[str, Decimal]]) -> dict[str, Decimal]:
    total = sum((v for _, v in values), Decimal("0"))
    if total <= 0:
        return {key: Decimal("0.0") for key, _ in values}
    exact = [(key, (value / total) * Decimal("1000")) for key, value in values]
    floors = [(key, int(value.to_integral_value(rounding=ROUND_FLOOR)), value - value.to_integral_value(rounding=ROUND_FLOOR)) for key, value in exact]
    remaining = 1000 - sum(floor for _, floor, _ in floors)
    order = sorted(range(len(floors)), key=lambda i: floors[i][2], reverse=True)
    result_tenths = {key: floor for key, floor, _ in floors}
    for index in order[:remaining]:
        result_tenths[floors[index][0]] += 1
    return {key: (Decimal(tenths) / Decimal(10)).quantize(Decimal("0.1")) for key, tenths in result_tenths.items()}


def breakdown(appliances: Iterable, meter_total_kwh: Decimal | float | None) -> dict:
    appliances = list(appliances)
    if meter_total_kwh is None:
        return {
            "available": False,
            "label": "Meter total not available",
            "items": [{"category": a.category, "category_label": CATEGORIES.get(a.category, "Other"), "name": a.name, "declared_kwh_week": float(weekly_kwh(a).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))} for a in appliances],
            "coverage_pct": None,
        }
    meter_total = Decimal(str(meter_total_kwh))
    if meter_total <= 0:
        return {"available": False, "label": "Meter total not available", "items": [], "coverage_pct": None}
    if not appliances:
        return {"available": True, "label": "Estimated from your entries and meter total; not measured per appliance", "items": [], "coverage_pct": 0.0, "everything_else_pct": 100.0}
    energies = [(a, weekly_kwh(a)) for a in appliances]
    declared = sum((v for _, v in energies), Decimal("0"))
    if declared <= meter_total:
        denom = meter_total
        entries = [(a.id, v) for a, v in energies] + [("everything_else", meter_total - declared)]
        coverage = (declared / meter_total * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        proportional = False
    else:
        denom = declared
        entries = [(a.id, v) for a, v in energies]
        coverage = Decimal("100.0")
        proportional = True
    shares = _largest_remainder_percent(entries)
    items = []
    for appliance, energy in energies:
        items.append({
            "id": appliance.id,
            "name": appliance.name,
            "category": appliance.category,
            "category_label": CATEGORIES.get(appliance.category, "Other"),
            "declared_kwh_week": float(energy.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
            "share_pct": float(shares.get(appliance.id, Decimal("0.0"))),
            "average_kw": float(average_kw(appliance).quantize(Decimal("0.001"))),
        })
    return {
        "available": True,
        "label": "Estimated from your entries and your meter total; not measured per appliance",
        "items": items,
        "coverage_pct": float(coverage),
        "everything_else_pct": float(shares.get("everything_else", Decimal("0.0"))),
        "proportional_shares": proportional,
        "declared_total_kwh": float(declared.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        "meter_total_kwh": float(meter_total.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
    }


def appliance_candidates(appliances: Iterable, observed_kw: float, usual_kw: float) -> list[dict]:
    excess = Decimal(str(max(0, observed_kw - usual_kw)))
    if excess <= 0:
        return []
    output = []
    for appliance in appliances:
        kw = average_kw(appliance)
        if excess * Decimal("0.5") <= kw <= excess * Decimal("1.5"):
            output.append({"category": appliance.category, "category_label": CATEGORIES.get(appliance.category, "Other")})
    return output
