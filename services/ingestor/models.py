"""
Canonical data schemas for the ingestor pipeline.

All market data flowing through IPMI-OS is normalised into these models
before being published to Redis or consumed by downstream services.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Tuple

import orjson


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Tick:
    """Single market tick from any feed."""

    symbol: str
    exchange: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp_ms: int
    local_recv_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "timestamp_ms": self.timestamp_ms,
            "local_recv_ms": self.local_recv_ms,
        }

    def to_bytes(self) -> bytes:
        return orjson.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> Tick:
        return cls(
            symbol=data["symbol"],
            exchange=data["exchange"],
            bid=float(data["bid"]),
            ask=float(data["ask"]),
            last=float(data["last"]),
            volume=float(data["volume"]),
            timestamp_ms=int(data["timestamp_ms"]),
            local_recv_ms=int(data.get("local_recv_ms", time.time() * 1000)),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> Tick:
        return cls.from_dict(orjson.loads(raw))


# ---------------------------------------------------------------------------
# Candle
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Candle:
    """OHLCV candle for any timeframe."""

    symbol: str
    timeframe: str
    time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    confirmed: bool

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "time_ms": self.time_ms,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "confirmed": self.confirmed,
        }

    def to_bytes(self) -> bytes:
        return orjson.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> Candle:
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            time_ms=int(data["time_ms"]),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data["volume"]),
            confirmed=bool(data["confirmed"]),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> Candle:
        return cls.from_dict(orjson.loads(raw))


# ---------------------------------------------------------------------------
# AnomalyEvent
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class AnomalyEvent:
    """
    Fired whenever the ingestor detects unusual market micro-structure:
    spread blow-outs, feed divergence, sequence gaps, etc.
    """

    symbol: str
    anomaly_type: str
    severity: float          # clamped 0.0 – 1.0
    description: str
    raw_value: float
    expected_range: Tuple[float, float]
    timestamp_ms: int

    def __post_init__(self) -> None:
        self.severity = max(0.0, min(1.0, self.severity))

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "raw_value": self.raw_value,
            "expected_range": list(self.expected_range),
            "timestamp_ms": self.timestamp_ms,
        }

    def to_bytes(self) -> bytes:
        return orjson.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> AnomalyEvent:
        er = data["expected_range"]
        return cls(
            symbol=data["symbol"],
            anomaly_type=data["anomaly_type"],
            severity=float(data["severity"]),
            description=data["description"],
            raw_value=float(data["raw_value"]),
            expected_range=(float(er[0]), float(er[1])),
            timestamp_ms=int(data["timestamp_ms"]),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> AnomalyEvent:
        return cls.from_dict(orjson.loads(raw))


# ---------------------------------------------------------------------------
# OrderBookSnapshot
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class OrderBookSnapshot:
    """
    Top-of-book depth snapshot.
    bids / asks are lists of [price, quantity] pairs, best first.
    """

    symbol: str
    bids: List[List[float]]
    asks: List[List[float]]
    timestamp_ms: int

    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 0.0

    @property
    def mid_price(self) -> float:
        bb = self.best_bid
        ba = self.best_ask
        if bb and ba:
            return (bb + ba) / 2.0
        return bb or ba

    def imbalance(self) -> float:
        """
        Order-book imbalance ratio: (bid_vol - ask_vol) / (bid_vol + ask_vol).
        Returns value in [-1, 1]. Positive ⇒ bid-heavy (bullish pressure).
        """
        bid_vol = sum(level[1] for level in self.bids)
        ask_vol = sum(level[1] for level in self.asks)
        total = bid_vol + ask_vol
        if total == 0.0:
            return 0.0
        return (bid_vol - ask_vol) / total

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bids": self.bids,
            "asks": self.asks,
            "timestamp_ms": self.timestamp_ms,
        }

    def to_bytes(self) -> bytes:
        return orjson.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> OrderBookSnapshot:
        return cls(
            symbol=data["symbol"],
            bids=[[float(p), float(q)] for p, q in data["bids"]],
            asks=[[float(p), float(q)] for p, q in data["asks"]],
            timestamp_ms=int(data["timestamp_ms"]),
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> OrderBookSnapshot:
        return cls.from_dict(orjson.loads(raw))
