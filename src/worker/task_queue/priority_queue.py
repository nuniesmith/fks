"""Priority queue implementation (placeholder)."""

import heapq
from typing import Any


class PriorityQueue:
	def __init__(self):
		self._items: list[tuple[int, Any]] = []

	def push(self, priority: int, item: Any) -> None:  # pragma: no cover - placeholder
		heapq.heappush(self._items, (priority, item))

	def pop(self) -> Any | None:  # pragma: no cover - placeholder
		return heapq.heappop(self._items)[1] if self._items else None


__all__ = ["PriorityQueue"]

