"""Shim package mapping legacy services.data.* imports to fks_data.* modules.

Routers inside fks_api still import paths like services.data.manager / active_assets.
To avoid broad refactors, we provide a thin re-export layer that points to the
actual implementations shipped in the fks_data package.
"""
from importlib import import_module as _im

manager = _im('fks_data.manager')  # noqa: F401
active_assets = _im('fks_data.active_assets')  # noqa: F401

__all__ = ['manager', 'active_assets']
