import asyncio
import heapq
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from croniter import croniter
from framework.base import BaseComponent

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"


@dataclass
class ScheduledTask:
    task_id: str
    task_name: str
    schedule_type: ScheduleType
    parameters: Dict[str, Any]
    priority: int
    next_run: Optional[datetime] = None
    cron_expression: Optional[str] = None
    interval: Optional[timedelta] = None
    is_one_time: bool = False


class TaskScheduler(BaseComponent):
    """
    Advanced task scheduler with multiple scheduling strategies
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__("scheduler", config)
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.pending_queue: List[tuple] = []  # Priority queue for one-time tasks
        self.running = False
        self._check_interval = config.get("check_interval_seconds", 1)

    async def initialize(self) -> None:
        """Initialize scheduler with configured jobs"""
        try:
            for job_config in self.config.get("jobs", []):
                await self._load_job_from_config(job_config)
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            raise

    async def _load_job_from_config(self, job_config: Dict[str, Any]) -> None:
        """Load a job from configuration"""
        schedule = job_config["schedule"]

        if self._is_cron_expression(schedule):
            await self.schedule_cron(
                task_name=job_config["task_type"],
                cron_expression=schedule,
                parameters=job_config.get("payload", {}),
                priority=job_config.get("priority", 5),
            )
        else:
            logger.warning(f"Unsupported schedule format: {schedule}")

    async def schedule_cron(
        self,
        task_name: str,
        cron_expression: str,
        parameters: Dict[str, Any] = None,
        priority: int = 5,
    ) -> str:
        """Schedule a task using cron expression"""
        try:
            croniter(cron_expression)  # Validate cron expression
        except ValueError as e:
            raise ValueError(f"Invalid cron expression '{cron_expression}': {e}")

        task_id = self._generate_task_id()
        task = ScheduledTask(
            task_id=task_id,
            task_name=task_name,
            schedule_type=ScheduleType.CRON,
            parameters=parameters or {},
            priority=priority,
            cron_expression=cron_expression,
        )

        self.scheduled_tasks[task_id] = task
        self._update_next_cron_run(task_id)

        logger.info(
            f"Scheduled cron task '{task_name}' with expression '{cron_expression}'"
        )
        return task_id

    async def schedule_interval(
        self,
        task_name: str,
        interval_seconds: int,
        parameters: Dict[str, Any] = None,
        priority: int = 5,
    ) -> str:
        """Schedule a task to run at fixed intervals"""
        if interval_seconds <= 0:
            raise ValueError("Interval must be greater than 0")

        task_id = self._generate_task_id()
        interval = timedelta(seconds=interval_seconds)

        task = ScheduledTask(
            task_id=task_id,
            task_name=task_name,
            schedule_type=ScheduleType.INTERVAL,
            parameters=parameters or {},
            priority=priority,
            interval=interval,
            next_run=datetime.utcnow() + interval,
        )

        self.scheduled_tasks[task_id] = task

        logger.info(
            f"Scheduled interval task '{task_name}' every {interval_seconds} seconds"
        )
        return task_id

    async def schedule_once(
        self,
        task_name: str,
        run_at: datetime,
        parameters: Dict[str, Any] = None,
        priority: int = 5,
    ) -> str:
        """Schedule a one-time task"""
        if run_at <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")

        task_id = self._generate_task_id()

        task_data = {
            "task_name": task_name,
            "parameters": parameters or {},
            "one_time": True,
        }

        heapq.heappush(
            self.pending_queue, (run_at.timestamp(), priority, task_id, task_data)
        )

        logger.info(f"Scheduled one-time task '{task_name}' for {run_at}")
        return task_id

    async def start(self) -> None:
        """Start the scheduler"""
        self.running = True
        logger.info("Task scheduler started")

        # Initialize next run times for existing tasks
        await self._initialize_next_runs()

        try:
            while self.running:
                await self._process_scheduled_tasks()
                await asyncio.sleep(self._check_interval)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            raise
        finally:
            logger.info("Task scheduler stopped")

    async def stop(self) -> None:
        """Stop the scheduler"""
        self.running = False

    async def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task"""
        if task_id in self.scheduled_tasks:
            del self.scheduled_tasks[task_id]
            logger.info(f"Removed scheduled task {task_id}")
            return True
        return False

    async def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a scheduled task"""
        task = self.scheduled_tasks.get(task_id)
        if task:
            return {
                "task_id": task.task_id,
                "task_name": task.task_name,
                "schedule_type": task.schedule_type.value,
                "next_run": task.next_run,
                "priority": task.priority,
                "parameters": task.parameters,
            }
        return None

    async def _initialize_next_runs(self) -> None:
        """Initialize next run times for all scheduled tasks"""
        for task_id, task in self.scheduled_tasks.items():
            if task.schedule_type == ScheduleType.CRON:
                self._update_next_cron_run(task_id)

    async def _process_scheduled_tasks(self) -> None:
        """Process all scheduled tasks that are due"""
        now = datetime.utcnow()

        # Process regular scheduled tasks
        for task_id, task in list(self.scheduled_tasks.items()):
            if task.next_run and task.next_run <= now:
                await self._execute_scheduled_task(task_id, task)

        # Process one-time tasks
        while self.pending_queue and self.pending_queue[0][0] <= now.timestamp():
            timestamp, priority, task_id, task_data = heapq.heappop(self.pending_queue)
            await self._execute_one_time_task(task_id, task_data)

    async def _execute_scheduled_task(self, task_id: str, task: ScheduledTask) -> None:
        """Execute a scheduled task and update next run time"""
        try:
            await self._queue_task(task_id, task.task_name, task.parameters)

            # Update next run time
            if task.schedule_type == ScheduleType.CRON:
                self._update_next_cron_run(task_id)
            elif task.schedule_type == ScheduleType.INTERVAL:
                task.next_run = datetime.utcnow() + task.interval

        except Exception as e:
            logger.error(f"Failed to execute scheduled task {task_id}: {e}")

    async def _execute_one_time_task(
        self, task_id: str, task_data: Dict[str, Any]
    ) -> None:
        """Execute a one-time task"""
        try:
            await self._queue_task(
                task_id, task_data["task_name"], task_data["parameters"]
            )
        except Exception as e:
            logger.error(f"Failed to execute one-time task {task_id}: {e}")

    async def _queue_task(
        self, task_id: str, task_name: str, parameters: Dict[str, Any]
    ) -> None:
        """Queue a task for execution"""
        # Create task object - assuming Task class exists
        executors.base import Task

        task = Task(
            id=f"{task_name}_{task_id}_{datetime.utcnow().timestamp()}",
            type=task_name,
            payload=parameters,
        )

        await self.queue_task(task)
        logger.debug(f"Queued task {task_name} with ID {task_id}")

    def _update_next_cron_run(self, task_id: str) -> None:
        """Update next run time for a cron task"""
        task = self.scheduled_tasks[task_id]
        if task.cron_expression:
            cron = croniter(task.cron_expression, datetime.utcnow())
            task.next_run = cron.get_next(datetime)

    def _generate_task_id(self) -> str:
        """Generate a unique task ID"""
        return str(uuid.uuid4())

    def _is_cron_expression(self, schedule: str) -> bool:
        """Check if a string is a valid cron expression"""
        try:
            croniter(schedule)
            return True
        except ValueError:
            return False
