# Crypto Algorithmic Trading Bot

A modular, scalable cryptocurrency algorithmic trading bot written in Python 3.11+.
Connects to the **Alpaca Paper Trading** API (or Binance Testnet), fetches live OHLCV
market data, runs a **Simple Moving Average (SMA) crossover strategy**, and executes
paper trades — no real capital at risk.

---

## Project Structure

```
crypto/
├── config.py          # Loads & validates settings from .env
├── strategy.py        # SMA 50/200 crossover signal logic
├── main.py            # Entry point: fetch → signal → trade
├── requirements.txt   # Python dependencies
├── .env.example       # Template for your .env file
└── trading_bot.log    # Created at runtime
```

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone https://github.com/RulzzBot-svg/crypto.git
cd crypto
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your API keys:

| Variable | Where to get it |
|---|---|
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | [app.alpaca.markets](https://app.alpaca.markets) → switch to **Paper** mode |
| `BINANCE_API_KEY` / `BINANCE_SECRET_KEY` | [testnet.binance.vision](https://testnet.binance.vision/) |

> **Never commit `.env` to version control.** It is already listed in `.gitignore`.

### 3. Run the bot

```bash
python main.py
```

All output is logged to stdout **and** `trading_bot.log`.

---

## How It Works

```
main.py
  └─ build_exchange()      # Creates ccxt Alpaca/Binance client (paper mode)
  └─ fetch_ohlcv()         # Pulls latest OHLCV candles via ccxt
  └─ generate_signal(df)   # strategy.py: SMA 50/200 crossover → BUY/SELL/HOLD
  └─ place_order()         # Fires a paper market order if signal != HOLD
```

### Strategy logic (strategy.py)

| Condition | Signal |
|---|---|
| SMA-50 crosses **above** SMA-200 (Golden Cross) | **BUY** |
| SMA-50 crosses **below** SMA-200 (Death Cross) | **SELL** |
| No crossover | **HOLD** |

---

## Swapping the Strategy

`main.py` calls `generate_signal(df: pd.DataFrame) -> str` from `strategy.py`.
To use a different strategy, create a new module (e.g. `strategy_rsi.py`) that
exposes the same function, then update the import in `main.py`:

```python
from strategy_rsi import generate_signal
```

## Swapping the Exchange

Add a new `elif settings.exchange == "your_exchange":` branch inside
`build_exchange()` in `main.py`, and add the corresponding credentials to
`.env.example` and `config.py`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `EXCHANGE` | `alpaca` | `alpaca` or `binance` |
| `ALPACA_API_KEY` | — | Alpaca API key (paper trading) |
| `ALPACA_SECRET_KEY` | — | Alpaca secret key |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Alpaca endpoint |
| `BINANCE_API_KEY` | — | Binance API key (testnet) |
| `BINANCE_SECRET_KEY` | — | Binance secret key |
| `TRADING_PAIR` | `BTC/USD` | ccxt symbol string |
| `TIMEFRAME` | `1h` | Candle timeframe |
| `CANDLE_LIMIT` | `250` | Number of candles to fetch (min 200) |
| `ORDER_SIZE` | `0.001` | Order size in base currency |

---

## Tech Stack

| Concern | Library |
|---|---|
| Exchange connectivity | [`ccxt`](https://github.com/ccxt/ccxt) |
| Data processing | [`pandas`](https://pandas.pydata.org/), [`numpy`](https://numpy.org/) |
| Environment variables | [`python-dotenv`](https://github.com/theskumar/python-dotenv) |
| Logging | Python built-in `logging` |
