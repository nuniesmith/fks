import logging
from typing import Dict, Optional

from shared.python.src.framework.base import BaseService
from framework.infrastructure.messaging import TaskQueue
from framework.patterns.space_based import SpaceBasedArchitecture
from executors.base import TaskExecutor
from monitoring import WorkerMonitor
from task_queue import TaskQueueManager
from scheduler import TaskScheduler

logger = logging.getLogger(__name__)


class WorkerService(BaseService):
    """
    Worker Service - Background task processing with distributed architecture

    Features:
    - Distributed task execution via Space-Based Architecture
    - Cron and interval scheduling
    - Priority-based task processing
    - Task retry and failure handling
    - Resource management and monitoring
    """

    def __init__(self):
        super().__init__("worker")
        self._scheduler: Optional[TaskScheduler] = None
        self._queue_manager: Optional[TaskQueueManager] = None
        self._executor_manager: Optional[TaskExecutor] = None
        self._monitor: Optional[WorkerMonitor] = None
        self._sba: Optional[SpaceBasedArchitecture] = None
        self._task_space = None
        self._result_space = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all worker service components"""
        if self._initialized:
            logger.warning("WorkerService already initialized")
            return

        try:
            logger.info("Initializing WorkerService...")

            # Initialize core components in dependency order
            await self._initialize_sba()
            await self._initialize_queue_manager()
            await self._initialize_executor_manager()
            await self._initialize_scheduler()
            await self._initialize_monitoring()

            # Register tasks after all components are ready
            await self._register_tasks()

            self._initialized = True
            logger.info("WorkerService initialization completed")

        except Exception as e:
            logger.error(f"Failed to initialize WorkerService: {e}")
            await self._cleanup_partial_initialization()
            raise

    async def _initialize_sba(self) -> None:
        """Initialize Space-Based Architecture for distributed processing"""
        logger.debug("Initializing Space-Based Architecture...")

        self._sba = SpaceBasedArchitecture()
        self._task_space = self._sba.create_space("tasks")
        self._result_space = self._sba.create_space("results")

        # Configure space policies
        await self._configure_spaces()

    async def _configure_spaces(self) -> None:
        """Configure space policies and replication"""
        space_config = self.config.get("sba", {})

        if "task_space" in space_config:
            await self._task_space.configure(space_config["task_space"])

        if "result_space" in space_config:
            await self._result_space.configure(space_config["result_space"])

    async def _initialize_queue_manager(self) -> None:
        """Initialize task queue manager"""
        logger.debug("Initializing TaskQueueManager...")

        queue_config = self.config.get("queues", {})
        self._queue_manager = TaskQueueManager(queue_config)
        await self._queue_manager.initialize()

    async def _initialize_executor_manager(self) -> None:
        """Initialize task executor manager"""
        logger.debug("Initializing TaskExecutor...")

        executor_config = self.config.get("executors", {})
        self._executor_manager = TaskExecutor(
            config=executor_config,
            task_space=self._task_space,
            result_space=self._result_space,
        )
        await self._executor_manager.initialize()

    async def _initialize_scheduler(self) -> None:
        """Initialize task scheduler"""
        logger.debug("Initializing TaskScheduler...")

        scheduler_config = self.config.get("scheduler", {})
        self._scheduler = TaskScheduler(
            config=scheduler_config, queue_manager=self._queue_manager
        )
        await self._scheduler.initialize()

    async def _initialize_monitoring(self) -> None:
        """Initialize monitoring and metrics collection"""
        logger.debug("Initializing WorkerMonitor...")

        monitor_config = self.config.get("monitoring", {})
        self._monitor = WorkerMonitor(
            config=monitor_config,
            scheduler=self._scheduler,
            queue_manager=self._queue_manager,
            executor_manager=self._executor_manager,
        )
        await self._monitor.initialize()

    async def _register_tasks(self) -> None:
        """Register available tasks with the scheduler"""
        logger.debug("Registering tasks...")

        task_definitions = self.config.get("tasks", {})
        for task_name, task_config in task_definitions.items():
            await self._scheduler.register_task(task_name, task_config)

    async def _cleanup_partial_initialization(self) -> None:
        """Clean up partially initialized components"""
        logger.debug("Cleaning up partial initialization...")

        components = [
            self._monitor,
            self._scheduler,
            self._executor_manager,
            self._queue_manager,
        ]

        for component in components:
            if component:
                try:
                    await component.shutdown()
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}")

    async def start(self) -> None:
        """Start the worker service"""
        if not self._initialized:
            raise RuntimeError("WorkerService not initialized")

        logger.info("Starting WorkerService...")

        # Start components in order
        await self._queue_manager.start()
        await self._executor_manager.start()
        await self._scheduler.start()
        await self._monitor.start()

        logger.info("WorkerService started successfully")

    async def stop(self) -> None:
        """Stop the worker service gracefully"""
        logger.info("Stopping WorkerService...")

        # Stop components in reverse order
        if self._monitor:
            await self._monitor.stop()
        if self._scheduler:
            await self._scheduler.stop()
        if self._executor_manager:
            await self._executor_manager.stop()
        if self._queue_manager:
            await self._queue_manager.stop()

        logger.info("WorkerService stopped")

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all worker components"""
        health_status = {
            "scheduler": False,
            "queue_manager": False,
            "executor_manager": False,
            "monitor": False,
            "sba": False,
        }

        if self._scheduler:
            health_status["scheduler"] = await self._scheduler.is_healthy()
        if self._queue_manager:
            health_status["queue_manager"] = await self._queue_manager.is_healthy()
        if self._executor_manager:
            health_status["executor_manager"] = (
                await self._executor_manager.is_healthy()
            )
        if self._monitor:
            health_status["monitor"] = await self._monitor.is_healthy()
        if self._sba:
            health_status["sba"] = await self._sba.is_healthy()

        return health_status

    @property
    def scheduler(self) -> TaskScheduler:
        """Get the task scheduler instance"""
        if not self._scheduler:
            raise RuntimeError("Scheduler not initialized")
        return self._scheduler

    @property
    def queue_manager(self) -> TaskQueueManager:
        """Get the queue manager instance"""
        if not self._queue_manager:
            raise RuntimeError("Queue manager not initialized")
        return self._queue_manager

    @property
    def executor_manager(self) -> TaskExecutor:
        """Get the executor manager instance"""
        if not self._executor_manager:
            raise RuntimeError("Executor manager not initialized")
        return self._executor_manager
