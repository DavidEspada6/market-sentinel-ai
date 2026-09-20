from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from market_sentinel_ai.domain.paper import (
    PaperAccountSnapshot,
    PaperPosition,
    PaperTrade,
    PaperTradeRecord,
)
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.ports.paper import PaperPortfolioStore


class SimulationError(ValueError):
    """A user-facing validation error in the local leveraged simulator."""


class SimulationLedger:
    """Persistent, mark-to-market paper account with bounded leverage.

    The ledger models margin and PnL locally. It deliberately has no broker or order
    submission dependency; every position is a row in the local paper database.
    """

    MAX_LEVERAGE = 10.0
    LIQUIDATION_BUFFER = 0.9

    def __init__(
        self,
        starting_equity: float = 100_000.0,
        *,
        store: PaperPortfolioStore | None = None,
        account_id: str = "simulation",
        fee_bps: float = 1.0,
        slippage_bps: float = 2.0,
        spread_bps: float = 1.0,
    ) -> None:
        if starting_equity <= 0:
            raise SimulationError("starting_equity must be positive")
        if min(fee_bps, slippage_bps, spread_bps) < 0:
            raise SimulationError("simulation costs cannot be negative")
        self.store = store
        self.account_id = account_id
        self.one_way_cost_bps = fee_bps + slippage_bps + spread_bps / 2
        recovered = store.load_paper_account(account_id) if store is not None else None
        self.starting_equity = recovered.starting_equity if recovered else starting_equity
        self.cash = recovered.equity if recovered else starting_equity
        self.positions = (
            store.list_paper_positions(account_id) if store is not None else []
        )
        self.trades = (
            [record.trade for record in store.list_paper_trades(account_id)]
            if store is not None
            else []
        )
        if store is not None and recovered is None:
            self._save_account()

    @property
    def used_margin(self) -> float:
        return sum(position.margin for position in self.positions)

    @property
    def unrealized_pnl(self) -> float:
        return sum(self.position_unrealized_pnl(position) for position in self.positions)

    @property
    def equity(self) -> float:
        return self.cash + self.unrealized_pnl

    @property
    def available_margin(self) -> float:
        return self.equity - self.used_margin

    @property
    def exposure(self) -> float:
        return sum(position.mark_notional for position in self.positions)

    @property
    def realized_pnl(self) -> float:
        return sum(trade.pnl for trade in self.trades)

    def position_unrealized_pnl(self, position: PaperPosition) -> float:
        estimated_exit_cost = position.mark_notional * self.one_way_cost_bps / 10_000
        return position.gross_unrealized_pnl - estimated_exit_cost

    def liquidation_price(self, position: PaperPosition) -> float:
        loss_budget = position.margin * self.LIQUIDATION_BUFFER
        distance = loss_budget / position.quantity
        if position.direction is Direction.SHORT:
            return position.entry_price + distance
        return max(0.00000001, position.entry_price - distance)

    def open_position(
        self,
        *,
        symbol: str,
        direction: Direction,
        margin: float,
        leverage: float,
        entry_price: float,
        opened_at: datetime | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> PaperPosition:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise SimulationError("symbol is required")
        if direction not in {Direction.LONG, Direction.SHORT}:
            raise SimulationError("simulation direction must be LONG or SHORT")
        if margin <= 0:
            raise SimulationError("margin must be positive")
        if not 1 <= leverage <= self.MAX_LEVERAGE:
            raise SimulationError(f"leverage must be between 1x and {self.MAX_LEVERAGE:g}x")
        if entry_price <= 0:
            raise SimulationError("entry_price must be positive")
        if stop_loss is not None and stop_loss <= 0:
            raise SimulationError("stop_loss must be positive")
        if take_profit is not None and take_profit <= 0:
            raise SimulationError("take_profit must be positive")
        if direction is Direction.LONG:
            if stop_loss is not None and stop_loss >= entry_price:
                raise SimulationError("LONG stop_loss must be below entry_price")
            if take_profit is not None and take_profit <= entry_price:
                raise SimulationError("LONG take_profit must be above entry_price")
        else:
            if stop_loss is not None and stop_loss <= entry_price:
                raise SimulationError("SHORT stop_loss must be above entry_price")
            if take_profit is not None and take_profit >= entry_price:
                raise SimulationError("SHORT take_profit must be below entry_price")
        if margin > self.available_margin:
            raise SimulationError(
                f"insufficient available margin ({self.available_margin:.2f})"
            )
        quantity = margin * leverage / entry_price
        notional = quantity * entry_price
        entry_cost = notional * self.one_way_cost_bps / 10_000
        if entry_cost >= self.cash:
            raise SimulationError("available balance is too small for simulation costs")
        timestamp = opened_at or datetime.now(tz=UTC)
        position = PaperPosition(
            position_id=str(uuid4()),
            account_id=self.account_id,
            symbol=normalized_symbol,
            direction=direction,
            quantity=quantity,
            entry_price=entry_price,
            mark_price=entry_price,
            leverage=leverage,
            margin=margin,
            entry_cost=entry_cost,
            opened_at=timestamp,
            updated_at=timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        self.positions.append(position)
        self.cash -= entry_cost
        self._persist_position(position)
        self._save_account()
        return position

    def mark_price(
        self,
        position_id: str,
        price: float,
        updated_at: datetime | None = None,
    ) -> PaperPosition:
        if price <= 0:
            raise SimulationError("mark price must be positive")
        position = self._find_position(position_id)
        updated = replace(
            position,
            mark_price=price,
            updated_at=updated_at or datetime.now(tz=UTC),
        )
        self.positions[self.positions.index(position)] = updated
        self._persist_position(updated)
        self._save_account()
        return updated

    def refresh_prices(self, prices: dict[str, float]) -> None:
        timestamp = datetime.now(tz=UTC)
        for position in list(self.positions):
            price = prices.get(position.symbol)
            if price is not None and price > 0:
                updated = self.mark_price(position.position_id, price, timestamp)
                close_reason: str | None = None
                if updated.direction is Direction.LONG:
                    if updated.stop_loss is not None and price <= updated.stop_loss:
                        close_reason = "stop_loss"
                    elif updated.take_profit is not None and price >= updated.take_profit:
                        close_reason = "take_profit"
                else:
                    if updated.stop_loss is not None and price >= updated.stop_loss:
                        close_reason = "stop_loss"
                    elif updated.take_profit is not None and price <= updated.take_profit:
                        close_reason = "take_profit"
                if close_reason is not None:
                    self.close_position(
                        updated.position_id,
                        price,
                        timestamp,
                        close_reason=close_reason,
                    )
                elif (
                    self.position_unrealized_pnl(updated)
                    <= -updated.margin * self.LIQUIDATION_BUFFER
                ):
                    self.close_position(
                        updated.position_id,
                        price,
                        timestamp,
                        close_reason="liquidation",
                    )

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        closed_at: datetime | None = None,
        close_reason: str = "manual",
    ) -> PaperTrade:
        if exit_price <= 0:
            raise SimulationError("exit_price must be positive")
        position = self._find_position(position_id)
        gross = exit_price - position.entry_price
        if position.direction is Direction.SHORT:
            gross *= -1
        gross *= position.quantity
        exit_cost = position.quantity * exit_price * self.one_way_cost_bps / 10_000
        pnl = gross - position.entry_cost - exit_cost
        timestamp = closed_at or datetime.now(tz=UTC)
        trade = PaperTrade(
            symbol=position.symbol,
            direction=position.direction,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            opened_at=position.opened_at,
            closed_at=timestamp,
            margin=position.margin,
            leverage=position.leverage,
            entry_cost=position.entry_cost,
            exit_cost=exit_cost,
            notional=position.notional,
            close_reason=close_reason,
        )
        self.positions.remove(position)
        self.trades.append(trade)
        self.cash += gross - exit_cost
        if self.store is not None:
            self.store.delete_paper_position(self.account_id, position_id)
            self.store.record_paper_trade(
                PaperTradeRecord(
                    trade_id=str(uuid4()),
                    account_id=self.account_id,
                    trade=trade,
                )
            )
        self._save_account()
        return trade

    def reset(self, starting_equity: float) -> None:
        if starting_equity <= 0:
            raise SimulationError("starting_equity must be positive")
        if self.positions:
            raise SimulationError("close all open positions before resetting the account")
        timestamp = datetime.now(tz=UTC)
        snapshot = PaperAccountSnapshot(
            account_id=self.account_id,
            starting_equity=starting_equity,
            equity=starting_equity,
            updated_at=timestamp,
            real_execution_enabled=False,
        )
        if self.store is not None:
            self.store.reset_paper_account(self.account_id, snapshot)
        self.starting_equity = starting_equity
        self.cash = starting_equity
        self.positions = []
        self.trades = []

    def _find_position(self, position_id: str) -> PaperPosition:
        for position in self.positions:
            if position.position_id == position_id:
                return position
        raise SimulationError("simulation position not found")

    def _persist_position(self, position: PaperPosition) -> None:
        if self.store is not None:
            self.store.save_paper_position(position)

    def _save_account(self) -> None:
        if self.store is None:
            return
        self.store.save_paper_account(
            PaperAccountSnapshot(
                account_id=self.account_id,
                starting_equity=self.starting_equity,
                equity=self.cash,
                updated_at=datetime.now(tz=UTC),
                real_execution_enabled=False,
            )
        )
