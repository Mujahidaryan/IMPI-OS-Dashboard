import numpy as np


def detect_cusum_break(log_returns: np.ndarray, realized_vol: np.ndarray) -> bool:
    """
    Standard CUSUM (Cumulative Sum) structural break detection algorithm.
    Formula:
      threshold = 0.5 * standard_deviation
      limit = 4.0 * standard_deviation
      Detects shift if cumulative sum bounds are breached.
    """
    if len(log_returns) < 10 or len(realized_vol) < 1:
        return False
        
    last_vol = realized_vol[-1]
    if last_vol <= 0.0:
        return False
        
    threshold = 0.5 * last_vol
    cusum_limit = 4.0 * last_vol
    
    cusum_pos = 0.0
    cusum_neg = 0.0
    
    # Iterate over the recent 50 periods (or length of array if smaller)
    lookback = min(50, len(log_returns))
    for r in log_returns[-lookback:]:
        cusum_pos = max(0.0, cusum_pos + r - threshold)
        cusum_neg = min(0.0, cusum_neg + r + threshold)
        
    return bool(cusum_pos > cusum_limit or abs(cusum_neg) > cusum_limit)
