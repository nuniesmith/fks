"""Process-based executor (placeholder)."""

from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable


class ProcessExecutor:
	def __init__(self, max_workers: int | None = None):
		self._pool = ProcessPoolExecutor(max_workers=max_workers)

	def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):  # pragma: no cover
		return self._pool.submit(fn, *args, **kwargs)


__all__ = ["ProcessExecutor"]

