"""Utilities for ingesting résumés and questionnaire data."""
from __future__ import annotations

import re
import uuid
from typing import Any

import aiofiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import QuestionnaireResponse, Resume, User


class ResumeProcessor:
    """Persist résumés and derive lightweight skill metadata."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def store_resume(self, session: AsyncSession, *, user_id: str, content: str) -> Resume:
        user = await self._ensure_user(session, user_id)
        storage_path = self._build_storage_path(user_id)

        async with aiofiles.open(storage_path, "w", encoding="utf-8") as handle:
            await handle.write(content)

        derived_skills = self._extract_skills(content)

        resume = Resume(
            user_id=user.id,
            storage_path=str(storage_path),
            extracted_text=content,
            derived_skills=derived_skills,
        )
        session.add(resume)
        await session.commit()
        await session.refresh(resume)
        return resume

    def _build_storage_path(self, user_id: str) -> Path:
        resume_dir = self.settings.resume_storage_directory
        resume_dir.mkdir(parents=True, exist_ok=True)
        return resume_dir / f"{user_id}_{uuid.uuid4()}.txt"

    @staticmethod
    def _extract_skills(resume_text: str) -> list[str]:
        tokens = {token.strip().lower() for token in re.split(r"[^A-Za-z0-9#+]+", resume_text) if token}
        keywords = {
            "python",
            "javascript",
            "typescript",
            "sql",
            "aws",
            "gcp",
            "azure",
            "docker",
            "kubernetes",
            "django",
            "fastapi",
            "react",
            "node",
            "ml",
            "nlp",
        }
        return sorted(keyword for keyword in keywords if keyword in tokens)

    async def _ensure_user(self, session: AsyncSession, user_id: str) -> User:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return user

        placeholder = User(id=user_id)
        session.add(placeholder)
        await session.commit()
        await session.refresh(placeholder)
        return placeholder


class QuestionnaireProcessor:
    """Persist questionnaire responses and compute a simple preference vector."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def store_responses(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        answers: dict[str, Any],
    ) -> QuestionnaireResponse:
        user = await ResumeProcessor(self.settings)._ensure_user(session, user_id)
        preference_vector = self._build_preference_vector(answers)

        record = QuestionnaireResponse(
            user_id=user.id,
            raw_answers=answers,
            preference_vector=preference_vector,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    def _build_preference_vector(answers: dict[str, Any]) -> dict[str, Any]:
        vector: dict[str, Any] = {}
        salary_min = answers.get("preferred_salary_min") or answers.get("salary_min")
        salary_max = answers.get("preferred_salary_max") or answers.get("salary_max")
        if salary_min is not None or salary_max is not None:
            vector["salary"] = {
                "min": int(salary_min) if salary_min is not None else None,
                "max": int(salary_max) if salary_max is not None else None,
            }

        locations = answers.get("preferred_locations")
        if isinstance(locations, (list, tuple)):
            vector["locations"] = [str(loc).lower() for loc in locations]

        culture_keywords = answers.get("culture_keywords")
        if isinstance(culture_keywords, (list, tuple)):
            vector["culture"] = [str(keyword).lower() for keyword in culture_keywords]

        remote = answers.get("remote_ok")
        if isinstance(remote, bool):
            vector["remote_ok"] = remote

        return vector


async def bootstrap_demo_user(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: str,
    resume_text: str,
    questionnaire_answers: dict[str, Any],
) -> None:
    """Populate the database with a demo user so the API has realistic data."""

    resume_processor = ResumeProcessor(settings)
    questionnaire_processor = QuestionnaireProcessor(settings)

    await resume_processor.store_resume(session, user_id=user_id, content=resume_text)
    await questionnaire_processor.store_responses(session, user_id=user_id, answers=questionnaire_answers)
