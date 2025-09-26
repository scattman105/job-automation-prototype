"""Database models for the prototype services."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    resumes: Mapped[list[Resume]] = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    questionnaires: Mapped[list[QuestionnaireResponse]] = relationship(
        "QuestionnaireResponse", back_populates="user", cascade="all, delete-orphan"
    )
    job_listings: Mapped[list[JobListing]] = relationship("JobListing", back_populates="user")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(255))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    derived_skills: Mapped[list[str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="resumes")


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    raw_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    preference_vector: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="questionnaires")


class JobListing(Base):
    __tablename__ = "job_listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(80))
    external_id: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    remote_type: Mapped[str | None] = mapped_column(String(50))
    culture_tags: Mapped[list[str] | None] = mapped_column(JSON)
    overlap_summary: Mapped[str | None] = mapped_column(Text)
    gap_summary: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    listing_url: Mapped[str] = mapped_column(String(500))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    deviation: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="job_listings")
    application_log: Mapped[ApplicationLog | None] = relationship(
        "ApplicationLog", back_populates="job_listing", uselist=False, cascade="all, delete-orphan"
    )


class ApplicationLog(Base):
    __tablename__ = "application_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_listing_id: Mapped[str] = mapped_column(ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    confirmation_details: Mapped[dict | None] = mapped_column(JSON)
    captcha_required: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    job_listing: Mapped[JobListing] = relationship("JobListing", back_populates="application_log")


class CaptchaQueueItem(Base):
    __tablename__ = "captcha_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_listing_id: Mapped[str] = mapped_column(ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    job_listing: Mapped[JobListing] = relationship("JobListing")
