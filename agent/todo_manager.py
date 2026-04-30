"""TODO task manager - persistent task list for autonomous agent."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import aiofiles
from loguru import logger


@dataclass
class Task:
    id: str
    description: str
    status: str = "pending"
    created_at: str = ""
    completed_at: str | None = None

    @staticmethod
    def create(description: str) -> Task:
        now = datetime.now().isoformat()
        return Task(
            id=uuid.uuid4().hex[:8],
            description=description,
            status="pending",
            created_at=now,
        )


class TodoManager:
    """Persistent TODO task list backed by JSON file."""

    def __init__(self, persist_path: Path):
        self.persist_path = persist_path
        self.tasks: list[Task] = []

    async def load(self) -> bool:
        if not self.persist_path.exists():
            self.tasks = []
            return False
        try:
            async with aiofiles.open(self.persist_path, "r", encoding="utf-8") as f:
                raw = await f.read()
            data = json.loads(raw)
            self.tasks = [Task(**item) for item in data]
            logger.info(f"Loaded {len(self.tasks)} TODO tasks from {self.persist_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load TODO tasks: {e}")
            self.tasks = []
            return False

    async def save(self):
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(t) for t in self.tasks]
        async with aiofiles.open(self.persist_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

    def add(self, description: str) -> Task:
        task = Task.create(description)
        self.tasks.append(task)
        return task

    def get_next(self) -> Task | None:
        for task in self.tasks:
            if task.status == "pending":
                return task
        return None

    def complete(self, task_id: str) -> bool:
        for task in self.tasks:
            if task.id == task_id and task.status == "pending":
                task.status = "completed"
                task.completed_at = datetime.now().isoformat()
                return True
        return False

    def list_pending(self) -> list[Task]:
        return [t for t in self.tasks if t.status == "pending"]

    def list_all(self) -> list[Task]:
        return list(self.tasks)

    def is_empty(self) -> bool:
        return all(t.status != "pending" for t in self.tasks)

    def format_status(self) -> str:
        if not self.tasks:
            return "当前没有任务。"

        lines = ["## 待办任务"]
        for task in self.tasks:
            if task.status == "pending":
                lines.append(f"- [ ] {task.description} (id: {task.id})")
            else:
                lines.append(f"- [x] ~~{task.description}~~ (id: {task.id})")
        return "\n".join(lines)
