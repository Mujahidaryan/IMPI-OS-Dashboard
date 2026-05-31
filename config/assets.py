from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AssetConfig:
    symbol: str
    canonical_symbol: str  # e.g., "XAUUSD" for both gold feeds, "BTCUSDT" for Bitcoin
    exchange: str
    display_name: str
    point_size: float
    pip_size: float
    min_volume: float
    base_weight: float  # Used in signal fusion weighting


ASSET_REGISTRY: Dict[str, AssetConfig] = {
    "XAUUSD_EXNESS": AssetConfig(
        symbol="XAUUSD",
        canonical_symbol="XAUUSD",
        exchange="exness",
        display_name="Gold (CFD)",
        point_size=0.01,
        pip_size=0.1,
        min_volume=0.01,
        base_weight=0.60
    ),
    "XAUUSDT": AssetConfig(
        symbol="XAUUSDT",
        canonical_symbol="XAUUSD",
        exchange="binance",
        display_name="Gold (Futures)",
        point_size=0.01,
        pip_size=0.01,
        min_volume=0.001,
        base_weight=0.40
    ),
    "BTCUSDT": AssetConfig(
        symbol="BTCUSDT",
        canonical_symbol="BTCUSDT",
        exchange="binance",
        display_name="Bitcoin (Futures)",
        point_size=0.1,
        pip_size=1.0,
        min_volume=0.001,
        base_weight=1.00
    )
}
