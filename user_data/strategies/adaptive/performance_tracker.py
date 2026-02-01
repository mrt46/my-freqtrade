"""
Performance Tracker - Records and analyzes strategy performance
Provides data for adaptive weight adjustment
"""
import logging
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Single trade result"""
    timestamp: datetime
    strategy: str
    pair: str
    side: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    profit_ratio: float
    profit_abs: float
    hold_duration_seconds: int
    market_condition: Dict
    entry_reason: str
    exit_reason: str

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "strategy": self.strategy,
            "pair": self.pair,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "profit_ratio": self.profit_ratio,
            "profit_abs": self.profit_abs,
            "hold_duration_seconds": self.hold_duration_seconds,
            "market_condition": self.market_condition,
            "entry_reason": self.entry_reason,
            "exit_reason": self.exit_reason
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeResult':
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class StrategyPerformanceStats:
    """Aggregated performance statistics for a strategy"""
    strategy_name: str
    period_start: datetime
    period_end: datetime
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    avg_hold_duration: float = 0.0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.5
        return self.winning_trades / self.total_trades

    @property
    def profit_factor(self) -> float:
        if self.total_loss == 0:
            return 10.0 if self.total_profit > 0 else 1.0
        return abs(self.total_profit / self.total_loss)

    @property
    def avg_profit(self) -> float:
        if self.winning_trades == 0:
            return 0.0
        return self.total_profit / self.winning_trades

    @property
    def avg_loss(self) -> float:
        if self.losing_trades == 0:
            return 0.0
        return self.total_loss / self.losing_trades

    @property
    def expectancy(self) -> float:
        """Expected profit per trade"""
        return (self.win_rate * self.avg_profit) - ((1 - self.win_rate) * abs(self.avg_loss))

    @property
    def sharpe_approximation(self) -> float:
        """Simplified Sharpe ratio approximation"""
        if self.total_trades < 5:
            return 0.0
        avg_return = (self.total_profit + self.total_loss) / self.total_trades
        # Rough estimate of std dev
        if self.total_trades == 0:
            return 0.0
        return avg_return / max(0.01, abs(self.avg_loss))


class PerformanceTracker:
    """
    Tracks and analyzes trading performance by strategy
    """

    def __init__(self, data_dir: str = "user_data/performance"):
        """
        Args:
            data_dir: Directory to store performance data
        """
        self.data_dir = data_dir
        self.trades: List[TradeResult] = []
        self.daily_stats: Dict[str, Dict[str, StrategyPerformanceStats]] = defaultdict(dict)

        os.makedirs(data_dir, exist_ok=True)
        self._load_trades()

        logger.info(f"Performance Tracker initialized with {len(self.trades)} historical trades")

    def record_trade(
        self,
        strategy: str,
        pair: str,
        side: str,
        entry_price: float,
        exit_price: float,
        profit_ratio: float,
        profit_abs: float,
        hold_duration_seconds: int,
        market_condition: Dict,
        entry_reason: str,
        exit_reason: str
    ):
        """Record a completed trade"""
        trade = TradeResult(
            timestamp=datetime.now(),
            strategy=strategy,
            pair=pair,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            profit_ratio=profit_ratio,
            profit_abs=profit_abs,
            hold_duration_seconds=hold_duration_seconds,
            market_condition=market_condition,
            entry_reason=entry_reason,
            exit_reason=exit_reason
        )

        self.trades.append(trade)
        self._save_trade(trade)

        logger.info(f"Trade recorded: {strategy} | {pair} | "
                   f"PnL: {profit_ratio*100:.2f}%")

    def get_strategy_stats(
        self,
        strategy: str,
        lookback_hours: int = 168  # 7 days default
    ) -> StrategyPerformanceStats:
        """Get performance stats for a strategy over lookback period"""
        cutoff = datetime.now() - timedelta(hours=lookback_hours)

        relevant_trades = [
            t for t in self.trades
            if t.strategy == strategy and t.timestamp > cutoff
        ]

        stats = StrategyPerformanceStats(
            strategy_name=strategy,
            period_start=cutoff,
            period_end=datetime.now()
        )

        for trade in relevant_trades:
            stats.total_trades += 1
            if trade.profit_ratio > 0:
                stats.winning_trades += 1
                stats.total_profit += trade.profit_ratio
                stats.max_win = max(stats.max_win, trade.profit_ratio)
            else:
                stats.losing_trades += 1
                stats.total_loss += trade.profit_ratio
                stats.max_loss = min(stats.max_loss, trade.profit_ratio)

        if relevant_trades:
            stats.avg_hold_duration = np.mean([t.hold_duration_seconds for t in relevant_trades])

        return stats

    def get_all_strategy_stats(self, lookback_hours: int = 168) -> Dict[str, StrategyPerformanceStats]:
        """Get stats for all strategies"""
        strategies = set(t.strategy for t in self.trades)
        return {
            strategy: self.get_strategy_stats(strategy, lookback_hours)
            for strategy in strategies
        }

    def get_best_strategy_for_condition(
        self,
        market_condition: Dict,
        lookback_hours: int = 168
    ) -> Optional[Tuple[str, float]]:
        """Find best performing strategy for given market condition"""
        cutoff = datetime.now() - timedelta(hours=lookback_hours)

        # Group trades by strategy for matching conditions
        strategy_performance: Dict[str, List[float]] = defaultdict(list)

        for trade in self.trades:
            if trade.timestamp < cutoff:
                continue

            # Check if market conditions match
            if self._conditions_match(trade.market_condition, market_condition):
                strategy_performance[trade.strategy].append(trade.profit_ratio)

        if not strategy_performance:
            return None

        # Calculate average profit for each strategy
        avg_profits = {
            strategy: np.mean(profits)
            for strategy, profits in strategy_performance.items()
            if len(profits) >= 3  # Minimum trades for significance
        }

        if not avg_profits:
            return None

        best = max(avg_profits.items(), key=lambda x: x[1])
        return best

    def _conditions_match(self, stored: Dict, query: Dict, tolerance: float = 0.2) -> bool:
        """Check if stored market condition matches query"""
        if not stored or not query:
            return False

        # Check trend match
        if stored.get("trend") != query.get("trend"):
            # Allow adjacent trends
            trend_order = ["strong_downtrend", "downtrend", "weak_downtrend",
                         "sideways", "weak_uptrend", "uptrend", "strong_uptrend"]
            try:
                idx1 = trend_order.index(stored.get("trend", "sideways"))
                idx2 = trend_order.index(query.get("trend", "sideways"))
                if abs(idx1 - idx2) > 1:
                    return False
            except ValueError:
                return False

        # Check volatility match
        if stored.get("volatility") != query.get("volatility"):
            vol_order = ["low", "normal", "high", "extreme"]
            try:
                idx1 = vol_order.index(stored.get("volatility", "normal"))
                idx2 = vol_order.index(query.get("volatility", "normal"))
                if abs(idx1 - idx2) > 1:
                    return False
            except ValueError:
                return False

        return True

    def get_performance_comparison(self, lookback_hours: int = 168) -> str:
        """Generate performance comparison report"""
        stats = self.get_all_strategy_stats(lookback_hours)

        if not stats:
            return "No performance data available"

        lines = [
            f"Performance Report (Last {lookback_hours}h)",
            "=" * 60,
            f"{'Strategy':<20} {'Trades':>8} {'Win%':>8} {'PF':>8} {'Expect':>10}",
            "-" * 60
        ]

        for name, s in sorted(stats.items(), key=lambda x: -x[1].profit_factor):
            lines.append(
                f"{name:<20} {s.total_trades:>8} "
                f"{s.win_rate*100:>7.1f}% {s.profit_factor:>7.2f} "
                f"{s.expectancy*100:>9.2f}%"
            )

        return "\n".join(lines)

    def _save_trade(self, trade: TradeResult):
        """Save trade to file"""
        date_str = trade.timestamp.strftime("%Y-%m-%d")
        filepath = os.path.join(self.data_dir, f"trades_{date_str}.json")

        trades_today = []
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                trades_today = json.load(f)

        trades_today.append(trade.to_dict())

        with open(filepath, 'w') as f:
            json.dump(trades_today, f, indent=2)

    def _load_trades(self):
        """Load all historical trades"""
        if not os.path.exists(self.data_dir):
            return

        for filename in os.listdir(self.data_dir):
            if filename.startswith("trades_") and filename.endswith(".json"):
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    for trade_data in data:
                        self.trades.append(TradeResult.from_dict(trade_data))
                except Exception as e:
                    logger.error(f"Failed to load trades from {filename}: {e}")

        # Sort by timestamp
        self.trades.sort(key=lambda t: t.timestamp)


class AdaptiveWeightManager:
    """
    Manages dynamic weights for strategy selection based on performance
    """

    def __init__(
        self,
        strategy_names: List[str],
        performance_tracker: PerformanceTracker,
        adjustment_interval_hours: int = 24,
        min_weight: float = 0.1,
        max_weight: float = 2.0
    ):
        """
        Args:
            strategy_names: List of available strategies
            performance_tracker: Performance tracker instance
            adjustment_interval_hours: How often to adjust weights
            min_weight: Minimum weight multiplier
            max_weight: Maximum weight multiplier
        """
        self.strategy_names = strategy_names
        self.tracker = performance_tracker
        self.adjustment_interval = timedelta(hours=adjustment_interval_hours)
        self.min_weight = min_weight
        self.max_weight = max_weight

        self.weights: Dict[str, float] = {name: 1.0 for name in strategy_names}
        self.last_adjustment: Optional[datetime] = None
        self.weight_history: List[Dict] = []

    def get_weight(self, strategy: str) -> float:
        """Get current weight for a strategy"""
        return self.weights.get(strategy, 1.0)

    def apply_weight(self, strategy: str, fitness_score: float) -> float:
        """Apply weight to fitness score"""
        return fitness_score * self.get_weight(strategy)

    def should_adjust(self) -> bool:
        """Check if it's time to adjust weights"""
        if self.last_adjustment is None:
            return True
        return datetime.now() - self.last_adjustment > self.adjustment_interval

    def adjust_weights(self, lookback_hours: int = 168) -> Dict[str, float]:
        """
        Adjust weights based on recent performance
        Returns the new weights
        """
        stats = self.tracker.get_all_strategy_stats(lookback_hours)

        if not stats:
            logger.info("No performance data for weight adjustment")
            return self.weights

        # Calculate performance scores
        scores = {}
        for name in self.strategy_names:
            if name in stats:
                s = stats[name]
                if s.total_trades >= 5:
                    # Score based on profit factor and win rate
                    score = (s.profit_factor * 0.5) + (s.win_rate * 0.3) + (min(s.expectancy * 10, 0.2))
                    scores[name] = score
                else:
                    scores[name] = 1.0  # Neutral for insufficient data
            else:
                scores[name] = 1.0

        # Normalize scores to weights
        avg_score = np.mean(list(scores.values()))
        if avg_score > 0:
            for name in self.strategy_names:
                raw_weight = scores.get(name, 1.0) / avg_score
                self.weights[name] = max(self.min_weight, min(self.max_weight, raw_weight))

        # Record history
        self.weight_history.append({
            "timestamp": datetime.now().isoformat(),
            "weights": self.weights.copy(),
            "scores": scores
        })

        self.last_adjustment = datetime.now()

        logger.info(f"Weights adjusted: {self.weights}")
        return self.weights

    def detect_underperformers(self, min_profit_factor: float = 1.2) -> List[str]:
        """Identify strategies performing below threshold"""
        stats = self.tracker.get_all_strategy_stats(lookback_hours=72)
        underperformers = []

        for name, s in stats.items():
            if s.total_trades >= 10 and s.profit_factor < min_profit_factor:
                underperformers.append(name)

        return underperformers

    def should_pause_strategy(self, strategy: str) -> Tuple[bool, str]:
        """
        Determine if a strategy should be paused

        Returns:
            (should_pause, reason)
        """
        stats = self.tracker.get_strategy_stats(strategy, lookback_hours=72)

        # Pause conditions
        if stats.total_trades >= 10:
            if stats.profit_factor < 0.8:
                return True, f"Low profit factor: {stats.profit_factor:.2f}"
            if stats.win_rate < 0.35:
                return True, f"Low win rate: {stats.win_rate*100:.1f}%"
            if stats.max_loss < -0.10:
                return True, f"Large single loss: {stats.max_loss*100:.1f}%"

        return False, "OK"

    def get_weight_report(self) -> str:
        """Generate weight report"""
        lines = [
            "Strategy Weights",
            "=" * 40,
            f"{'Strategy':<20} {'Weight':>10} {'Status':>10}"
        ]

        for name, weight in sorted(self.weights.items(), key=lambda x: -x[1]):
            should_pause, reason = self.should_pause_strategy(name)
            status = "PAUSED" if should_pause else "Active"
            lines.append(f"{name:<20} {weight:>10.2f} {status:>10}")

        return "\n".join(lines)
