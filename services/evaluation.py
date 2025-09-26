"""Job discovery and scoring logic."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import JobListing, QuestionnaireResponse, Resume


@dataclass
class EvaluationContext:
    skills: set[str]
    preferences: dict[str, Any]


class JobEvaluator:
    """Score job listings against résumé and questionnaire data."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def evaluate_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        limit: int | None = None,
    ) -> list[JobListing]:
        context = await self._build_context(session, user_id)
        job_samples = self._load_job_samples()
        matches: list[JobListing] = []

        for index, job in enumerate(job_samples):
            external_id = job.get("id")
            if external_id:
                existing_stmt = select(JobListing).where(
                    JobListing.user_id == user_id, JobListing.external_id == external_id
                )
                existing_result = await session.execute(existing_stmt)
                if existing_result.scalar_one_or_none():
                    continue

            score, deviation = self._score_job(context, job)
            if deviation > self.settings.deviation_tolerance or score < self.settings.evaluation_similarity_threshold:
                continue

            listing = JobListing(
                user_id=user_id,
                source=job.get("source", "sample"),
                external_id=job.get("id"),
                title=job.get("title", "Unknown Role"),
                company=job.get("company", "Unknown"),
                location=job.get("location"),
                salary_min=job.get("salary_min"),
                salary_max=job.get("salary_max"),
                remote_type=job.get("remote_type"),
                culture_tags=job.get("culture"),
                overlap_summary=", ".join(sorted(context.skills & set(job.get("skills", [])))),
                gap_summary=", ".join(sorted(set(job.get("skills", [])) - context.skills)),
                notes=job.get("notes"),
                listing_url=job.get("url", ""),
                score=score,
                deviation=deviation,
                status="queued",
            )
            session.add(listing)
            matches.append(listing)

            if limit and len(matches) >= limit:
                break

        await session.commit()
        for listing in matches:
            await session.refresh(listing)
        return matches

    async def _build_context(self, session: AsyncSession, user_id: str) -> EvaluationContext:
        resume_stmt = (
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
            .limit(1)
        )
        questionnaire_stmt = (
            select(QuestionnaireResponse)
            .where(QuestionnaireResponse.user_id == user_id)
            .order_by(QuestionnaireResponse.created_at.desc())
            .limit(1)
        )

        resume_result = await session.execute(resume_stmt)
        questionnaire_result = await session.execute(questionnaire_stmt)

        resume = resume_result.scalar_one_or_none()
        questionnaire = questionnaire_result.scalar_one_or_none()

        skills = set(resume.derived_skills or []) if resume else set()
        preferences = questionnaire.preference_vector if questionnaire else {}

        return EvaluationContext(skills=skills, preferences=preferences or {})

    def _load_job_samples(self) -> list[dict[str, Any]]:
        path = Path(self.settings.sample_job_file)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _score_job(self, context: EvaluationContext, job: dict[str, Any]) -> tuple[float, float]:
        job_skills = set(map(str.lower, job.get("skills", [])))
        overlap = context.skills & job_skills
        gap = job_skills - context.skills

        if not job_skills:
            base_score = 0.0
        else:
            base_score = len(overlap) / len(job_skills)

        salary_deviation = self._salary_deviation(context.preferences, job)
        culture_bonus = self._culture_alignment(context.preferences, job)

        score = base_score + culture_bonus
        score = min(score, 1.0)

        deviation = salary_deviation + (len(gap) * 0.05)

        return round(score, 3), round(deviation, 3)

    @staticmethod
    def _salary_deviation(preferences: dict[str, Any], job: dict[str, Any]) -> float:
        salary_pref = preferences.get("salary")
        if not salary_pref:
            return 0.0

        desired_min = salary_pref.get("min")
        desired_max = salary_pref.get("max")
        job_min = job.get("salary_min")
        job_max = job.get("salary_max")

        if job_min is None and job_max is None:
            return 0.5  # penalise unknown salary slightly

        target = (desired_min or desired_max or job_min or job_max or 0)
        job_value = (job_min or job_max or target)
        if target == 0:
            return 0.0

        delta = abs(job_value - target)
        return round(delta / max(target, 1), 3)

    @staticmethod
    def _culture_alignment(preferences: dict[str, Any], job: dict[str, Any]) -> float:
        desired = {kw.lower() for kw in preferences.get("culture", [])}
        job_culture = {kw.lower() for kw in job.get("culture", [])}
        if not desired or not job_culture:
            return 0.0
        overlap = desired & job_culture
        return round(len(overlap) / len(desired) * 0.2, 3)
