"""Queue manager (placeholder)."""

from collections import deque
from typing import Any


class QueueManager:
	def __init__(self):
		self._q: deque[Any] = deque()

	def push(self, item: Any) -> None:  # pragma: no cover - placeholder
		self._q.append(item)

	def pop(self) -> Any | None:  # pragma: no cover - placeholder
		return self._q.popleft() if self._q else None


__all__ = ["QueueManager"]

