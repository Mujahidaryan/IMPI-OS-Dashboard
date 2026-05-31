import numpy as np
import pandas as pd
from typing import List, Tuple, Dict


def ema(values: np.ndarray, period: int) -> np.ndarray:
    """
    Standard Exponential Moving Average.
    Formula:
      α = 2 / (period + 1)
      ema[0] = values[0]
      ema[i] = α * values[i] + (1 - α) * ema[i-1]
    """
    if len(values) == 0:
        return np.array([])
    alpha = 2.0 / (period + 1.0)
    ema_arr = np.zeros_like(values)
    ema_arr[0] = values[0]
    for i in range(1, len(values)):
        ema_arr[i] = alpha * values[i] + (1.0 - alpha) * ema_arr[i - 1]
    return ema_arr


def wilder_smooth(values: np.ndarray, period: int) -> np.ndarray:
    """
    Wilder's Smoothing technique.
    Formula:
      smooth[0] = mean(values[:period])
      smooth[i] = smooth[i-1] - smooth[i-1]/period + values[period - 1 + i] / period
    """
    if len(values) < period:
        return np.array([np.nan] * len(values))
    
    n = len(values)
    smooth = np.empty(n - period + 1)
    smooth[0] = np.mean(values[:period])
    
    alpha = 1.0 / period
    for i in range(1, len(smooth)):
        smooth[i] = smooth[i - 1] - alpha * smooth[i - 1] + values[period - 1 + i] * alpha
        
    # Prepend NaNs to match original array size
    nan_prefix = np.full(period - 1, np.nan)
    return np.concatenate([nan_prefix, smooth])


def calculate_tr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
    """Calculate True Range (TR)."""
    n = len(closes)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
    return tr


def calculate_adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Average Directional Index (ADX), +DI, and -DI using Wilder's smoothing.
    """
    n = len(closes)
    tr = calculate_tr(highs, lows, closes)
    
    pdm = np.zeros(n)
    ndm = np.zeros(n)
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        
        if up_move > down_move and up_move > 0:
            pdm[i] = up_move
        else:
            pdm[i] = 0.0
            
        if down_move > up_move and down_move > 0:
            ndm[i] = down_move
        else:
            ndm[i] = 0.0

    smooth_tr = wilder_smooth(tr, period)
    smooth_pdm = wilder_smooth(pdm, period)
    smooth_ndm = wilder_smooth(ndm, period)
    
    pdi = 100.0 * smooth_pdm / (smooth_tr + 1e-9)
    ndi = 100.0 * smooth_ndm / (smooth_tr + 1e-9)
    
    dx = 100.0 * np.abs(pdi - ndi) / (pdi + ndi + 1e-9)
    adx = wilder_smooth(dx, period)
    
    return adx, pdi, ndi


def calculate_supertrend(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 10, multiplier: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate Supertrend line and buy/sell state.
    Returns (supertrend_line, supertrend_bullish).
    """
    n = len(closes)
    tr = calculate_tr(highs, lows, closes)
    atr = wilder_smooth(tr, period)
    
    hl2 = (highs + lows) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr
    
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    bullish = np.zeros(n, dtype=bool)
    
    for i in range(1, n):
        # Upper band
        if basic_upper[i] < final_upper[i - 1] or closes[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]
            
        # Lower band
        if basic_lower[i] > final_lower[i - 1] or closes[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

    for i in range(1, n):
        if closes[i] > final_upper[i - 1]:
            bullish[i] = True
        elif closes[i] < final_lower[i - 1]:
            bullish[i] = False
        else:
            bullish[i] = bullish[i - 1]
            
        supertrend[i] = final_lower[i] if bullish[i] else final_upper[i]
        
    return supertrend, bullish


def calculate_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Relative Strength Index (RSI) using Wilder's smoothing."""
    if len(closes) < period + 1:
        return np.full(len(closes), np.nan)
        
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    
    # Calculate wilder smoothing on gains/losses
    smooth_gains = wilder_smooth(gains, period)
    smooth_losses = wilder_smooth(losses, period)
    
    rs = smooth_gains / (smooth_losses + 1e-9)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    
    # Prepend NaN to match original array size
    return np.concatenate([[np.nan], rsi])


def calculate_rsi_divergences(closes: np.ndarray, rsi: np.ndarray, lookback: int = 10) -> Tuple[bool, bool]:
    """
    Detect bullish or bearish divergences over a lookback window.
    Returns (bull_divergence, bear_divergence).
    """
    if len(closes) < lookback + 5 or np.isnan(rsi[-1]):
        return False, False

    # Check for hidden/regular bullish divergence
    # Lower low in price, higher low in RSI
    price_10_low = closes[-1] < min(closes[-lookback-1:-1])
    rsi_10_low = rsi[-1] < min(rsi[-lookback:])
    bull_div = price_10_low and not rsi_10_low

    # Check for hidden/regular bearish divergence
    # Higher high in price, lower high in RSI
    price_10_high = closes[-1] > max(closes[-lookback-1:-1])
    rsi_10_high = rsi[-1] > max(rsi[-lookback:])
    bear_div = price_10_high and not rsi_10_high

    return bull_div, bear_div


def calculate_macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate MACD Line, Signal Line, and MACD Histogram."""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(closes: np.ndarray, period: int = 20, multiplier: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands.
    Returns (mid_band, upper_band, lower_band, percent_b).
    """
    df = pd.Series(closes)
    mid = df.rolling(period).mean().values
    std = df.rolling(period).std().values
    upper = mid + multiplier * std
    lower = mid - multiplier * std
    pct_b = (closes - lower) / (upper - lower + 1e-9)
    return mid, upper, lower, pct_b


def calculate_keltner_channels(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, ema_period: int = 20, atr_period: int = 10, multiplier: float = 1.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Keltner Channels.
    Returns (mid, upper, lower).
    """
    tr = calculate_tr(highs, lows, closes)
    atr = wilder_smooth(tr, atr_period)
    mid = ema(closes, ema_period)
    upper = mid + multiplier * atr
    lower = mid - multiplier * atr
    return mid, upper, lower


def calculate_bb_kc_squeeze(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> Tuple[bool, bool]:
    """
    Identifies Bollinger Bands / Keltner Channel Squeeze and Release events.
    Returns (is_squeezed, is_squeeze_release).
    """
    _, bb_up, bb_low, _ = calculate_bollinger_bands(closes, 20, 2.0)
    _, kc_up, kc_low = calculate_keltner_channels(highs, lows, closes, 20, 10, 1.5)
    
    if np.isnan(bb_up[-2]) or np.isnan(kc_up[-2]):
        return False, False
        
    squeeze = (bb_up < kc_up) & (bb_low > kc_low)
    is_squeezed = bool(squeeze[-1])
    is_squeeze_release = bool((not squeeze[-1]) and squeeze[-2])
    
    return is_squeezed, is_squeeze_release


def calculate_zscore(closes: np.ndarray, period: int = 20) -> float:
    """Calculate standard Z-score of close relative to rolling window."""
    if len(closes) < period:
        return 0.0
    recent = closes[-period:]
    mu = np.mean(recent)
    sigma = np.std(recent, ddof=1)
    return float((closes[-1] - mu) / (sigma + 1e-9))
