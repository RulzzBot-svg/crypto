"""
strategy.py
-----------
Contains the SMA crossover strategy logic.

The function `sma_crossover_signal` is the single public interface:
    - Accepts a standard OHLCV DataFrame (columns: open, high, low, close, volume).
    - Computes a 50-period and 200-period Simple Moving Average on the close price.
    - Returns 'BUY', 'SELL', or 'HOLD' based on the crossover condition.

Design note:
    All strategy modules in this project must expose a function with the signature:
        generate_signal(df: pd.DataFrame) -> str
    This lets main.py swap strategies without any other changes.
"""

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

Signal = Literal["BUY", "SELL", "HOLD"]

# SMA periods — adjust here if you want different windows.
FAST_PERIOD: int = 50
SLOW_PERIOD: int = 200


def _validate_ohlcv(df: pd.DataFrame) -> None:
    """Raise ValueError if the DataFrame doesn't meet minimum requirements."""
    required_columns = {"open", "high", "low", "close", "volume"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing columns: {missing}")

    min_rows = SLOW_PERIOD + 2  # need current row + one previous row to detect crossover
    if len(df) < min_rows:
        raise ValueError(
            f"Not enough data: {len(df)} rows provided, "
            f"but at least {min_rows} are required for a {SLOW_PERIOD}-period SMA."
        )


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Return a Simple Moving Average series for the given period."""
    return series.rolling(window=period, min_periods=period).mean()


def sma_crossover_signal(df: pd.DataFrame) -> Signal:
    """
    Determine a trading signal using a Golden Cross / Death Cross strategy.

    Logic:
        - Golden Cross  → BUY:  fast SMA crosses *above* slow SMA
          (previous fast < previous slow  AND  current fast > current slow)
        - Death Cross   → SELL: fast SMA crosses *below* slow SMA
          (previous fast > previous slow  AND  current fast < current slow)
        - Otherwise     → HOLD

    Args:
        df: DataFrame with at minimum a 'close' column and SLOW_PERIOD + 1 rows.
            Index should be sorted in ascending chronological order.

    Returns:
        'BUY', 'SELL', or 'HOLD'
    """
    _validate_ohlcv(df)

    close = df["close"]
    fast_sma = compute_sma(close, FAST_PERIOD)
    slow_sma = compute_sma(close, SLOW_PERIOD)

    # Current and previous candle values
    fast_current = fast_sma.iloc[-1]
    slow_current = slow_sma.iloc[-1]
    fast_prev = fast_sma.iloc[-2]
    slow_prev = slow_sma.iloc[-2]

    # Guard: NaN means not enough data to compute one of the SMAs
    if any(np.isnan(v) for v in [fast_current, slow_current, fast_prev, slow_prev]):
        logger.warning("SMA values contain NaN — not enough data yet. Returning HOLD.")
        return "HOLD"

    logger.debug(
        "SMA(%d)=%.4f  SMA(%d)=%.4f  |  prev SMA(%d)=%.4f  prev SMA(%d)=%.4f",
        FAST_PERIOD, fast_current,
        SLOW_PERIOD, slow_current,
        FAST_PERIOD, fast_prev,
        SLOW_PERIOD, slow_prev,
    )

    # Golden Cross: fast crosses above slow
    if fast_prev <= slow_prev and fast_current > slow_current:
        logger.info(
            "BUY signal: Golden Cross detected (SMA%d crossed above SMA%d).",
            FAST_PERIOD, SLOW_PERIOD,
        )
        return "BUY"

    # Death Cross: fast crosses below slow
    if fast_prev >= slow_prev and fast_current < slow_current:
        logger.info(
            "SELL signal: Death Cross detected (SMA%d crossed below SMA%d).",
            FAST_PERIOD, SLOW_PERIOD,
        )
        return "SELL"

    logger.info("HOLD signal: No crossover detected.")
    return "HOLD"


# Public alias — main.py always calls `generate_signal` so strategies are
# interchangeable without touching main.py.
generate_signal = sma_crossover_signal
