"""Pydantic schemas shared across services."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResumeUpload(BaseModel):
    content: str = Field(..., description="Raw text extracted from the résumé")
    detected_skills: list[str] | None = Field(default=None, description="Optional pre-extracted skills list")


class QuestionnaireSubmission(BaseModel):
    answers: dict[str, Any]
    preferred_salary_min: int | None = None
    preferred_salary_max: int | None = None
    preferred_locations: list[str] | None = None
    remote_ok: bool = True
    culture_keywords: list[str] | None = None


class EvaluationRequest(BaseModel):
    max_results: int = 10


class JobMatch(BaseModel):
    id: str
    title: str
    company: str
    location: str | None = None
    salary_range: tuple[float | None, float | None] | None = None
    remote_type: str | None = None
    overlap: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    culture_alignment: list[str] = Field(default_factory=list)
    notes: str | None = None
    url: str
    score: float
    deviation: float
    created_at: datetime


class ApplicationStatus(BaseModel):
    job_id: str
    status: str
    submitted_at: datetime | None = None
    captcha_required: bool = False
    notes: str | None = None


class CaptchaItem(BaseModel):
    job_id: str
    company: str
    title: str
    url: str
    added_at: datetime
    notes: str | None = None
