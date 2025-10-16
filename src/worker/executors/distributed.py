from datetime import datetime

from framework.patterns.space_based import ProcessingUnit
tasks.base import BaseTask, TaskContext


class DistributedTaskExecutor(ProcessingUnit):
    """
    Distributed task executor using Space-Based Architecture
    """

    def __init__(self, name: str, task_space, result_space):
        super().__init__(name, self._process_tasks, task_space)
        self.result_space = result_space
        self.task_registry = {}

    def register_task(self, task: BaseTask) -> None:
        """Register a task for execution"""
        self.task_registry[task.name] = task

    async def _process_tasks(self, space) -> None:
        """Process tasks from space"""
        # Take task from space
        task_data = await space.take(lambda t: t.get("type") == "task", timeout=1.0)

        if task_data:
            context = TaskContext(**task_data["context"])
            task = self.task_registry.get(context.task_name)

            if task:
                try:
                    # Execute task
                    result = await task.run(context)

                    # Put result in result space
                    await self.result_space.put(
                        {
                            "task_id": context.task_id,
                            "task_name": context.task_name,
                            "status": "success",
                            "result": result,
                            "timestamp": datetime.utcnow(),
                        }
                    )

                except Exception as e:
                    # Put error in result space
                    await self.result_space.put(
                        {
                            "task_id": context.task_id,
                            "task_name": context.task_name,
                            "status": "failure",
                            "error": str(e),
                            "timestamp": datetime.utcnow(),
                        }
                    )
