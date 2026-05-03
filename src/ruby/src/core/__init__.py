# Audited: unused re-exports removed 2026-03-26
# Grep across src/ruby/ --include="*.py" found 0 hits for
# `from core import <symbol>` for every symbol previously re-exported here.
# All consumers import directly from the submodules, e.g.:
#
#   from core.breakout_types import BreakoutType
#   from core.cache import cache_get, cache_set
#   from core.models import ASSETS, init_db
#   from core.multi_session import RBSession, get_session
#   from core.logging_config import get_logger
#   from core.alerts import AlertDispatcher
#
# If you need to add a genuine public re-export, add it here together with an
# entry in __all__ and a note explaining which consumer requires it.
"""
lib.core — Core infrastructure modules.

Import directly from the relevant sub-module:

    from core.alerts import AlertDispatcher, get_dispatcher, send_risk_alert
    from core.breakout_types import BreakoutType, get_range_config
    from core.cache import cache_get, cache_set, get_daily
    from core.logging_config import get_logger, setup_logging
    from core.models import ASSETS, init_db, get_open_trades
    from core.multi_session import RBSession, ORBSession, get_session

.. note::

   ``RBSession`` is the preferred name (Phase 1G rename).
   ``ORBSession`` is kept as a backward-compatible alias in multi_session.py.
"""

__all__: list[str] = []
