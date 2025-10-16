"""Cron-based scheduling (placeholder)."""


def schedule_cron(expr: str, task):  # pragma: no cover - placeholder
	return {"cron": expr, "task": getattr(task, "__name__", str(task))}


__all__ = ["schedule_cron"]

