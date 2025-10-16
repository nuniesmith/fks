from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional

from framework.base import BaseComponent


@dataclass
class Task:
    id: str
    type: str
    payload: dict
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class TaskResult:
    task_id: str
    status: str  # 'success', 'failure', 'retry'
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ProcessingUnit:
    name: str
    processor: Callable


class TaskExecutor(BaseComponent):
    def __init__(self, task_type: str, config: dict):
        super().__init__(f"executor_{task_type}", config)
        self.task_type = task_type
        self.processing_units = []

    async def initialize(self):
        """Initialize executor"""
        # Setup processing units for parallel execution
        num_workers = self.config.get("workers", 4)
        for i in range(num_workers):
            unit = ProcessingUnit(
                name=f"{self.task_type}_worker_{i}", processor=self._process_task
            )
            self.processing_units.append(unit)

    async def execute(self, task: Task) -> TaskResult:
        """Execute a task"""
        try:
            # Pre-execution checks
            if not await self._can_execute(task):
                return TaskResult(
                    task_id=task.id, status="failure", error="Task cannot be executed"
                )

            # Execute task
            result = await self._execute_task(task)

            # Post-execution processing
            await self._post_process(task, result)

            return TaskResult(task_id=task.id, status="success", result=result)

        except Exception as e:
            return await self._handle_error(task, e)

    @abstractmethod
    async def _execute_task(self, task: Task) -> Any:
        """Execute the actual task logic"""
        pass
