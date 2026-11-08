from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Manila")
UTC = timezone.utc


@dataclass(frozen=True)
class Injection:
    anomaly_type: str
    start_utc: datetime
    end_utc: datetime


@dataclass(frozen=True)
class GeneratedReading:
    interval_start_utc: datetime
    energy_kwh: float
    quality: str = "ok"
    label_type: str | None = None


def generate_meter_series(seed: int = 20261031, days: int = 35, end_local_date: date | None = None):
    """Create deterministic, simulated 15-minute data and explicit ground-truth windows."""
    rng = random.Random(seed)
    end_date = end_local_date or (datetime.now(TZ).date() - timedelta(days=1))
    start_date = end_date - timedelta(days=days - 1)
    readings: list[GeneratedReading] = []
    injections: list[Injection] = []
    injection_specs = [
        ("spike", 6, time(19, 0), time(19, 30)),
        ("sustained_evening_rise", 11, time(18, 0), time(21, 0)),
        ("gradual_drift", 15, time(0, 0), time(23, 45)),
        ("sudden_sustained_drop", 20, time(0, 0), time(23, 45)),
        ("night_floor_collapse", 25, time(1, 0), time(5, 0)),
        ("communication_gap", 29, time(2, 0), time(3, 0)),
    ]
    for anomaly_type, offset, st, en in injection_specs:
        start_local = datetime.combine(start_date + timedelta(days=offset), st, TZ)
        end_local = datetime.combine(start_date + timedelta(days=offset), en, TZ)
        if anomaly_type in {"sustained_evening_rise", "gradual_drift", "sudden_sustained_drop", "night_floor_collapse"}:
            end_local = datetime.combine(start_date + timedelta(days=offset + (2 if anomaly_type in {"sustained_evening_rise", "sudden_sustained_drop", "night_floor_collapse"} else 3)), en, TZ)
        injections.append(Injection(anomaly_type, start_local.astimezone(UTC), (end_local + timedelta(minutes=15)).astimezone(UTC)))

    for day_offset in range(days):
        local_day = start_date + timedelta(days=day_offset)
        is_weekend = local_day.weekday() >= 5
        for slot in range(96):
            local_time = (datetime.combine(local_day, time.min, TZ) + timedelta(minutes=15 * slot))
            hour = slot / 4
            # A repeatable household shape with a morning and evening peak.
            morning = 0.11 if 6 <= hour < 9 else 0.0
            afternoon = 0.045 if 13 <= hour < 17 else 0.0
            evening = 0.22 if 18 <= hour < 22 else 0.0
            night = 0.015 if 0 <= hour < 5 else 0.0
            weekend_factor = 1.08 if is_weekend else 1.0
            daily_energy = (0.105 + morning + afternoon + evening + night) * weekend_factor
            daily_energy += rng.uniform(-0.018, 0.018)
            daily_energy = max(0.008, daily_energy)
            label = None
            if day_offset == 6 and time(19, 0) <= local_time.time() < time(19, 30):
                daily_energy = 1.25 + rng.uniform(0.0, 0.12)
                label = "spike"
            if 11 <= day_offset <= 13 and time(18, 0) <= local_time.time() < time(21, 0):
                daily_energy *= 1.95
                label = "sustained_evening_rise"
            if 15 <= day_offset <= 18:
                daily_energy *= 1 + 0.09 * (day_offset - 14)
                label = "gradual_drift"
            if 20 <= day_offset <= 22:
                daily_energy *= 0.42
                label = "sudden_sustained_drop"
            if 25 <= day_offset <= 27 and time(1, 0) <= local_time.time() < time(5, 0):
                daily_energy = 0.002
                label = "night_floor_collapse"
            if day_offset == 29 and time(2, 0) <= local_time.time() < time(3, 0):
                # Missing intervals are deliberately omitted, not silently imputed.
                continue
            readings.append(
                GeneratedReading(
                    interval_start_utc=local_time.astimezone(UTC).replace(tzinfo=None),
                    energy_kwh=round(daily_energy, 4),
                    quality="ok",
                    label_type=label,
                )
            )
    return readings, injections, {"seed": seed, "days": days, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "source": "synthetic"}
