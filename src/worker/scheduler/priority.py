"""Priority-based scheduling (placeholder)."""


def schedule_priority(priority: int, task):  # pragma: no cover - placeholder
	return {"priority": priority, "task": getattr(task, "__name__", str(task))}


__all__ = ["schedule_priority"]

