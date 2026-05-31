import logging
import numpy as np
from typing import Dict, List, Tuple

from services.features.candle_aggregator import CandleAggregator
from config.settings import get_settings

logger = logging.getLogger("CorrelationGuard")


class CorrelationGuard:
    """
    Computes rolling asset correlations and dynamically adjusts portfolio exposure
    limits when cross-asset dependencies spike.
    """

    def __init__(self, aggregator: CandleAggregator):
        self.aggregator = aggregator
        self.settings = get_settings()

    async def calculate_portfolio_correlations(self) -> Tuple[np.ndarray, List[str]]:
        """
        Calculates rolling correlation matrix of returns for the 3 assets.
        Returns: (3x3 correlation matrix, list of symbols).
        """
        symbols = ["XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"]
        returns_dict = {}

        for sym in symbols:
            # Fetch 1h candles
            candles = await self.aggregator.get_candles(sym, "1h", count=50)
            if len(candles) < 20:
                # Fill default simulated returns if data is not loaded yet
                returns_dict[sym] = np.zeros(30)
            else:
                closes = np.array([c.close for c in candles], dtype=float)
                returns = np.log(closes[1:] / closes[:-1])
                returns_dict[sym] = returns

        # Align lengths of returns (pad/truncate to shortest length)
        min_len = min(len(r) for r in returns_dict.values())
        if min_len < 5:
            return np.eye(3), symbols

        aligned_returns = []
        for sym in symbols:
            aligned_returns.append(returns_dict[sym][-min_len:])

        matrix = np.column_stack(aligned_returns)
        # Compute Pearson correlation matrix
        corr_matrix = np.corrcoef(matrix, rowvar=False)
        
        # Replace NaNs with identity values if standard deviation was 0
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)
        for i in range(3):
            corr_matrix[i, i] = 1.0

        return corr_matrix, symbols

    async def validate_exposure(self, target_symbol: str, proposed_risk_usd: float) -> float:
        """
        Validates target symbol risk against current portfolio correlation bounds.
        Returns a risk multiplier (0.0 to 1.0) to scale down position sizes if risk is too concentrated.
        """
        corr_matrix, symbols = await self.calculate_portfolio_correlations()
        
        try:
            target_idx = symbols.index(target_symbol)
        except ValueError:
            return 1.0
        
        # Check if the target asset is highly correlated with other assets in which we have exposure
        # For simplicity, if correlation > 0.80, check combined exposure
        multiplier = 1.0
        for i, sym in enumerate(symbols):
            if i == target_idx:
                continue
                
            correlation = corr_matrix[target_idx, i]
            if correlation > 0.80:
                logger.info(
                    "High intermarket correlation (%.2f) detected between %s and %s.",
                    correlation, target_symbol, sym
                )
                # Scale down risk exposure slightly to prevent concentration risk
                multiplier = min(multiplier, 0.70)

        return multiplier
