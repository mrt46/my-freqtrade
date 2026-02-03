"""
BinanceOptimized Strategy
-------------------------
Combines best-performing strategies from backtests:
  - FixedRiskRewardLoss  -> ATR-based stoploss, 3.5:1 R:R
  - Supertrend           -> Trend following
  - MultiMa (TEMA)       -> Trend confirmation

Timeframe : 4h
Exchange  : Binance spot
Mode      : dry_run / live
"""

import logging
from functools import reduce
from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

import talib.abstract as ta

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class BinanceOptimized(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = '4h'

    # ── Risk / ROI ────────────────────────────────────
    stoploss = -0.10                         # fallback if custom_stoploss returns -1
    use_custom_stoploss = True

    minimal_roi = {
        "0":   0.10,   # 10 %
        "120": 0.06,   # 6 %  after  5 d
        "360": 0.04,   # 4 %  after 15 d
        "720": 0.02,   # 2 %  after 30 d
    }

    # ── Trailing stop ─────────────────────────────────
    # Disabled: custom_stoploss handles BE + TP locking
    trailing_stop = False

    # ── Orders ────────────────────────────────────────
    order_types = {
        "entry":                 "limit",
        "exit":                  "limit",
        "stoploss":              "market",
        "stoploss_on_exchange":  False,        # MUST be False for dry_run
    }
    order_time_in_force = {
        "entry": "gtc",
        "exit":  "gtc",
    }

    # ── Startup ───────────────────────────────────────
    startup_candle_count = 200
    process_only_new_candles = True

    # ── Hyperparameters ──────────────────────────────
    st_multiplier = DecimalParameter(1.0, 7.0, default=4.0,  space="buy")
    st_period    = IntParameter(7, 21,         default=10,   space="buy")
    ma_count     = IntParameter(2, 8,          default=4,    space="buy")
    ma_gap       = IntParameter(10, 30,        default=15,   space="buy")
    volume_factor = DecimalParameter(0.5, 2.0, default=0.8,  space="buy")

    # ── Per-pair stoploss cache (instance-level) ─────
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._sl_cache: dict[str, pd.DataFrame] = {}
        self._rr_ratio       = 3.5
        self._be_at_profit   = 1.0   # move to break-even at 1 × risk

    # ═══════════════════════════════════════════════════
    #  INDICATORS
    # ═══════════════════════════════════════════════════
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata['pair']

        # ── ATR (risk sizing) ─────────────────────────
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['stoploss_rate'] = dataframe['close'] - dataframe['atr'] * 2

        # Cache stoploss prices per-pair for custom_stoploss
        self._sl_cache[pair] = (
            dataframe[['date', 'stoploss_rate']]
            .copy()
            .set_index('date')
        )

        # ── Supertrend (only for CURRENT params) ─────
        st = self._supertrend(
            dataframe,
            float(self.st_multiplier.value),
            int(self.st_period.value),
        )
        dataframe['st_val'] = st['ST']
        dataframe['st_dir'] = st['STX']

        # ── TEMA chain (only the periods actually used) ─
        ma_cnt = int(self.ma_count.value)
        ma_g   = int(self.ma_gap.value)
        for i in range(0, ma_cnt + 1):
            period = i * ma_g
            if period >= 2:
                col = f'tema_{period}'
                if col not in dataframe.columns:
                    dataframe[col] = ta.TEMA(dataframe, timeperiod=period)

        # ── RSI ───────────────────────────────────────
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # ── Volume ────────────────────────────────────
        dataframe['volume_ma']    = dataframe['volume'].rolling(20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']

        # ── Bollinger Bands ───────────────────────────
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper']  = bb['upperband']
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_lower']  = bb['lowerband']
        dataframe['bb_width']  = (bb['upperband'] - bb['lowerband']) / bb['middleband']

        # ── ADX (trend strength) ──────────────────────
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        return dataframe

    # ═══════════════════════════════════════════════════
    #  ENTRY
    # ═══════════════════════════════════════════════════
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0

        ma_cnt     = int(self.ma_count.value)
        ma_g       = int(self.ma_gap.value)
        vol_factor = float(self.volume_factor.value)

        # ── TEMA rainbow: shorter MA > longer MA ──────
        ma_conds: list[pd.Series] = []
        for i in range(1, ma_cnt):
            short_col = f'tema_{(i - 1) * ma_g}'
            long_col  = f'tema_{i * ma_g}'
            if short_col in dataframe.columns and long_col in dataframe.columns:
                # tema_0 doesn't exist (period=0); first valid pair is tema_15 vs tema_30
                if (i - 1) * ma_g >= 2:
                    ma_conds.append(dataframe[short_col] > dataframe[long_col])

        # ── Base conditions ───────────────────────────
        base = [
            dataframe['st_dir']      == 'up',        # supertrend bullish
            dataframe['volume_ratio'] > vol_factor,   # volume confirmation
            dataframe['rsi']         < 70,            # not overbought
            dataframe['adx']         > 20,            # clear trend
            dataframe['close']       > dataframe['bb_middle'],  # above mid-BB
        ]

        all_conds = base + ma_conds if ma_conds else base

        dataframe.loc[reduce(lambda a, b: a & b, all_conds), 'enter_long'] = 1

        return dataframe

    # ═══════════════════════════════════════════════════
    #  EXIT
    # ═══════════════════════════════════════════════════
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0

        dataframe.loc[
            (dataframe['st_dir'] == 'down') |   # supertrend flipped
            (dataframe['rsi']    > 80),          # extreme overbought
            'exit_long'
        ] = 1

        return dataframe

    # ═══════════════════════════════════════════════════
    #  CUSTOM STOPLOSS  —  ATR-based with R:R levels
    # ═══════════════════════════════════════════════════
    def custom_stoploss(self, pair: str, trade: Trade, current_time,
                        current_rate: float, current_profit: float,
                        after_fill: bool = False, **kwargs) -> float:

        sl_df = self._sl_cache.get(pair)
        if sl_df is None or sl_df.empty:
            return -1.0

        try:
            # stoploss_rate at trade-open candle (normalise tz for comparison)
            open_dt = trade.open_date_utc.replace(tzinfo=None) if trade.open_date_utc.tzinfo else trade.open_date_utc
            idx = sl_df.index.tz_localize(None) if sl_df.index.tzinfo else sl_df.index
            mask = idx <= open_dt
            if not mask.any():
                return -1.0
            initial_sl_abs = float(sl_df.loc[mask, 'stoploss_rate'].iloc[-1])

            # ── Risk distance ─────────────────────────
            risk_dist = trade.open_rate - initial_sl_abs
            if risk_dist <= 0:
                return -1.0

            # ── Levels ────────────────────────────────
            initial_sl_pct = initial_sl_abs / current_rate - 1.0

            # Break-even: when profit ≥ 1 × risk_dist
            be_pct = risk_dist / trade.open_rate

            # Take-profit lock: when profit ≥ 3.5 × risk_dist
            tp_abs = trade.open_rate + risk_dist * self._rr_ratio
            tp_pct = tp_abs / trade.open_rate - 1.0

            # ── Apply levels top-down (most restrictive first) ─
            if current_profit >= tp_pct:
                # lock in at TP price
                return tp_abs / current_rate - 1.0

            if current_profit >= be_pct:
                # lock in at break-even (+ fees)
                fee_total = trade.fee_open + (trade.fee_close or 0.0)
                return trade.open_rate * (1.0 + fee_total) / current_rate - 1.0

            return initial_sl_pct

        except Exception:
            logger.exception(f"custom_stoploss error – {pair}")
            return -1.0

    # ═══════════════════════════════════════════════════
    #  CUSTOM EXIT
    # ═══════════════════════════════════════════════════
    def custom_exit(self, pair: str, trade: Trade, current_time,
                    current_rate: float, current_profit: float,
                    **kwargs) -> Optional[str]:

        # Hard max-loss guard: never let a single trade exceed -10%
        if current_profit < -0.10:
            return "max_loss_guard"

        # Extreme profit → take it
        if current_profit > 0.15:
            return "extreme_profit"

        # Stale loss → cut it (>24h and still -2%)
        if trade.is_open:
            hours = (current_time - trade.open_date_utc).total_seconds() / 3600
            if hours > 24 and current_profit < -0.02:
                return "stale_trade"

        return None

    # ═══════════════════════════════════════════════════
    #  ENTRY / EXIT CONFIRMATION
    # ═══════════════════════════════════════════════════
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time,
                            entry_tag: Optional[str] = None, side: str = "long",
                            **kwargs) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return True
        last = dataframe.iloc[-1]

        if last['bb_width'] > 0.35:                  # extreme volatility (crypto-realistic)
            return False
        if last['volume_ratio'] < 0.3:               # dead volume
            return False
        return True

    # ═══════════════════════════════════════════════════
    #  SUPERTREND helper  (vectorised bands, loop only for state)
    # ═══════════════════════════════════════════════════
    @staticmethod
    def _supertrend(dataframe: DataFrame, multiplier: float, period: int) -> DataFrame:
        high  = dataframe['high'].to_numpy()
        low   = dataframe['low'].to_numpy()
        close = dataframe['close'].to_numpy()
        n     = len(dataframe)

        # ATR via rolling TR  (no copy needed)
        tr = np.maximum(high - low,
             np.maximum(np.abs(high - np.roll(close, 1)),
                        np.abs(low  - np.roll(close, 1))))
        tr[0] = high[0] - low[0]
        atr = pd.Series(tr).rolling(period).mean().to_numpy()

        # Basic bands (vectorised)
        hl2      = (high + low) / 2.0
        basic_ub = hl2 + multiplier * atr
        basic_lb = hl2 - multiplier * atr

        # Final bands  – sequential dependency
        final_ub = np.empty(n)
        final_lb = np.empty(n)
        final_ub[:period] = basic_ub[:period]
        final_lb[:period] = basic_lb[:period]

        for i in range(period, n):
            final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]) else final_ub[i-1]
            final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]) else final_lb[i-1]

        # Supertrend value – sequential
        st = np.zeros(n)
        st[period] = final_ub[period]           # seed
        for i in range(period + 1, n):
            if st[i-1] == final_ub[i-1]:
                st[i] = final_ub[i] if close[i] <= final_ub[i] else final_lb[i]
            else:
                st[i] = final_lb[i] if close[i] >= final_lb[i] else final_ub[i]

        # Direction string
        stx = np.where(st > 0,
                       np.where(close < st, 'down', 'up'),
                       None)

        return pd.DataFrame({'ST': st, 'STX': stx}, index=dataframe.index)
