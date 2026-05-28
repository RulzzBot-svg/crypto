"""
main.py
-------
Entry point for the crypto algorithmic trading bot.

How to run:
    1. Install dependencies:
           pip install -r requirements.txt

    2. Copy .env.example to .env and fill in your API credentials:
           cp .env.example .env

    3. Run the bot:
           python main.py

The bot will:
    a. Read configuration from .env via config.py.
    b. Connect to the paper-trading endpoint of your chosen exchange.
    c. Fetch the latest OHLCV candles for the configured trading pair.
    d. Pass the candles to strategy.py to get a BUY / SELL / HOLD signal.
    e. Place a paper (mock) market order if a BUY or SELL signal is triggered.

To swap the strategy, replace `from strategy import generate_signal` with your
own module that exposes `generate_signal(df: pd.DataFrame) -> str`.

To swap the exchange, add a new factory branch inside `build_exchange()`.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Optional

import ccxt
import pandas as pd

import strategy  # noqa: F401  (imported for the generate_signal alias below)
from config import settings
from strategy import generate_signal

# ---------------------------------------------------------------------------
# Logging setup — writes to both stdout and a rotating log file.
# ---------------------------------------------------------------------------

LOG_FILE = "trading_bot.log"


def configure_logging() -> None:
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exchange factory — returns a configured ccxt exchange instance.
# ---------------------------------------------------------------------------

def build_exchange() -> ccxt.Exchange:
    """
    Instantiate and return a ccxt exchange configured for paper trading.

    Extend this function to support additional exchanges.
    """
    if settings.exchange == "alpaca":
        exchange = ccxt.alpaca(
            {
                "apiKey": settings.alpaca_api_key,
                "secret": settings.alpaca_secret_key,
                # Override the base URL to target the Alpaca paper-trading sandbox.
                "urls": {
                    "api": {
                        "rest": settings.alpaca_base_url,
                    }
                },
                "options": {
                    "paper": True,
                },
            }
        )

    elif settings.exchange == "binance":
        exchange = ccxt.binance(
            {
                "apiKey": settings.binance_api_key,
                "secret": settings.binance_secret_key,
            }
        )
        # Enable Binance testnet (sandbox)
        exchange.set_sandbox_mode(True)

    else:
        # This branch should never be reached because config.py validates the
        # EXCHANGE value, but it's here as an explicit guard.
        raise ValueError(f"Unsupported exchange: {settings.exchange}")

    logger.info(
        "Exchange initialised: %s (sandbox/paper mode)", exchange.id.upper()
    )
    return exchange


# ---------------------------------------------------------------------------
# Market data helpers
# ---------------------------------------------------------------------------

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def fetch_ohlcv(exchange: ccxt.Exchange) -> pd.DataFrame:
    """
    Fetch the latest OHLCV candles for the configured trading pair.

    Returns:
        A DataFrame with columns [timestamp, open, high, low, close, volume]
        sorted in ascending chronological order.

    Raises:
        ccxt.BaseError: propagated from ccxt on API or network errors.
    """
    logger.info(
        "Fetching %d × %s candles for %s …",
        settings.candle_limit,
        settings.timeframe,
        settings.trading_pair,
    )

    raw: list = exchange.fetch_ohlcv(
        symbol=settings.trading_pair,
        timeframe=settings.timeframe,
        limit=settings.candle_limit,
    )

    df = pd.DataFrame(raw, columns=OHLCV_COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df = df.sort_index()  # guarantee ascending order

    logger.info(
        "Received %d candles from %s to %s.",
        len(df),
        df.index[0].isoformat(),
        df.index[-1].isoformat(),
    )
    return df


# ---------------------------------------------------------------------------
# Order execution helpers
# ---------------------------------------------------------------------------

def place_order(
    exchange: ccxt.Exchange,
    side: str,
    amount: float,
) -> Optional[dict]:
    """
    Place a market order on the exchange.

    In paper / sandbox mode the exchange records the order without touching
    real funds.  The raw order dict returned by ccxt is logged for auditing.

    Args:
        exchange: An authenticated ccxt exchange instance.
        side:     'buy' or 'sell'.
        amount:   Order size in the base currency (e.g. BTC).

    Returns:
        The order dict from ccxt, or None if the order failed.
    """
    symbol = settings.trading_pair
    logger.info(
        "Placing PAPER %s order | pair=%s amount=%s",
        side.upper(), symbol, amount,
    )

    try:
        order = exchange.create_market_order(
            symbol=symbol,
            side=side,
            amount=amount,
        )
        logger.info(
            "Order accepted | id=%s status=%s filled=%s price=%s",
            order.get("id"),
            order.get("status"),
            order.get("filled"),
            order.get("average") or order.get("price"),
        )
        return order

    except ccxt.InsufficientFunds as exc:
        logger.error("Insufficient funds to place %s order: %s", side.upper(), exc)
    except ccxt.InvalidOrder as exc:
        logger.error("Invalid order parameters: %s", exc)
    except ccxt.NetworkError as exc:
        logger.error("Network error while placing order: %s", exc)
    except ccxt.BaseError as exc:
        logger.error("Unexpected ccxt error: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Main execution loop
# ---------------------------------------------------------------------------

def run() -> None:
    """Single iteration of: fetch → analyse → (optionally) trade."""
    configure_logging()
    logger.info("=" * 60)
    logger.info(
        "Trading bot started at %s UTC",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )

    # 1. Connect to the exchange
    try:
        exchange = build_exchange()
    except (ccxt.AuthenticationError, ccxt.ExchangeError) as exc:
        logger.critical("Failed to initialise exchange: %s", exc)
        sys.exit(1)

    # 2. Fetch OHLCV data
    try:
        df = fetch_ohlcv(exchange)
    except ccxt.NetworkError as exc:
        logger.critical("Network error fetching market data: %s", exc)
        sys.exit(1)
    except ccxt.BaseError as exc:
        logger.critical("Exchange error fetching market data: %s", exc)
        sys.exit(1)

    # 3. Run the strategy
    try:
        signal = generate_signal(df)
    except ValueError as exc:
        logger.critical("Strategy error: %s", exc)
        sys.exit(1)

    logger.info("Strategy signal: %s", signal)

    # 4. Execute a paper trade if the signal is actionable
    if signal in ("BUY", "SELL"):
        place_order(
            exchange=exchange,
            side=signal.lower(),
            amount=settings.order_size,
        )
    else:
        logger.info("No trade executed (HOLD).")

    logger.info("Bot run complete.")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
