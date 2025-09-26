"""FastAPI entrypoint wiring services together."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import CaptchaQueueItem, JobListing, QuestionnaireResponse
from app.schemas import (
    ApplicationStatus,
    CaptchaItem,
    EvaluationRequest,
    JobMatch,
    QuestionnaireSubmission,
    ResumeUpload,
)
from services import ApplicationSubmitter, JobEvaluator, QuestionnaireProcessor, ResumeProcessor


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def create_app() -> FastAPI:
    app = FastAPI(title="Job Automation Prototype", version="0.1.0")

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - framework hook
        await init_models()

    async def get_session() -> AsyncSession:
        async with AsyncSessionLocal() as session:
            yield session

    def get_settings_dep() -> Settings:
        return get_settings()

    @app.post("/users/{user_id}/resume", response_model=dict)
    async def upload_resume(
        user_id: str,
        payload: ResumeUpload,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings_dep),
    ) -> dict[str, Any]:
        processor = ResumeProcessor(settings)
        resume = await processor.store_resume(session, user_id=user_id, content=payload.content)
        return {
            "resume_id": resume.id,
            "derived_skills": resume.derived_skills,
            "storage_path": resume.storage_path,
        }

    @app.post("/users/{user_id}/questionnaire", response_model=dict)
    async def submit_questionnaire(
        user_id: str,
        payload: QuestionnaireSubmission,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings_dep),
    ) -> dict[str, Any]:
        processor = QuestionnaireProcessor(settings)
        record = await processor.store_responses(session, user_id=user_id, answers=payload.model_dump())
        return {
            "questionnaire_id": record.id,
            "preference_vector": record.preference_vector,
        }

    @app.post("/users/{user_id}/evaluate", response_model=list[JobMatch])
    async def evaluate_jobs(
        user_id: str,
        request: EvaluationRequest,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings_dep),
    ) -> list[JobMatch]:
        evaluator = JobEvaluator(settings)
        matches = await evaluator.evaluate_for_user(
            session,
            user_id=user_id,
            limit=request.max_results or settings.evaluation_batch_size,
        )
        return [
            JobMatch(
                id=match.id,
                title=match.title,
                company=match.company,
                location=match.location,
                salary_range=(match.salary_min, match.salary_max),
                remote_type=match.remote_type,
                overlap=match.overlap_summary.split(", ") if match.overlap_summary else [],
                gaps=match.gap_summary.split(", ") if match.gap_summary else [],
                culture_alignment=match.culture_tags or [],
                notes=match.notes,
                url=match.listing_url,
                score=match.score,
                deviation=match.deviation,
                created_at=match.created_at,
            )
            for match in matches
        ]

    @app.get("/users/{user_id}/jobs", response_model=list[JobMatch])
    async def list_jobs(
        user_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> list[JobMatch]:
        stmt = select(JobListing).where(JobListing.user_id == user_id).order_by(JobListing.created_at.desc())
        result = await session.execute(stmt)
        listings = result.scalars().all()
        return [
            JobMatch(
                id=listing.id,
                title=listing.title,
                company=listing.company,
                location=listing.location,
                salary_range=(listing.salary_min, listing.salary_max),
                remote_type=listing.remote_type,
                overlap=listing.overlap_summary.split(", ") if listing.overlap_summary else [],
                gaps=listing.gap_summary.split(", ") if listing.gap_summary else [],
                culture_alignment=listing.culture_tags or [],
                notes=listing.notes,
                url=listing.listing_url,
                score=listing.score,
                deviation=listing.deviation,
                created_at=listing.created_at,
            )
            for listing in listings
        ]

    @app.post("/users/{user_id}/jobs/{job_id}/submit", response_model=ApplicationStatus)
    async def submit_application(
        user_id: str,
        job_id: str,
        session: AsyncSession = Depends(get_session),
        settings: Settings = Depends(get_settings_dep),
    ) -> ApplicationStatus:
        listing_stmt = select(JobListing).where(JobListing.id == job_id, JobListing.user_id == user_id)
        listing_result = await session.execute(listing_stmt)
        listing = listing_result.scalar_one_or_none()
        if listing is None:
            raise HTTPException(status_code=404, detail="Job listing not found")

        questionnaire_stmt = (
            select(QuestionnaireResponse)
            .where(QuestionnaireResponse.user_id == user_id)
            .order_by(QuestionnaireResponse.created_at.desc())
            .limit(1)
        )
        questionnaire_result = await session.execute(questionnaire_stmt)
        questionnaire = questionnaire_result.scalar_one_or_none()
        answers: dict[str, Any] = questionnaire.raw_answers if questionnaire else {}

        submitter = ApplicationSubmitter(settings)
        log = await submitter.submit_job(session, listing, answers)

        return ApplicationStatus(
            job_id=listing.id,
            status=log.status,
            submitted_at=log.submitted_at,
            captcha_required=log.captcha_required,
            notes=log.error_message,
        )

    @app.get("/captcha", response_model=list[CaptchaItem])
    async def captcha_queue(session: AsyncSession = Depends(get_session)) -> list[CaptchaItem]:
        stmt = select(CaptchaQueueItem).order_by(CaptchaQueueItem.created_at.desc())
        result = await session.execute(stmt)
        queue_items = result.scalars().all()
        return [
            CaptchaItem(
                job_id=item.job_listing_id,
                company=item.job_listing.company if item.job_listing else "Unknown",
                title=item.job_listing.title if item.job_listing else "Unknown",
                url=item.job_listing.listing_url if item.job_listing else "",
                added_at=item.created_at,
                notes=item.notes,
            )
            for item in queue_items
        ]

    return app


app = create_app()
