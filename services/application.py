"""Application submission automation scaffolding."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import Any

from playwright.async_api import PlaywrightError, async_playwright
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import ApplicationLog, CaptchaQueueItem, JobListing


class ApplicationSubmitter:
    """Drive Playwright to fill and submit application forms."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def submit_job(
        self,
        session: AsyncSession,
        job_listing: JobListing,
        answers: dict[str, Any],
    ) -> ApplicationLog:
        log = ApplicationLog(job_listing_id=job_listing.id, status="pending")
        session.add(log)
        await session.flush()

        try:
            captcha_detected = await self._attempt_submission(job_listing, answers)
            if captcha_detected:
                log.status = "awaiting_captcha"
                log.captcha_required = True
                queue_item = CaptchaQueueItem(job_listing_id=job_listing.id, notes="Manual captcha solve required")
                session.add(queue_item)
            else:
                log.status = "submitted"
                log.submitted_at = datetime.utcnow()
        except PlaywrightError as exc:
            log.status = "error"
            log.error_message = f"Playwright error: {exc}"
        except Exception as exc:  # pylint: disable=broad-except
            log.status = "error"
            log.error_message = str(exc)
        finally:
            await session.commit()
            await session.refresh(log)

        return log

    async def _attempt_submission(self, job_listing: JobListing, answers: dict[str, Any]) -> bool:
        """Best-effort automated form submission.

        Returns True when a captcha is detected and the flow should be paused.
        """

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.settings.playwright_headless)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(job_listing.listing_url)

            captcha_detected = False
            with contextlib.suppress(Exception):
                await self._fill_form(page, answers)
                await asyncio.sleep(1.0)
                await page.click("text=Submit")

            if await self._page_has_captcha(page):
                captcha_detected = True

            await context.close()
            await browser.close()

        return captcha_detected

    async def _fill_form(self, page, answers: dict[str, Any]) -> None:  # type: ignore[override]
        for field, value in answers.items():
            selector = f"input[name=\"{field}\"]"
            if isinstance(value, bool):
                if value:
                    await page.check(selector)
                else:
                    await page.uncheck(selector)
            else:
                await page.fill(selector, str(value))

    @staticmethod
    async def _page_has_captcha(page) -> bool:  # type: ignore[override]
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            "input[name='captcha']",
            "div.g-recaptcha",
        ]
        for selector in captcha_selectors:
            element = await page.query_selector(selector)
            if element is not None:
                return True
        return False
