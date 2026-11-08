from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from sme.schemas import ApplianceInput, FeedbackInput
from sme.services.appliances import breakdown, validate_appliance
from sme.services.detection import detect_events
from sme.services.narrative import create_story, validate_story
from sme.services.synthetic import generate_meter_series


def test_synthetic_generator_is_repeatable_and_has_expected_intervals():
    first, labels1, meta1 = generate_meter_series(20261031, 35)
    second, labels2, meta2 = generate_meter_series(20261031, 35)
    assert len(first) == 35 * 96 - 4  # one synthetic one-hour communications gap is omitted
    assert [r.energy_kwh for r in first] == [r.energy_kwh for r in second]
    assert [x.anomaly_type for x in labels1] == [x.anomaly_type for x in labels2]
    assert meta1 == meta2
    assert {x.anomaly_type for x in labels1} >= {
        "spike", "sustained_evening_rise", "gradual_drift", "sudden_sustained_drop", "night_floor_collapse", "communication_gap"
    }


def test_detector_is_deterministic_for_same_input():
    readings, _labels, _meta = generate_meter_series(20261031, 35)
    events_a, summary_a = detect_events(readings, seed=20261031)
    events_b, summary_b = detect_events(readings, seed=20261031)
    assert [(e.anomaly_type, e.window_start, e.tier) for e in events_a] == [(e.anomaly_type, e.window_start, e.tier) for e in events_b]
    assert summary_a["model_scores"] == summary_b["model_scores"]
    assert all(e.audience in {"customer", "internal"} for e in events_a)


def test_appliance_validation_rejects_bad_values_and_accepts_quarter_hours():
    good = validate_appliance({"name":"Window AC", "category":"air_conditioner", "rated_power_w":"900", "quantity":1, "duty_pct":"80", "hours_per_day":"4.5", "days_per_week":6, "notes":"Bedroom"})
    assert good["rated_power_w"] == Decimal("900.00")
    assert good["active_name_key"] == "window ac"
    with pytest.raises(Exception):
        validate_appliance({"name":"Bad", "category":"air_conditioner", "rated_power_w":"-5", "quantity":1, "duty_pct":80, "hours_per_day":4, "days_per_week":7})
    with pytest.raises(Exception):
        ApplianceInput(name="AC", category="air_conditioner", rated_power_w=900, quantity=1, duty_pct=80, hours_per_day=4.1, days_per_week=7)


def test_breakdown_percentages_are_balanced_and_label_as_estimates():
    appliances = [
        SimpleNamespace(id="1", name="Fridge", category="refrigerator", rated_power_w=Decimal("150"), quantity=1, duty_pct=Decimal("40"), hours_per_day=Decimal("24"), days_per_week=7),
        SimpleNamespace(id="2", name="Fan", category="fan", rated_power_w=Decimal("60"), quantity=2, duty_pct=Decimal("100"), hours_per_day=Decimal("8"), days_per_week=7),
    ]
    result = breakdown(appliances, Decimal("100"))
    assert result["available"] is True
    assert sum(item["share_pct"] for item in result["items"]) + result["everything_else_pct"] == 100.0
    assert "not measured" in result["label"]


def test_story_is_deterministic_and_validator_rejects_unsupported_numbers():
    facts = {"total_kwh":100.0,"previous_total_kwh":95.0,"change_pct":5.3,"coverage_pct":99.0,"top_share_pct":35.0,"driver":"Cooling","top_category":"Cooling","average_power_kw":0.6,"declared_coverage_pct":40.0,"period_start":"2026-10-01","period_end":"2026-10-07","received_intervals":665,"expected_intervals":672,"appliances_count":4,"simulated":True,"interval_minutes":15}
    story = create_story(facts, "en")
    assert story["validator_passed"] is True
    assert story["engine"] == "template"
    assert validate_story("Usage increased by 900%.", facts)[0] is False


def test_feedback_schema_regex_is_usable():
    assert FeedbackInput(feedback_type="normal").feedback_type == "normal"
    with pytest.raises(Exception):
        FeedbackInput(feedback_type="abnormal")


def test_missing_quality_rows_do_not_count_as_received_or_energy():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from sme.services.analytics import summarize_day, day_explorer_payload
    day = datetime(2026, 10, 31, tzinfo=timezone.utc).date()
    start = datetime(2026, 10, 30, 16, 0)  # local midnight in Manila
    rows = [SimpleNamespace(interval_start_utc=start, energy_kwh=Decimal("0.1"), quality="ok", label_type=None),
            SimpleNamespace(interval_start_utc=start.replace(minute=15), energy_kwh=Decimal("0.0"), quality="missing", label_type=None)]
    summary = summarize_day(rows, day)
    assert summary["received_intervals"] == 1
    assert summary["total_kwh"] == 0.1
    payload = day_explorer_payload(rows, day)
    assert payload["intervals"][1]["energy_kwh"] is None
    assert payload["intervals"][1]["quality"] == "missing"


def test_fixed_synthetic_scenario_detects_all_six_patterns_with_internal_routing():
    readings, labels, _meta = generate_meter_series(20261031, 35)
    events, summary = detect_events(readings, seed=20261031)
    injected = {label.anomaly_type for label in labels}
    detected = {event.anomaly_type for event in events}
    expected = {
        "spike", "sustained_evening_rise", "gradual_drift",
        "sudden_sustained_drop", "night_floor_collapse", "communication_gap",
    }
    assert expected <= injected
    assert expected <= detected
    internal = [event for event in events if event.anomaly_type == "night_floor_collapse"]
    assert internal and all(event.audience == "internal" for event in internal)
    assert all(event.audience in {"customer", "internal"} for event in events)
    assert summary["data_source"] == "synthetic"
    assert summary["model_scores"]["isolation_forest"] == "scored"
    assert summary["model_scores"]["pattern_autoencoder"] == "scored"


def test_recommendations_use_deterministic_fact_grounded_fallback():
    from sme.services.narrative import create_recommendations
    facts = {
        "total_kwh": 120.0, "previous_total_kwh": 100.0, "change_pct": 20.0,
        "coverage_pct": 82.5, "top_share_pct": 38.0, "driver": "Cooling",
        "top_category": "Cooling", "average_power_kw": 0.7,
        "declared_coverage_pct": 50.0, "period_start": "2026-10-01",
        "period_end": "2026-10-07", "received_intervals": 554,
        "expected_intervals": 672, "appliances_count": 3, "simulated": True,
        "interval_minutes": 15,
    }
    result = create_recommendations(facts, "en")
    assert result["engine"] == "template"
    assert result["validator_passed"] is True
    assert 1 <= len(result["items"]) <= 3
    assert all("guaranteed" not in item.casefold() for item in result["items"])
    assert any("coverage" in item.casefold() for item in result["items"])


def test_filipino_recommendations_use_reviewed_template():
    from sme.services.narrative import create_recommendations
    result = create_recommendations({"coverage_pct": 80.0, "change_pct": None}, "fil")
    assert result["engine"] == "template"
    assert result["reason"] == "reviewed_language_template"
    assert result["items"] and "saklaw" in result["items"][0].casefold()


def test_ollama_model_manifest_hash_is_verified_from_local_files(tmp_path):
    import hashlib
    from sme.services.narrative import ollama_manifest_digest
    manifest = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "qwen2.5" / "3b"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schemaVersion":2,"config":{"digest":"sha256:demo"}}', encoding="utf-8")
    expected = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert ollama_manifest_digest("qwen2.5:3b", tmp_path) == expected
    assert ollama_manifest_digest("../../outside:latest", tmp_path) is None
    assert ollama_manifest_digest("qwen2.5:missing", tmp_path) is None


def test_recommendations_reject_unverified_llm_numbers_and_fall_back(monkeypatch):
    import sme.services.narrative as narrative
    facts = {"total_kwh": 100.0, "previous_total_kwh": 90.0, "change_pct": 11.1,
             "coverage_pct": 99.0, "top_share_pct": 30.0, "driver": "Cooling"}
    monkeypatch.setattr(narrative, "_local_model_json", lambda _prompt: ({"recommendations": ["You will save 50% immediately by switching this appliance."]}, 5, "fake-model"))
    result = narrative.create_recommendations(facts)
    assert result["engine"] == "template"
    assert result["reason"] == "safe_template_fallback"


def test_recommendations_reject_accusatory_llm_output(monkeypatch):
    import sme.services.narrative as narrative
    facts = {"total_kwh": 100.0, "previous_total_kwh": 90.0, "change_pct": 11.1,
             "coverage_pct": 99.0, "top_share_pct": 30.0, "driver": "Cooling"}
    monkeypatch.setattr(narrative, "_local_model_json", lambda _prompt: ({"recommendations": ["This pattern proves electricity theft by someone in the home."]}, 5, "fake-model"))
    result = narrative.create_recommendations(facts)
    assert result["engine"] == "template"
    assert all("theft" not in item.casefold() for item in result["items"])


def test_multiday_detectors_do_not_treat_missing_calendar_days_as_consecutive():
    from datetime import date, datetime, time, timedelta, timezone
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    local_tz = ZoneInfo("Asia/Manila")

    def make_series(high_evenings=False, low_days=False):
        rows = []
        start_day = date(2026, 10, 1)
        for offset in range(14):
            if offset == 11:  # Entire calendar day absent: a real communication outage.
                continue
            day = start_day + timedelta(days=offset)
            low = low_days and offset in {10, 12}
            for slot in range(96):
                local_time = time(slot // 4, (slot % 4) * 15)
                value = 0.1
                if high_evenings and offset in {10, 12, 13} and time(18) <= local_time < time(21):
                    value = 0.3
                if low:
                    value = 0.005 if time(1) <= local_time < time(5) else 0.03
                local_dt = datetime.combine(day, local_time, local_tz)
                utc_naive = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
                rows.append(SimpleNamespace(interval_start_utc=utc_naive, energy_kwh=value, quality="ok"))
        return rows

    evening_events, _ = detect_events(make_series(high_evenings=True), seed=7)
    assert "sustained_evening_rise" not in {event.anomaly_type for event in evening_events}

    drop_events, _ = detect_events(make_series(low_days=True), seed=7)
    drop_types = {event.anomaly_type for event in drop_events}
    assert "sudden_sustained_drop" not in drop_types
    assert "night_floor_collapse" not in drop_types


def test_adaptive_intelligence_handles_cold_start_and_detects_persistent_shift():
    from sme.services.intelligence import analyze_consumption
    from datetime import date, timedelta
    start = date(2026, 9, 1)
    cold = [{"date": (start + timedelta(days=i)).isoformat(), "total_kwh": 5.0, "coverage_pct": 100} for i in range(7)]
    assert analyze_consumption(cold)["status"] == "cold_start"
    rows = [{"date": (start + timedelta(days=i)).isoformat(), "total_kwh": (5.0 if i < 12 else 8.0), "coverage_pct": 100} for i in range(20)]
    result = analyze_consumption(rows)
    assert result["status"] == "ready"
    assert result["forecast"]["expected_kwh"] >= 5.0
    assert result["change_point"] is not None
    assert result["change_point"]["direction"] == "increase"
    assert any(signal["method"] == "change_point" for signal in result["signals"])


def test_adaptive_intelligence_excludes_low_coverage_and_invalid_rows():
    from sme.services.intelligence import analyze_consumption
    from datetime import date, timedelta
    start = date(2026, 9, 1)
    rows = [{"date": (start + timedelta(days=i)).isoformat(), "total_kwh": 4.0, "coverage_pct": 100} for i in range(8)]
    rows += [{"date": (start + timedelta(days=8)).isoformat(), "total_kwh": 999.0, "coverage_pct": 20},
             {"date": "not-a-date", "total_kwh": 1.0, "coverage_pct": 100}]
    result = analyze_consumption(rows)
    assert result["valid_days"] == 8
    assert result["latest_kwh"] == 4.0


def test_weather_usage_correlation_is_exploratory_and_requires_five_days():
    from sme.services.intelligence import weather_consumption_correlation
    usage = [{"date": f"2026-10-{i:02d}", "total_kwh": float(i), "coverage_pct": 100} for i in range(1, 7)]
    weather = [{"date": f"2026-10-{i:02d}", "temperature_c": float(i * 2)} for i in range(1, 7)]
    result = weather_consumption_correlation(usage, weather)
    assert result["status"] == "exploratory"
    assert result["pearson_r"] == 1.0
    assert "does not prove" in result["message"]
    assert weather_consumption_correlation(usage[:3], weather[:3])["status"] == "insufficient_data"


def test_intelligence_does_not_bridge_calendar_gaps_for_change_points():
    from sme.services.intelligence import analyze_consumption
    from datetime import date, timedelta
    start = date(2026, 9, 1)
    rows = [{"date": (start + timedelta(days=i)).isoformat(), "total_kwh": 5.0, "coverage_pct": 100} for i in range(5)]
    # A missing day separates the two regimes; they must not be treated as adjacent.
    rows += [{"date": (start + timedelta(days=i)).isoformat(), "total_kwh": 9.0, "coverage_pct": 100} for i in range(6, 14)]
    result = analyze_consumption(rows)
    assert result["data_quality"]["calendar_gaps"]
    assert result["change_point"] is None


def test_intelligence_detects_sustained_downward_shift_and_reports_quality():
    from sme.services.intelligence import analyze_consumption
    from datetime import date, timedelta
    start = date(2026, 9, 1)
    rows = [{"date": (start + timedelta(days=i)).isoformat(), "total_kwh": (9.0 if i < 12 else 5.0), "coverage_pct": 100} for i in range(20)]
    result = analyze_consumption(rows)
    assert result["status"] == "ready"
    assert result["cusum_negative"] < 0
    assert any(signal["direction"] == "decrease" for signal in result["signals"])
    assert result["recommendations"]
    assert "interval" in result["forecast"]["interval_method"]


def test_intelligence_deduplicates_dates_and_rejects_nonfinite_values():
    from sme.services.intelligence import analyze_consumption
    from datetime import date, timedelta
    start = date(2026, 9, 1)
    rows = [{"date": (start + timedelta(days=i)).isoformat(), "total_kwh": 4.0, "coverage_pct": 100} for i in range(8)]
    rows += [{"date": (start + timedelta(days=7)).isoformat(), "total_kwh": 6.0, "coverage_pct": 100},
             {"date": (start + timedelta(days=8)).isoformat(), "total_kwh": float("nan"), "coverage_pct": 100}]
    result = analyze_consumption(rows)
    assert result["valid_days"] == 8
    assert result["latest_kwh"] == 6.0
    assert result["data_quality"]["duplicate_dates"] == 1
    assert result["data_quality"]["rejected_rows"] == 1


def test_weather_correlation_includes_rank_statistic_and_confounder_warning():
    from sme.services.intelligence import weather_consumption_correlation
    usage = [{"date": f"2026-10-{i:02d}", "total_kwh": float(i*i), "coverage_pct": 100} for i in range(1, 7)]
    weather = [{"date": f"2026-10-{i:02d}", "temperature_c": float(i)} for i in range(1, 7)]
    result = weather_consumption_correlation(usage, weather)
    assert result["status"] == "exploratory"
    assert result["spearman_rho"] == 1.0
    assert "confounders" in result["message"]
