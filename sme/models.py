from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_label: Mapped[str] = mapped_column(String(50), default="Demo household")
    language: Mapped[str] = mapped_column(String(8), default="en")
    push_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_sign_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        CheckConstraint("role IN ('customer','reviewer','administrator')", name="ck_accounts_role"),
        CheckConstraint("status IN ('active','locked','disabled')", name="ck_accounts_status"),
        CheckConstraint("(role = 'customer' AND customer_id IS NOT NULL) OR (role IN ('reviewer','administrator') AND customer_id IS NULL)", name="ck_account_role_customer"),
    )


class AppSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (Index("ix_sessions_account", "account_id"), Index("ix_sessions_expiry", "expires_at"))


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    challenge_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    challenge_type: Mapped[str] = mapped_column(String(24), nullable=False)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (Index("ix_auth_challenges_expiry", "expires_at"),)


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    text_version: Mapped[str] = mapped_column(String(20), nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_screen: Mapped[str] = mapped_column(String(40), default="consent", nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("account_id", "purpose", "request_id", name="uq_consent_idempotent"),
        Index("ix_consent_current", "account_id", "purpose", "decided_at"),
        CheckConstraint("status IN ('granted','withdrawn')", name="ck_consent_status"),
    )


class Meter(Base):
    __tablename__ = "meters"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    pseudonymous_label: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("customer_id", "pseudonymous_label", name="uq_meter_label"),)


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    interval_start_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    quality: Mapped[str] = mapped_column(String(16), default="ok", nullable=False)
    label_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    __table_args__ = (
        UniqueConstraint("meter_id", "interval_start_utc", name="uq_reading_meter_interval"),
        Index("ix_readings_meter_time", "meter_id", "interval_start_utc"),
        CheckConstraint("energy_kwh >= 0 AND energy_kwh <= 100", name="ck_reading_energy"),
        CheckConstraint("quality IN ('ok','missing','estimated')", name="ck_reading_quality"),
    )


class SyntheticLabel(Base):
    __tablename__ = "synthetic_labels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    meter_id: Mapped[str] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(40), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (Index("ix_synthetic_labels_window", "meter_id", "window_start", "window_end"),)


class Appliance(Base):
    __tablename__ = "appliances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    active_name_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    rated_power_w: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    duty_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    hours_per_day: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    retired_on: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_appliances_customer_status", "customer_id", "status"),
        UniqueConstraint("customer_id", "active_name_key", name="uq_appliance_active_name"),
        CheckConstraint("rated_power_w > 0 AND rated_power_w <= 20000", name="ck_appliance_power"),
        CheckConstraint("quantity BETWEEN 1 AND 99", name="ck_appliance_quantity"),
        CheckConstraint("duty_pct BETWEEN 1 AND 100", name="ck_appliance_duty"),
        CheckConstraint("hours_per_day BETWEEN 0 AND 24", name="ck_appliance_hours"),
        CheckConstraint("days_per_week BETWEEN 1 AND 7", name="ck_appliance_days"),
        CheckConstraint("status IN ('active','retired','removed')", name="ck_appliance_status"),
    )


class ApplianceVersion(Base):
    __tablename__ = "appliance_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    appliance_id: Mapped[str] = mapped_column(ForeignKey("appliances.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    rated_power_w: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    duty_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    hours_per_day: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("appliance_id", "version", name="uq_appliance_version"), Index("ix_appliance_versions_date", "appliance_id", "valid_from"))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    meter_id: Mapped[str] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[str] = mapped_column(String(12), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(48), nullable=False)
    reason_text: Mapped[str] = mapped_column(String(240), nullable=False)
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    detector_version: Mapped[str] = mapped_column(String(30), nullable=False)
    settings_version: Mapped[str] = mapped_column(String(30), nullable=False)
    feature_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ix_alert_customer_time", "customer_id", "created_at"), Index("ix_alert_audience_status", "audience", "status"), UniqueConstraint("meter_id", "alert_type", "window_start", name="uq_alert_detection_window"))


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    alert_id: Mapped[str | None] = mapped_column(ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    tier: Mapped[str] = mapped_column(String(12), nullable=False)
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="not_sent_mock", nullable=False)
    suppression_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FactSheet(Base):
    __tablename__ = "fact_sheets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    facts: Mapped[dict] = mapped_column(JSON, nullable=False)
    fact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (Index("ix_fact_customer_period", "customer_id", "period_start", "period_end"),)


class Narrative(Base):
    __tablename__ = "narratives"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fact_sheet_id: Mapped[str] = mapped_column(ForeignKey("fact_sheets.id", ondelete="CASCADE"), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str] = mapped_column(String(16), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    validator_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SettingsVersion(Base):
    __tablename__ = "settings_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    values: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_source: Mapped[str] = mapped_column(String(20), default="synthetic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    split_description: Mapped[str] = mapped_column(String(160), nullable=False)
    data_source: Mapped[str] = mapped_column(String(20), default="synthetic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    __table_args__ = (Index("ix_audit_time", "occurred_at"),)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (Index("ix_security_source_time", "source_hash", "occurred_at"),)


class LockState(Base):
    __tablename__ = "lock_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    reason_code: Mapped[str] = mapped_column(String(48), nullable=False, default="normal")
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    unlocked_by: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (Index("ix_login_source_time", "source_hash", "occurred_at"), Index("ix_login_identifier_time", "identifier_hash", "occurred_at"))

# Explicit MySQL storage settings: do not silently fall back to a non-transactional
# engine or a legacy character set when the migration runs on the local server.
for _table in Base.metadata.tables.values():
    _table.dialect_options["mysql"]["engine"] = "InnoDB"
    _table.dialect_options["mysql"]["charset"] = "utf8mb4"
