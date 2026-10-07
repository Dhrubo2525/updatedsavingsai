"""Validated API input models."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class GoalCreate(BaseModel):
    user_id: str = Field(min_length=3, max_length=24)
    goal_name: str = Field(min_length=2, max_length=80)
    target_amount: float = Field(gt=0, le=100_000_000)
    current_saved_amount: float = Field(ge=0, le=100_000_000)
    target_months: int = Field(ge=1, le=36)
    deadline: str | None = None
    priority: Literal["low", "medium", "high"] = "medium"

    @field_validator("deadline")
    @classmethod
    def valid_date(cls, value):
        if value:
            from datetime import date
            try: date.fromisoformat(value)
            except ValueError as exc: raise ValueError("deadline must use YYYY-MM-DD") from exc
        return value

class WhatIfRequest(BaseModel):
    reductions: dict[str, float] = Field(default_factory=dict)
    @field_validator("reductions")
    @classmethod
    def allowed_categories(cls, value):
        allowed={"Food","Shopping","Transport","Entertainment"}
        if set(value)-allowed: raise ValueError("Use Food, Shopping, Transport, or Entertainment.")
        for category, pct in value.items():
            if not 0 <= pct <= .30: raise ValueError(f"{category} reduction must be between 0 and 30%.")
        return value

class CSVPreview(BaseModel):
    csv_text: str = Field(min_length=1, max_length=8_000_000)
    region: str = Field(default="", max_length=80)
    column_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("region")
    @classmethod
    def trim_region(cls, value):
        return value.strip()

class CSVImport(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    monthly_income: float = Field(ge=0, le=100_000_000, allow_inf_nan=False)
    current_savings: float = Field(ge=0, le=100_000_000, allow_inf_nan=False)
    region: str = Field(default="", max_length=80)
    occupation: str = Field(default="Not provided", max_length=80)
    language: Literal["en", "bn"] = "en"
    csv_text: str = Field(min_length=1, max_length=8_000_000)
    filename: str = Field(default="transactions.csv", max_length=120)
    column_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("display_name", "region", "occupation", "filename")
    @classmethod
    def trim_profile_text(cls, value):
        return value.strip()

    @field_validator("display_name")
    @classmethod
    def require_display_name(cls, value):
        if not value:
            raise ValueError("Enter a name for this imported profile.")
        return value

class GoalContributionCreate(BaseModel):
    amount: float = Field(gt=0, le=100_000_000, allow_inf_nan=False)
    note: str = Field(default="", max_length=120)

    @field_validator("note")
    @classmethod
    def trim_note(cls, value):
        return value.strip()
