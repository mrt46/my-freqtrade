from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy


class VisualPriceAction(IStrategy):
    """
    Range odaklı price-action stratejisi.

    - Swing high/low (2 sol + 2 sağ)
    - Trend: UP / DOWN / RANGE
    - RANGE alt bandında wick + hacim filtresiyle giriş
    - RANGE üst bandında wick + hacim filtresiyle çıkış
    """

    timeframe = "15m"
    minimal_roi = {"0": 0.02}
    stoploss = -0.03

    trailing_stop = False
    process_only_new_candles = True
    startup_candle_count = 120
    use_exit_signal = True

    range_tolerance = 0.003
    touch_lookback = 30
    min_touches = 3
    wick_ratio = 1.5

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
        df = dataframe

        df["body"] = (df["close"] - df["open"]).abs()
        df["upper_wick"] = df["high"] - df[["close", "open"]].max(axis=1)
        df["lower_wick"] = df[["close", "open"]].min(axis=1) - df["low"]
        df["volume_sma_20"] = df["volume"].rolling(20).mean()

        raw_swing_high = (
            (df["high"] > df["high"].shift(1))
            & (df["high"] > df["high"].shift(2))
            & (df["high"] > df["high"].shift(-1))
            & (df["high"] > df["high"].shift(-2))
        )
        raw_swing_low = (
            (df["low"] < df["low"].shift(1))
            & (df["low"] < df["low"].shift(2))
            & (df["low"] < df["low"].shift(-1))
            & (df["low"] < df["low"].shift(-2))
        )

        # Lookahead bias engeli için swing onayı 2 mum sonra aktif olur.
        df["swing_high"] = raw_swing_high.shift(2).fillna(False)
        df["swing_low"] = raw_swing_low.shift(2).fillna(False)

        last_high = np.nan
        prev_high = np.nan
        last_low = np.nan
        prev_low = np.nan

        last_highs: list[float] = []
        prev_highs: list[float] = []
        last_lows: list[float] = []
        prev_lows: list[float] = []

        for high, low, is_high, is_low in zip(df["high"], df["low"], df["swing_high"], df["swing_low"]):
            if is_high:
                prev_high = last_high
                last_high = high
            if is_low:
                prev_low = last_low
                last_low = low

            last_highs.append(last_high)
            prev_highs.append(prev_high)
            last_lows.append(last_low)
            prev_lows.append(prev_low)

        df["last_swing_high"] = pd.Series(last_highs, index=df.index)
        df["prev_swing_high"] = pd.Series(prev_highs, index=df.index)
        df["last_swing_low"] = pd.Series(last_lows, index=df.index)
        df["prev_swing_low"] = pd.Series(prev_lows, index=df.index)

        trend_up = (df["last_swing_high"] > df["prev_swing_high"]) & (df["last_swing_low"] > df["prev_swing_low"])
        trend_down = (df["last_swing_high"] < df["prev_swing_high"]) & (df["last_swing_low"] < df["prev_swing_low"])

        df["trend"] = np.select([trend_up, trend_down], ["UP", "DOWN"], default="RANGE")
        df["range_high"] = df["last_swing_high"]
        df["range_low"] = df["last_swing_low"]

        df["near_range_low"] = ((df["close"] - df["range_low"]).abs() / df["range_low"]) <= self.range_tolerance
        df["near_range_high"] = ((df["close"] - df["range_high"]).abs() / df["range_high"]) <= self.range_tolerance

        df["touch_low"] = df["low"] <= (df["range_low"] * (1 + self.range_tolerance))
        df["touch_high"] = df["high"] >= (df["range_high"] * (1 - self.range_tolerance))
        df["touch_low_bounce"] = df["touch_low"] & (df["close"] > df["open"])
        df["touch_high_reject"] = df["touch_high"] & (df["close"] < df["open"])

        df["touch_low_count"] = df["touch_low_bounce"].rolling(self.touch_lookback).sum()
        df["touch_high_count"] = df["touch_high_reject"].rolling(self.touch_lookback).sum()

        df["lower_wick_ratio"] = df["lower_wick"] / df["body"].replace(0, np.nan)
        df["upper_wick_ratio"] = df["upper_wick"] / df["body"].replace(0, np.nan)

        return df

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
        df = dataframe

        long_condition = (
            (df["trend"] == "RANGE")
            & df["near_range_low"]
            & (df["touch_low_count"] >= self.min_touches)
            & (df["lower_wick_ratio"] > self.wick_ratio)
            & (df["volume"] < df["volume_sma_20"])
        )

        df.loc[long_condition, ["enter_long", "enter_tag"]] = (1, "range_support_bounce")
        return df

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
        df = dataframe

        exit_condition = (
            (df["trend"] == "RANGE")
            & df["near_range_high"]
            & (df["touch_high_count"] >= self.min_touches)
            & (df["upper_wick_ratio"] > self.wick_ratio)
            & (df["volume"] < df["volume_sma_20"])
        )

        df.loc[exit_condition, ["exit_long", "exit_tag"]] = (1, "range_resistance_reject")
        return df
