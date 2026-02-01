"""
Base Strategy Class with Fitness Scoring for Multi-Strategy Selection
"""
import logging
from abc import abstractmethod
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class StrategyMetadata:
    """Strategy metadata container"""

    def __init__(
        self,
        name: str,
        description: str,
        ideal_trends: List[str],
        ideal_volatility: List[str],
        ideal_volume: List[str],
        min_fitness_threshold: float = 0.3,
        max_positions: int = 3,
        max_capital_pct: float = 0.3
    ):
        self.name = name
        self.description = description
        self.ideal_trends = ideal_trends
        self.ideal_volatility = ideal_volatility
        self.ideal_volume = ideal_volume
        self.min_fitness_threshold = min_fitness_threshold
        self.max_positions = max_positions
        self.max_capital_pct = max_capital_pct

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "ideal_conditions": {
                "trend": self.ideal_trends,
                "volatility": self.ideal_volatility,
                "volume": self.ideal_volume
            },
            "min_fitness_threshold": self.min_fitness_threshold,
            "max_positions": self.max_positions,
            "max_capital_pct": self.max_capital_pct
        }


class SubStrategyBase:
    """
    Base class for sub-strategies used in the multi-strategy system.
    Each sub-strategy implements its own entry/exit logic and fitness scoring.
    """

    def __init__(self):
        self._metadata: Optional[StrategyMetadata] = None
        self._last_fitness_score: float = 0.0
        self._trade_count: int = 0
        self._win_count: int = 0

    @property
    def metadata(self) -> StrategyMetadata:
        if self._metadata is None:
            self._metadata = self._create_metadata()
        return self._metadata

    @abstractmethod
    def _create_metadata(self) -> StrategyMetadata:
        """Create and return strategy metadata"""
        pass

    @abstractmethod
    def calculate_fitness_score(self, market_condition: Dict) -> float:
        """
        Calculate how suitable this strategy is for current market conditions.

        Args:
            market_condition: Dict from MarketRegimeDetector with keys:
                - trend: str
                - volatility: str
                - volume: str
                - trend_confidence: float
                - adx: float
                - rsi: float
                etc.

        Returns:
            float: Fitness score 0.0 (unsuitable) to 1.0 (perfect match)
        """
        pass

    @abstractmethod
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Add strategy-specific indicators"""
        pass

    @abstractmethod
    def generate_entry_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        """
        Generate entry signal based on current data and market condition.
        Returns: (should_enter, enter_tag)
        """
        pass

    @abstractmethod
    def generate_exit_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        """
        Generate exit signal.
        Returns: (should_exit, exit_tag)
        """
        pass

    def get_optimal_parameters(self, market_condition: Dict) -> Dict:
        """
        Get optimal parameters for current market condition.
        Override in subclasses for dynamic parameter adjustment.
        """
        return {}

    def update_performance(self, is_win: bool):
        """Update performance tracking"""
        self._trade_count += 1
        if is_win:
            self._win_count += 1

    @property
    def win_rate(self) -> float:
        if self._trade_count == 0:
            return 0.5  # Neutral assumption
        return self._win_count / self._trade_count


class TrendFollowingSubStrategy(SubStrategyBase):
    """Trend following strategy for trending markets"""

    def _create_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="TrendFollowing",
            description="EMA crossover + ADX trend following strategy",
            ideal_trends=["strong_uptrend", "uptrend", "strong_downtrend", "downtrend"],
            ideal_volatility=["normal", "high"],
            ideal_volume=["normal", "high", "spike"],
            min_fitness_threshold=0.25,
            max_positions=2,
            max_capital_pct=0.35
        )

    def calculate_fitness_score(self, market_condition: Dict) -> float:
        score = 0.0

        trend = market_condition.get("trend", "sideways")
        volatility = market_condition.get("volatility", "normal")
        volume = market_condition.get("volume", "normal")
        adx = market_condition.get("adx", 20)

        # Trend scoring (max 0.5)
        if trend in ["strong_uptrend", "strong_downtrend"]:
            score += 0.5
        elif trend in ["uptrend", "downtrend"]:
            score += 0.35
        elif trend in ["weak_uptrend", "weak_downtrend"]:
            score += 0.15

        # ADX scoring (max 0.25)
        if adx > 35:
            score += 0.25
        elif adx > 25:
            score += 0.2
        elif adx > 20:
            score += 0.1

        # Volume scoring (max 0.15)
        if volume in ["high", "spike"]:
            score += 0.15
        elif volume == "normal":
            score += 0.1

        # Volatility scoring (max 0.1)
        if volatility in ["normal", "high"]:
            score += 0.1

        self._last_fitness_score = min(score, 1.0)
        return self._last_fitness_score

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # EMAs
        dataframe['ema_20'] = dataframe['close'].ewm(span=20, adjust=False).mean()
        dataframe['ema_50'] = dataframe['close'].ewm(span=50, adjust=False).mean()
        dataframe['ema_200'] = dataframe['close'].ewm(span=200, adjust=False).mean()

        # MACD
        exp1 = dataframe['close'].ewm(span=12, adjust=False).mean()
        exp2 = dataframe['close'].ewm(span=26, adjust=False).mean()
        dataframe['macd'] = exp1 - exp2
        dataframe['macd_signal'] = dataframe['macd'].ewm(span=9, adjust=False).mean()
        dataframe['macd_hist'] = dataframe['macd'] - dataframe['macd_signal']

        # RSI
        delta = dataframe['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        dataframe['rsi'] = 100 - (100 / (1 + rs))

        return dataframe

    def generate_entry_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        if len(dataframe) < 2:
            return False, None

        current = dataframe.iloc[-1]
        prev = dataframe.iloc[-2]

        trend = market_condition.get("trend", "sideways")
        adx = market_condition.get("adx", 20)

        # Long entry conditions (relaxed - any 2 of 4 conditions)
        if trend in ["uptrend", "strong_uptrend", "weak_uptrend"]:
            # EMA crossover
            ema_cross_up = (prev['ema_20'] <= prev['ema_50']) and (current['ema_20'] > current['ema_50'])
            # Price above EMA 200
            above_ema200 = current['close'] > current['ema_200']
            # MACD confirmation
            macd_positive = current['macd'] > current['macd_signal']
            # RSI not overbought
            rsi_ok = current['rsi'] < 75  # Relaxed from 70

            # Count matching conditions
            conditions_met = sum([ema_cross_up, above_ema200, macd_positive, rsi_ok])
            
            # Entry if at least 2 conditions met and ADX shows trend
            if conditions_met >= 2 and adx > 15:  # Relaxed from 20
                return True, "trend_long_relaxed"

            # Strong trend continuation (relaxed)
            if (current['close'] > current['ema_20'] > current['ema_50']
                    and macd_positive and rsi_ok and adx > 20):  # Relaxed from 25
                return True, "trend_long_continuation"

        # Sideways market - allow entries on mean reversion signals
        elif trend == "sideways" and adx < 25:
            # Allow entries when price is near support and RSI oversold
            if current['rsi'] < 35 and current['close'] < current['ema_50']:
                return True, "trend_sideways_buy"

        return False, None

    def generate_exit_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        if len(dataframe) < 2:
            return False, None

        current = dataframe.iloc[-1]
        prev = dataframe.iloc[-2]

        # Exit on EMA cross down
        ema_cross_down = (prev['ema_20'] >= prev['ema_50']) and (current['ema_20'] < current['ema_50'])
        if ema_cross_down:
            return True, "trend_exit_ema_cross"

        # Exit on RSI overbought
        if current['rsi'] > 75:
            return True, "trend_exit_rsi_overbought"

        # Exit on MACD reversal
        macd_reversal = (prev['macd'] >= prev['macd_signal']) and (current['macd'] < current['macd_signal'])
        if macd_reversal and current['rsi'] > 60:
            return True, "trend_exit_macd_reversal"

        return False, None


class GridSubStrategy(SubStrategyBase):
    """Grid trading strategy for sideways markets"""

    def __init__(self, grid_levels: int = 10, grid_spacing_pct: float = 0.5):
        super().__init__()
        self.grid_levels = grid_levels
        self.grid_spacing_pct = grid_spacing_pct

    def _create_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="Grid",
            description="Grid trading for sideways/ranging markets",
            ideal_trends=["sideways", "weak_uptrend", "weak_downtrend"],
            ideal_volatility=["low", "normal"],
            ideal_volume=["low", "normal"],
            min_fitness_threshold=0.25,
            max_positions=5,
            max_capital_pct=0.4
        )

    def calculate_fitness_score(self, market_condition: Dict) -> float:
        score = 0.0

        trend = market_condition.get("trend", "sideways")
        volatility = market_condition.get("volatility", "normal")
        adx = market_condition.get("adx", 20)

        # Sideways market scoring (max 0.45)
        if trend == "sideways":
            score += 0.45
        elif trend in ["weak_uptrend", "weak_downtrend"]:
            score += 0.25

        # Low ADX scoring (max 0.25)
        if adx < 15:
            score += 0.25
        elif adx < 20:
            score += 0.2
        elif adx < 25:
            score += 0.1

        # Low volatility scoring (max 0.2)
        if volatility == "low":
            score += 0.2
        elif volatility == "normal":
            score += 0.15

        # Penalty for trending markets
        if trend in ["strong_uptrend", "strong_downtrend"]:
            score *= 0.3

        # Penalty for extreme volatility
        if volatility == "extreme":
            score *= 0.4

        self._last_fitness_score = min(score, 1.0)
        return self._last_fitness_score

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Bollinger Bands for range detection
        dataframe['bb_sma'] = dataframe['close'].rolling(window=20).mean()
        dataframe['bb_std'] = dataframe['close'].rolling(window=20).std()
        dataframe['bb_upper'] = dataframe['bb_sma'] + (dataframe['bb_std'] * 2)
        dataframe['bb_lower'] = dataframe['bb_sma'] - (dataframe['bb_std'] * 2)
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_sma'] * 100

        # ATR for grid spacing
        high = dataframe['high']
        low = dataframe['low']
        close = dataframe['close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        dataframe['atr'] = tr.rolling(window=14).mean()

        # Support/Resistance levels (simplified)
        dataframe['recent_high'] = dataframe['high'].rolling(window=20).max()
        dataframe['recent_low'] = dataframe['low'].rolling(window=20).min()

        return dataframe

    def generate_entry_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        if len(dataframe) < 2:
            return False, None

        current = dataframe.iloc[-1]

        trend = market_condition.get("trend", "sideways")
        if trend not in ["sideways", "weak_uptrend", "weak_downtrend"]:
            return False, None

        # Entry near lower Bollinger Band (relaxed)
        price_near_lower = current['close'] < current['bb_lower'] * 1.03

        # Entry near recent low (relaxed)
        price_near_support = current['close'] < current['recent_low'] * 1.05

        # Entry when price is in lower half of BB range
        bb_mid = (current['bb_upper'] + current['bb_lower']) / 2
        price_below_mid = current['close'] < bb_mid

        if price_near_lower or price_near_support or (price_below_mid and current['rsi'] < 50):
            return True, "grid_buy_support"

        return False, None

    def generate_exit_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        if len(dataframe) < 2:
            return False, None

        current = dataframe.iloc[-1]

        # Exit near upper Bollinger Band
        price_near_upper = current['close'] > current['bb_upper'] * 0.99

        # Exit near recent high
        price_near_resistance = current['close'] > current['recent_high'] * 0.98

        if price_near_upper or price_near_resistance:
            return True, "grid_sell_resistance"

        return False, None


class MeanReversionSubStrategy(SubStrategyBase):
    """Mean reversion strategy using RSI and Bollinger Bands"""

    def _create_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="MeanReversion",
            description="RSI + Bollinger Band mean reversion strategy",
            ideal_trends=["sideways", "weak_uptrend", "weak_downtrend"],
            ideal_volatility=["normal", "low"],
            ideal_volume=["normal", "low"],
            min_fitness_threshold=0.25,
            max_positions=3,
            max_capital_pct=0.25
        )

    def calculate_fitness_score(self, market_condition: Dict) -> float:
        score = 0.0

        trend = market_condition.get("trend", "sideways")
        volatility = market_condition.get("volatility", "normal")
        rsi = market_condition.get("rsi", 50)

        # Sideways market (max 0.35)
        if trend == "sideways":
            score += 0.35
        elif trend in ["weak_uptrend", "weak_downtrend"]:
            score += 0.2

        # RSI at extremes (max 0.35)
        if rsi < 25 or rsi > 75:
            score += 0.35
        elif rsi < 30 or rsi > 70:
            score += 0.25
        elif rsi < 35 or rsi > 65:
            score += 0.1

        # Normal volatility (max 0.2)
        if volatility in ["normal", "low"]:
            score += 0.2

        # Penalty for strong trends
        if trend in ["strong_uptrend", "strong_downtrend"]:
            score *= 0.3

        self._last_fitness_score = min(score, 1.0)
        return self._last_fitness_score

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # RSI
        delta = dataframe['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        dataframe['rsi'] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        dataframe['bb_sma'] = dataframe['close'].rolling(window=20).mean()
        dataframe['bb_std'] = dataframe['close'].rolling(window=20).std()
        dataframe['bb_upper'] = dataframe['bb_sma'] + (dataframe['bb_std'] * 2)
        dataframe['bb_lower'] = dataframe['bb_sma'] - (dataframe['bb_std'] * 2)

        # Z-Score
        dataframe['zscore'] = (dataframe['close'] - dataframe['bb_sma']) / dataframe['bb_std']

        # Stochastic
        low_14 = dataframe['low'].rolling(window=14).min()
        high_14 = dataframe['high'].rolling(window=14).max()
        dataframe['stoch_k'] = 100 * (dataframe['close'] - low_14) / (high_14 - low_14)
        dataframe['stoch_d'] = dataframe['stoch_k'].rolling(window=3).mean()

        return dataframe

    def generate_entry_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        if len(dataframe) < 2:
            return False, None

        current = dataframe.iloc[-1]

        # Oversold conditions (relaxed)
        rsi_oversold = current['rsi'] < 40  # Relaxed from 30
        price_below_lower_bb = current['close'] < current['bb_lower'] * 1.02  # Relaxed
        zscore_extreme = current['zscore'] < -1.0  # Relaxed from -2
        stoch_oversold = current['stoch_k'] < 30  # Relaxed from 20

        # Entry signal (any 1 condition is enough)
        oversold_count = sum([rsi_oversold, price_below_lower_bb, zscore_extreme, stoch_oversold])

        if oversold_count >= 1:  # Relaxed from 2
            return True, f"meanrev_oversold_{oversold_count}"

        return False, None

    def generate_exit_signal(self, dataframe: pd.DataFrame, market_condition: Dict) -> Tuple[bool, Optional[str]]:
        if len(dataframe) < 2:
            return False, None

        current = dataframe.iloc[-1]

        # Exit at mean (middle band)
        price_at_mean = abs(current['close'] - current['bb_sma']) / current['bb_sma'] < 0.005

        # Exit on RSI overbought
        rsi_overbought = current['rsi'] > 70

        # Exit on upper band touch
        price_at_upper = current['close'] > current['bb_upper'] * 0.99

        if price_at_mean:
            return True, "meanrev_exit_mean"
        if rsi_overbought:
            return True, "meanrev_exit_rsi"
        if price_at_upper:
            return True, "meanrev_exit_upper_band"

        return False, None
