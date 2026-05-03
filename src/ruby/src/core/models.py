"""Backward-compatible re-export facade — all symbols moved to dedicated modules.

This file exists so that the 100+ import sites across the codebase
(``from core.models import ...`` and ``from core import models``)
continue to work without modification.

Actual implementations now live in:
  - lib.core.contracts  — contract specs, account profiles, watchlists, tickers
  - lib.core.db_layer   — DB config, connection wrappers, row helpers, statuses
  - lib.core.schema     — DDL strings, init_db(), _init_audit_tables()
  - lib.core.trades     — trade CRUD, query helpers, daily P&L, risk helpers
  - lib.core.journal    — daily journal CRUD
  - lib.core.audit      — risk-event & ORB-event CRUD, audit summary
  - lib.core.migration  — SQLite → Postgres one-time migration
"""

from core.audit import *  # noqa: F401,F403
from core.contracts import *  # noqa: F401,F403
from core.db_layer import *  # noqa: F401,F403
from core.journal import *  # noqa: F401,F403
from core.migration import *  # noqa: F401,F403
from core.schema import *  # noqa: F401,F403
from core.trades import *  # noqa: F401,F403
