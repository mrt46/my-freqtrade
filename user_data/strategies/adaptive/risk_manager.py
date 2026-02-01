"""
Multi-Strategy Risk Management System
Handles position sizing, drawdown protection, and strategy-specific limits
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class StrategyRiskConfig:
    """Risk configuration for a specific strategy"""
    name: str
    max_capital_pct: float = 0.3  # Max 30% of capital
    max_positions: int = 3
    max_daily_trades: int = 10
    max_daily_loss_pct: float = 0.05  # Max 5% daily loss
    cooldown_after_loss: int = 30  # Minutes to wait after a loss
    position_size_multiplier: float = 1.0


@dataclass
class PortfolioRiskConfig:
    """Overall portfolio risk configuration"""
    total_capital: float
    max_open_trades: int = 5
    max_drawdown_pct: float = 0.15  # 15% max drawdown
    daily_loss_limit_pct: float = 0.05  # 5% daily loss limit
    risk_per_trade_pct: float = 0.02  # 2% risk per trade
    risk_level: RiskLevel = RiskLevel.MODERATE


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    strategy: str
    pair: str
    profit_pct: float
    timestamp: datetime
    entry_reason: str
    exit_reason: str


class RiskManager:
    """
    Central risk management for multi-strategy trading
    """

    def __init__(self, portfolio_config: PortfolioRiskConfig):
        self.portfolio_config = portfolio_config
        self.strategy_configs: Dict[str, StrategyRiskConfig] = {}
        self.trade_history: List[TradeRecord] = []
        self.daily_pnl: float = 0.0
        self.last_daily_reset: datetime = datetime.now()
        self.strategy_positions: Dict[str, int] = {}
        self.strategy_daily_trades: Dict[str, int] = {}
        self.strategy_last_loss: Dict[str, datetime] = {}
        self.peak_capital: float = portfolio_config.total_capital
        self.current_capital: float = portfolio_config.total_capital

        self._setup_default_strategy_configs()

    def _setup_default_strategy_configs(self):
        """Setup default risk configs for known strategies"""
        self.strategy_configs = {
            "TrendFollowing": StrategyRiskConfig(
                name="TrendFollowing",
                max_capital_pct=0.35,
                max_positions=2,
                max_daily_trades=8,
                max_daily_loss_pct=0.04,
                cooldown_after_loss=20,
                position_size_multiplier=1.0
            ),
            "Grid": StrategyRiskConfig(
                name="Grid",
                max_capital_pct=0.40,
                max_positions=5,
                max_daily_trades=15,
                max_daily_loss_pct=0.03,
                cooldown_after_loss=15,
                position_size_multiplier=0.8
            ),
            "MeanReversion": StrategyRiskConfig(
                name="MeanReversion",
                max_capital_pct=0.25,
                max_positions=3,
                max_daily_trades=10,
                max_daily_loss_pct=0.03,
                cooldown_after_loss=25,
                position_size_multiplier=0.9
            )
        }

    def _reset_daily_counters(self):
        """Reset daily counters if new day"""
        now = datetime.now()
        if now.date() > self.last_daily_reset.date():
            self.daily_pnl = 0.0
            self.strategy_daily_trades = {k: 0 for k in self.strategy_daily_trades}
            self.last_daily_reset = now
            logger.info("Daily risk counters reset")

    def check_position_allowed(
        self,
        strategy_name: str,
        pair: str,
        current_positions: int
    ) -> Tuple[bool, str]:
        """
        Check if opening a new position is allowed

        Returns:
            (allowed, reason)
        """
        self._reset_daily_counters()

        # Check portfolio-level limits
        if current_positions >= self.portfolio_config.max_open_trades:
            return False, f"Max portfolio positions reached ({self.portfolio_config.max_open_trades})"

        # Check daily loss limit
        if self.daily_pnl <= -self.portfolio_config.daily_loss_limit_pct:
            return False, f"Daily loss limit reached ({self.portfolio_config.daily_loss_limit_pct*100:.1f}%)"

        # Check drawdown limit
        current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        if current_drawdown >= self.portfolio_config.max_drawdown_pct:
            return False, f"Max drawdown reached ({current_drawdown*100:.1f}%)"

        # Check strategy-specific limits
        config = self.strategy_configs.get(strategy_name)
        if config:
            # Check strategy position limit
            strategy_positions = self.strategy_positions.get(strategy_name, 0)
            if strategy_positions >= config.max_positions:
                return False, f"Strategy {strategy_name} max positions reached ({config.max_positions})"

            # Check strategy daily trade limit
            daily_trades = self.strategy_daily_trades.get(strategy_name, 0)
            if daily_trades >= config.max_daily_trades:
                return False, f"Strategy {strategy_name} daily trade limit reached"

            # Check cooldown after loss
            last_loss = self.strategy_last_loss.get(strategy_name)
            if last_loss:
                cooldown_end = last_loss + timedelta(minutes=config.cooldown_after_loss)
                if datetime.now() < cooldown_end:
                    remaining = (cooldown_end - datetime.now()).seconds // 60
                    return False, f"Strategy {strategy_name} in cooldown ({remaining} min remaining)"

        return True, "OK"

    def calculate_position_size(
        self,
        strategy_name: str,
        confidence: float,
        proposed_stake: float,
        entry_price: float,
        stop_loss_pct: float
    ) -> float:
        """
        Calculate optimal position size using Kelly Criterion and risk limits

        Args:
            strategy_name: Name of the strategy
            confidence: Strategy confidence score (0-1)
            proposed_stake: Proposed stake amount
            entry_price: Entry price
            stop_loss_pct: Stop loss percentage (e.g., 0.03 for 3%)

        Returns:
            Adjusted position size
        """
        config = self.strategy_configs.get(strategy_name)

        # Base: Risk per trade
        risk_amount = self.current_capital * self.portfolio_config.risk_per_trade_pct

        # Kelly Criterion (simplified)
        # Assuming 50% base win rate, adjusted by confidence
        win_prob = 0.45 + (confidence * 0.2)  # 45-65% win rate
        avg_win = 0.02  # 2% average win
        avg_loss = abs(stop_loss_pct)

        if avg_loss > 0:
            kelly_fraction = (win_prob * avg_win - (1 - win_prob) * avg_loss) / avg_loss
            kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25%
        else:
            kelly_fraction = 0.1

        # Position size based on risk
        position_from_risk = risk_amount / abs(stop_loss_pct) if stop_loss_pct != 0 else proposed_stake

        # Apply strategy multiplier
        if config:
            position_from_risk *= config.position_size_multiplier

        # Apply confidence adjustment
        confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5x to 1.0x
        position_from_risk *= confidence_multiplier

        # Check against strategy capital limit
        if config:
            max_strategy_capital = self.current_capital * config.max_capital_pct
            current_strategy_exposure = self.strategy_positions.get(strategy_name, 0) * proposed_stake
            available = max_strategy_capital - current_strategy_exposure
            position_from_risk = min(position_from_risk, available)

        # Final bounds check
        final_position = min(position_from_risk, proposed_stake)
        final_position = max(final_position, proposed_stake * 0.3)  # At least 30% of proposed

        logger.debug(f"Position sizing for {strategy_name}: "
                    f"confidence={confidence:.2f}, kelly={kelly_fraction:.3f}, "
                    f"final={final_position:.2f}")

        return final_position

    def record_trade(
        self,
        strategy_name: str,
        pair: str,
        profit_pct: float,
        entry_reason: str,
        exit_reason: str
    ):
        """Record a completed trade"""
        record = TradeRecord(
            strategy=strategy_name,
            pair=pair,
            profit_pct=profit_pct,
            timestamp=datetime.now(),
            entry_reason=entry_reason,
            exit_reason=exit_reason
        )
        self.trade_history.append(record)

        # Update daily PnL
        self.daily_pnl += profit_pct

        # Update capital tracking
        self.current_capital *= (1 + profit_pct)
        self.peak_capital = max(self.peak_capital, self.current_capital)

        # Update strategy counters
        if strategy_name in self.strategy_daily_trades:
            self.strategy_daily_trades[strategy_name] += 1
        else:
            self.strategy_daily_trades[strategy_name] = 1

        # Record loss for cooldown
        if profit_pct < 0:
            self.strategy_last_loss[strategy_name] = datetime.now()

        logger.info(f"Trade recorded: {strategy_name} | {pair} | "
                   f"PnL: {profit_pct*100:.2f}% | Daily: {self.daily_pnl*100:.2f}%")

    def update_position_count(self, strategy_name: str, delta: int):
        """Update strategy position count"""
        if strategy_name not in self.strategy_positions:
            self.strategy_positions[strategy_name] = 0
        self.strategy_positions[strategy_name] += delta
        self.strategy_positions[strategy_name] = max(0, self.strategy_positions[strategy_name])

    def get_risk_status(self) -> Dict:
        """Get current risk status"""
        current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital

        return {
            "current_capital": self.current_capital,
            "peak_capital": self.peak_capital,
            "drawdown_pct": current_drawdown * 100,
            "daily_pnl_pct": self.daily_pnl * 100,
            "strategy_positions": self.strategy_positions.copy(),
            "daily_trades": self.strategy_daily_trades.copy(),
            "is_trading_allowed": self._is_trading_allowed(),
            "risk_level": self._get_current_risk_level()
        }

    def _is_trading_allowed(self) -> bool:
        """Check if trading is allowed based on risk limits"""
        current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital

        if current_drawdown >= self.portfolio_config.max_drawdown_pct:
            return False
        if self.daily_pnl <= -self.portfolio_config.daily_loss_limit_pct:
            return False

        return True

    def _get_current_risk_level(self) -> str:
        """Determine current risk level"""
        current_drawdown = (self.peak_capital - self.current_capital) / self.peak_capital

        if current_drawdown > 0.10 or self.daily_pnl < -0.03:
            return "HIGH"
        elif current_drawdown > 0.05 or self.daily_pnl < -0.02:
            return "MEDIUM"
        else:
            return "LOW"

    def get_strategy_stats(self, strategy_name: str, lookback_days: int = 7) -> Dict:
        """Get performance statistics for a strategy"""
        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent_trades = [
            t for t in self.trade_history
            if t.strategy == strategy_name and t.timestamp > cutoff
        ]

        if not recent_trades:
            return {
                "total_trades": 0,
                "win_rate": 0.5,
                "total_pnl": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 1.0
            }

        wins = [t for t in recent_trades if t.profit_pct > 0]
        losses = [t for t in recent_trades if t.profit_pct <= 0]

        total_wins = sum(t.profit_pct for t in wins) if wins else 0
        total_losses = abs(sum(t.profit_pct for t in losses)) if losses else 0

        return {
            "total_trades": len(recent_trades),
            "win_rate": len(wins) / len(recent_trades) if recent_trades else 0.5,
            "total_pnl": sum(t.profit_pct for t in recent_trades),
            "avg_win": total_wins / len(wins) if wins else 0,
            "avg_loss": total_losses / len(losses) if losses else 0,
            "profit_factor": total_wins / total_losses if total_losses > 0 else 2.0
        }


class CircuitBreaker:
    """
    Emergency circuit breaker for extreme market conditions
    """

    def __init__(self):
        self.is_tripped: bool = False
        self.trip_reason: Optional[str] = None
        self.trip_time: Optional[datetime] = None
        self.auto_reset_minutes: int = 60

    def check_and_trip(
        self,
        volatility: str,
        price_change_1h: float,
        volume_spike: float
    ) -> bool:
        """
        Check conditions and trip circuit breaker if needed

        Returns:
            True if circuit breaker is tripped
        """
        # Auto-reset after timeout
        if self.is_tripped and self.trip_time:
            if datetime.now() - self.trip_time > timedelta(minutes=self.auto_reset_minutes):
                self.reset()

        if self.is_tripped:
            return True

        # Trip conditions
        if volatility == "extreme":
            self.trip("extreme_volatility")
            return True

        if abs(price_change_1h) > 0.10:  # 10% move in 1 hour
            self.trip(f"flash_crash_or_pump_{price_change_1h*100:.1f}%")
            return True

        if volume_spike > 5.0:  # 5x normal volume
            self.trip(f"volume_anomaly_{volume_spike:.1f}x")
            return True

        return False

    def trip(self, reason: str):
        """Trip the circuit breaker"""
        self.is_tripped = True
        self.trip_reason = reason
        self.trip_time = datetime.now()
        logger.warning(f"CIRCUIT BREAKER TRIPPED: {reason}")

    def reset(self):
        """Reset the circuit breaker"""
        logger.info(f"Circuit breaker reset (was: {self.trip_reason})")
        self.is_tripped = False
        self.trip_reason = None
        self.trip_time = None

    def get_status(self) -> Dict:
        """Get circuit breaker status"""
        return {
            "is_tripped": self.is_tripped,
            "reason": self.trip_reason,
            "trip_time": self.trip_time.isoformat() if self.trip_time else None,
            "auto_reset_in": self._get_reset_countdown()
        }

    def _get_reset_countdown(self) -> Optional[int]:
        """Get minutes until auto-reset"""
        if not self.is_tripped or not self.trip_time:
            return None

        elapsed = (datetime.now() - self.trip_time).seconds // 60
        remaining = self.auto_reset_minutes - elapsed
        return max(0, remaining)
