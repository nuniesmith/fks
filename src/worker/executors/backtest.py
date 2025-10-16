from typing import Any

executors.base import Task, TaskExecutor


class BacktestExecutor(TaskExecutor):
    def __init__(self, config: dict):
        super().__init__("backtest", config)

    async def _execute_task(self, task: Task) -> Any:
        """Execute backtest task"""
        strategy_id = task.payload["strategy_id"]
        params = task.payload["parameters"]

        # Load strategy
        strategy = await self._load_strategy(strategy_id)

        # Run backtest
        results = await self._run_backtest(
            strategy=strategy,
            start_date=params["start_date"],
            end_date=params["end_date"],
            initial_capital=params["initial_capital"],
        )

        # Calculate metrics
        metrics = await self._calculate_metrics(results)

        return {
            "strategy_id": strategy_id,
            "parameters": params,
            "results": results,
            "metrics": metrics,
        }
