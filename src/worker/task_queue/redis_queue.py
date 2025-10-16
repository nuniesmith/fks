"""Redis-based queue (placeholder)."""

from typing import Any


class RedisQueue:
	def push(self, item: Any) -> None:  # pragma: no cover - placeholder
		pass

	def pop(self) -> Any | None:  # pragma: no cover - placeholder
		return None


__all__ = ["RedisQueue"]

