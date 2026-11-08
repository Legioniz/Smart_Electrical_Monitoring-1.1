from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .config import ROOT, settings, validate_settings
from .db import build_engine, build_session_factory
from .models import (
    Account, Alert, Appliance, ApplianceVersion, BenchmarkRun, ConsentRecord,
    Customer, FactSheet, LockState, Meter, ModelRun, NotificationOutbox,
    Reading, SettingsVersion, SyntheticLabel,
)
from .security import hash_password, new_id, utcnow, write_audit
from .services.analytics import make_fact_sheet
from .services.detection import DETECTOR_VERSION, SETTINGS_VERSION, detect_events
from .services.narrative import create_story
from .services.synthetic import generate_meter_series


def alembic_upgrade():
    if not settings.migration_database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL is required. See README.md for least-privilege MySQL setup.")
    os.environ["MIGRATION_DATABASE_URL"] = settings.migration_database_url
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    print("Database migrations are at head.")


def _create_account(db, username: str, role: str, customer_id: str | None = None) -> tuple[Account, str | None]:
    existing = db.scalar(select(Account).where(Account.username == username))
    if existing:
        return existing, None
    password = secrets.token_urlsafe(20) + "-aA7!"
    account = Account(
        id=new_id(), customer_id=customer_id, username=username,
        password_hash=hash_password(password), role=role,
        status="active", must_change_password=True, created_at=utcnow(),
    )
    db.add(account)
    db.flush()
    return account, password


def _add_appliance(db, customer_id, name, category, watts, quantity, duty, hours, days):
    appliance = Appliance(
        id=new_id(), customer_id=customer_id, name=name, active_name_key=name.casefold(),
        category=category, rated_power_w=Decimal(str(watts)), quantity=quantity,
        duty_pct=Decimal(str(duty)), hours_per_day=Decimal(str(hours)), days_per_week=days,
        notes="", status="active", version=1, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(appliance)
    db.flush()
    db.add(ApplianceVersion(
        id=new_id(), appliance_id=appliance.id, version=1, category=category,
        rated_power_w=appliance.rated_power_w, quantity=quantity,
        duty_pct=appliance.duty_pct, hours_per_day=appliance.hours_per_day,
        days_per_week=days, valid_from=utcnow(), valid_to=None,
    ))


def seed_demo():
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required. Configure .env first.")
    engine = build_engine(settings.database_url)
    factory = build_session_factory(engine)
    generated_credentials: list[tuple[str, str, str]] = []
    with factory() as db:
        account = db.scalar(select(Account).where(Account.username == settings.demo_customer_username.casefold()))
        if account:
            print("Demo data already exists. No duplicate sample account was created.")
            return
        customer_id = new_id()
        customer = Customer(id=customer_id, display_label="Demo household", language="en", push_opt_in=False, sms_opt_in=False, created_at=utcnow())
        db.add(customer)
        db.flush()
        user, user_password = _create_account(db, settings.demo_customer_username.casefold(), "customer", customer_id)
        reviewer, reviewer_password = _create_account(db, "demo.reviewer", "reviewer")
        admin1, admin1_password = _create_account(db, "demo.admin.one", "administrator")
        admin2, admin2_password = _create_account(db, "demo.admin.two", "administrator")
        for name, role, password in [
            (user.username, user.role, user_password),
            (reviewer.username, reviewer.role, reviewer_password),
            (admin1.username, admin1.role, admin1_password),
            (admin2.username, admin2.role, admin2_password),
        ]:
            if password:
                generated_credentials.append((name, role, password))

        meter = Meter(id=new_id(), customer_id=customer_id, pseudonymous_label="SIM-METER-001", created_at=utcnow())
        db.add(meter)
        _add_appliance(db, customer_id, "Air conditioner", "air_conditioner", 1550, 1, 100, 4.5, 7)
        _add_appliance(db, customer_id, "Refrigerator", "refrigerator", 150, 1, 40, 24, 7)
        _add_appliance(db, customer_id, "Lighting group", "lighting", 8, 10, 100, 5, 7)
        _add_appliance(db, customer_id, "TV and computer", "electronics", 200, 1, 100, 4, 7)

        readings, injections, meta = generate_meter_series(settings.seed, 35)
        db.add_all([
            Reading(meter_id=meter.id, interval_start_utc=row.interval_start_utc, energy_kwh=Decimal(str(row.energy_kwh)), quality=row.quality, label_type=row.label_type)
            for row in readings
        ])
        db.add_all([
            SyntheticLabel(id=new_id(), meter_id=meter.id, anomaly_type=item.anomaly_type, window_start=item.start_utc.replace(tzinfo=None), window_end=item.end_utc.replace(tzinfo=None), seed=settings.seed)
            for item in injections
        ])
        db.flush()
        events, detection_summary = detect_events(readings, settings.seed)
        detected_types = {event.anomaly_type for event in events}
        ground_types = {item.anomaly_type for item in injections}
        matched = detected_types & ground_types
        precision = len(matched) / max(len(detected_types), 1)
        recall = len(matched) / max(len(ground_types), 1)
        benchmark_metrics = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "injected_anomalies": len(ground_types),
            "detected_event_types": sorted(detected_types),
            "matched_event_types": sorted(matched),
            "unmatched_injected_types": sorted(ground_types - detected_types),
            "model_scores": detection_summary.get("model_scores", {}),
            "label": "synthetic benchmark only; not real-world performance",
        }
        db.add(ModelRun(id=new_id(), model_type="hybrid_rules_iforest_autoencoder", model_version=DETECTOR_VERSION, seed=settings.seed, settings={"version": SETTINGS_VERSION, "spike_ratio": 2.8, "evening_ratio": 1.5, "drop_ratio": 0.55, "night_floor_ratio": 0.15}, result_summary=detection_summary, data_source="synthetic", created_at=utcnow()))
        db.add(BenchmarkRun(id=new_id(), seed=settings.seed, settings={"detector_version": DETECTOR_VERSION, "settings_version": SETTINGS_VERSION}, metrics=benchmark_metrics, split_description="First 14 days used as baseline; later days scored in chronological order", data_source="synthetic", created_at=utcnow()))
        for event in events:
            # The alert row is created only from the stored-reading detection pipeline.
            exists = db.scalar(select(Alert.id).where(Alert.meter_id == meter.id, Alert.alert_type == event.anomaly_type, Alert.window_start == event.window_start))
            if exists:
                continue
            alert = Alert(
                id=new_id(), customer_id=customer_id, meter_id=meter.id, tier=event.tier,
                alert_type=event.anomaly_type, reason_code=event.reason_code, reason_text=event.reason_text,
                audience=event.audience, status="open", score=Decimal(str(event.score)), threshold=Decimal(str(event.threshold)),
                window_start=event.window_start, window_end=event.window_end,
                detector_version=DETECTOR_VERSION, settings_version=SETTINGS_VERSION,
                feature_values={"detector": DETECTOR_VERSION, "settings_version": SETTINGS_VERSION, **event.feature_values, "coverage": "computed from stored readings"}, created_at=utcnow(),
            )
            db.add(alert)
            db.flush()
            if event.audience == "customer":
                db.add(NotificationOutbox(
                    id=new_id(), customer_id=customer_id, alert_id=alert.id,
                    channel="in_app", audience="customer", tier=event.tier,
                    text=event.reason_text, language="en", status="recorded_in_app_mock",
                    suppression_reason=None, created_at=utcnow(),
                ))
        settings_record = SettingsVersion(id=new_id(), version=SETTINGS_VERSION, values={"seed": settings.seed, "thresholds": {"evening_ratio": 1.5, "drop_ratio": 0.55, "night_floor_ratio": 0.15, "spike_ratio": 2.8}}, changed_by=None, created_at=utcnow())
        db.add(settings_record)
        db.add(LockState(id=1, mode="normal", reason_code="normal", changed_at=utcnow()))
        write_audit(db, None, "demo_seeded", "demo_dataset", meter.id, {"source": "synthetic", "seed": settings.seed, "readings": len(readings), "injected_anomaly_types": sorted(ground_types)})
        db.commit()
        # Compute and store the first fact sheet and template narrative for the demo.
        latest = max(r.interval_start_utc for r in readings).replace(tzinfo=timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("Asia/Manila")).date()
        apps = list(db.scalars(select(Appliance).where(Appliance.customer_id == customer_id, Appliance.status == "active")))
        built = make_fact_sheet(db, customer_id, meter.id, latest, apps)
        sheet = FactSheet(id=new_id(), customer_id=customer_id, period_start=built["period_start_utc"], period_end=built["period_end_utc"], version="facts-v1", facts=built["facts"], fact_hash=built["fact_hash"], coverage_pct=Decimal(str(built["coverage_pct"])), created_at=utcnow())
        db.add(sheet)
        db.flush()
        narrative = create_story(sheet.facts, "en")
        from .models import Narrative
        db.add(Narrative(id=new_id(), fact_sheet_id=sheet.id, language="en", text=narrative["text"], engine=narrative["engine"], model_name=narrative["model_name"], model_hash=narrative["model_hash"], prompt_version=narrative["prompt_version"], validator_passed=narrative["validator_passed"], provenance={"fact_hash": sheet.fact_hash, "data_source": "synthetic", "reason": narrative["reason"]}, latency_ms=narrative["latency_ms"], created_at=utcnow()))
        db.commit()
    print("\nSMART METER EXPLORER V2 — GENERATED DEMO ACCOUNTS")
    print("Copy these credentials now. They are generated locally, not stored in source code.")
    for name, role, password in generated_credentials:
        print(f"{role:14} {name:20} {password}")
    print("\nInternal accounts require a one-time code printed in the server terminal after password validation.")
    print("Synthetic readings and benchmark labels were saved to the local MySQL database.")
    print("Benchmark results are synthetic only. Review docs/VALIDATION_LOG.md for untested phases.\n")


def main():
    parser = argparse.ArgumentParser(description="Smart Meter Explorer V2 local setup commands")
    parser.add_argument("command", choices=["migrate", "seed-demo", "bootstrap", "serve", "check"])
    args = parser.parse_args()
    if args.command == "serve":
        validate_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is required. Run bootstrap and configure MySQL first.")
        import uvicorn
        uvicorn.run("sme.main:app", host="127.0.0.1", port=settings.app_port, reload=False, access_log=False)
        return
    if args.command == "check":
        validate_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        engine = build_engine(settings.database_url)
        from .db import check_database
        check_database(engine)
        print("Configuration and MySQL connection are available.")
        return
    validate_settings()
    if args.command in {"migrate", "bootstrap"}:
        alembic_upgrade()
    if args.command in {"seed-demo", "bootstrap"}:
        seed_demo()


if __name__ == "__main__":
    main()
