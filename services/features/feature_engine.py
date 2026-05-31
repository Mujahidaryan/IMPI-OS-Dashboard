from dataclasses import dataclass
import numpy as np
from typing import Dict, List, Any, Optional

from services.features.candle_aggregator import CandleAggregator
from services.features.technical import (
    ema, calculate_adx, calculate_supertrend, calculate_rsi,
    calculate_macd, calculate_bollinger_bands, calculate_keltner_channels,
    calculate_bb_kc_squeeze, calculate_rsi_divergences, calculate_zscore, calculate_tr, wilder_smooth
)

@dataclass
class FeatureVector:
    symbol: str
    timeframe: str
    timestamp_ms: int
    close: float
    high: float
    low: float
    open: float
    volume: float
    
    # Trend Indicators
    ema9: float
    ema21: float
    ema50: float
    adx: float
    pdi: float
    ndi: float
    supertrend: float
    supertrend_bullish: bool
    
    # Momentum Indicators
    macd: float
    macd_signal: float
    macd_hist: float
    rsi: float
    rsi_bull_divergence: bool
    rsi_bear_divergence: bool
    roc_10: float
    williams_r: float
    
    # Volatility Indicators
    atr_14: float
    vol_ratio: float
    z_score: float
    bb_mid: float
    bb_upper: float
    bb_lower: float
    bb_pct: float
    kc_mid: float
    kc_upper: float
    kc_lower: float
    is_squeezed: bool
    is_squeeze_release: bool


class FeatureEngine:
    """
    Compiles raw Candle arrays into formatted FeatureVector structures
    for model feeding and strategy execution.
    """

    def __init__(self, aggregator: CandleAggregator):
        self.aggregator = aggregator

    async def build_feature_vector(self, symbol: str, timeframe: str) -> Optional[FeatureVector]:
        """Fetch candles from aggregator and compute all features for the last bar."""
        # Need at least 60 candles to compute ema50, adx14, etc.
        candles = await self.aggregator.get_candles(symbol, timeframe, count=100)
        if len(candles) < 60:
            return None

        closes = np.array([c.close for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        opens = np.array([c.open for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)

        # Computations
        ema9_arr = ema(closes, 9)
        ema21_arr = ema(closes, 21)
        ema50_arr = ema(closes, 50)
        
        adx_arr, pdi_arr, ndi_arr = calculate_adx(highs, lows, closes, 14)
        supertrend_arr, st_bullish = calculate_supertrend(highs, lows, closes, 10, 3.0)
        
        macd_line, macd_sig, macd_hist = calculate_macd(closes, 12, 26, 9)
        rsi_arr = calculate_rsi(closes, 14)
        
        bull_div, bear_div = calculate_rsi_divergences(closes, rsi_arr, lookback=10)
        
        # Williams %R (period=14)
        hh = np.array([max(highs[max(0, i-13):i+1]) for i in range(len(highs))])
        ll = np.array([min(lows[max(0, i-13):i+1]) for i in range(len(lows))])
        williams_r = ((hh - closes) / (hh - ll + 1e-9)) * -100.0
        
        # ROC (period=10)
        roc = np.zeros(len(closes))
        for i in range(10, len(closes)):
            roc[i] = ((closes[i] - closes[i - 10]) / (closes[i - 10] + 1e-9)) * 100.0
            
        # Volatility
        tr_arr = calculate_tr(highs, lows, closes)
        atr_14_arr = wilder_smooth(tr_arr, 14)
        
        # Vol ratio = atr14 / average(atr_14 over past 20 periods)
        atr_history = []
        for i in range(20, len(atr_14_arr) + 1):
            atr_history.append(np.mean(atr_14_arr[i-20:i]))
        vol_ratio = 1.0
        if len(atr_history) > 0:
            vol_ratio = float(atr_14_arr[-1] / (atr_history[-1] + 1e-9))
            
        zscore_val = calculate_zscore(closes, 20)
        bb_mid, bb_up, bb_low, bb_pct = calculate_bollinger_bands(closes, 20, 2.0)
        kc_mid, kc_up, kc_low = calculate_keltner_channels(highs, lows, closes, 20, 10, 1.5)
        is_squeezed, is_release = calculate_bb_kc_squeeze(closes, highs, lows)

        return FeatureVector(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_ms=candles[-1].time_ms,
            close=closes[-1],
            high=highs[-1],
            low=lows[-1],
            open=opens[-1],
            volume=volumes[-1],
            
            ema9=ema9_arr[-1],
            ema21=ema21_arr[-1],
            ema50=ema50_arr[-1],
            adx=adx_arr[-1],
            pdi=pdi_arr[-1],
            ndi=ndi_arr[-1],
            supertrend=supertrend_arr[-1],
            supertrend_bullish=st_bullish[-1],
            
            macd=macd_line[-1],
            macd_signal=macd_sig[-1],
            macd_hist=macd_hist[-1],
            rsi=rsi_arr[-1],
            rsi_bull_divergence=bull_div,
            rsi_bear_divergence=bear_div,
            roc_10=roc[-1],
            williams_r=williams_r[-1],
            
            atr_14=atr_14_arr[-1],
            vol_ratio=vol_ratio,
            z_score=zscore_val,
            bb_mid=bb_mid[-1],
            bb_upper=bb_up[-1],
            bb_lower=bb_low[-1],
            bb_pct=bb_pct[-1],
            kc_mid=kc_mid[-1],
            kc_upper=kc_up[-1],
            kc_lower=kc_low[-1],
            is_squeezed=is_squeezed,
            is_squeeze_release=is_release
        )
