"""
Adaptive Multi-Strategy Trading System

This module provides an adaptive trading system that automatically
selects the best strategy based on market conditions.
"""

# Core modules (no freqtrade dependency)
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

from .risk_manager import (
    RiskManager,
    PortfolioRiskConfig,
    StrategyRiskConfig,
    CircuitBreaker,
    RiskLevel
)

# Freqtrade-dependent modules (lazy import to avoid dependency issues during testing)
def get_adaptive_strategy():
    """Lazy import for AdaptiveMultiStrategy (requires freqtrade)"""
    from .adaptive_multi_strategy import AdaptiveMultiStrategy
    return AdaptiveMultiStrategy

def get_strategy_selector():
    """Lazy import for StrategySelector (requires freqtrade)"""
    from .adaptive_multi_strategy import StrategySelector
    return StrategySelector

__all__ = [
    # Lazy loaders for freqtrade-dependent classes
    'get_adaptive_strategy',
    'get_strategy_selector',

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

    # Risk Management
    'RiskManager',
    'PortfolioRiskConfig',
    'StrategyRiskConfig',
    'CircuitBreaker',
    'RiskLevel',
]
