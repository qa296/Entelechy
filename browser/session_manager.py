"""Browser session persistence manager."""

import json
from pathlib import Path

from loguru import logger


class SessionManager:
    """Manages browser session state (cookies, localStorage) persistence."""

    def __init__(self, profile_path: Path):
        self.profile_path = Path(profile_path)
        self.state_file = self.profile_path / "state.json"
        self.profile_path.mkdir(parents=True, exist_ok=True)

    def has_saved_state(self) -> bool:
        """Check if a saved browser state exists."""
        return self.state_file.exists()

    def get_state_path(self) -> str:
        """Get the path to the state file for Playwright."""
        return str(self.state_file)

    async def save_state(self, context) -> None:
        """Save browser context state (cookies, localStorage).

        Args:
            context: Playwright browser context.
        """
        try:
            await context.storage_state(path=self.get_state_path())
            logger.debug(f"Browser state saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save browser state: {e}")

    def load_state_for_context(self) -> dict | None:
        """Load saved state for use in context creation.

        Returns:
            State dict or None if no saved state.
        """
        if not self.has_saved_state():
            return None
        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load browser state: {e}")
            return None
