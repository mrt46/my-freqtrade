"""
Adaptive Multi-Strategy Trading System
"""

from .market_regime import (
    MarketRegimeDetector,
    TrendDetector,
    VolatilityAnalyzer,
    VolumeAnalyzer,
    TrendState,
    VolatilityState,
    VolumeState,
    MarketPhase
)

from .strategy_base import (
    SubStrategyBase,
    StrategyMetadata,
    TrendFollowingSubStrategy,
    GridSubStrategy,
    MeanReversionSubStrategy
)

from .adaptive_multi_strategy import (
    AdaptiveMultiStrategy,
    StrategySelector
)

__all__ = [
    # Main Strategy
    'AdaptiveMultiStrategy',
    'StrategySelector',

    # Market Regime
    'MarketRegimeDetector',
    'TrendDetector',
    'VolatilityAnalyzer',
    'VolumeAnalyzer',
    'TrendState',
    'VolatilityState',
    'VolumeState',
    'MarketPhase',

    # Strategy Base
    'SubStrategyBase',
    'StrategyMetadata',
    'TrendFollowingSubStrategy',
    'GridSubStrategy',
    'MeanReversionSubStrategy',
]
