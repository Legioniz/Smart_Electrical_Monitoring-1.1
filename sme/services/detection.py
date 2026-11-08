from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from statistics import median, mean, pstdev
from typing import Iterable
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Manila")
UTC = timezone.utc
DETECTOR_VERSION = "guardian-v2.3"
SETTINGS_VERSION = "settings-2026-11-a"


@dataclass(frozen=True)
class DetectorEvent:
    anomaly_type: str
    tier: str
    audience: str
    reason_code: str
    reason_text: str
    score: float
    threshold: float
    window_start: datetime
    window_end: datetime
    feature_values: dict


def _local_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).astimezone(TZ)
    return value.astimezone(TZ)


def _rows_by_day(readings: Iterable) -> tuple[dict[date, list], dict[date, dict]]:
    by_day: dict[date, list] = defaultdict(list)
    for row in readings:
        if getattr(row, "quality", "ok") == "missing":
            continue
        local = _local_dt(row.interval_start_utc)
        by_day[local.date()].append((local, float(row.energy_kwh), row))
    summaries = {}
    if not by_day:
        return by_day, summaries
    current = min(by_day)
    end = max(by_day)
    while current <= end:
        rows = by_day.get(current, [])
        evening = [energy for local, energy, _ in rows if time(18, 0) <= local.time() < time(21, 0)]
        night = [energy for local, energy, _ in rows if time(1, 0) <= local.time() < time(5, 0)]
        summaries[current] = {
            "total": sum(energy for _, energy, _ in rows),
            "evening": sum(evening),
            "night": sum(night),
            "count": len(rows),
            "rows": rows,
        }
        current += timedelta(days=1)
    return by_day, summaries


def _window(day: date, start_hour: int = 0, end_hour: int = 23, end_minute: int = 45) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(start_hour, 0), TZ).astimezone(UTC).replace(tzinfo=None)
    end = datetime.combine(day, time(end_hour, end_minute), TZ).astimezone(UTC).replace(tzinfo=None)
    return start, end


def _model_scores(by_day: dict[date, list], seed: int) -> dict:
    """Optional sklearn scores trained only on the first fourteen days."""
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except Exception:
        return {"isolation_forest": "unavailable", "pattern_autoencoder": "unavailable", "point_outliers": 0, "pattern_outliers": 0}
    days = sorted(by_day)
    if len(days) < 18:
        return {"isolation_forest": "cold_start", "pattern_autoencoder": "cold_start", "point_outliers": 0, "pattern_outliers": 0}
    train_days = days[:14]
    scored_days = days[14:]
    train_rows = [item for d in train_days for item in by_day[d]]
    test_rows = [item for d in scored_days for item in by_day[d]]

    def vector(item):
        local, energy, _row = item
        slot = local.hour + local.minute / 60
        return [energy, np.sin(2 * np.pi * slot / 24), np.cos(2 * np.pi * slot / 24), local.weekday(), int(local.weekday() >= 5)]

    x_train = np.asarray([vector(item) for item in train_rows], dtype=float)
    x_test = np.asarray([vector(item) for item in test_rows], dtype=float)
    try:
        forest = IsolationForest(n_estimators=120, contamination=0.025, random_state=seed, n_jobs=1)
        forest.fit(x_train)
        train_scores = -forest.score_samples(x_train)
        test_scores = -forest.score_samples(x_test)
        cutoff = float(np.quantile(train_scores, 0.975))
        point_count = int((test_scores > cutoff).sum())
        forest_state = "scored"
    except Exception:
        point_count, forest_state = 0, "failed"

    def daily_vector(day):
        slots = {local.hour * 4 + local.minute // 15: energy for local, energy, _ in by_day[day]}
        return [slots[slot] for slot in range(96)]

    # Train and score the daily reconstruction model on complete days only.
    # A missing interval is not replaced with a zero-valued observation.
    x_days_train = np.asarray([daily_vector(d) for d in train_days if len(by_day[d]) == 96], dtype=float)
    x_days_test = np.asarray([daily_vector(d) for d in scored_days if len(by_day[d]) == 96], dtype=float)
    try:
        if len(x_days_train) >= 10 and len(x_days_test):
            # A compact linear autoencoder: PCA projection/reconstruction is
            # deterministic, avoids slow iterative MLP convergence, and keeps
            # missing/incomplete days out of training and scoring.
            from sklearn.decomposition import PCA
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            scaled_train = scaler.fit_transform(x_days_train)
            scaled_test = scaler.transform(x_days_test)
            components = max(1, min(8, len(scaled_train) - 1, scaled_train.shape[1]))
            autoencoder = PCA(n_components=components, svd_solver="full", random_state=seed)
            projected_train = autoencoder.fit_transform(scaled_train)
            reconstructed_train = autoencoder.inverse_transform(projected_train)
            reconstructed_test = autoencoder.inverse_transform(autoencoder.transform(scaled_test))
            train_error = np.mean((reconstructed_train - scaled_train) ** 2, axis=1) ** 0.5
            test_error = np.mean((reconstructed_test - scaled_test) ** 2, axis=1) ** 0.5
            cutoff = float(np.mean(train_error) + 2.5 * np.std(train_error))
            pattern_count = int((test_error > cutoff).sum())
            ae_state = "scored"
        else:
            pattern_count, ae_state = 0, "insufficient_days"
    except Exception:
        pattern_count, ae_state = 0, "failed"
    return {
        "isolation_forest": forest_state,
        "pattern_autoencoder": ae_state,
        "point_outliers": point_count,
        "pattern_outliers": pattern_count,
    }


def _complete_calendar_window(daily: dict[date, dict], start: date, length: int, *, min_intervals: int = 80) -> list[date] | None:
    """Return an exact, contiguous calendar window with adequate daily coverage.

    Indexing only the days that happened to contain readings can accidentally
    treat Monday and Wednesday as consecutive days when Tuesday is absent.
    Multi-day persistence and trend rules must use calendar continuity.
    """
    window = [start + timedelta(days=offset) for offset in range(length)]
    if any(day not in daily or daily[day]["count"] < min_intervals for day in window):
        return None
    return window


def detect_events(readings: Iterable, seed: int = 20261031) -> tuple[list[DetectorEvent], dict]:
    rows = list(readings)
    by_day, daily = _rows_by_day(rows)
    dates = sorted(daily)
    if len(dates) < 8:
        return [], {"cold_start": True, "model_scores": _model_scores(by_day, seed)}
    events: list[DetectorEvent] = []

    # Point anomaly: compare each interval only with prior same-slot observations.
    slot_history: dict[int, list[float]] = defaultdict(list)
    spike_found = False
    for day in dates:
        for local, energy, row in sorted(by_day[day], key=lambda x: x[0]):
            slot = local.hour * 4 + local.minute // 15
            history = slot_history[slot][-7:]
            if len(history) >= 5:
                baseline = median(history)
                if energy >= max(0.85, baseline * 2.8) and not spike_found:
                    start = row.interval_start_utc
                    events.append(DetectorEvent(
                        "spike", "INFO", "customer", "isolated_spike",
                        "One 15-minute interval was much higher than the meter's recent pattern.",
                        round(energy / max(baseline, 0.001), 3), 2.8,
                        start, start + timedelta(minutes=15),
                        {"interval_kwh": round(energy, 4), "prior_same_slot_median_kwh": round(baseline, 4), "prior_days": len(history)},
                    ))
                    spike_found = True
            slot_history[slot].append(energy)

    # Sustained evening rise: three actual consecutive calendar days above
    # 1.5x a trailing seven-calendar-day baseline. Missing days are not skipped.
    evening_ratio: dict[date, tuple[float, float]] = {}
    for day in dates:
        prior = [day - timedelta(days=offset) for offset in range(1, 8)]
        baseline_values = [daily[d]["evening"] for d in prior if d in daily and daily[d]["count"] >= 80]
        baseline = median(baseline_values) if len(baseline_values) >= 5 else 0
        ratio = daily[day]["evening"] / baseline if baseline > 0 else 0
        evening_ratio[day] = (ratio, baseline)
    for day in dates:
        block_days = [day - timedelta(days=offset) for offset in (2, 1, 0)]
        if all(d in evening_ratio and daily[d]["count"] >= 80 and evening_ratio[d][0] >= 1.5 for d in block_days):
            ratios = [evening_ratio[d][0] for d in block_days]
            baseline = evening_ratio[day][1]
            start, end = _window(block_days[0], 18, 20, 45)
            events.append(DetectorEvent(
                "sustained_evening_rise", "WATCH", "customer", "evening_load_persisted",
                "Evening usage stayed above its recent pattern for several days.",
                round(min(ratios), 3), 1.5, start, end,
                {"evening_ratio_days": [round(value, 3) for value in ratios], "baseline_kwh": round(baseline, 3), "persistence_days": 3},
            ))
            break

    # Gradual drift: trailing three complete calendar days compared with the
    # seven complete calendar days immediately before them.
    for day in dates:
        recent_days = _complete_calendar_window(daily, day - timedelta(days=2), 3)
        prior_days = _complete_calendar_window(daily, day - timedelta(days=10), 7)
        if not recent_days or not prior_days:
            continue
        baseline = mean(daily[d]["total"] for d in prior_days)
        recent = [daily[d]["total"] for d in recent_days]
        ratio = mean(recent) / max(baseline, 0.001)
        if ratio >= 1.25 and recent[-1] >= recent[0]:
            start, end = _window(recent_days[0])
            events.append(DetectorEvent(
                "gradual_drift", "WATCH", "customer", "consumption_drift",
                "Daily usage has gradually moved above the earlier baseline.",
                round(ratio, 3), 1.25, start, end,
                {"recent_3day_average_kwh": round(mean(recent), 3), "prior_7day_average_kwh": round(baseline, 3), "ratio": round(ratio, 3)},
            ))
            break

    # Sustained drop: seven complete baseline days and two complete lower days.
    for day in dates:
        prior_days = _complete_calendar_window(daily, day - timedelta(days=7), 7)
        current_days = _complete_calendar_window(daily, day, 2)
        if not prior_days or not current_days:
            continue
        baseline = median(daily[d]["total"] for d in prior_days)
        current = [daily[d]["total"] for d in current_days]
        ratios = [value / max(baseline, 0.001) for value in current]
        if all(ratio < 0.55 for ratio in ratios):
            start, _ = _window(current_days[0])
            _, end = _window(current_days[1])
            events.append(DetectorEvent(
                "sudden_sustained_drop", "CRITICAL", "customer", "sustained_usage_drop",
                "Recorded usage was substantially lower than the meter's recent pattern. Check for schedule changes or a meter issue.",
                round(min(ratios), 3), 0.55, start, end + timedelta(minutes=15),
                {"daily_to_baseline_ratios": [round(x, 3) for x in ratios], "prior_7day_median_kwh": round(baseline, 3), "persistence_days": 2},
            ))
            break

    # Night-floor collapse: internal lead only, based on complete consecutive days.
    for day in dates:
        prior_days = _complete_calendar_window(daily, day - timedelta(days=7), 7)
        current_days = _complete_calendar_window(daily, day, 2)
        if not prior_days or not current_days:
            continue
        baseline = median(daily[d]["night"] for d in prior_days)
        current = [daily[d]["night"] for d in current_days]
        ratios = [value / max(baseline, 0.001) for value in current]
        if baseline > 0.12 and all(ratio < 0.15 for ratio in ratios):
            start, _ = _window(current_days[0], 1, 4, 45)
            _, end = _window(current_days[1], 1, 4, 45)
            events.append(DetectorEvent(
                "night_floor_collapse", "CRITICAL", "internal", "night_floor_pattern",
                "Pattern consistent with a sustained night-time floor collapse; requires authorized human review.",
                round(min(ratios), 3), 0.15, start, end + timedelta(minutes=15),
                {"night_floor_ratios": [round(x, 3) for x in ratios], "prior_night_median_kwh": round(baseline, 3), "persistence_days": 2},
            ))
            break

    # Communication gap: missing intervals are retained as missing, never imputed.
    gap_found = False
    for day in dates:
        slots = sorted(local.hour * 4 + local.minute // 15 for local, _, _ in by_day[day])
        missing = sorted(set(range(96)) - set(slots))
        if len(missing) >= 3:
            start_slot = missing[0]
            end_slot = start_slot
            for slot in missing[1:]:
                if slot == end_slot + 1:
                    end_slot = slot
                else:
                    break
            if end_slot - start_slot + 1 >= 3 and not gap_found:
                start = datetime.combine(day, time(start_slot // 4, (start_slot % 4) * 15), TZ).astimezone(UTC).replace(tzinfo=None)
                end = start + timedelta(minutes=15 * (end_slot - start_slot + 1))
                events.append(DetectorEvent(
                    "communication_gap", "WATCH", "customer", "interval_coverage_gap",
                    "Several expected meter intervals were not received. The daily total is partial.",
                    round((end_slot - start_slot + 1) / 96, 3), 3 / 96, start, end,
                    {"missing_intervals": len(missing), "longest_gap_intervals": end_slot - start_slot + 1, "expected_intervals": 96},
                ))
                gap_found = True

    model_scores = _model_scores(by_day, seed)
    from .intelligence import analyze_consumption
    intelligence_rows = [
        {"date": day.isoformat(), "total_kwh": daily[day]["total"],
         "coverage_pct": daily[day]["count"] / 96 * 100}
        for day in dates
    ]
    intelligence = analyze_consumption(intelligence_rows)
    summary = {
        "cold_start": False,
        "data_source": "synthetic",
        "readings_scored": len(rows),
        "days_available": len(dates),
        "events": len(events),
        "model_scores": model_scores,
        "intelligence": intelligence,
        "detector_version": DETECTOR_VERSION,
        "settings_version": SETTINGS_VERSION,
    }
    return events, summary
