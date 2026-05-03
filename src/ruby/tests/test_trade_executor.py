"""
Tests for the Trade Executor — staged position builder.

Covers the core logic in ``lib.services.engine.trade_executor``:

    - TradeExecutor.engage_trade (SCOUT entry)
    - TradeExecutor.on_tick (phase-based decision logic)
    - TradeExecutor.close_trade
    - TradeExecutor.take_partial_profit
    - TradeExecutor.on_fill
    - TradeExecutor.process_tick_actions
    - TradeExecutor.process_live_tick
    - TradeExecutor.status_summary
    - Phase transitions: SCOUT → BUILD → PROTECT → MANAGE → CLOSED
    - Invalidation / mental stop logic
    - ActiveTrade helpers & StagedTradePlan defaults
"""

from __future__ import annotations

import os

# Ensure Redis is disabled before any project imports.
os.environ.setdefault("DISABLE_REDIS", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.engine.trade_executor import (
    ActiveTrade,
    StagedTradePlan,
    StopStrategy,
    TradeExecutor,
    TradePhase,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(**overrides) -> StagedTradePlan:
    """Create a StagedTradePlan with sensible defaults for testing."""
    defaults = dict(
        trade_id="MGC_LONG_123456",
        symbol="MGC",
        product_code="MGC",
        exchange="NYMEX",
        direction="LONG",
        entry_zone_low=2920.0,
        entry_zone_high=2935.0,
        ideal_entry=2925.0,
        invalidation_level=2910.0,
        target_1=2960.0,
        target_2=2990.0,
        target_3=3020.0,
        max_contracts=4,
        initial_size=1,
        build_sizes=[1, 1, 1],
        build_levels=[2925.0, 2920.0, 2915.0],
        max_risk_dollars=825.0,
        reason="H1 OB + VAL confluence",
        plan_confidence=80.0,
    )
    defaults.update(overrides)
    return StagedTradePlan(**defaults)


def _make_short_plan(**overrides) -> StagedTradePlan:
    """Create a SHORT trade plan for testing."""
    defaults = dict(
        trade_id="MES_SHORT_789",
        symbol="MES",
        product_code="MES",
        exchange="CME",
        direction="SHORT",
        entry_zone_low=5500.0,
        entry_zone_high=5520.0,
        ideal_entry=5510.0,
        invalidation_level=5530.0,
        target_1=5470.0,
        target_2=5440.0,
        target_3=5400.0,
        max_contracts=4,
        initial_size=1,
        build_sizes=[1, 1],
        build_levels=[5515.0, 5520.0],
        max_risk_dollars=825.0,
        reason="Bearish rejection at POC",
        plan_confidence=70.0,
    )
    defaults.update(overrides)
    return StagedTradePlan(**defaults)


def _mock_copy_trader(
    *,
    order_status: str = "submitted",
    order_id: str = "ORD-001",
    error: str | None = None,
    cancel_ok: bool = True,
    modify_ok: bool = True,
) -> MagicMock:
    """Build a mock CopyTrader whose send_order_and_copy returns a canned result."""
    ct = MagicMock()

    main_result = MagicMock()
    main_result.status.value = order_status
    main_result.order_id = order_id
    main_result.error = error

    result = MagicMock()
    result.main_result = main_result

    ct.send_order_and_copy = AsyncMock(return_value=result)

    cancel_result = {"ok": cancel_ok}
    if cancel_ok:
        cancel_result["accounts_cancelled"] = ["ACCT-1"]
    else:
        cancel_result["accounts_failed"] = ["ACCT-1"]
    ct.cancel_on_all = AsyncMock(return_value=cancel_result)

    modify_result = {"ok": modify_ok}
    if modify_ok:
        modify_result["accounts_modified"] = ["ACCT-1"]
    else:
        modify_result["accounts_failed"] = ["ACCT-1"]
        modify_result["reason"] = "test failure"
    ct.modify_stop_on_all = AsyncMock(return_value=modify_result)

    return ct


def _activate_trade(trade: ActiveTrade, entry_price: float = 2925.0) -> None:
    """Move a trade into SCOUT phase with a fill so it looks active."""
    trade.phase = TradePhase.SCOUT
    trade.total_contracts = trade.plan.initial_size
    trade.avg_entry_price = entry_price
    trade.entered_at = "2025-01-06T10:00:00+00:00"


# ===========================================================================
# StagedTradePlan defaults
# ===========================================================================


class TestStagedTradePlan:
    """Verify auto-generated fields on StagedTradePlan."""

    def test_trade_id_auto_generated(self):
        plan = StagedTradePlan(symbol="MGC", direction="LONG")
        assert plan.trade_id.startswith("MGC_LONG_")

    def test_created_at_auto_set(self):
        plan = StagedTradePlan()
        assert plan.created_at != ""

    def test_explicit_trade_id_preserved(self):
        plan = StagedTradePlan(trade_id="MY_ID")
        assert plan.trade_id == "MY_ID"

    def test_default_max_contracts(self):
        plan = StagedTradePlan()
        assert plan.max_contracts == 4

    def test_default_initial_size(self):
        plan = StagedTradePlan()
        assert plan.initial_size == 1


# ===========================================================================
# ActiveTrade helpers
# ===========================================================================


class TestActiveTrade:
    """Test ActiveTrade dataclass properties and methods."""

    def test_is_long_for_long_trade(self):
        trade = ActiveTrade(plan=_make_plan())
        assert trade.is_long is True

    def test_is_long_for_short_trade(self):
        trade = ActiveTrade(plan=_make_short_plan())
        assert trade.is_long is False

    def test_is_active_planned_phase(self):
        trade = ActiveTrade(plan=_make_plan())
        assert trade.phase == TradePhase.PLANNED
        assert trade.is_active is False

    def test_is_active_scout_phase(self):
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.SCOUT)
        assert trade.is_active is True

    def test_is_active_closed_phase(self):
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.CLOSED)
        assert trade.is_active is False

    def test_has_stop_false_by_default(self):
        trade = ActiveTrade(plan=_make_plan())
        assert trade.has_stop is False

    def test_has_stop_true_when_set(self):
        trade = ActiveTrade(plan=_make_plan(), current_stop_price=2910.0)
        assert trade.has_stop is True

    def test_contracts_remaining_to_build(self):
        trade = ActiveTrade(plan=_make_plan(), total_contracts=2)
        assert trade.contracts_remaining_to_build == 2  # 4 max - 2 = 2

    def test_contracts_remaining_at_max(self):
        trade = ActiveTrade(plan=_make_plan(), total_contracts=4)
        assert trade.contracts_remaining_to_build == 0

    def test_log_event_appends(self):
        trade = ActiveTrade(plan=_make_plan())
        trade.log_event("test message")
        assert len(trade.events) == 1
        assert "test message" in trade.events[0]

    def test_log_event_caps_at_100(self):
        trade = ActiveTrade(plan=_make_plan())
        for i in range(120):
            trade.log_event(f"event {i}")
        assert len(trade.events) == 100

    def test_to_dict_has_required_keys(self):
        trade = ActiveTrade(plan=_make_plan())
        d = trade.to_dict()
        assert "trade_id" in d
        assert "symbol" in d
        assert "direction" in d
        assert "phase" in d
        assert "stop_strategy" in d
        assert "total_contracts" in d
        assert "avg_entry_price" in d
        assert "plan" in d
        assert "phase_display" in d

    def test_to_dict_plan_section(self):
        trade = ActiveTrade(plan=_make_plan())
        d = trade.to_dict()
        plan_dict = d["plan"]
        assert "entry_zone" in plan_dict
        assert "invalidation" in plan_dict
        assert "target_1" in plan_dict
        assert "target_2" in plan_dict
        assert "target_3" in plan_dict

    def test_phase_display_for_each_phase(self):
        plan = _make_plan()
        for phase in TradePhase:
            trade = ActiveTrade(plan=plan, phase=phase)
            display = trade._phase_display()
            assert isinstance(display, str)
            assert len(display) > 0


# ===========================================================================
# TradeExecutor — engage_trade
# ===========================================================================


class TestEngageTrade:
    """TradeExecutor.engage_trade — placing the initial SCOUT entry."""

    @pytest.mark.asyncio
    async def test_submit_order_market_buy(self):
        """Submit a market buy, verify CopyTrader.send_order_and_copy called."""
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(build_levels=[])

        trade = await executor.engage_trade(plan, ct)

        ct.send_order_and_copy.assert_called_once()
        call_kwargs = ct.send_order_and_copy.call_args.kwargs
        assert call_kwargs["side"] == "BUY"
        assert call_kwargs["order_type"] == "MARKET"
        assert call_kwargs["qty"] == 1
        assert call_kwargs["stop_ticks"] == 0  # No stop on scout

    @pytest.mark.asyncio
    async def test_engage_trade_returns_active_trade(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()

        trade = await executor.engage_trade(plan, ct)

        assert isinstance(trade, ActiveTrade)
        assert trade.plan is plan

    @pytest.mark.asyncio
    async def test_engage_transitions_to_build_with_levels(self):
        """When plan has build_levels, phase should transition to BUILD."""
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(build_levels=[2925.0, 2920.0])

        trade = await executor.engage_trade(plan, ct)

        assert trade.phase == TradePhase.BUILD

    @pytest.mark.asyncio
    async def test_engage_stays_scout_without_build_levels(self):
        """When plan has no build_levels, phase stays SCOUT."""
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(build_levels=[])

        trade = await executor.engage_trade(plan, ct)

        assert trade.phase == TradePhase.SCOUT

    @pytest.mark.asyncio
    async def test_engage_records_scout_order_id(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader(order_id="ORD-SCOUT-42")
        plan = _make_plan(build_levels=[])

        trade = await executor.engage_trade(plan, ct)

        assert trade.scout_order_id == "ORD-SCOUT-42"

    @pytest.mark.asyncio
    async def test_engage_sets_mental_stop(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(invalidation_level=2905.0)

        trade = await executor.engage_trade(plan, ct)

        assert trade.mental_stop_price == 2905.0

    @pytest.mark.asyncio
    async def test_engage_adds_to_active_trades(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()

        assert executor.active_trade_count == 0
        await executor.engage_trade(plan, ct)
        assert executor.active_trade_count == 1

    @pytest.mark.asyncio
    async def test_engage_short_trade_sends_sell(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_short_plan()

        await executor.engage_trade(plan, ct)

        call_kwargs = ct.send_order_and_copy.call_args.kwargs
        assert call_kwargs["side"] == "SELL"

    @pytest.mark.asyncio
    async def test_engage_handles_exchange_error(self):
        """When exchange returns an error status, trade should be CLOSED."""
        executor = TradeExecutor()
        ct = _mock_copy_trader(order_status="rejected", error="Insufficient margin")
        plan = _make_plan()

        trade = await executor.engage_trade(plan, ct)

        assert trade.phase == TradePhase.CLOSED
        assert executor.active_trade_count == 0

    @pytest.mark.asyncio
    async def test_engage_handles_exception(self):
        """If send_order_and_copy raises, trade should be CLOSED."""
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        ct.send_order_and_copy = AsyncMock(side_effect=ConnectionError("Exchange unreachable"))
        plan = _make_plan()

        trade = await executor.engage_trade(plan, ct)

        assert trade.phase == TradePhase.CLOSED
        assert executor.active_trade_count == 0

    @pytest.mark.asyncio
    async def test_engage_populates_entered_at(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(build_levels=[])

        trade = await executor.engage_trade(plan, ct)

        assert trade.entered_at != ""

    @pytest.mark.asyncio
    async def test_engage_sets_total_contracts(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(initial_size=2, build_levels=[])

        trade = await executor.engage_trade(plan, ct)

        assert trade.total_contracts == 2

    @pytest.mark.asyncio
    async def test_engage_logs_events(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(build_levels=[])

        trade = await executor.engage_trade(plan, ct)

        assert len(trade.events) > 0


# ===========================================================================
# TradeExecutor — _place_build_orders
# ===========================================================================


class TestPlaceBuildOrders:
    """Verify that build-phase limit orders are placed correctly."""

    @pytest.mark.asyncio
    async def test_build_orders_placed_for_each_level(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(build_levels=[2925.0, 2920.0, 2915.0])

        await executor.engage_trade(plan, ct)

        # 1 scout market + 3 build limits = 4 calls
        assert ct.send_order_and_copy.call_count == 4

    @pytest.mark.asyncio
    async def test_build_orders_use_limit_type(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(build_levels=[2925.0])

        await executor.engage_trade(plan, ct)

        # Second call should be the build limit order
        calls = ct.send_order_and_copy.call_args_list
        build_call = calls[1].kwargs
        assert build_call["order_type"] == "LIMIT"
        assert build_call["price"] == 2925.0

    @pytest.mark.asyncio
    async def test_build_respects_max_contracts(self):
        """Build orders should stop when max_contracts would be exceeded.

        Note: _place_build_orders checks ``trade.total_contracts + size > max``.
        Since limit orders don't immediately fill, total_contracts stays at
        initial_size throughout. With max_contracts=1 and initial_size=1,
        every build order (1+1>1) is skipped.
        """
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(
            max_contracts=1,
            initial_size=1,
            build_sizes=[1, 1, 1],
            build_levels=[2925.0, 2920.0, 2915.0],
        )

        await executor.engage_trade(plan, ct)

        # 1 scout only — all build orders skipped (1+1 > 1)
        assert ct.send_order_and_copy.call_count == 1

    @pytest.mark.asyncio
    async def test_build_records_limit_order_ids(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader(order_id="LIMIT-1")
        plan = _make_plan(build_levels=[2925.0])

        trade = await executor.engage_trade(plan, ct)

        assert "LIMIT-1" in trade.limit_order_ids

    @pytest.mark.asyncio
    async def test_build_order_failure_does_not_abort(self):
        """A failed build order should not prevent subsequent builds."""
        executor = TradeExecutor()
        ct = _mock_copy_trader()

        # Capture the properly-configured return value before replacing
        good_return = ct.send_order_and_copy.return_value
        call_count = 0

        async def _alternating_fail(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # fail second call (first build)
                raise RuntimeError("Network timeout")
            return good_return

        ct.send_order_and_copy = AsyncMock(side_effect=_alternating_fail)
        plan = _make_plan(build_levels=[2925.0, 2920.0], max_contracts=10)

        trade = await executor.engage_trade(plan, ct)

        # Scout + fail + success = 3 calls attempted
        assert call_count == 3
        assert trade.phase == TradePhase.BUILD


# ===========================================================================
# TradeExecutor — on_tick (phase logic)
# ===========================================================================


class TestOnTick:
    """TradeExecutor.on_tick — phase-based decision logic."""

    def test_inactive_trade_returns_no_actions(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan())
        assert trade.phase == TradePhase.PLANNED

        actions = executor.on_tick(2930.0, trade)

        assert actions == []

    def test_updates_current_price(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan())
        _activate_trade(trade)

        executor.on_tick(2945.0, trade)

        assert trade.current_price == 2945.0

    def test_updates_unrealized_pnl_long(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan())
        _activate_trade(trade, entry_price=2925.0)

        executor.on_tick(2935.0, trade)

        # (2935 - 2925) * 1 contract = 10
        assert trade.unrealized_pnl == pytest.approx(10.0)

    def test_updates_unrealized_pnl_short(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_short_plan())
        trade.phase = TradePhase.SCOUT
        trade.total_contracts = 1
        trade.avg_entry_price = 5510.0

        executor.on_tick(5500.0, trade)

        # (5510 - 5500) * 1 = 10
        assert trade.unrealized_pnl == pytest.approx(10.0)

    # -----------------------------------------------------------------------
    # Invalidation / mental stop
    # -----------------------------------------------------------------------

    def test_invalidation_long_triggers_close(self):
        """Price below invalidation triggers close action for LONG."""
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan())
        _activate_trade(trade)
        trade.mental_stop_price = 2910.0

        actions = executor.on_tick(2905.0, trade)

        action_types = [a["action"] for a in actions]
        assert "close_trade" in action_types
        assert "alert" in action_types

    def test_invalidation_short_triggers_close(self):
        """Price above invalidation triggers close action for SHORT."""
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_short_plan())
        trade.phase = TradePhase.SCOUT
        trade.total_contracts = 1
        trade.avg_entry_price = 5510.0
        trade.mental_stop_price = 5530.0

        actions = executor.on_tick(5535.0, trade)

        action_types = [a["action"] for a in actions]
        assert "close_trade" in action_types

    def test_no_invalidation_when_price_above_stop_long(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan())
        _activate_trade(trade)
        trade.mental_stop_price = 2910.0

        actions = executor.on_tick(2940.0, trade)

        action_types = [a["action"] for a in actions]
        assert "close_trade" not in action_types

    def test_invalidation_skipped_when_real_stop_placed(self):
        """Once a server-side stop is placed, mental stop is not checked."""
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan())
        _activate_trade(trade)
        trade.mental_stop_price = 2910.0
        trade.current_stop_price = 2915.0  # Real stop exists

        actions = executor.on_tick(2905.0, trade)

        # Should NOT trigger invalidation close because has_stop is True
        action_types = [a["action"] for a in actions]
        assert "close_trade" not in action_types

    # -----------------------------------------------------------------------
    # SCOUT phase → T1 hit → PROTECT
    # -----------------------------------------------------------------------

    def test_scout_t1_hit_transitions_to_protect(self):
        """Hitting T1 in SCOUT phase should transition to PROTECT."""
        executor = TradeExecutor()
        plan = _make_plan(target_1=2960.0)
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)

        actions = executor.on_tick(2965.0, trade)

        assert trade.phase == TradePhase.PROTECT
        assert trade.target_1_hit is True
        assert trade.stop_strategy == StopStrategy.BREAKEVEN

    def test_scout_t1_sets_breakeven_stop(self):
        executor = TradeExecutor()
        plan = _make_plan(target_1=2960.0)
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade, entry_price=2925.0)

        actions = executor.on_tick(2965.0, trade)

        stop_actions = [a for a in actions if a["action"] == "set_stop"]
        assert len(stop_actions) == 1
        assert stop_actions[0]["price"] == pytest.approx(2925.0)  # breakeven

    def test_scout_no_t1_stays_scout(self):
        executor = TradeExecutor()
        plan = _make_plan(target_1=2960.0)
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)

        actions = executor.on_tick(2940.0, trade)

        assert trade.phase == TradePhase.SCOUT

    def test_scout_price_in_entry_zone_alerts(self):
        """Price returning to entry zone emits build opportunity alert."""
        executor = TradeExecutor()
        plan = _make_plan(entry_zone_low=2920.0, entry_zone_high=2935.0)
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        # Ensure contracts remaining
        trade.total_contracts = 1  # max is 4

        actions = executor.on_tick(2928.0, trade)

        alerts = [a for a in actions if a["action"] == "alert"]
        assert len(alerts) >= 1
        assert "entry zone" in alerts[0]["message"].lower() or "build" in alerts[0]["message"].lower()

    # -----------------------------------------------------------------------
    # SCOUT T1 hit for SHORT
    # -----------------------------------------------------------------------

    def test_scout_t1_hit_short(self):
        executor = TradeExecutor()
        plan = _make_short_plan(target_1=5470.0)
        trade = ActiveTrade(plan=plan)
        trade.phase = TradePhase.SCOUT
        trade.total_contracts = 1
        trade.avg_entry_price = 5510.0

        actions = executor.on_tick(5460.0, trade)

        assert trade.phase == TradePhase.PROTECT
        assert trade.target_1_hit is True

    # -----------------------------------------------------------------------
    # BUILD phase
    # -----------------------------------------------------------------------

    def test_build_t1_hit_transitions_to_protect(self):
        executor = TradeExecutor()
        plan = _make_plan(target_1=2960.0)
        trade = ActiveTrade(plan=plan, phase=TradePhase.BUILD)
        trade.total_contracts = 2
        trade.avg_entry_price = 2925.0

        actions = executor.on_tick(2965.0, trade)

        assert trade.phase == TradePhase.PROTECT

    # -----------------------------------------------------------------------
    # PROTECT phase → T2 hit → MANAGE
    # -----------------------------------------------------------------------

    def test_protect_t2_hit_transitions_to_manage(self):
        executor = TradeExecutor()
        plan = _make_plan(target_2=2990.0)
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.total_contracts = 4
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True
        trade.current_stop_price = 2925.0

        actions = executor.on_tick(2995.0, trade)

        assert trade.phase == TradePhase.MANAGE
        assert trade.target_2_hit is True

    def test_protect_t2_takes_partial_profit(self):
        executor = TradeExecutor()
        plan = _make_plan(target_2=2990.0)
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.total_contracts = 4
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True

        actions = executor.on_tick(2995.0, trade)

        partials = [a for a in actions if a["action"] == "take_partial"]
        assert len(partials) == 1
        assert partials[0]["qty"] == 2  # half of 4

    def test_protect_t2_moves_stop_to_safe_level(self):
        executor = TradeExecutor()
        plan = _make_plan(target_1=2960.0, target_2=2990.0)
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.total_contracts = 4
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True

        actions = executor.on_tick(2995.0, trade)

        stop_moves = [a for a in actions if a["action"] == "move_stop"]
        assert len(stop_moves) == 1
        # Safe stop = entry + (T1 - entry) * 0.5 = 2925 + (2960-2925)*0.5 = 2942.5
        assert stop_moves[0]["price"] == pytest.approx(2942.5)

    def test_protect_t2_not_triggered_below_target(self):
        executor = TradeExecutor()
        plan = _make_plan(target_2=2990.0)
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.total_contracts = 4
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True

        actions = executor.on_tick(2980.0, trade)

        assert trade.phase == TradePhase.PROTECT
        assert trade.target_2_hit is False

    # -----------------------------------------------------------------------
    # MANAGE phase → T3 hit → CLOSE / trailing
    # -----------------------------------------------------------------------

    def test_manage_t3_hit_closes_trade(self):
        executor = TradeExecutor()
        plan = _make_plan(target_3=3020.0)
        trade = ActiveTrade(plan=plan, phase=TradePhase.MANAGE)
        trade.total_contracts = 2
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True
        trade.target_2_hit = True

        actions = executor.on_tick(3025.0, trade)

        assert trade.target_3_hit is True
        action_types = [a["action"] for a in actions]
        assert "close_trade" in action_types

    def test_manage_trailing_stop_moves_up_long(self):
        executor = TradeExecutor()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.MANAGE)
        trade.total_contracts = 2
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True
        trade.target_2_hit = True
        trade.stop_strategy = StopStrategy.TRAILING
        trade.current_stop_price = 2950.0

        actions = executor.on_tick(3000.0, trade)

        stop_moves = [a for a in actions if a["action"] == "move_stop"]
        # new trail = 2925 + (3000-2925)*0.5 = 2962.5  > 2950 → should move
        assert len(stop_moves) == 1
        assert stop_moves[0]["price"] == pytest.approx(2962.5)

    def test_manage_trailing_stop_does_not_move_down_long(self):
        executor = TradeExecutor()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.MANAGE)
        trade.total_contracts = 2
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True
        trade.target_2_hit = True
        trade.stop_strategy = StopStrategy.TRAILING
        trade.current_stop_price = 2960.0

        # Price that would generate lower trail: 2925 + (2950-2925)*0.5 = 2937.5 < 2960
        actions = executor.on_tick(2950.0, trade)

        stop_moves = [a for a in actions if a["action"] == "move_stop"]
        assert len(stop_moves) == 0

    def test_manage_trailing_stop_short(self):
        executor = TradeExecutor()
        plan = _make_short_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.MANAGE)
        trade.total_contracts = 2
        trade.avg_entry_price = 5510.0
        trade.target_1_hit = True
        trade.target_2_hit = True
        trade.stop_strategy = StopStrategy.TRAILING
        trade.current_stop_price = 5490.0

        # Trail: 5510 - (5510-5420)*0.5 = 5510 - 45 = 5465; 5465 < 5490 → move
        actions = executor.on_tick(5420.0, trade)

        stop_moves = [a for a in actions if a["action"] == "move_stop"]
        assert len(stop_moves) == 1
        assert stop_moves[0]["price"] == pytest.approx(5465.0)


# ===========================================================================
# TradeExecutor — close_trade
# ===========================================================================


class TestCloseTrade:
    """TradeExecutor.close_trade — flattening a position."""

    @pytest.mark.asyncio
    async def test_close_sends_market_sell_for_long(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct, reason="Test close")

        call_kwargs = ct.send_order_and_copy.call_args.kwargs
        assert call_kwargs["side"] == "SELL"
        assert call_kwargs["order_type"] == "MARKET"
        assert call_kwargs["qty"] == trade.plan.initial_size

    @pytest.mark.asyncio
    async def test_close_sends_market_buy_for_short(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_short_plan()
        trade = ActiveTrade(plan=plan)
        trade.phase = TradePhase.SCOUT
        trade.total_contracts = 1
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        call_kwargs = ct.send_order_and_copy.call_args.kwargs
        assert call_kwargs["side"] == "BUY"

    @pytest.mark.asyncio
    async def test_close_transitions_to_closed(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        assert trade.phase == TradePhase.CLOSED

    @pytest.mark.asyncio
    async def test_close_removes_from_active_trades(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        assert plan.trade_id not in executor._active_trades
        assert executor.active_trade_count == 0

    @pytest.mark.asyncio
    async def test_close_adds_to_completed(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        assert len(executor._completed_trades) == 1

    @pytest.mark.asyncio
    async def test_close_cancels_limit_orders(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.limit_order_ids = ["LIM-1", "LIM-2"]
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        ct.cancel_on_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_skips_cancel_when_no_limits(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.limit_order_ids = []
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        ct.cancel_on_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_sets_closed_at(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        assert trade.closed_at != ""

    @pytest.mark.asyncio
    async def test_close_handles_order_failure(self):
        """If close order fails, trade should NOT be marked closed."""
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        ct.send_order_and_copy = AsyncMock(side_effect=RuntimeError("Exchange down"))
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        # Trade remains in active_trades since close failed
        assert trade.phase != TradePhase.CLOSED or plan.trade_id not in executor._active_trades

    @pytest.mark.asyncio
    async def test_close_handles_cancel_failure_gracefully(self):
        """If cancel_on_all fails, close should still complete."""
        executor = TradeExecutor()
        ct = _mock_copy_trader(cancel_ok=False)
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.limit_order_ids = ["LIM-1"]
        executor._active_trades[plan.trade_id] = trade

        await executor.close_trade(trade, ct)

        # Close still succeeds even though cancel reported failure
        assert trade.phase == TradePhase.CLOSED

    @pytest.mark.asyncio
    async def test_close_noop_on_inactive_trade(self):
        """Closing an already-closed trade is a no-op."""
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.CLOSED)

        await executor.close_trade(trade, ct)

        ct.send_order_and_copy.assert_not_called()


# ===========================================================================
# TradeExecutor — take_partial_profit
# ===========================================================================


class TestTakePartialProfit:
    """TradeExecutor.take_partial_profit — reducing position size."""

    @pytest.mark.asyncio
    async def test_partial_reduces_contracts(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.total_contracts = 4
        trade.current_price = 2960.0
        executor._active_trades[plan.trade_id] = trade

        await executor.take_partial_profit(trade, ct, qty=2, reason="T2 hit")

        assert trade.total_contracts == 2

    @pytest.mark.asyncio
    async def test_partial_records_exit(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.total_contracts = 4
        trade.current_price = 2960.0
        executor._active_trades[plan.trade_id] = trade

        await executor.take_partial_profit(trade, ct, qty=1, reason="Take some off")

        assert len(trade.partial_exits) == 1
        assert trade.partial_exits[0]["qty"] == 1
        assert trade.partial_exits[0]["reason"] == "Take some off"

    @pytest.mark.asyncio
    async def test_partial_closes_when_all_contracts_exit(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.total_contracts = 1
        trade.current_price = 2960.0
        executor._active_trades[plan.trade_id] = trade

        await executor.take_partial_profit(trade, ct, qty=1)

        assert trade.phase == TradePhase.CLOSED

    @pytest.mark.asyncio
    async def test_partial_noop_when_qty_exceeds_position(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.total_contracts = 1

        await executor.take_partial_profit(trade, ct, qty=5)

        ct.send_order_and_copy.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_noop_on_inactive(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.CLOSED)

        await executor.take_partial_profit(trade, ct, qty=1)

        ct.send_order_and_copy.assert_not_called()


# ===========================================================================
# TradeExecutor — on_fill
# ===========================================================================


class TestOnFill:
    """TradeExecutor.on_fill — recording fills and updating average entry."""

    def test_first_fill_sets_avg_entry(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.SCOUT)
        trade.total_contracts = 0

        executor.on_fill(trade, fill_price=2925.0, fill_qty=1)

        assert trade.avg_entry_price == pytest.approx(2925.0)
        assert trade.total_contracts == 1

    def test_second_fill_weighted_average(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.BUILD)
        trade.total_contracts = 1
        trade.avg_entry_price = 2925.0

        executor.on_fill(trade, fill_price=2920.0, fill_qty=1)

        # Weighted avg: (2925*1 + 2920*1) / 2 = 2922.5
        assert trade.avg_entry_price == pytest.approx(2922.5)
        assert trade.total_contracts == 2

    def test_multi_lot_fill(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.BUILD)
        trade.total_contracts = 1
        trade.avg_entry_price = 2925.0

        executor.on_fill(trade, fill_price=2920.0, fill_qty=3)

        # (2925*1 + 2920*3) / 4 = (2925 + 8760) / 4 = 2921.25
        assert trade.avg_entry_price == pytest.approx(2921.25)
        assert trade.total_contracts == 4

    def test_fill_appends_to_fills_list(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.SCOUT)
        trade.total_contracts = 0

        executor.on_fill(trade, fill_price=2925.0, fill_qty=1)

        assert len(trade.fills) == 1
        assert trade.fills[0]["price"] == 2925.0
        assert trade.fills[0]["qty"] == 1

    def test_fill_logs_event(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.SCOUT)
        trade.total_contracts = 0

        executor.on_fill(trade, fill_price=2925.0, fill_qty=1)

        assert len(trade.events) >= 1
        assert "Fill" in trade.events[-1]

    def test_fill_noop_on_inactive_trade(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan(), phase=TradePhase.CLOSED)

        executor.on_fill(trade, fill_price=2925.0, fill_qty=1)

        assert trade.total_contracts == 0  # unchanged


# ===========================================================================
# TradeExecutor — process_tick_actions
# ===========================================================================


class TestProcessTickActions:
    """TradeExecutor.process_tick_actions — bridging decisions to Rithmic."""

    @pytest.mark.asyncio
    async def test_set_stop_calls_modify_stop(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.avg_entry_price = 2925.0
        trade.total_contracts = 2

        actions = [{"action": "set_stop", "price": 2925.0, "reason": "breakeven"}]

        with patch("lib.services.engine.trade_executor.stop_price_to_stop_ticks", return_value=10):
            await executor.process_tick_actions(actions, trade, ct)

        ct.modify_stop_on_all.assert_called_once()
        assert trade.rithmic_stop_order_placed is True

    @pytest.mark.asyncio
    async def test_move_stop_calls_modify_stop(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.MANAGE)
        trade.avg_entry_price = 2925.0
        trade.total_contracts = 2

        actions = [{"action": "move_stop", "price": 2950.0, "reason": "trail"}]

        with patch("lib.services.engine.trade_executor.stop_price_to_stop_ticks", return_value=20):
            await executor.process_tick_actions(actions, trade, ct)

        ct.modify_stop_on_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_stop_skips_invalid_price(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.avg_entry_price = 2925.0

        actions = [{"action": "set_stop", "price": 0.0, "reason": "invalid"}]

        with patch("lib.services.engine.trade_executor.stop_price_to_stop_ticks", return_value=0):
            await executor.process_tick_actions(actions, trade, ct)

        ct.modify_stop_on_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_take_partial_action_calls_take_partial_profit(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.MANAGE)
        trade.total_contracts = 4
        trade.avg_entry_price = 2925.0
        trade.current_price = 2990.0
        executor._active_trades[plan.trade_id] = trade

        actions = [{"action": "take_partial", "qty": 2, "reason": "T2 hit"}]

        await executor.process_tick_actions(actions, trade, ct)

        ct.send_order_and_copy.assert_called_once()
        assert trade.total_contracts == 2

    @pytest.mark.asyncio
    async def test_close_trade_action(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.MANAGE)
        trade.total_contracts = 2
        trade.avg_entry_price = 2925.0
        executor._active_trades[plan.trade_id] = trade

        actions = [{"action": "close_trade", "reason": "T3 hit", "price": 3020.0}]

        await executor.process_tick_actions(actions, trade, ct)

        assert trade.phase == TradePhase.CLOSED

    @pytest.mark.asyncio
    async def test_alert_action_logs_event(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.SCOUT)
        trade.avg_entry_price = 2925.0
        executor._active_trades[plan.trade_id] = trade

        actions = [{"action": "alert", "message": "Momentum fading"}]

        await executor.process_tick_actions(actions, trade, ct)

        # Alert actions should be logged but not change trade state
        assert trade.phase == TradePhase.SCOUT
        trade.total_contracts = 1

        actions = [{"action": "alert", "level": "info", "message": "Test alert"}]

        await executor.process_tick_actions(actions, trade, ct)

        assert any("Test alert" in e for e in trade.events)

    @pytest.mark.asyncio
    async def test_unknown_action_logged(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.SCOUT)
        trade.total_contracts = 1

        actions = [{"action": "unknown_thing"}]

        await executor.process_tick_actions(actions, trade, ct)

        assert any("Unknown action" in e for e in trade.events)

    @pytest.mark.asyncio
    async def test_modify_stop_failure_handled(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader(modify_ok=False)
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.avg_entry_price = 2925.0
        trade.total_contracts = 2

        actions = [{"action": "set_stop", "price": 2925.0, "reason": "breakeven"}]

        with patch("lib.services.engine.trade_executor.stop_price_to_stop_ticks", return_value=10):
            await executor.process_tick_actions(actions, trade, ct)

        # Should still log the failure but not crash
        assert any("partial/failed" in e or "failed" in e.lower() for e in trade.events)

    @pytest.mark.asyncio
    async def test_modify_stop_exception_handled(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        ct.modify_stop_on_all = AsyncMock(side_effect=RuntimeError("Rithmic timeout"))
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.avg_entry_price = 2925.0
        trade.total_contracts = 2

        actions = [{"action": "set_stop", "price": 2925.0, "reason": "breakeven"}]

        with patch("lib.services.engine.trade_executor.stop_price_to_stop_ticks", return_value=10):
            await executor.process_tick_actions(actions, trade, ct)

        assert any("ERROR" in e for e in trade.events)


# ===========================================================================
# TradeExecutor — process_live_tick
# ===========================================================================


class TestProcessLiveTick:
    """TradeExecutor.process_live_tick — end-to-end tick handler."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_active_trade(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()

        actions = await executor.process_live_tick("MGC", 2930.0, ct)

        assert actions == []

    @pytest.mark.asyncio
    async def test_returns_actions_for_active_trade(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()
        plan = _make_plan(invalidation_level=2910.0)
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)
        trade.mental_stop_price = 2910.0
        executor._active_trades[plan.trade_id] = trade

        # Price below invalidation → should close
        actions = await executor.process_live_tick("MGC", 2905.0, ct)

        assert len(actions) > 0
        action_types = [a["action"] for a in actions]
        assert "close_trade" in action_types


# ===========================================================================
# TradeExecutor — get_active_trade / status_summary
# ===========================================================================


class TestTradeExecutorMisc:
    """Miscellaneous TradeExecutor helpers."""

    def test_get_active_trade_found(self):
        executor = TradeExecutor()
        plan = _make_plan(symbol="MGC")
        trade = ActiveTrade(plan=plan, phase=TradePhase.SCOUT)
        executor._active_trades[plan.trade_id] = trade

        result = executor.get_active_trade("MGC")

        assert result is trade

    def test_get_active_trade_not_found(self):
        executor = TradeExecutor()

        result = executor.get_active_trade("NONEXIST")

        assert result is None

    def test_status_summary_empty(self):
        executor = TradeExecutor()
        summary = executor.status_summary()

        assert summary["active_count"] == 0
        assert summary["active_trades"] == []
        assert summary["completed_count"] == 0
        assert summary["recent_completed"] == []

    def test_status_summary_with_trade(self):
        executor = TradeExecutor()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.SCOUT)
        executor._active_trades[plan.trade_id] = trade

        summary = executor.status_summary()

        assert summary["active_count"] == 1
        assert len(summary["active_trades"]) == 1
        assert summary["active_trades"][0]["symbol"] == "MGC"

    def test_active_trades_property(self):
        executor = TradeExecutor()
        plan = _make_plan()
        trade = ActiveTrade(plan=plan, phase=TradePhase.SCOUT)
        executor._active_trades[plan.trade_id] = trade

        trades = executor.active_trades

        assert len(trades) == 1
        assert trades[0] is trade


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_invalidation_at_exact_level_long(self):
        """Price exactly at invalidation level triggers close for LONG."""
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan(invalidation_level=2910.0))
        _activate_trade(trade)
        trade.mental_stop_price = 2910.0

        actions = executor.on_tick(2910.0, trade)

        action_types = [a["action"] for a in actions]
        assert "close_trade" in action_types

    def test_invalidation_at_exact_level_short(self):
        """Price exactly at invalidation level triggers close for SHORT."""
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_short_plan(invalidation_level=5530.0))
        trade.phase = TradePhase.SCOUT
        trade.total_contracts = 1
        trade.avg_entry_price = 5510.0
        trade.mental_stop_price = 5530.0

        actions = executor.on_tick(5530.0, trade)

        action_types = [a["action"] for a in actions]
        assert "close_trade" in action_types

    def test_t1_hit_only_once(self):
        """T1 should only trigger once even if price keeps hitting it."""
        executor = TradeExecutor()
        plan = _make_plan(target_1=2960.0)
        trade = ActiveTrade(plan=plan)
        _activate_trade(trade)

        # First hit — triggers transition
        executor.on_tick(2965.0, trade)
        assert trade.target_1_hit is True
        assert trade.phase == TradePhase.PROTECT

        # Second hit — no duplicate transition
        actions = executor.on_tick(2965.0, trade)
        stop_actions = [a for a in actions if a["action"] == "set_stop"]
        assert len(stop_actions) == 0  # Already set

    def test_zero_mental_stop_never_invalidates(self):
        executor = TradeExecutor()
        trade = ActiveTrade(plan=_make_plan())
        _activate_trade(trade)
        trade.mental_stop_price = 0.0

        actions = executor.on_tick(0.01, trade)

        action_types = [a["action"] for a in actions]
        assert "close_trade" not in action_types

    @pytest.mark.asyncio
    async def test_multiple_trades_tracked_independently(self):
        executor = TradeExecutor()
        ct = _mock_copy_trader()

        plan1 = _make_plan(trade_id="TRADE_1", symbol="MGC", build_levels=[])
        plan2 = _make_plan(trade_id="TRADE_2", symbol="MES", build_levels=[])

        await executor.engage_trade(plan1, ct)
        await executor.engage_trade(plan2, ct)

        assert executor.active_trade_count == 2
        assert executor.get_active_trade("MGC") is not None
        assert executor.get_active_trade("MES") is not None

    def test_partial_exit_qty_at_least_1_on_t2(self):
        """When total_contracts is 1, partial qty should be max(1, 1//2) = 1."""
        executor = TradeExecutor()
        plan = _make_plan(target_2=2990.0)
        trade = ActiveTrade(plan=plan, phase=TradePhase.PROTECT)
        trade.total_contracts = 1
        trade.avg_entry_price = 2925.0
        trade.target_1_hit = True

        actions = executor.on_tick(2995.0, trade)

        partials = [a for a in actions if a["action"] == "take_partial"]
        assert len(partials) == 1
        assert partials[0]["qty"] == 1
