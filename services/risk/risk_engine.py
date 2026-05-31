import logging
import numpy as np
import redis.asyncio as aioredis

from config.settings import get_settings

logger = logging.getLogger("RiskEngine")


class RiskEngine:
    """
    Computes optimal position sizes using ATR-based sizing, enforces anti-martingale
    compounding scaling down, and monitors rolling portfolio VaR (95%) and CVaR.
    Enforces a strict drawdown halt.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.settings = get_settings()

    async def calculate_position_size(
        self,
        symbol: str,
        atr_14: float,
        price: float,
        probability: float
    ) -> dict:
        """
        Calculates position size in units, Stop Loss distance, and Take Profit target.
        Also returns VaR/CVaR statistics and whether the trading loop is currently halted.
        """
        # 1. Drawdown Halt Check
        drawdown_halt = await self.redis.get("risk:drawdown_halt")
        if drawdown_halt and drawdown_halt.decode("utf-8") == "true":
            logger.warning("Trading is HALTED due to maximum drawdown breach.")
            return self._halt_payload(0.0, 0.0, 0.0, halted=True)

        # 2. Risk Amount Calculation
        # Quality adjustment scales risk linearly: 55% prob -> 0.55 risk weight, 80%+ prob -> 1.0 weight
        prob_factor = (probability - 50.0) / 30.0  # Normalized factor
        quality_adj = float(np.clip(0.5 + 0.5 * prob_factor, 0.5, 1.0))
        
        balance = float(await self.redis.get("risk:balance") or self.settings.ACCOUNT_BALANCE)
        max_risk_pct = self.settings.MAX_RISK_PCT  # e.g., 1.0%
        risk_amount = balance * (max_risk_pct / 100.0) * quality_adj

        # 3. Stop Distance
        # If ATR is invalid or 0, fallback to 1.5% of price
        atr_distance = atr_14 if (atr_14 > 0) else (price * 0.01)
        stop_distance = atr_distance * 1.5

        # Raw size in units of asset
        raw_size = risk_amount / (stop_distance + 1e-9)

        # 4. Anti-martingale scaling
        consecutive_losses = int(await self.redis.get("risk:consecutive_losses") or 0)
        if consecutive_losses >= 1:
            raw_size *= (0.75 ** consecutive_losses)
            logger.info("Applying Anti-martingale scaling. Reduced size by %d%%", int((1 - 0.75**consecutive_losses) * 100))

        # Size boundaries check
        min_volume = 0.001
        if raw_size < min_volume:
            raw_size = 0.0  # Size too small, skip

        # 5. VaR / CVaR calculations
        # Load historical PnL percentages from Redis list
        pnl_history_bytes = await self.redis.lrange("risk:pnl_history", 0, -1)
        pnl_pcts = [float(p) for p in pnl_history_bytes] if pnl_history_bytes else []
        
        # Warmup default simulation data if history is sparse
        if len(pnl_pcts) < 20:
            # Seed typical simulated log returns
            pnl_pcts = pnl_pcts + list(np.random.normal(-0.02, 0.05, 50))

        pnl_arr = np.array(pnl_pcts)
        var_95 = float(np.percentile(pnl_arr, 5))  # 5th percentile
        
        bad_tail = pnl_arr[pnl_arr <= var_95]
        cvar_95 = float(np.mean(bad_tail)) if len(bad_tail) > 0 else var_95

        # Take Profit Target (2:1 reward-to-risk ratio typical)
        tp_target = stop_distance * 2.0

        return {
            "position_size": float(raw_size),
            "stop_loss_distance": float(stop_distance),
            "take_profit_distance": float(tp_target),
            "risk_amount_usd": float(risk_amount),
            "var_95": var_95,
            "cvar_95": cvar_95,
            "consecutive_losses": consecutive_losses,
            "halted": False
        }

    def _halt_payload(self, atr_14, price, stop_distance, halted=True) -> dict:
        return {
            "position_size": 0.0,
            "stop_loss_distance": stop_distance,
            "take_profit_distance": stop_distance * 2.0,
            "risk_amount_usd": 0.0,
            "var_95": -0.05,
            "cvar_95": -0.08,
            "consecutive_losses": 0,
            "halted": halted
        }

    async def update_drawdown(self, current_balance: float):
        """Enforces halt logic if peak-to-trough drawdown breaches limit."""
        await self.redis.set("risk:balance", str(current_balance))
        
        peak_balance_raw = await self.redis.get("risk:peak_balance")
        peak_balance = float(peak_balance_raw) if peak_balance_raw else current_balance
        
        if current_balance > peak_balance:
            peak_balance = current_balance
            await self.redis.set("risk:peak_balance", str(peak_balance))

        drawdown_pct = (peak_balance - current_balance) / peak_balance
        max_drawdown_limit = 0.15  # 15% Max Drawdown limit

        if drawdown_pct > max_drawdown_limit:
            await self.redis.set("risk:drawdown_halt", "true")
            logger.critical(
                "Drawdown of %.2f%% breached limit of %.2f%%. Halting all trades.",
                drawdown_pct * 100.0, max_drawdown_limit * 100.0
            )
        else:
            await self.redis.set("risk:drawdown_halt", "false")
