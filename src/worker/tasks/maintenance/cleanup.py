from typing import Any, Dict

from infrastructure.persistence.database import get_db
tasks.base import BaseTask, TaskContext


class DataCleanupTask(BaseTask):
    """Clean up old data from various tables"""

    def __init__(self):
        super().__init__("data_cleanup")

    async def execute(self, context: TaskContext) -> Dict[str, Any]:
        """Execute data cleanup"""
        older_than_days = context.parameters.get("older_than_days", 30)
        tables = context.parameters.get("tables", [])

        results = {"deleted_records": {}, "freed_space_mb": 0}

        async with get_db() as conn:
            for table in tables:
                self.logger.info(f"Cleaning {table}")

                # Delete old records
                deleted = await conn.execute(
                    f"""
                    DELETE FROM {table}
                    WHERE created_at < NOW() - INTERVAL '{older_than_days} days'
                    RETURNING COUNT(*)
                    """
                )

                results["deleted_records"][table] = deleted

            # Vacuum to reclaim space
            await conn.execute("VACUUM ANALYZE")

        return results
