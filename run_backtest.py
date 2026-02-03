#!/usr/bin/env python3
"""
Offline backtest runner — monkey-patches Exchange.reload_markets
so that backtesting works without network access to Binance.
"""

import sys, time

# ── 1.  Fake markets for 10 pairs ────────────────────────────────
FAKE_MARKETS = {}
PAIRS_META = {
    "BTC/USDT":  ("BTCUSDT",  8, 2),
    "ETH/USDT":  ("ETHUSDT",  6, 2),
    "BNB/USDT":  ("BNBUSDT",  6, 2),
    "SOL/USDT":  ("SOLUSDT",  6, 2),
    "XRP/USDT":  ("XRPUSDT",  6, 8),
    "ADA/USDT":  ("ADAUSDT",  6, 8),
    "AVAX/USDT": ("AVAXUSDT", 6, 2),
    "DOGE/USDT": ("DOGEUSDT", 6, 8),
    "DOT/USDT":  ("DOTUSDT",  6, 2),
    "LINK/USDT": ("LINKUSDT", 6, 2),
}

for symbol, (pair_id, amt_prec, price_prec) in PAIRS_META.items():
    base, quote = symbol.split("/")
    FAKE_MARKETS[symbol] = {
        "id":            pair_id,
        "symbol":        symbol,
        "base":          base,
        "quote":         quote,
        "baseId":        base.lower(),
        "quoteId":       quote.lower(),
        "spot":          True,
        "future":        False,
        "margin":        False,
        "swap":          False,
        "active":        True,
        "contract":      False,
        "settle":        None,
        "expiry":        None,
        "expiryDatetime": None,
        "strike":        None,
        "option":        None,
        "limits": {
            "amount": {"min": 0.00001, "max": 90000},
            "price":  {"min": 0.00000001, "max": 1000000},
            "cost":   {"min": 10.0, "max": 9000000},
        },
        "precision": {
            "amount": amt_prec,
            "price":  price_prec,
            "cost":   2,
        },
        "info": {"status": "TRADING", "pricePrecision": price_prec},
    }


# ── 2.  Monkey-patch Exchange BEFORE freqtrade imports it ────────
import freqtrade.exchange.exchange as _exc_mod

_original_reload = _exc_mod.Exchange.reload_markets

def _patched_reload(self, force=False, *, load_leverage_tiers=True):
    """Drop-in: set markets from FAKE_MARKETS, skip network."""
    self._markets = FAKE_MARKETS
    # Also set on ccxt sync/async instances so internal helpers work
    self._api.markets = FAKE_MARKETS
    self._api_async.markets = FAKE_MARKETS
    self._last_markets_refresh = time.time() * 1000
    return None

_exc_mod.Exchange.reload_markets = _patched_reload

# Patch validate_config so it doesn't choke on missing market fields
_orig_validate = _exc_mod.Exchange.validate_config

def _patched_validate(self, config):
    """Skip heavy validation that requires real market data."""
    pass

_exc_mod.Exchange.validate_config = _patched_validate

# Binance fee: 0.1% maker & taker (lowest tier)
_exc_mod.Exchange.get_fee = lambda self, symbol="", taker_or_maker="taker", **kw: 0.001


# ── 3.  Now run freqtrade backtesting normally ───────────────────
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.enums import RunMode
from pathlib import Path

cli_args = [
    "backtesting",
    "--config",     "user_data/config/config_backtest.json",
    "--strategy",   "BinanceOptimized",
    "--timeframe",  "4h",
    "--timerange",  "20250203-20260203",
]

parsed_args = Arguments(cli_args).get_parsed_arg()
config      = setup_optimize_configuration(parsed_args, RunMode.BACKTEST)

# Force offline data paths + proper enums
from freqtrade.enums import CandleType, TradingMode
config["datadir"]           = Path("user_data/data/binance")
config["user_data_dir"]     = Path("user_data")
config["trading_mode"]      = TradingMode.SPOT
config["candle_type_def"]   = CandleType.SPOT
config["margin_mode"]       = ""
config["dataformat_ohlcv"]  = "json"      # our data is in JSON, not feather

print("\n" + "=" * 70)
print("  FREQTRADE OFFLINE BACKTEST  –  BinanceOptimized  –  4h")
print("=" * 70 + "\n")

from freqtrade.optimize.backtesting import Backtesting
bt = Backtesting(config)
bt.start()
