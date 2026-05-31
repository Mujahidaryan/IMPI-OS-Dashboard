import logging
from typing import Dict, Any

from services.macro.data_fetcher import MacroDataFetcher
from services.microstructure.liquidity import LiquidityMonitor
from services.microstructure.order_flow import MicrostructureOrderFlow

logger = logging.getLogger("AssetContext")


class AssetMacroContextBuilder:
    """
    Compiles intermarket macro variables, local microstructure indices,
    and order imbalances to form a unified situational context per asset.
    """

    def __init__(
        self,
        data_fetcher: MacroDataFetcher,
        liquidity_monitor: LiquidityMonitor,
        order_flow_analyzer: MicrostructureOrderFlow
    ):
        self.data_fetcher = data_fetcher
        self.liquidity_monitor = liquidity_monitor
        self.order_flow_analyzer = order_flow_analyzer

    async def get_context_for_asset(self, symbol: str) -> Dict[str, Any]:
        """
        Gathers macro variables, microstructure skewness, and liquidity metrics
        for the given asset.
        """
        # Fetch global macro indicators
        macro = await self.data_fetcher.get_macro_context()

        # Fetch local liquidity stats
        spread_z, depth_deficit = await self.liquidity_monitor.check_liquidity_quality(symbol)

        # Fetch trade volume clusters skewness
        flow_clusters = await self.order_flow_analyzer.analyze_trade_clusters(symbol)

        return {
            "symbol": symbol,
            "macro": macro,
            "liquidity": {
                "spread_zscore": spread_z,
                "depth_deficit": depth_deficit
            },
            "order_flow": flow_clusters
        }
