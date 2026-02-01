"""
Thompson Sampling - Multi-Armed Bandit for Strategy Selection
Uses Bayesian inference to balance exploration vs exploitation
"""
import logging
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BetaDistribution:
    """Beta distribution parameters for Thompson Sampling"""
    alpha: float = 1.0  # Successes + 1
    beta: float = 1.0   # Failures + 1

    def sample(self) -> float:
        """Sample from beta distribution"""
        return np.random.beta(self.alpha, self.beta)

    def mean(self) -> float:
        """Expected value of the distribution"""
        return self.alpha / (self.alpha + self.beta)

    def variance(self) -> float:
        """Variance of the distribution"""
        total = self.alpha + self.beta
        return (self.alpha * self.beta) / (total * total * (total + 1))

    def update(self, reward: float):
        """Update distribution based on reward (0-1)"""
        if reward > 0:
            self.alpha += reward
        else:
            self.beta += abs(reward) if reward < 0 else 0.1


@dataclass
class StrategyArm:
    """Represents a strategy as a bandit arm"""
    name: str
    distribution: BetaDistribution = field(default_factory=BetaDistribution)
    total_pulls: int = 0
    total_reward: float = 0.0
    last_pulled: Optional[datetime] = None

    def pull(self) -> float:
        """Sample the arm"""
        self.total_pulls += 1
        self.last_pulled = datetime.now()
        return self.distribution.sample()

    def update(self, reward: float):
        """Update arm with observed reward"""
        self.total_reward += reward
        self.distribution.update(reward)

    @property
    def average_reward(self) -> float:
        if self.total_pulls == 0:
            return 0.0
        return self.total_reward / self.total_pulls


class ThompsonSamplingSelector:
    """
    Thompson Sampling for strategy selection
    Balances exploration (trying different strategies) with
    exploitation (using the best known strategy)
    """

    def __init__(self, strategy_names: List[str], state_file: Optional[str] = None):
        """
        Initialize Thompson Sampling selector

        Args:
            strategy_names: List of available strategy names
            state_file: Optional file path to persist state
        """
        self.arms: Dict[str, StrategyArm] = {
            name: StrategyArm(name=name) for name in strategy_names
        }
        self.state_file = state_file
        self.selection_history: List[Dict] = []

        # Load state if file exists
        if state_file and os.path.exists(state_file):
            self.load_state()

        logger.info(f"Thompson Sampling initialized with {len(self.arms)} strategies")

    def select_strategy(self, context: Optional[Dict] = None) -> Tuple[str, float]:
        """
        Select a strategy using Thompson Sampling

        Args:
            context: Optional market context (for contextual bandits - future use)

        Returns:
            (selected_strategy_name, sampled_value)
        """
        samples = {}

        for name, arm in self.arms.items():
            sample = arm.pull()
            samples[name] = sample

        # Select arm with highest sample
        selected = max(samples, key=samples.get)
        sampled_value = samples[selected]

        # Log selection
        self.selection_history.append({
            "timestamp": datetime.now().isoformat(),
            "selected": selected,
            "sampled_value": sampled_value,
            "all_samples": samples.copy(),
            "context": context
        })

        logger.debug(f"Thompson Sampling selected: {selected} (sample: {sampled_value:.3f})")

        return selected, sampled_value

    def update(self, strategy_name: str, reward: float):
        """
        Update strategy arm with observed reward

        Args:
            strategy_name: Name of the strategy that was used
            reward: Observed reward (typically profit ratio, e.g., 0.02 for 2% profit)
        """
        if strategy_name not in self.arms:
            logger.warning(f"Unknown strategy: {strategy_name}")
            return

        # Normalize reward to 0-1 range for Beta distribution
        # Assuming reward is profit ratio (-1 to +1 typically)
        normalized_reward = (reward + 0.1) / 0.2  # Maps -0.1 to 0.1 -> 0 to 1
        normalized_reward = max(0, min(1, normalized_reward))

        self.arms[strategy_name].update(normalized_reward)

        logger.debug(f"Updated {strategy_name}: reward={reward:.4f}, "
                    f"normalized={normalized_reward:.3f}, "
                    f"new_mean={self.arms[strategy_name].distribution.mean():.3f}")

        # Auto-save state
        if self.state_file:
            self.save_state()

    def get_strategy_stats(self) -> Dict[str, Dict]:
        """Get statistics for all strategies"""
        stats = {}
        for name, arm in self.arms.items():
            stats[name] = {
                "total_pulls": arm.total_pulls,
                "total_reward": arm.total_reward,
                "average_reward": arm.average_reward,
                "expected_value": arm.distribution.mean(),
                "alpha": arm.distribution.alpha,
                "beta": arm.distribution.beta,
                "uncertainty": arm.distribution.variance() ** 0.5
            }
        return stats

    def get_best_strategy(self) -> Tuple[str, float]:
        """Get strategy with highest expected value"""
        best = max(self.arms.items(), key=lambda x: x[1].distribution.mean())
        return best[0], best[1].distribution.mean()

    def get_exploration_rate(self) -> float:
        """Calculate current exploration rate (how uncertain we are)"""
        total_pulls = sum(arm.total_pulls for arm in self.arms.values())
        if total_pulls < 10:
            return 1.0  # Full exploration at start

        # Calculate average uncertainty
        avg_variance = np.mean([arm.distribution.variance() for arm in self.arms.values()])
        return min(1.0, avg_variance * 10)  # Scale to 0-1

    def save_state(self):
        """Save state to file"""
        if not self.state_file:
            return

        state = {
            "arms": {
                name: {
                    "alpha": arm.distribution.alpha,
                    "beta": arm.distribution.beta,
                    "total_pulls": arm.total_pulls,
                    "total_reward": arm.total_reward
                }
                for name, arm in self.arms.items()
            },
            "timestamp": datetime.now().isoformat()
        }

        os.makedirs(os.path.dirname(self.state_file) or '.', exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

        logger.debug(f"Thompson Sampling state saved to {self.state_file}")

    def load_state(self):
        """Load state from file"""
        if not self.state_file or not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)

            for name, data in state.get("arms", {}).items():
                if name in self.arms:
                    self.arms[name].distribution.alpha = data["alpha"]
                    self.arms[name].distribution.beta = data["beta"]
                    self.arms[name].total_pulls = data["total_pulls"]
                    self.arms[name].total_reward = data["total_reward"]

            logger.info(f"Thompson Sampling state loaded from {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to load Thompson Sampling state: {e}")


class EpsilonGreedySelector:
    """
    Epsilon-Greedy strategy selection
    Simpler alternative to Thompson Sampling
    """

    def __init__(self, strategy_names: List[str], epsilon: float = 0.1):
        """
        Args:
            strategy_names: List of available strategies
            epsilon: Exploration probability (default 10%)
        """
        self.strategies = strategy_names
        self.epsilon = epsilon
        self.rewards: Dict[str, List[float]] = {name: [] for name in strategy_names}
        self.counts: Dict[str, int] = {name: 0 for name in strategy_names}

    def select_strategy(self) -> str:
        """Select strategy using epsilon-greedy"""
        if np.random.random() < self.epsilon:
            # Exploration: random strategy
            return np.random.choice(self.strategies)
        else:
            # Exploitation: best average reward
            avg_rewards = {
                name: np.mean(rewards) if rewards else 0
                for name, rewards in self.rewards.items()
            }
            return max(avg_rewards, key=avg_rewards.get)

    def update(self, strategy_name: str, reward: float):
        """Update strategy with observed reward"""
        if strategy_name in self.rewards:
            self.rewards[strategy_name].append(reward)
            self.counts[strategy_name] += 1


class ContextualBandit:
    """
    Contextual Bandit - considers market context for strategy selection
    Uses separate Thompson Sampling for each market regime
    """

    def __init__(self, strategy_names: List[str], contexts: List[str]):
        """
        Args:
            strategy_names: List of available strategies
            contexts: List of possible market contexts (e.g., ['sideways', 'trending', 'volatile'])
        """
        self.strategy_names = strategy_names
        self.contexts = contexts

        # Create separate Thompson Sampling for each context
        self.samplers: Dict[str, ThompsonSamplingSelector] = {
            context: ThompsonSamplingSelector(strategy_names)
            for context in contexts
        }

        self.default_sampler = ThompsonSamplingSelector(strategy_names)

    def select_strategy(self, context: str) -> Tuple[str, float]:
        """Select strategy based on context"""
        if context in self.samplers:
            return self.samplers[context].select_strategy()
        else:
            return self.default_sampler.select_strategy()

    def update(self, context: str, strategy_name: str, reward: float):
        """Update the appropriate sampler"""
        if context in self.samplers:
            self.samplers[context].update(strategy_name, reward)
        else:
            self.default_sampler.update(strategy_name, reward)

    def get_best_strategy_for_context(self, context: str) -> Tuple[str, float]:
        """Get best strategy for a specific context"""
        if context in self.samplers:
            return self.samplers[context].get_best_strategy()
        return self.default_sampler.get_best_strategy()

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get stats for all contexts"""
        return {
            context: sampler.get_strategy_stats()
            for context, sampler in self.samplers.items()
        }
