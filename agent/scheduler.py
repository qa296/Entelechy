"""Scheduler manager - cron and one-shot scheduled tasks.

At todo_complete time, checks for due schedules and injects them
to the TODO list head for immediate attention.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from croniter import croniter
from loguru import logger

if TYPE_CHECKING:
    from agent.todo_manager import TodoManager


@dataclass
class Schedule:
    id: str
    description: str
    schedule_type: str  # "cron" | "once"
    cron: str = ""  # e.g. "0 9 * * *"
    delay_minutes: int = 0  # original user-provided delay (informational)
    run_at: str = ""  # ISO datetime for "once" type
    enabled: bool = True
    created_at: str = ""
    last_triggered_at: str = ""  # ISO datetime, used to avoid double trigger

    @staticmethod
    def create_cron(description: str, cron: str) -> Schedule:
        now = datetime.now().isoformat()
        return Schedule(
            id=uuid.uuid4().hex[:8],
            description=description,
            schedule_type="cron",
            cron=cron,
            enabled=True,
            created_at=now,
        )

    @staticmethod
    def create_once(description: str, delay_minutes: int) -> Schedule:
        now = datetime.now()
        run_at = (now + timedelta(minutes=delay_minutes)).isoformat()
        return Schedule(
            id=uuid.uuid4().hex[:8],
            description=description,
            schedule_type="once",
            delay_minutes=delay_minutes,
            run_at=run_at,
            enabled=True,
            created_at=now.isoformat(),
        )


class SchedulerManager:
    """Manage cron and one-shot schedules, persisting to a JSON file."""

    def __init__(self, persist_path: Path):
        self.persist_path = Path(persist_path)
        self.schedules: list[Schedule] = []

    async def load(self) -> bool:
        """Load schedules from persist_path. Returns True if loaded."""
        if not self.persist_path.exists():
            self.schedules = []
            return False
        try:
            async with aiofiles.open(self.persist_path, "r", encoding="utf-8") as f:
                raw = await f.read()
            data = json.loads(raw)
            self.schedules = [Schedule(**item) for item in data]
            logger.info(f"Loaded {len(self.schedules)} schedules from {self.persist_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load schedules: {e}")
            self.schedules = []
            return False

    async def save(self):
        """Persist schedules to disk."""
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(s) for s in self.schedules]
        async with aiofiles.open(self.persist_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        logger.debug(f"Saved {len(self.schedules)} schedules to {self.persist_path}")

    def add(self, description: str, cron: str | None = None,
            delay_minutes: int | None = None) -> Schedule:
        """Add a new schedule.

        Args:
            description: Task description.
            cron: Cron expression for periodic schedules.
            delay_minutes: Delay in minutes for one-shot schedules.

        Returns:
            The new Schedule.

        Raises:
            ValueError: If neither cron nor delay_minutes is provided,
                        or if both are provided.
        """
        if cron and delay_minutes is not None:
            raise ValueError("Cannot provide both cron and delay_minutes.")
        if not cron and delay_minutes is None:
            raise ValueError("Must provide either cron or delay_minutes.")

        if cron:
            if not croniter.is_valid(cron):
                raise ValueError(f"Invalid cron expression: {cron}")
            schedule = Schedule.create_cron(description, cron)
        else:
            if delay_minutes <= 0:
                raise ValueError("delay_minutes must be greater than 0.")
            schedule = Schedule.create_once(description, delay_minutes)

        self.schedules.append(schedule)
        return schedule

    def remove(self, schedule_id: str) -> bool:
        """Remove a schedule by id. Returns True if found and removed."""
        for i, s in enumerate(self.schedules):
            if s.id == schedule_id:
                self.schedules.pop(i)
                return True
        return False

    def list(self) -> list[Schedule]:
        """Return all schedules."""
        return list(self.schedules)

    def format_list(self) -> str:
        """Return a human-readable schedule listing."""
        if not self.schedules:
            return "当前没有定时任务。"
        lines = ["## 定时任务"]
        for s in self.schedules:
            if s.schedule_type == "cron":
                schedule_info = f"cron: `{s.cron}`"
            else:
                schedule_info = f"一次性 (run_at: {s.run_at})"
            status = "[active]" if s.enabled else "[paused]"
            lines.append(f"- {status} [{s.id}] {s.description} ({schedule_info})")
        return "\n".join(lines)

    def merge_config(self, config_schedules: list[dict]):
        """Merge schedules from config.yaml.

        Config entries (description + cron) are added only if they
        don't already exist in the current schedule list (by matching
        both description and cron).
        """
        existing_keys = {(s.description, s.cron) for s in self.schedules}
        for entry in config_schedules:
            desc = entry.get("description", "")
            cron = entry.get("cron", "")
            if not desc or not cron:
                continue
            key = (desc, cron)
            if key in existing_keys:
                continue
            schedule = Schedule.create_cron(desc, cron)
            self.schedules.append(schedule)
            existing_keys.add(key)
            logger.info(f"Loaded schedule from config: {desc} ({cron})")

    async def check_and_trigger(self, todo_manager: TodoManager):
        """Check all schedules and trigger any that are due.

        Due cron schedules insert the task at the TODO head.
        Due one-shot schedules insert and then delete themselves.
        """
        now = datetime.now()
        triggered: list[Schedule] = []
        to_delete: list[str] = []

        for s in self.schedules:
            if not s.enabled:
                continue

            if s.schedule_type == "cron":
                if self._cron_is_due(s, now):
                    triggered.append(s)
                    s.last_triggered_at = now.isoformat()
            elif s.schedule_type == "once":
                if s.run_at and now >= datetime.fromisoformat(s.run_at):
                    triggered.append(s)
                    to_delete.append(s.id)

        # Insert at head (reversed to preserve order if multiple trigger at once)
        for s in reversed(triggered):
            todo_manager.add_at_head(s.description)
            logger.info(
                "Schedule triggered: [{}] {} -> TODO head",
                s.id, s.description,
            )

        # Delete one-shot schedules after trigger
        for sid in to_delete:
            self.remove(sid)
            logger.info("One-shot schedule consumed and removed: [{}]", sid)

    def _cron_is_due(self, schedule: Schedule, now: datetime) -> bool:
        """Check if a cron schedule is due relative to its last trigger."""
        if not croniter.is_valid(schedule.cron):
            return False

        if schedule.last_triggered_at:
            # Get the next cron time after the last trigger
            try:
                base = datetime.fromisoformat(schedule.last_triggered_at)
            except ValueError:
                base = now
            cron = croniter(schedule.cron, base)
            next_time = cron.get_next(datetime)
            return next_time <= now
        else:
            # Never triggered: check if the first occurrence is <= now
            cron = croniter(schedule.cron, now - timedelta(days=1))
            next_time = cron.get_next(datetime)
            return next_time <= now
