from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from market_sentinel_ai.domain.paper import PaperTrade, PaperTradeRecord
from market_sentinel_ai.domain.prediction import Direction, Signal
from market_sentinel_ai.domain.risk import RiskLimits
from market_sentinel_ai.ports.paper import PaperPortfolioStore


class PaperTradingLedger:
    def __init__(
        self,
        starting_equity: float = 100_000.0,
        *,
        store: PaperPortfolioStore | None = None,
        account_id: str = "default",
    ) -> None:
        if starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        self.store = store
        self.account_id = account_id
        recovered = store.load_paper_account(account_id) if store is not None else None
        self.starting_equity = recovered.starting_equity if recovered else starting_equity
        self.equity = recovered.equity if recovered else starting_equity
        self.trades: list[PaperTrade] = []
        if store is not None:
            self.trades = [
                record.trade for record in store.list_paper_trades(account_id)
            ]
            if recovered is None:
                self._save_account()

    def simulate_round_trip(
        self,
        signal: Signal,
        entry_price: float,
        exit_price: float,
        opened_at: datetime,
        closed_at: datetime,
        risk: RiskLimits,
    ) -> PaperTrade | None:
        if not signal.is_actionable:
            return None
        if signal.prediction.direction is Direction.NO_TRADE:
            return None

        notional = self.equity * risk.max_position_pct
        quantity = notional / entry_price
        gross = (exit_price - entry_price) * quantity
        if signal.prediction.direction is Direction.SHORT:
            gross *= -1
        costs = notional * (
            (risk.fee_bps * 2 + risk.slippage_bps * 2 + risk.spread_bps) / 10_000
        )
        pnl = gross - costs
        trade = PaperTrade(
            symbol=signal.prediction.symbol,
            direction=signal.prediction.direction,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            opened_at=opened_at,
            closed_at=closed_at,
            margin=notional,
            leverage=1.0,
            entry_cost=costs / 2,
            exit_cost=costs / 2,
            notional=notional,
            close_reason="signal_horizon",
        )
        self.trades.append(trade)
        self.equity += pnl
        if self.store is not None:
            self.store.record_paper_trade(
                PaperTradeRecord(
                    trade_id=str(uuid4()),
                    account_id=self.account_id,
                    trade=trade,
                )
            )
            self._save_account()
        return trade

    @property
    def total_pnl(self) -> float:
        return self.equity - self.starting_equity

    def _save_account(self) -> None:
        from datetime import UTC

        from market_sentinel_ai.domain.paper import PaperAccountSnapshot

        assert self.store is not None
        self.store.save_paper_account(
            PaperAccountSnapshot(
                account_id=self.account_id,
                starting_equity=self.starting_equity,
                equity=self.equity,
                updated_at=datetime.now(tz=UTC),
                real_execution_enabled=False,
            )
        )
