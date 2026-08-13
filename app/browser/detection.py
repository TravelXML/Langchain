"""Challenge-screen detection (Section 12/42).

Deliberately shallow: these only *detect* an OTP/CAPTCHA screen so the
caller can pause and hand off to a human (Section 12 prohibits solving or
bypassing either). No fingerprinting, no interaction with the challenge
widget itself.
"""

from __future__ import annotations

from playwright.async_api import Page


async def is_otp_screen(page: Page) -> bool:
    return await page.locator('[data-testid="otp-input"]').count() > 0


async def is_captcha_screen(page: Page) -> bool:
    return await page.locator('[data-testid="captcha-widget"]').count() > 0
