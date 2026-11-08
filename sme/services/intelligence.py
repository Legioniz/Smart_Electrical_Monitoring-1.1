"""Explainable, calendar-aware and uncertainty-conscious meter intelligence.

All scores are decision-support indicators, not diagnoses of theft, appliance faults,
or causal weather effects. The implementation intentionally uses transparent
statistics and exposes assumptions so it can be validated against labelled data.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import exp, isfinite, log, pi, sqrt
from statistics import median
from typing import Iterable

INTELLIGENCE_VERSION = "sme-intelligence-v2.0"
MIN_COVERAGE_PCT = 80.0


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lo, hi = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 5 or len(a) != len(b):
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va, vb = sum((x-ma)**2 for x in a), sum((y-mb)**2 for y in b)
    if va <= 1e-12 or vb <= 1e-12:
        return None
    return max(-1.0, min(1.0, sum((x-ma)*(y-mb) for x, y in zip(a,b)) / sqrt(va*vb)))


def _spearman(a: list[float], b: list[float]) -> float | None:
    """Spearman rank correlation with average ranks for ties."""
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=values.__getitem__)
        result = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i + 1
            while j < len(order) and values[order[j]] == values[order[i]]:
                j += 1
            rank = (i + 1 + j) / 2
            for k in order[i:j]:
                result[k] = rank
            i = j
        return result
    return _pearson(ranks(a), ranks(b))


def _valid_daily_rows(daily_rows: Iterable[dict]) -> tuple[list[tuple[date, float]], dict]:
    parsed, rejected, low_coverage = [], 0, 0
    for row in daily_rows:
        try:
            day = date.fromisoformat(str(row["date"]))
            value = float(row["total_kwh"])
            coverage = float(row.get("coverage_pct", 100))
            if not isfinite(value) or value < 0 or not isfinite(coverage):
                rejected += 1
                continue
            if coverage < MIN_COVERAGE_PCT:
                low_coverage += 1
                continue
            parsed.append((day, value))
        except (KeyError, TypeError, ValueError):
            rejected += 1
    parsed.sort(key=lambda item: item[0])
    # Deterministic last-valid-row-wins de-duplication.
    by_date = {day: value for day, value in parsed}
    rows = sorted(by_date.items())
    duplicate_count = len(parsed) - len(rows)
    gaps = []
    for (left, _), (right, _) in zip(rows, rows[1:]):
        if (right-left).days > 1:
            gaps.append({"after": left.isoformat(), "before": right.isoformat(), "missing_days": (right-left).days-1})
    diagnostics = {"rejected_rows": rejected, "low_coverage_rows": low_coverage,
                   "duplicate_dates": duplicate_count, "calendar_gaps": gaps,
                   "coverage_threshold_pct": MIN_COVERAGE_PCT}
    return rows, diagnostics


def _contiguous(values: list[tuple[date, float]], start: int, stop: int) -> bool:
    segment = values[start:stop]
    return len(segment) >= 2 and all((segment[i][0]-segment[i-1][0]).days == 1 for i in range(1, len(segment)))


def analyze_consumption(daily_rows: Iterable[dict]) -> dict:
    """Return calendar-aware robust signals, forecasts and transparent evidence.

    A day is eligible only with >=80% interval coverage. Statistical windows that
    claim persistence or change points must be calendar-contiguous; gaps are never
    silently compressed into consecutive observations.
    """
    rows, quality = _valid_daily_rows(daily_rows)
    values = [value for _, value in rows]
    if len(values) < 8:
        return {"version": INTELLIGENCE_VERSION, "status": "cold_start", "valid_days": len(values),
                "message": "At least eight adequately covered days are needed for adaptive analysis.",
                "forecast": None, "signals": [], "change_point": None,
                "confidence": "insufficient_data", "data_quality": quality}

    # Recent baseline excludes the latest day and stops at a calendar gap.
    end = len(rows)-1
    start = end-1
    while start > 0 and (rows[start][0]-rows[start-1][0]).days == 1 and end-start < 13:
        start -= 1
    baseline_rows = rows[start:end]
    baseline = [v for _, v in baseline_rows]
    if len(baseline) < 5:
        # Fallback to valid historical days, but label the discontinuity.
        baseline = values[-min(14, len(values)-1):-1]
        baseline_basis = "historical_valid_days_with_calendar_gaps"
    else:
        baseline_basis = "contiguous_calendar_window"
    center = median(baseline)
    mad = median([abs(x-center) for x in baseline])
    sigma = max(1.4826*mad, abs(center)*0.05, 0.01)
    latest = values[-1]
    robust_z = (latest-center)/sigma

    # Chronological change-point candidates require 5 prior + 3 recent contiguous days.
    change_point = None
    for split in range(5, len(rows)-2):
        if not (_contiguous(rows, split-5, split+3) and (rows[split][0]-rows[split-1][0]).days == 1):
            continue
        prior = [v for _, v in rows[split-5:split]]
        recent = [v for _, v in rows[split:split+3]]
        prior_med, recent_med = median(prior), median(recent)
        relative = (recent_med-prior_med)/max(abs(prior_med), 0.01)
        if abs(relative) >= 0.20:
            change_point = {"candidate": True, "direction": "increase" if relative > 0 else "decrease",
                            "relative_change_pct": round(relative*100, 1),
                            "after_date": rows[split][0].isoformat(),
                            "method": "calendar-contiguous robust 5-day vs 3-day regime scan",
                            "caveat": "Candidate only; validate with longer history and independent evidence."}
            break


    # EWMA and two-sided CUSUM. Reset CUSUM at calendar gaps to avoid bridging outages.
    alpha = 0.25
    ewma = baseline[0]
    for value in baseline[1:]:
        ewma = alpha*value + (1-alpha)*ewma
    ewma = alpha*latest + (1-alpha)*ewma
    ewma_variance = (alpha/(2-alpha)) * sigma**2
    ewma_z = (ewma-center)/max(sqrt(ewma_variance), 0.01)
    cusum_pos = cusum_neg = 0.0
    # If a contiguous candidate regime shift exists, score drift against the
    # pre-shift reference rather than allowing the new regime to normalize itself.
    cusum_reference, cusum_sigma = center, sigma
    if change_point:
        split_index = next((i for i, (day, _) in enumerate(rows) if day.isoformat() == change_point["after_date"]), None)
        if split_index is not None:
            pre = [v for _, v in rows[split_index-5:split_index]]
            cusum_reference = median(pre)
            pre_mad = median([abs(v-cusum_reference) for v in pre])
            cusum_sigma = max(1.4826*pre_mad, abs(cusum_reference)*0.05, 0.01)
    for idx in range(max(0, len(rows)-14), len(rows)):
        if idx > 0 and (rows[idx][0]-rows[idx-1][0]).days != 1:
            cusum_pos = cusum_neg = 0.0
        standardized = (rows[idx][1]-cusum_reference)/cusum_sigma
        cusum_pos = max(0.0, cusum_pos + standardized - 0.5)
        cusum_neg = min(0.0, cusum_neg + standardized + 0.5)


    # Weekday baseline, with fallback and an explicit empirical interval.
    next_day = rows[-1][0] + timedelta(days=1)
    weekday_values = [v for day, v in rows[:-1] if day.weekday() == next_day.weekday()]
    if len(weekday_values) >= 3:
        forecast_sample = weekday_values[-8:]
        forecast_method = "same-weekday robust historical median"
    else:
        forecast_sample = values[-min(14, len(values)):]
        forecast_method = "robust trailing historical median"
    forecast_center = median(forecast_sample)
    abs_errors = [abs(v-forecast_center) for v in forecast_sample]
    # Empirical conformal-style absolute-error quantile; minimum floor avoids zero-width ranges.
    q_error = _quantile(abs_errors, min(0.90, (len(abs_errors)+1)/(len(abs_errors))))
    spread = max(q_error, 1.4826*median(abs_errors), abs(forecast_center)*0.05, 0.02)
    forecast = {"expected_kwh": round(forecast_center, 3),
                "lower_kwh": round(max(0.0, forecast_center-spread), 3),
                "upper_kwh": round(forecast_center+spread, 3),
                "method": forecast_method,
                "interval_method": "empirical absolute-error envelope; not a calibrated probabilistic interval",
                "warning": "Short-history next-day estimate; performance must be measured with rolling-origin backtests."}

    # Bayesian posterior under a transparent illustrative two-Gaussian hypothesis.
    log_l0 = -0.5*(robust_z**2) - log(sigma*sqrt(2*pi))
    alt_sigma = 3*sigma
    x = latest-center
    log_l1 = -0.5*(x/alt_sigma)**2 - log(alt_sigma*sqrt(2*pi))
    prior = 0.02
    log_odds = log(prior/(1-prior)) + log_l1-log_l0
    posterior = 1/(1+exp(-max(-60.0, min(60.0, log_odds))))

    signals = []
    if robust_z >= 3:
        signals.append({"method":"robust_mad","direction":"increase","severity":"elevated","score":round(robust_z,2),
                        "explanation":"Latest daily use is at least three robust scale units above its recent baseline."})
    elif robust_z <= -3:
        signals.append({"method":"robust_mad","direction":"decrease","severity":"watch","score":round(robust_z,2),
                        "explanation":"Latest daily use is substantially below its recent baseline; check occupancy and data completeness."})
    if cusum_pos >= 5:
        signals.append({"method":"cusum_positive","direction":"increase","severity":"watch","score":round(cusum_pos,2),
                        "explanation":"Small positive deviations accumulated across consecutive calendar days."})
    if cusum_neg <= -5:
        signals.append({"method":"cusum_negative","direction":"decrease","severity":"watch","score":round(cusum_neg,2),
                        "explanation":"Small negative deviations accumulated across consecutive calendar days."})
    if abs(ewma_z) >= 2.5:
        signals.append({"method":"ewma","direction":"increase" if ewma_z>0 else "decrease","severity":"watch",
                        "score":round(ewma_z,2),"explanation":"The smoothed consumption level has shifted relative to its robust baseline."})
    if change_point:
        signals.append({"method":"change_point","direction":change_point["direction"],"severity":"watch",
                        "score":abs(change_point["relative_change_pct"]),
                        "explanation":"A calendar-contiguous window suggests a possible consumption regime change."})

    # Direction-aware evidence aggregation; no unsupported theft/appliance labels.
    positive = min(1.0, max(0.0, robust_z)/5)
    cusum_component = min(1.0, max(0.0, cusum_pos)/10)
    ewma_component = min(1.0, max(0.0, ewma_z)/5)
    change_component = 1.0 if change_point and change_point["direction"] == "increase" else 0.0
    ensemble = 0.30*positive + 0.25*cusum_component + 0.20*ewma_component + 0.25*change_component

    recent_dates = [day for day, _ in rows[-14:]]
    consecutive_recent = sum(1 for a,b in zip(recent_dates,recent_dates[1:]) if (b-a).days==1)
    confidence = "moderate" if len(rows)>=21 and consecutive_recent>=10 else "limited"
    recommendations = []
    if any(s["direction"] == "increase" for s in signals):
        recommendations.append("Compare recent operating schedules and cooling use with the same weekdays in the baseline.")
    if any(s["direction"] == "decrease" for s in signals):
        recommendations.append("Check occupancy changes, missing intervals, meter communications, and appliance schedules before interpreting the drop.")
    if quality["calendar_gaps"]:
        recommendations.append("Resolve missing calendar days before relying on persistence or trend conclusions.")
    if not recommendations:
        recommendations.append("Continue monitoring; no strong directional change is indicated by the current daily aggregate.")

    return {"version":INTELLIGENCE_VERSION,"status":"ready","valid_days":len(rows),
            "baseline_kwh":round(center,3),"baseline_basis":baseline_basis,"baseline_days":len(baseline),
            "latest_kwh":round(latest,3),"robust_z":round(robust_z,3),"ewma_kwh":round(ewma,3),
            "ewma_z":round(ewma_z,3),"cusum_positive":round(cusum_pos,3),"cusum_negative":round(cusum_neg,3),
            "forecast":forecast,"bayesian_anomaly_probability":round(posterior,4),
            "bayesian_prior_assumption":"2% illustrative prior; alternative hypothesis is a 3x-scale Gaussian, not a learned prevalence.",
            "ensemble_score":round(ensemble,3),"ensemble_components":{"positive_deviation":round(positive,3),
                "positive_cusum":round(cusum_component,3),"positive_ewma":round(ewma_component,3),"increase_change_point":change_component},
            "change_point":change_point,"signals":signals,"confidence":confidence,
            "data_quality":quality,"recommendations":recommendations,
            "limitations":["Daily aggregates cannot identify individual appliances.",
                "A statistical anomaly is not proof of theft, tampering, or equipment failure.",
                "Forecast intervals are empirical envelopes and require rolling-origin calibration.",
                "Weather correlation is exploratory and does not establish causation.",
                "Synthetic demonstration readings must not be treated as real customer measurements."]}


def weather_consumption_correlation(daily_rows: Iterable[dict], weather_daily: Iterable[dict]) -> dict:
    """Exploratory matched-day temperature/usage association; never causal inference."""
    usage = {}
    for row in daily_rows:
        try:
            coverage = float(row.get("coverage_pct", 100))
            value = float(row["total_kwh"])
            if coverage >= MIN_COVERAGE_PCT and isfinite(coverage) and isfinite(value) and value >= 0:
                usage[str(row["date"])] = value
        except (KeyError, TypeError, ValueError):
            continue
    pairs = []
    for row in weather_daily:
        try:
            day, temp = str(row["date"]), float(row["temperature_c"])
            if day in usage and isfinite(temp):
                pairs.append((usage[day], temp))
        except (KeyError, TypeError, ValueError):
            continue
    x, y = [p[0] for p in pairs], [p[1] for p in pairs]
    pearson, spearman = _pearson(x,y), _spearman(x,y)
    enough = len(pairs) >= 5 and pearson is not None
    return {"days_compared":len(pairs),"pearson_r":round(pearson,3) if pearson is not None else None,
            "spearman_rho":round(spearman,3) if spearman is not None else None,
            "status":"exploratory" if enough else "insufficient_data",
            "message":"Exploratory association only; occupancy, weekday, tariff, and appliance changes are potential confounders. Correlation does not prove weather caused consumption changes." if enough else "At least five matched, adequately covered days with variation are needed."}
