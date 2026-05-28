"""
config.py
---------
Loads and validates all environment variables from a .env file.

Usage:
    from config import settings
    print(settings.exchange)
"""

import os
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load variables from .env into the process environment.
# If .env doesn't exist the script falls back to real env vars,
# which is intentional for containerised deployments.
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """Immutable settings object populated from environment variables."""

    exchange: str
    trading_pair: str
    timeframe: str
    candle_limit: int
    order_size: float

    # Alpaca credentials (only required when exchange == "alpaca")
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str

    # Binance credentials (only required when exchange == "binance")
    binance_api_key: str
    binance_secret_key: str


def _require(name: str) -> str:
    """Return the value of an env var, raising if it is missing or empty."""
    value = os.getenv(name, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return value


def load_settings() -> Settings:
    """
    Read, validate, and return a Settings instance.

    Raises:
        EnvironmentError: if a required variable is absent or empty.
        ValueError:       if a numeric variable cannot be parsed.
    """
    exchange = os.getenv("EXCHANGE", "alpaca").strip().lower()
    if exchange not in {"alpaca", "binance"}:
        raise ValueError(
            f"Unsupported exchange '{exchange}'. Choose 'alpaca' or 'binance'."
        )

    try:
        candle_limit = int(os.getenv("CANDLE_LIMIT", "250"))
    except ValueError as exc:
        raise ValueError("CANDLE_LIMIT must be an integer.") from exc

    if candle_limit < 200:
        raise ValueError(
            f"CANDLE_LIMIT is {candle_limit}, but at least 200 candles are "
            "required to compute the 200-period SMA."
        )

    try:
        order_size = float(os.getenv("ORDER_SIZE", "0.001"))
    except ValueError as exc:
        raise ValueError("ORDER_SIZE must be a float.") from exc

    if order_size <= 0:
        raise ValueError("ORDER_SIZE must be a positive number.")

    # Validate exchange-specific credentials
    if exchange == "alpaca":
        alpaca_api_key = _require("ALPACA_API_KEY")
        alpaca_secret_key = _require("ALPACA_SECRET_KEY")
        binance_api_key = ""
        binance_secret_key = ""
    else:  # binance
        binance_api_key = _require("BINANCE_API_KEY")
        binance_secret_key = _require("BINANCE_SECRET_KEY")
        alpaca_api_key = ""
        alpaca_secret_key = ""

    settings = Settings(
        exchange=exchange,
        trading_pair=os.getenv("TRADING_PAIR", "BTC/USD"),
        timeframe=os.getenv("TIMEFRAME", "1h"),
        candle_limit=candle_limit,
        order_size=order_size,
        alpaca_api_key=alpaca_api_key,
        alpaca_secret_key=alpaca_secret_key,
        alpaca_base_url=os.getenv(
            "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
        ),
        binance_api_key=binance_api_key,
        binance_secret_key=binance_secret_key,
    )

    logger.info(
        "Settings loaded: exchange=%s pair=%s timeframe=%s candles=%d",
        settings.exchange,
        settings.trading_pair,
        settings.timeframe,
        settings.candle_limit,
    )
    return settings


# Module-level singleton — import `settings` directly for convenience.
settings: Settings = load_settings()
