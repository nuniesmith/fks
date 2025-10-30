"""Celery tasks for fks_app service."""

from .asmbtr_prediction import predict_asmbtr_task

__all__ = ["predict_asmbtr_task"]
