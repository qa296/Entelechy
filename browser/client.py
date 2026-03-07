"""Playwright browser client with session persistence."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from loguru import logger

from browser.session_manager import SessionManager


class BrowserClient:
    """Playwright browser automation with persistent sessions."""

    def __init__(self, profile_path: Path, headless: bool = True):
        self.session_manager = SessionManager(profile_path)
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._started = False

    def _require_page(self) -> Any:
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")
        return self.page

    def _require_context(self) -> Any:
        if self.context is None:
            raise RuntimeError("Browser context is not initialized")
        return self.context

    async def start(self):
        """Launch the browser and restore session state."""
        if self._started:
            return

        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)

        # Create context with saved state if available
        context_opts = {}
        if self.session_manager.has_saved_state():
            context_opts["storage_state"] = self.session_manager.get_state_path()
            logger.info("Restoring browser session state")

        self.context = await self.browser.new_context(**context_opts)
        self.page = await self.context.new_page()
        self._started = True
        logger.info("Browser started")

    async def stop(self):
        """Save state and close the browser."""
        if not self._started:
            return

        try:
            if self.context:
                await self.session_manager.save_state(self.context)
        except Exception as e:
            logger.warning(f"Error saving state on stop: {e}")

        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

        self._started = False
        logger.info("Browser stopped")

    async def ensure_started(self):
        """Ensure the browser is running."""
        if not self._started:
            await self.start()

    async def navigate(self, url: str) -> str:
        """Navigate to a URL.

        Returns:
            The page title after navigation.
        """
        await self.ensure_started()
        try:
            page = self._require_page()
            context = self._require_context()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = await page.title()
            await self.session_manager.save_state(context)
            return f"Navigated to: {url}\nTitle: {title}"
        except Exception as e:
            return f"Navigation error: {e}"

    async def click(self, selector: str) -> str:
        """Click an element."""
        await self.ensure_started()
        try:
            page = self._require_page()
            await page.click(selector, timeout=10000)
            await page.wait_for_load_state("domcontentloaded")
            return f"Clicked: {selector}"
        except Exception as e:
            return f"Click error: {e}"

    async def type_text(self, selector: str, text: str) -> str:
        """Type text into an element."""
        await self.ensure_started()
        try:
            page = self._require_page()
            await page.fill(selector, text, timeout=10000)
            return f"Typed text into: {selector}"
        except Exception as e:
            return f"Type error: {e}"

    async def screenshot(self, full_page: bool = True) -> str:
        """Take a screenshot and return as base64.

        Returns:
            Base64 encoded PNG image string.
        """
        await self.ensure_started()
        try:
            page = self._require_page()
            raw = await page.screenshot(full_page=full_page)
            encoded = base64.b64encode(raw).decode("utf-8")
            return f"Screenshot taken ({len(raw)} bytes). Base64: {encoded[:100]}..."
        except Exception as e:
            return f"Screenshot error: {e}"

    async def extract_content(self) -> str:
        """Extract text content from the current page."""
        await self.ensure_started()
        try:
            page = self._require_page()
            title = await page.title()
            url = page.url
            text = await page.inner_text("body")
            # Truncate very long pages
            if len(text) > 50000:
                text = text[:50000] + "\n\n... (truncated)"
            return f"URL: {url}\nTitle: {title}\n\n{text}"
        except Exception as e:
            return f"Extract error: {e}"

    async def execute_action(self, action: str, **kwargs) -> str:
        """Execute a browser action by name."""
        if action == "navigate":
            return await self.navigate(kwargs.get("url", ""))
        elif action == "click":
            return await self.click(kwargs.get("selector", ""))
        elif action == "type":
            return await self.type_text(
                kwargs.get("selector", ""), kwargs.get("text", "")
            )
        elif action == "screenshot":
            return await self.screenshot()
        elif action == "extract":
            return await self.extract_content()
        else:
            return f"Unknown browser action: {action}"
