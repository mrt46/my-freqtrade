"""
Adaptive Multi-Strategy Trading Bot
Automatically selects the best strategy based on market conditions
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade

from .market_regime import MarketRegimeDetector
from .strategy_base import (
    SubStrategyBase,
    TrendFollowingSubStrategy,
    GridSubStrategy,
    MeanReversionSubStrategy
)

logger = logging.getLogger(__name__)


class StrategySelector:
    """
    Intelligent strategy selector that chooses the best strategy
    based on market conditions and historical performance
    """

    def __init__(self, strategies: List[SubStrategyBase]):
        self.strategies = {s.metadata.name: s for s in strategies}
        self.performance_history: Dict[str, List[Dict]] = {name: [] for name in self.strategies}
        self.selection_history: List[Dict] = []
        self.last_switch_time: Optional[datetime] = None
        self.min_switch_interval = timedelta(minutes=30)  # Don't switch too frequently
        self.current_strategy: Optional[str] = None

    def select_best_strategy(self, market_condition: Dict) -> Tuple[str, float, Dict[str, float]]:
        """
        Select the best strategy for current market conditions

        Returns:
            (strategy_name, confidence, all_scores)
        """
        scores = {}

        for name, strategy in self.strategies.items():
            base_score = strategy.calculate_fitness_score(market_condition)

            # Adjust score based on recent performance
            perf_multiplier = self._get_performance_multiplier(name)
            adjusted_score = base_score * perf_multiplier

            # Check minimum threshold
            if adjusted_score < strategy.metadata.min_fitness_threshold:
                adjusted_score = 0.0

            scores[name] = adjusted_score

        # Find best strategy
        best_strategy = max(scores, key=scores.get)
        best_score = scores[best_strategy]

        # Check if we should switch
        if self.current_strategy and self.last_switch_time:
            time_since_switch = datetime.now() - self.last_switch_time
            if time_since_switch < self.min_switch_interval:
                # Don't switch unless significantly better (>20% improvement)
                current_score = scores.get(self.current_strategy, 0)
                if best_score < current_score * 1.2:
                    best_strategy = self.current_strategy
                    best_score = current_score

        # Update tracking
        if best_strategy != self.current_strategy:
            logger.info(f"Strategy switch: {self.current_strategy} -> {best_strategy} "
                       f"(score: {best_score:.2f})")
            self.current_strategy = best_strategy
            self.last_switch_time = datetime.now()

        self.selection_history.append({
            "timestamp": datetime.now(),
            "selected": best_strategy,
            "score": best_score,
            "all_scores": scores.copy(),
            "market_condition": market_condition.copy()
        })

        return best_strategy, best_score, scores

    def select_ensemble(self, market_condition: Dict, top_n: int = 2) -> Dict[str, float]:
        """
        Select multiple strategies with capital allocation weights

        Returns:
            Dict of {strategy_name: weight}
        """
        _, _, scores = self.select_best_strategy(market_condition)

        # Filter strategies above threshold
        valid_scores = {k: v for k, v in scores.items() if v > 0}

        if not valid_scores:
            # Fallback to trend following
            return {"TrendFollowing": 1.0}

        # Normalize scores to weights
        total = sum(valid_scores.values())
        weights = {k: v / total for k, v in valid_scores.items()}

        # Keep only top N
        sorted_weights = dict(sorted(weights.items(), key=lambda x: x[1], reverse=True)[:top_n])

        # Re-normalize
        total = sum(sorted_weights.values())
        return {k: v / total for k, v in sorted_weights.items()}

    def _get_performance_multiplier(self, strategy_name: str) -> float:
        """Calculate performance multiplier based on recent trades"""
        history = self.performance_history.get(strategy_name, [])

        if len(history) < 5:
            return 1.0  # Neutral if insufficient data

        recent = history[-20:]  # Last 20 trades

        wins = sum(1 for t in recent if t.get("profit", 0) > 0)
        win_rate = wins / len(recent)

        # Multiplier: 0.7 to 1.3 based on win rate
        return 0.7 + (win_rate * 0.6)

    def record_trade_result(self, strategy_name: str, profit: float, market_condition: Dict):
        """Record trade result for performance tracking"""
        if strategy_name in self.performance_history:
            self.performance_history[strategy_name].append({
                "timestamp": datetime.now(),
                "profit": profit,
                "market_condition": market_condition
            })

    def get_strategy(self, name: str) -> Optional[SubStrategyBase]:
        return self.strategies.get(name)


class AdaptiveMultiStrategy(IStrategy):
    """
    Freqtrade strategy that automatically adapts to market conditions
    by selecting the best sub-strategy
    """

    INTERFACE_VERSION = 3

    # Hyperparameters
    buy_rsi = IntParameter(20, 40, default=30, space="buy")
    sell_rsi = IntParameter(60, 80, default=70, space="sell")
    atr_multiplier = DecimalParameter(1.5, 3.0, default=2.0, space="stoploss")

    # Strategy settings
    minimal_roi = {
        "0": 0.05,      # 5% ROI
        "30": 0.03,     # 3% after 30 min
        "60": 0.02,     # 2% after 60 min
        "120": 0.01,    # 1% after 120 min
        "240": 0.005    # 0.5% after 240 min
    }

    stoploss = -0.03  # 3% stoploss (will be adjusted dynamically)

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True

    # Order settings
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True
    }

    # Timeframe
    timeframe = '5m'
    process_only_new_candles = True

    # Position stacking
    position_adjustment_enable = True
    max_entry_position_adjustment = 2

    # Startup candles
    startup_candle_count = 200

    # Custom variables
    use_custom_stoploss = True

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        # Initialize market regime detector
        self.regime_detector = MarketRegimeDetector()

        # Initialize sub-strategies
        self.sub_strategies = [
            TrendFollowingSubStrategy(),
            GridSubStrategy(),
            MeanReversionSubStrategy()
        ]

        # Initialize strategy selector
        self.strategy_selector = StrategySelector(self.sub_strategies)

        # Cache for market condition
        self._market_condition: Optional[Dict] = None
        self._last_regime_check: Optional[datetime] = None
        self._regime_check_interval = timedelta(minutes=5)

        # Active strategy tracking
        self._active_strategy: Optional[str] = None
        self._strategy_weights: Dict[str, float] = {}

        logger.info("AdaptiveMultiStrategy initialized with sub-strategies: "
                   f"{[s.metadata.name for s in self.sub_strategies]}")

    def bot_start(self, **kwargs) -> None:
        """Called when bot starts"""
        logger.info("Adaptive Multi-Strategy Bot starting...")

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        """Called at the start of each bot loop"""
        # Refresh market regime periodically
        if (self._last_regime_check is None or
                current_time - self._last_regime_check > self._regime_check_interval):
            self._last_regime_check = current_time

    def informative_pairs(self) -> list:
        """Additional pairs for analysis"""
        return [
            ("BTC/USDT", self.timeframe),
            ("ETH/USDT", self.timeframe),
        ]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Populate all indicators needed by all sub-strategies"""

        # Market Regime Detection
        if len(dataframe) >= 200:
            regime = self.regime_detector.analyze(dataframe)
            self._market_condition = regime

            # Add regime info to dataframe
            dataframe['market_trend'] = regime['trend']
            dataframe['market_volatility'] = regime['volatility']
            dataframe['market_adx'] = regime['adx']

        # Populate indicators from all sub-strategies
        for strategy in self.sub_strategies:
            dataframe = strategy.populate_indicators(dataframe, metadata)

        # Common indicators
        # RSI
        if 'rsi' not in dataframe.columns:
            delta = dataframe['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            dataframe['rsi'] = 100 - (100 / (1 + rs))

        # ATR for dynamic stoploss
        high = dataframe['high']
        low = dataframe['low']
        close = dataframe['close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        dataframe['atr'] = tr.rolling(window=14).mean()
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close'] * 100

        # Volume analysis
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Generate entry signals based on selected strategy"""

        dataframe['enter_long'] = 0
        dataframe['enter_tag'] = ''

        if len(dataframe) < self.startup_candle_count:
            return dataframe

        # Get market condition
        market_condition = self._market_condition or self.regime_detector.analyze(dataframe)

        # Select best strategy
        strategy_name, confidence, scores = self.strategy_selector.select_best_strategy(market_condition)
        self._active_strategy = strategy_name
        self._strategy_weights = scores

        # Get the selected strategy
        strategy = self.strategy_selector.get_strategy(strategy_name)

        if strategy is None:
            return dataframe

        # Generate entry signal from selected strategy
        should_enter, enter_tag = strategy.generate_entry_signal(dataframe, market_condition)

        if should_enter and confidence > 0.4:
            # Set entry signal on last candle
            dataframe.loc[dataframe.index[-1], 'enter_long'] = 1
            dataframe.loc[dataframe.index[-1], 'enter_tag'] = f"{strategy_name}_{enter_tag}"

            logger.info(f"Entry signal: {strategy_name} | {enter_tag} | "
                       f"Confidence: {confidence:.2f} | "
                       f"Market: {market_condition['trend']}/{market_condition['volatility']}")

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Generate exit signals"""

        dataframe['exit_long'] = 0
        dataframe['exit_tag'] = ''

        if len(dataframe) < self.startup_candle_count:
            return dataframe

        market_condition = self._market_condition or self.regime_detector.analyze(dataframe)

        # Check all strategies for exit signals (not just active one)
        for strategy in self.sub_strategies:
            should_exit, exit_tag = strategy.generate_exit_signal(dataframe, market_condition)

            if should_exit:
                dataframe.loc[dataframe.index[-1], 'exit_long'] = 1
                dataframe.loc[dataframe.index[-1], 'exit_tag'] = f"{strategy.metadata.name}_{exit_tag}"
                break

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """Dynamic stoploss based on ATR"""

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if len(dataframe) < 1:
            return None

        current_atr_pct = dataframe['atr_pct'].iloc[-1]

        # Dynamic stoploss: 2x ATR
        dynamic_sl = -(current_atr_pct * float(self.atr_multiplier.value) / 100)

        # Minimum stoploss
        dynamic_sl = max(dynamic_sl, -0.05)  # Max 5% loss

        # Tighten stoploss as profit increases
        if current_profit > 0.02:
            dynamic_sl = max(dynamic_sl, -0.015)  # Tighten to 1.5%
        elif current_profit > 0.03:
            dynamic_sl = max(dynamic_sl, -0.01)  # Tighten to 1%

        return dynamic_sl

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """Custom exit logic"""

        # Exit if market regime changes dramatically
        if self._market_condition:
            trend = self._market_condition.get('trend', 'sideways')
            volatility = self._market_condition.get('volatility', 'normal')

            # Quick exit in extreme volatility with profit
            if volatility == 'extreme' and current_profit > 0.01:
                return "exit_extreme_volatility"

            # Exit long if strong downtrend develops
            if trade.is_open and current_profit < 0:
                if trend in ['strong_downtrend', 'downtrend']:
                    return "exit_trend_reversal"

        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time: datetime,
                           entry_tag: Optional[str], side: str, **kwargs) -> bool:
        """Confirm trade entry - additional validation"""

        # Check market condition
        if self._market_condition:
            volatility = self._market_condition.get('volatility', 'normal')

            # Don't enter in extreme volatility
            if volatility == 'extreme':
                logger.warning(f"Trade entry blocked for {pair}: extreme volatility")
                return False

            # Check confidence
            if self._active_strategy:
                score = self._strategy_weights.get(self._active_strategy, 0)
                if score < 0.3:
                    logger.warning(f"Trade entry blocked for {pair}: low confidence ({score:.2f})")
                    return False

        return True

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                          amount: float, rate: float, time_in_force: str,
                          exit_reason: str, current_time: datetime, **kwargs) -> bool:
        """Confirm trade exit"""

        # Record result for performance tracking
        if self._active_strategy and self._market_condition:
            self.strategy_selector.record_trade_result(
                self._active_strategy,
                trade.calc_profit_ratio(rate),
                self._market_condition
            )

        return True

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                side: str, **kwargs) -> float:
        """Set leverage - spot trading = 1.0"""
        return 1.0  # Spot trading, no leverage

    def custom_stake_amount(self, pair: str, current_time: datetime,
                           current_rate: float, proposed_stake: float,
                           min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str],
                           side: str, **kwargs) -> float:
        """Calculate stake amount based on strategy confidence"""

        if self._active_strategy and self._strategy_weights:
            confidence = self._strategy_weights.get(self._active_strategy, 0.5)

            # Adjust stake based on confidence
            # Low confidence (0.3-0.5): 50% of proposed
            # Medium confidence (0.5-0.7): 75% of proposed
            # High confidence (0.7+): 100% of proposed
            if confidence < 0.5:
                return proposed_stake * 0.5
            elif confidence < 0.7:
                return proposed_stake * 0.75

        return proposed_stake
