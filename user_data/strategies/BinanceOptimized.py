"""
Binance Optimized Strategy
Combines the best performing strategies: FixedRiskRewardLoss, Supertrend, and MultiMa
Optimized for 4h timeframe with strong risk management
"""

import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional
import talib.abstract as ta

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

import logging
logger = logging.getLogger(__name__)


class BinanceOptimized(IStrategy):
    """
    Hybrid strategy combining:
    - Risk/Reward management from FixedRiskRewardLoss (3.5:1 R:R)
    - Supertrend trend following
    - MultiMa confirmation

    Target: 4h timeframe, Binance spot trading
    Expected: High win rate with strong profit factor
    """

    INTERFACE_VERSION = 3

    # Strategy configuration
    timeframe = '4h'

    # Risk Management - Aggressive but controlled
    stoploss = -0.9  # Wide stoploss, managed by custom_stoploss
    use_custom_stoploss = True

    # ROI - Let winners run
    minimal_roi = {
        "0": 0.10,      # 10% target
        "120": 0.06,    # 6% after 20 hours
        "360": 0.04,    # 4% after 60 hours
        "720": 0.02     # 2% after 120 hours
    }

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # Order types
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True
    }

    # Custom parameters
    custom_info = {
        'risk_reward_ratio': 3.5,
        'set_to_break_even_at_profit': 1.0,
    }

    # Hyperparameters
    # Supertrend parameters (optimized from backtests)
    st_multiplier = DecimalParameter(1.0, 7.0, default=4.0, space="buy")
    st_period = IntParameter(7, 21, default=10, space="buy")

    # MultiMa parameters
    ma_count = IntParameter(2, 8, default=4, space="buy")
    ma_gap = IntParameter(10, 30, default=15, space="buy")

    # Volume filter
    volume_factor = DecimalParameter(0.5, 2.0, default=0.8, space="buy")

    # Startup candles
    startup_candle_count = 200

    # Position adjustment
    position_adjustment_enable = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate all indicators"""

        # ATR for risk management (FixedRiskRewardLoss method)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['stoploss_rate'] = dataframe['close'] - (dataframe['atr'] * 2)

        # Store stoploss rates for custom_stoploss
        self.custom_info[metadata['pair']] = dataframe[['date', 'stoploss_rate']].copy().set_index('date')

        # Supertrend indicator
        for mult in range(1, 8):
            for period in range(7, 22):
                st_result = self.supertrend(dataframe, mult, period)
                dataframe[f'st_{mult}_{period}'] = st_result['ST']
                dataframe[f'stx_{mult}_{period}'] = st_result['STX']

        # MultiMa - TEMA indicators
        for count in range(1, 9):
            for gap in range(10, 31):
                period = count * gap
                if period > 1 and period <= 200:
                    dataframe[f'tema_{period}'] = ta.TEMA(dataframe, timeperiod=period)

        # RSI for additional confirmation
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Volume analysis
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']

        # Bollinger Bands for volatility
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']

        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry conditions:
        1. Supertrend is UP (trend following)
        2. MultiMa alignment (lower MAs below higher MAs = uptrend)
        3. Volume confirmation
        4. RSI not overbought
        5. ADX shows trend strength
        """

        dataframe['enter_long'] = 0

        # Get current parameter values
        st_mult = int(self.st_multiplier.value)
        st_per = int(self.st_period.value)
        ma_cnt = int(self.ma_count.value)
        ma_g = int(self.ma_gap.value)
        vol_factor = float(self.volume_factor.value)

        # Build MultiMa conditions
        ma_conditions = []
        for i in range(1, ma_cnt):
            key = i * ma_g
            past_key = (i - 1) * ma_g
            tema_col = f'tema_{key}'
            tema_past_col = f'tema_{past_key}'

            if tema_col in dataframe.columns and tema_past_col in dataframe.columns:
                # For uptrend: shorter MA should be above longer MA
                ma_conditions.append(dataframe[tema_past_col] > dataframe[tema_col])

        # Entry signal
        st_col = f'stx_{st_mult}_{st_per}'

        if st_col in dataframe.columns:
            conditions = [
                # Supertrend is UP
                (dataframe[st_col] == 'up'),

                # Volume confirmation
                (dataframe['volume_ratio'] > vol_factor),

                # RSI not overbought
                (dataframe['rsi'] < 70),

                # Trend strength (ADX > 20)
                (dataframe['adx'] > 20),

                # Price above middle BB (bullish)
                (dataframe['close'] > dataframe['bb_middle']),
            ]

            # Add MultiMa conditions
            if ma_conditions:
                from functools import reduce
                ma_combined = reduce(lambda x, y: x & y, ma_conditions)
                conditions.append(ma_combined)

            # Combine all conditions
            if conditions:
                from functools import reduce
                dataframe.loc[
                    reduce(lambda x, y: x & y, conditions),
                    'enter_long'
                ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit conditions:
        1. Supertrend turns DOWN
        2. RSI overbought
        """

        dataframe['exit_long'] = 0

        st_mult = int(self.st_multiplier.value)
        st_per = int(self.st_period.value)
        st_col = f'stx_{st_mult}_{st_per}'

        if st_col in dataframe.columns:
            dataframe.loc[
                (
                    # Supertrend turns down
                    (dataframe[st_col] == 'down') |
                    # Or RSI extremely overbought
                    (dataframe['rsi'] > 80)
                ),
                'exit_long'
            ] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Custom stoploss using FixedRiskRewardLoss logic
        - Initial SL: 2x ATR below entry
        - Break-even at 1x risk
        - Take profit at 3.5x risk
        """

        result = -1
        custom_info_pair = self.custom_info.get(pair)

        if custom_info_pair is not None:
            try:
                # Find entry candle
                open_date_mask = custom_info_pair.index.unique().get_loc(
                    trade.open_date_utc, method='ffill'
                )
                open_df = custom_info_pair.iloc[open_date_mask]

                if len(open_df) != 1:
                    return -1

                initial_sl_abs = open_df['stoploss_rate']

                # Calculate initial stoploss
                initial_sl = initial_sl_abs / current_rate - 1

                # Calculate risk/reward levels
                risk_distance = trade.open_rate - initial_sl_abs
                reward_distance = risk_distance * self.custom_info['risk_reward_ratio']

                # Take profit price
                take_profit_price_abs = trade.open_rate + reward_distance
                take_profit_pct = take_profit_price_abs / trade.open_rate - 1

                # Break-even distance
                break_even_profit_distance = risk_distance * self.custom_info['set_to_break_even_at_profit']
                break_even_profit_pct = (break_even_profit_distance + current_rate) / current_rate - 1

                result = initial_sl

                # Move to break-even when profit reaches 1x risk
                if current_profit >= break_even_profit_pct:
                    break_even_sl = (trade.open_rate * (1 + trade.fee_open + trade.fee_close) / current_rate) - 1
                    result = break_even_sl
                    logger.info(f"{pair}: Break-even triggered at {current_profit:.2%}")

                # Lock in profit at 3.5x risk
                if current_profit >= take_profit_pct:
                    takeprofit_sl = take_profit_price_abs / current_rate - 1
                    result = takeprofit_sl
                    logger.info(f"{pair}: Take-profit level reached at {current_profit:.2%}")

            except Exception as e:
                logger.error(f"Error in custom_stoploss for {pair}: {e}")
                return -1

        return result

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """Custom exit logic"""

        # Quick profit taking on extreme moves (>15%)
        if current_profit > 0.15:
            return "extreme_profit"

        # Cut losses if trade is underwater too long (>5 days on 4h = 30 candles)
        if trade.is_open:
            trade_duration_hours = (current_time - trade.open_date_utc).total_seconds() / 3600
            if trade_duration_hours > 120 and current_profit < -0.03:  # 5 days and -3%
                return "stale_trade"

        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time: datetime,
                           entry_tag: Optional[str], side: str, **kwargs) -> bool:
        """Additional entry confirmation"""

        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]

            # Don't enter in extreme volatility (BB width > 10%)
            if last_candle['bb_width'] > 0.10:
                logger.warning(f"{pair}: Entry blocked - extreme volatility")
                return False

            # Don't enter if volume is too low
            if last_candle['volume_ratio'] < 0.3:
                logger.warning(f"{pair}: Entry blocked - very low volume")
                return False

        return True

    def supertrend(self, dataframe: DataFrame, multiplier: int, period: int) -> DataFrame:
        """
        Supertrend indicator calculation
        Adapted from freqtrade-strategies
        """
        df = dataframe.copy()
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        length = len(df)

        # Calculate ATR
        tr = ta.TRANGE(df['high'], df['low'], df['close'])
        atr = pd.Series(tr).rolling(period).mean().to_numpy()

        # Basic upper/lower bands
        basic_ub = (high + low) / 2 + multiplier * atr
        basic_lb = (high + low) / 2 - multiplier * atr

        # Final bands
        final_ub = np.zeros(length)
        final_lb = np.zeros(length)

        for i in range(period, length):
            final_ub[i] = basic_ub[i] if basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1] else final_ub[i-1]
            final_lb[i] = basic_lb[i] if basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1] else final_lb[i-1]

        # Supertrend
        st = np.zeros(length)
        for i in range(period, length):
            if st[i-1] == final_ub[i-1]:
                st[i] = final_ub[i] if close[i] <= final_ub[i] else final_lb[i]
            elif st[i-1] == final_lb[i-1]:
                st[i] = final_lb[i] if close[i] >= final_lb[i] else final_ub[i]

        # Direction
        stx = np.where(st > 0, np.where(close < st, 'down', 'up'), None)

        result = pd.DataFrame({'ST': st, 'STX': stx}, index=df.index)
        result.fillna(0, inplace=True)

        return result
