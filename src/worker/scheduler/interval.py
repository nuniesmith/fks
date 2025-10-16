"""Interval scheduling (placeholder)."""


def schedule_interval(seconds: float, task):  # pragma: no cover - placeholder
	return {"interval": seconds, "task": getattr(task, "__name__", str(task))}


__all__ = ["schedule_interval"]

