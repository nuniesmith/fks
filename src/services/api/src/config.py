"""Configuration for fks_api service.

Provides a small Pydantic settings wrapper plus a convenience getter with
`functools.lru_cache` so importing modules get a singleton-ish settings
instance without global mutation. Designed to interoperate with the optional
`shared_python` package but remain fully functional standalone.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional
import os

try:  # Prefer pydantic v2
	from pydantic import BaseSettings
except Exception:  # pragma: no cover - fallback
	from pydantic import BaseModel as BaseSettings  # type: ignore


class Settings(BaseSettings):
	app_name: str = "FKS Trading API"
	app_version: str = os.getenv("APP_VERSION", "0.1.0")
	environment: str = os.getenv("APP_ENV", "development")
	api_port: int = int(os.getenv("API_SERVICE_PORT", "8000"))
	allow_origins: str = os.getenv("CORS_ORIGINS", "")
	use_shared: bool = os.getenv("USE_SHARED", "0") == "1"
	celery_broker_url: Optional[str] = os.getenv("CELERY_BROKER_URL")
	celery_result_backend: Optional[str] = os.getenv("CELERY_RESULT_BACKEND")

	class Config:  # type: ignore[override]
		env_prefix = "FKS_"  # Allow FKS_APP_NAME etc.
		case_sensitive = False

	def cors_origin_list(self) -> list[str]:
		base = [
			"http://localhost",
			"http://localhost:3000",
			"http://localhost:8080",
			"http://localhost:8081",
			"http://fks_web:3000",
			"http://web:3000",
		]
		extra = [o.strip() for o in self.allow_origins.split(",") if o.strip()]
		# preserve order while deduplicating
		seen = set()
		out: list[str] = []
		for o in base + extra:
			if o not in seen:
				seen.add(o)
				out.append(o)
		return out


@lru_cache
def get_settings() -> Settings:
	return Settings()  # type: ignore[arg-type]


__all__ = ["Settings", "get_settings"]
