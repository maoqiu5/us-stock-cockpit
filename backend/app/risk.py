from __future__ import annotations

from dataclasses import dataclass

from .models import OrderRequest, RiskDecision


@dataclass
class RiskConfig:
    account_value: float = 2736.95
    position_limit: float = 0.05
    total_exposure_limit: float = 0.50
    daily_loss_limit: float = 0.02
    weekly_loss_limit: float = 0.06
    current_exposure: float = 1.0
    today_pnl: float = -21.72
    weekly_pnl: float = -1611.95
    automation_paused: bool = False


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

    def status(self) -> RiskDecision:
        if self.config.automation_paused:
            return self._blocked("自动执行已暂停")
        if self.config.today_pnl <= -self.config.account_value * self.config.daily_loss_limit:
            return self._blocked("触发日亏损停机")
        if self.config.weekly_pnl <= -self.config.account_value * self.config.weekly_loss_limit:
            return self._blocked("触发周亏损停机")
        return RiskDecision(
            allowed=True,
            blocked_reason="",
            position_limit=self.config.position_limit,
            total_exposure_limit=self.config.total_exposure_limit,
            daily_loss_state="正常",
            daily_loss_limit=self.config.daily_loss_limit,
            weekly_loss_limit=self.config.weekly_loss_limit,
        )

    def evaluate_order(self, request: OrderRequest) -> RiskDecision:
        status = self.status()
        if not status.allowed:
            return status

        notional = request.qty * request.limit_price
        if notional > self.config.account_value * self.config.position_limit:
            return self._blocked("订单超过单票 5% 仓位上限")
        if self.config.current_exposure + notional / self.config.account_value > self.config.total_exposure_limit:
            return self._blocked("订单会导致总仓位超过 50%")
        return status

    def _blocked(self, reason: str) -> RiskDecision:
        return RiskDecision(
            allowed=False,
            blocked_reason=reason,
            position_limit=self.config.position_limit,
            total_exposure_limit=self.config.total_exposure_limit,
            daily_loss_state="停机" if "亏损" in reason else "正常",
            daily_loss_limit=self.config.daily_loss_limit,
            weekly_loss_limit=self.config.weekly_loss_limit,
        )
