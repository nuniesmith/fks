from datetime import datetime
from typing import Any, Dict

tasks.base import BaseTask, TaskContext


class DailyReportTask(BaseTask):
    """Generate daily performance reports"""

    def __init__(self):
        super().__init__("generate_daily_report")

    async def execute(self, context: TaskContext) -> Dict[str, Any]:
        """Generate daily report"""
        report_type = context.parameters.get("report_type", "performance")
        recipients = context.parameters.get("recipients", [])

        # Gather data
        data = await self._gather_report_data(report_type)

        # Generate report
        report = await self._generate_report(data, report_type)

        # Send report
        await self._send_report(report, recipients)

        return {
            "report_type": report_type,
            "recipients": recipients,
            "status": "sent",
            "timestamp": datetime.utcnow(),
        }
