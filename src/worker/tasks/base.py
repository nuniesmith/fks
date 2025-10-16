import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class TaskContext:
    """Context passed to each task"""

    task_id: str
    task_name: str
    parameters: Dict[str, Any]
    attempt: int = 1
    max_attempts: int = 3
    timeout: Optional[int] = None
    priority: int = 5


class BaseTask(ABC):
    """Base class for all tasks"""

    def __init__(self, name: str):
        self.name = name
        self.logger = self._setup_logger()
        self.metrics = self._setup_metrics()

    @abstractmethod
    async def execute(self, context: TaskContext) -> Any:
        """Execute the task logic"""
        pass

    async def run(self, context: TaskContext) -> Any:
        """Run task with error handling and metrics"""
        start_time = datetime.utcnow()

        try:
            # Pre-execution
            await self.before_execute(context)

            # Execute with timeout
            if context.timeout:
                result = await asyncio.wait_for(
                    self.execute(context), timeout=context.timeout
                )
            else:
                result = await self.execute(context)

            # Post-execution
            await self.after_execute(context, result)

            # Record success metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.metrics.record_success(self.name, duration)

            return result

        except asyncio.TimeoutError:
            self.logger.error(f"Task {context.task_id} timed out")
            self.metrics.record_timeout(self.name)
            raise

        except Exception as e:
            self.logger.error(f"Task {context.task_id} failed: {e}")
            self.metrics.record_failure(self.name)

            # Retry logic
            if context.attempt < context.max_attempts:
                context.attempt += 1
                self.logger.info(
                    f"Retrying task {context.task_id}, attempt {context.attempt}"
                )
                return await self.run(context)
            raise

    async def before_execute(self, context: TaskContext) -> None:
        """Hook called before task execution"""
        pass

    async def after_execute(self, context: TaskContext, result: Any) -> None:
        """Hook called after successful execution"""
        pass
