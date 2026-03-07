"""Environment adapter - auto-detect and adapt to different runtime environments."""

import os
from pathlib import Path
from enum import Enum


class Environment(Enum):
    DOCKER = "docker"
    LOCAL = "local"


class EnvAdapter:
    """Environment adapter for Docker / local."""

    def __init__(self):
        self.env = self._detect_environment()
        self.data_dir = self._get_data_dir()
        self.browser_headless = self._should_be_headless()

    def _detect_environment(self) -> Environment:
        if os.getenv("DOCKER_CONTAINER"):
            return Environment.DOCKER
        return Environment.LOCAL

    def _get_data_dir(self) -> Path:
        override = os.getenv("DATA_DIR")
        if override:
            return Path(override)
        return Path("data")

    def _should_be_headless(self) -> bool:
        return os.getenv("BROWSER_HEADLESS", "true").lower() == "true"

    def get_memory_path(self) -> Path:
        return self.data_dir / "memory"

    def get_plugins_path(self) -> Path:
        return self.data_dir / "plugins"

    def get_browser_profile_path(self) -> Path:
        return self.data_dir / "browser" / "profiles"

    def get_log_path(self) -> Path:
        return self.data_dir / "logs"


# Global instance
env = EnvAdapter()
