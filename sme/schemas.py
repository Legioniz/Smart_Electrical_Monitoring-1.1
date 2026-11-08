from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CustomerLogin(StrictInput):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class AdminLogin(StrictInput):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class AdminVerify(StrictInput):
    challenge_id: str = Field(min_length=20, max_length=200)
    code: str = Field(pattern=r"^\d{6}$")


class ConsentInput(StrictInput):
    text_version: str = Field(min_length=1, max_length=20)
    request_id: str = Field(min_length=36, max_length=36)
    required_analytics: bool
    push_alerts: bool = False
    sms_alerts: bool = False


class ApplianceInput(StrictInput):
    name: str = Field(min_length=1, max_length=60)
    category: str = Field(min_length=1, max_length=32)
    rated_power_w: Decimal
    quantity: int = Field(ge=1, le=99)
    duty_pct: Decimal = Field(default=Decimal("100"), ge=1, le=100)
    hours_per_day: Decimal = Field(ge=0, le=24)
    days_per_week: int = Field(ge=1, le=7)
    notes: str = Field(default="", max_length=200)
    version: int | None = Field(default=None, ge=1)

    @field_validator("rated_power_w")
    @classmethod
    def power_range(cls, value: Decimal) -> Decimal:
        if not Decimal("0") < value <= Decimal("20000"):
            raise ValueError("rated_power_w must be above 0 and at most 20,000")
        return value

    @field_validator("hours_per_day")
    @classmethod
    def quarter_hours(cls, value: Decimal) -> Decimal:
        if value * 4 != (value * 4).to_integral_value():
            raise ValueError("hours_per_day must use 15-minute steps")
        return value


class ApplianceRemoval(StrictInput):
    action: str = Field(pattern=r"^(retire|remove)$")
    version: int = Field(ge=1)


class ApplianceRestore(StrictInput):
    version: int = Field(ge=1)


class NotificationSettings(StrictInput):
    push_alerts: bool = False
    sms_alerts: bool = False
    language: str = Field(pattern=r"^(en|fil)$")


class PasswordChange(StrictInput):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=15, max_length=1024)


class FeedbackInput(StrictInput):
    feedback_type: str = Field(pattern=r"^normal$")


class ReviewInput(StrictInput):
    status: str = Field(pattern=r"^(reviewed|field_check_requested)$")


class SafeModeUnlock(StrictInput):
    current_password: str = Field(min_length=15, max_length=1024)
    approval_challenge_id: str = Field(min_length=20, max_length=200)
    approval_code: str = Field(pattern=r"^\d{6}$")
