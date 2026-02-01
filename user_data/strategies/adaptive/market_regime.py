"""
Market Regime Detection System
Detects current market conditions: trend, volatility, volume, market phase
"""
import logging
from typing import Dict, Tuple, Optional
from enum import Enum
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TrendState(Enum):
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    WEAK_UPTREND = "weak_uptrend"
    SIDEWAYS = "sideways"
    WEAK_DOWNTREND = "weak_downtrend"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class VolatilityState(Enum):
    EXTREME = "extreme"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class VolumeState(Enum):
    SPIKE = "spike"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class MarketPhase(Enum):
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"


class TrendDetector:
    """Detects trend direction and strength using ADX and EMAs"""

    def __init__(self, adx_period: int = 14, ema_periods: list = None):
        self.adx_period = adx_period
        self.ema_periods = ema_periods or [20, 50, 200]

    def calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average Directional Index"""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=self.adx_period).mean()

        plus_di = 100 * (plus_dm.rolling(window=self.adx_period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=self.adx_period).mean() / atr)

        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.rolling(window=self.adx_period).mean()

        return adx

    def calculate_ema_slopes(self, df: pd.DataFrame) -> Dict[int, float]:
        """Calculate EMA slopes for trend direction"""
        slopes = {}
        for period in self.ema_periods:
            ema = df['close'].ewm(span=period, adjust=False).mean()
            # Slope over last 5 candles, normalized
            if len(ema) >= 5:
                slope = (ema.iloc[-1] - ema.iloc[-5]) / ema.iloc[-5] * 100
                slopes[period] = slope
            else:
                slopes[period] = 0.0
        return slopes

    def detect(self, df: pd.DataFrame) -> Tuple[TrendState, float, Dict]:
        """
        Detect trend state
        Returns: (trend_state, confidence, details)
        """
        if len(df) < 200:
            return TrendState.SIDEWAYS, 0.5, {"reason": "insufficient_data"}

        adx = self.calculate_adx(df)
        current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20

        slopes = self.calculate_ema_slopes(df)

        # Price position relative to EMAs
        current_price = df['close'].iloc[-1]
        ema_20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
        ema_50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        ema_200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]

        above_emas = sum([
            current_price > ema_20,
            current_price > ema_50,
            current_price > ema_200
        ])

        # Determine trend
        avg_slope = np.mean(list(slopes.values()))

        if current_adx > 40 and avg_slope > 1:
            trend = TrendState.STRONG_UPTREND
            confidence = min(0.95, 0.7 + current_adx / 100)
        elif current_adx > 25 and avg_slope > 0.5:
            trend = TrendState.UPTREND
            confidence = 0.75
        elif current_adx > 20 and avg_slope > 0:
            trend = TrendState.WEAK_UPTREND
            confidence = 0.6
        elif current_adx > 40 and avg_slope < -1:
            trend = TrendState.STRONG_DOWNTREND
            confidence = min(0.95, 0.7 + current_adx / 100)
        elif current_adx > 25 and avg_slope < -0.5:
            trend = TrendState.DOWNTREND
            confidence = 0.75
        elif current_adx > 20 and avg_slope < 0:
            trend = TrendState.WEAK_DOWNTREND
            confidence = 0.6
        else:
            trend = TrendState.SIDEWAYS
            confidence = 0.8 if current_adx < 20 else 0.6

        details = {
            "adx": current_adx,
            "slopes": slopes,
            "avg_slope": avg_slope,
            "above_emas": above_emas,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_200": ema_200
        }

        return trend, confidence, details


class VolatilityAnalyzer:
    """Analyzes market volatility using ATR and Bollinger Bands"""

    def __init__(self, atr_period: int = 14, bb_period: int = 20, lookback_days: int = 30):
        self.atr_period = atr_period
        self.bb_period = bb_period
        self.lookback_days = lookback_days

    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return tr.rolling(window=self.atr_period).mean()

    def calculate_bb_width(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Bollinger Band width"""
        sma = df['close'].rolling(window=self.bb_period).mean()
        std = df['close'].rolling(window=self.bb_period).std()

        upper = sma + (std * 2)
        lower = sma - (std * 2)

        width = (upper - lower) / sma * 100
        return width

    def detect(self, df: pd.DataFrame) -> Tuple[VolatilityState, float, Dict]:
        """
        Detect volatility state
        Returns: (volatility_state, percentile, details)
        """
        atr = self.calculate_atr(df)
        bb_width = self.calculate_bb_width(df)

        current_atr = atr.iloc[-1]
        current_bb_width = bb_width.iloc[-1]

        # Calculate percentile over lookback period
        lookback_candles = min(self.lookback_days * 24, len(atr) - 1)  # Assuming hourly
        if lookback_candles > 0:
            atr_percentile = (atr.iloc[-lookback_candles:] < current_atr).sum() / lookback_candles * 100
        else:
            atr_percentile = 50

        # Determine volatility state
        if atr_percentile > 95:
            state = VolatilityState.EXTREME
        elif atr_percentile > 75:
            state = VolatilityState.HIGH
        elif atr_percentile > 25:
            state = VolatilityState.NORMAL
        else:
            state = VolatilityState.LOW

        # ATR as percentage of price
        atr_pct = (current_atr / df['close'].iloc[-1]) * 100

        details = {
            "atr": current_atr,
            "atr_pct": atr_pct,
            "bb_width": current_bb_width,
            "percentile": atr_percentile
        }

        return state, atr_percentile, details


class VolumeAnalyzer:
    """Analyzes trading volume patterns"""

    def __init__(self, ma_period: int = 20, spike_threshold: float = 2.5):
        self.ma_period = ma_period
        self.spike_threshold = spike_threshold

    def detect(self, df: pd.DataFrame) -> Tuple[VolumeState, float, Dict]:
        """
        Detect volume state
        Returns: (volume_state, volume_ratio, details)
        """
        if 'volume' not in df.columns:
            return VolumeState.NORMAL, 1.0, {"reason": "no_volume_data"}

        volume = df['volume']
        volume_ma = volume.rolling(window=self.ma_period).mean()

        current_volume = volume.iloc[-1]
        current_ma = volume_ma.iloc[-1]

        volume_ratio = current_volume / current_ma if current_ma > 0 else 1.0

        # Volume trend (increasing or decreasing)
        volume_trend = (volume.iloc[-5:].mean() / volume.iloc[-20:-5].mean()
                       if len(volume) >= 20 else 1.0)

        # Determine state
        if volume_ratio > self.spike_threshold:
            state = VolumeState.SPIKE
        elif volume_ratio > 1.5:
            state = VolumeState.HIGH
        elif volume_ratio > 0.7:
            state = VolumeState.NORMAL
        else:
            state = VolumeState.LOW

        details = {
            "current_volume": current_volume,
            "volume_ma": current_ma,
            "volume_ratio": volume_ratio,
            "volume_trend": volume_trend
        }

        return state, volume_ratio, details


class MarketPhaseDetector:
    """Detects Wyckoff market phases"""

    def detect(self, df: pd.DataFrame, trend: TrendState, volatility: VolatilityState,
               volume: VolumeState) -> Tuple[MarketPhase, float]:
        """
        Detect market phase based on combined indicators
        Returns: (phase, confidence)
        """
        # Simplified Wyckoff detection
        if trend in [TrendState.SIDEWAYS] and volume == VolumeState.LOW:
            return MarketPhase.ACCUMULATION, 0.7
        elif trend in [TrendState.UPTREND, TrendState.STRONG_UPTREND]:
            if volume in [VolumeState.HIGH, VolumeState.SPIKE]:
                return MarketPhase.MARKUP, 0.8
            return MarketPhase.MARKUP, 0.6
        elif trend == TrendState.SIDEWAYS and volatility == VolatilityState.HIGH:
            return MarketPhase.DISTRIBUTION, 0.65
        elif trend in [TrendState.DOWNTREND, TrendState.STRONG_DOWNTREND]:
            return MarketPhase.MARKDOWN, 0.75
        else:
            return MarketPhase.ACCUMULATION, 0.5


class MarketRegimeDetector:
    """
    Main class that combines all detectors to determine market regime
    """

    def __init__(self):
        self.trend_detector = TrendDetector()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.volume_analyzer = VolumeAnalyzer()
        self.phase_detector = MarketPhaseDetector()

    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Comprehensive market regime analysis

        Returns dict with:
        - trend: str (e.g., "strong_uptrend")
        - trend_confidence: float (0-1)
        - volatility: str (e.g., "high")
        - volatility_percentile: float
        - volume: str (e.g., "spike")
        - volume_ratio: float
        - market_phase: str
        - overall_confidence: float
        - details: dict with all raw metrics
        """
        # Detect all components
        trend, trend_conf, trend_details = self.trend_detector.detect(df)
        vol_state, vol_pct, vol_details = self.volatility_analyzer.detect(df)
        volume_state, volume_ratio, volume_details = self.volume_analyzer.detect(df)
        phase, phase_conf = self.phase_detector.detect(df, trend, vol_state, volume_state)

        # Overall confidence
        overall_confidence = (trend_conf + phase_conf) / 2

        # RSI for additional context
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

        # Compile result
        result = {
            "trend": trend.value,
            "trend_confidence": trend_conf,
            "volatility": vol_state.value,
            "volatility_percentile": vol_pct,
            "volume": volume_state.value,
            "volume_ratio": volume_ratio,
            "market_phase": phase.value,
            "phase_confidence": phase_conf,
            "overall_confidence": overall_confidence,
            "rsi": current_rsi,
            "adx": trend_details.get("adx", 0),
            "atr_pct": vol_details.get("atr_pct", 0),
            "details": {
                "trend": trend_details,
                "volatility": vol_details,
                "volume": volume_details
            }
        }

        logger.info(f"Market Regime: {trend.value} | Vol: {vol_state.value} | "
                   f"Phase: {phase.value} | Conf: {overall_confidence:.2f}")

        return result

    def get_strategy_recommendation(self, regime: Dict) -> Dict[str, float]:
        """
        Get strategy fitness recommendations based on regime
        Returns dict of strategy_name -> recommended_weight
        """
        trend = regime["trend"]
        volatility = regime["volatility"]
        volume = regime["volume"]
        adx = regime.get("adx", 20)

        recommendations = {
            "grid": 0.0,
            "trend_following": 0.0,
            "mean_reversion": 0.0,
            "scalping": 0.0
        }

        # Grid Strategy - best in sideways, low-normal volatility
        if trend == "sideways" and volatility in ["low", "normal"]:
            recommendations["grid"] = 0.9
        elif trend in ["weak_uptrend", "weak_downtrend"] and volatility == "low":
            recommendations["grid"] = 0.6

        # Trend Following - best in strong trends
        if trend in ["strong_uptrend", "strong_downtrend"] and adx > 25:
            recommendations["trend_following"] = 0.9
        elif trend in ["uptrend", "downtrend"]:
            recommendations["trend_following"] = 0.7

        # Mean Reversion - best in sideways with RSI extremes
        rsi = regime.get("rsi", 50)
        if trend == "sideways" and (rsi < 30 or rsi > 70):
            recommendations["mean_reversion"] = 0.85
        elif volatility in ["normal", "low"] and trend == "sideways":
            recommendations["mean_reversion"] = 0.6

        # Scalping - best in high volatility
        if volatility in ["high", "extreme"] and volume in ["high", "spike"]:
            recommendations["scalping"] = 0.7

        return recommendations
