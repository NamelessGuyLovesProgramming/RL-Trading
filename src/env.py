"""
Interactive Trading Environment mit Human-in-the-Loop Feedback
Inspiriert vom Trackmania Reward Shaping Beispiel
"""

import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, List, Tuple, Optional
import hashlib

from rewards import RewardManager, PnLReward, FVGReward, OrderBlockReward, LiquidityZoneReward, HumanFeedbackReward, RiskManagementReward
from patterns import PatternManager, FVGDetector, OrderBlockDetector, LiquidityZoneDetector, MarketStructureDetector


class InteractiveTradingEnv(gym.Env):
    """
    Trading Environment mit modularem Reward System und Pattern Detection
    """

    def __init__(self,
                 df: pd.DataFrame,
                 initial_cash: float = 10000,
                 transaction_cost: float = 0.001,
                 max_position_size: float = 1.0,
                 enable_patterns: bool = True,
                 reward_config: Optional[Dict] = None):
        super().__init__()

        # Data Setup
        self.df = df.reset_index(drop=True)
        self.initial_cash = initial_cash
        self.transaction_cost = transaction_cost
        self.max_position_size = max_position_size
        self.enable_patterns = enable_patterns

        # Spaces
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(30,), dtype=np.float32  # Erweitert für Pattern Features
        )
        self.action_space = spaces.Discrete(3)  # 0: Hold, 1: Buy, 2: Sell

        # Trading State
        self.current_step = 0
        self.cash = initial_cash
        self.position = 0.0  # Normalized position (-1 to 1)
        self.shares_held = 0
        self.entry_price = 0
        self.max_drawdown = 0
        self.peak_value = initial_cash

        # Trading History
        self.trades_history = []
        self.action_history = []
        self.portfolio_history = []

        # Metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # Reward System Setup
        self._setup_reward_system(reward_config or {})

        # Pattern Detection Setup
        if enable_patterns:
            self._setup_pattern_detection()

    def _setup_reward_system(self, config: Dict):
        """Initialisiert das modulare Reward System"""
        self.reward_manager = RewardManager()

        # Standard Reward Komponenten mit Gewichtungen
        default_weights = {
            'pnl': 1.0,
            'fvg': 0.8,
            'order_block': 0.5,
            'liquidity_zone': 0.7,
            'human': 2.0,  # Human Feedback hat hohes Gewicht
            'risk_management': 0.3
        }

        # Override mit user config
        weights = {**default_weights, **config.get('weights', {})}

        # Füge Reward Komponenten hinzu
        self.reward_manager.add_component(PnLReward(), weights['pnl'])
        self.reward_manager.add_component(FVGReward(bonus_multiplier=2.5), weights['fvg'])
        self.reward_manager.add_component(OrderBlockReward(), weights['order_block'])
        self.reward_manager.add_component(LiquidityZoneReward(), weights['liquidity_zone'])
        self.reward_manager.add_component(HumanFeedbackReward(), weights['human'])
        self.reward_manager.add_component(RiskManagementReward(), weights['risk_management'])

    def _setup_pattern_detection(self):
        """Initialisiert Pattern Detection System"""
        self.pattern_manager = PatternManager()

        # Füge Pattern Detectors hinzu
        self.pattern_manager.add_detector(FVGDetector(min_gap_percent=0.05))
        self.pattern_manager.add_detector(OrderBlockDetector(lookback=15))
        self.pattern_manager.add_detector(LiquidityZoneDetector())
        self.pattern_manager.add_detector(MarketStructureDetector())

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Reset trading state
        self.current_step = 50  # Start nach genug Historie für Patterns
        self.cash = self.initial_cash
        self.position = 0.0
        self.shares_held = 0
        self.entry_price = 0
        self.max_drawdown = 0
        self.peak_value = self.initial_cash

        # Reset histories
        self.trades_history.clear()
        self.action_history.clear()
        self.portfolio_history.clear()

        # Reset metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # Reset reward history
        self.reward_manager.reset_history()

        return self._get_observation(), {}

    def _get_observation(self) -> np.ndarray:
        """
        Erweiterte Observation mit Pattern Features
        """
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1

        idx = self.current_step
        current = self.df.iloc[idx]

        # Basis Price Features (normalisiert)
        price_features = [
            current['open'] / current['close'] - 1,
            current['high'] / current['close'] - 1,
            current['low'] / current['close'] - 1,
            (current['volume'] / self.df['volume'].rolling(20).mean().iloc[idx] - 1) if idx >= 19 else 0
        ]

        # Technical Features
        returns = self.df['close'].pct_change()
        if idx >= 20:
            technical_features = [
                returns.iloc[idx-5:idx].mean(),  # 5-period return
                returns.iloc[idx-20:idx].std(),  # 20-period volatility
                (current['close'] / self.df['close'].iloc[idx-20:idx].mean() - 1),  # Price momentum
                self._calculate_rsi(idx),
                self._calculate_macd_signal(idx)
            ]
        else:
            technical_features = [0.0] * 5

        # Pattern Features
        pattern_features = [0.0] * 10  # Default
        if self.enable_patterns and hasattr(self, 'pattern_manager'):
            signals = self.pattern_manager.get_trading_signals(self.df, idx)
            pattern_features = [
                float(signals['in_fvg_zone']),
                min(signals['fvg_distance'] * 100, 5.0),  # Capped distance
                float(signals['near_support_ob']),
                float(signals['near_resistance_ob']),
                signals['liquidity_direction'],
                signals['market_structure'],
                signals['pattern_confluence'] / 3.0,  # Normalized confluence
                0.0, 0.0, 0.0  # Reserved for future patterns
            ]

        # Position & Portfolio Features
        portfolio_value = self.cash + self.shares_held * current['close']
        portfolio_features = [
            self.position,  # Normalized position
            self.cash / self.initial_cash - 1,  # Cash ratio
            portfolio_value / self.initial_cash - 1,  # Portfolio performance
            self.max_drawdown,
            len(self.trades_history) / 100.0  # Normalized trade count
        ]

        # Action History Features (last 5 actions)
        action_history = [0.0] * 5
        for i, action in enumerate(self.action_history[-5:]):
            if i < len(self.action_history):
                action_history[i] = (action - 1) / 1.0  # Normalize to [-1, 1]

        # Risk Features
        risk_features = [
            abs(self.position),  # Position size
            self._calculate_portfolio_risk(),
            0.0, 0.0, 0.0  # Reserved for more risk metrics
        ]

        # Combine all features
        observation = np.array(
            price_features + technical_features + pattern_features +
            portfolio_features + action_history + risk_features,
            dtype=np.float32
        )

        # Pad or truncate to exact size
        if len(observation) < 30:
            observation = np.pad(observation, (0, 30 - len(observation)), mode='constant')
        else:
            observation = observation[:30]

        # Replace any NaN or inf values
        observation = np.nan_to_num(observation, nan=0.0, posinf=5.0, neginf=-5.0)

        return observation

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute trading action and calculate rewards
        """
        if self.current_step >= len(self.df) - 1:
            return self._get_observation(), 0.0, True, False, {}

        current_price = self.df.iloc[self.current_step]['close']
        prev_portfolio_value = self.cash + self.shares_held * current_price

        # Execute trade
        trade_info = self._execute_trade(action, current_price)

        # Update step
        self.current_step += 1

        # Check if episode is done
        done = self.current_step >= len(self.df) - 1

        # Calculate new portfolio value
        if not done:
            new_price = self.df.iloc[self.current_step]['close']
        else:
            new_price = current_price

        new_portfolio_value = self.cash + self.shares_held * new_price
        pnl_change = new_portfolio_value - prev_portfolio_value

        # Update portfolio tracking
        self.portfolio_history.append(new_portfolio_value)
        if new_portfolio_value > self.peak_value:
            self.peak_value = new_portfolio_value
        current_drawdown = (self.peak_value - new_portfolio_value) / self.peak_value
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown

        # Update action history
        self.action_history.append(action)

        # Prepare environment info for rewards
        env_info = self._prepare_env_info(pnl_change, trade_info, new_price)

        # Calculate modular rewards
        total_reward, reward_breakdown = self.reward_manager.calculate_total_reward(
            self._get_observation(), action, env_info
        )

        # Prepare info dict
        info = {
            'portfolio_value': new_portfolio_value,
            'cash': self.cash,
            'position': self.position,
            'shares_held': self.shares_held,
            'total_trades': self.total_trades,
            'win_rate': self.winning_trades / max(1, self.total_trades),
            'max_drawdown': self.max_drawdown,
            'reward_breakdown': reward_breakdown,
            'trade_info': trade_info,
            'pattern_signals': env_info.get('pattern_signals', {}),
            'pnl_change': pnl_change
        }

        return self._get_observation(), total_reward, done, False, info

    def _execute_trade(self, action: int, price: float) -> Dict:
        """Execute trading action with realistic constraints"""
        trade_info = {
            'executed': False,
            'type': 'hold',
            'price': price,
            'shares': 0,
            'cost': 0,
            'reason': ''
        }

        if action == 1:  # Buy
            # Calculate maximum affordable shares
            available_cash = self.cash * 0.95  # Reserve 5% for safety
            max_shares = available_cash / (price * (1 + self.transaction_cost))

            # Check position limits
            target_position = self.position + 0.5  # Increase position by 50%
            if target_position > self.max_position_size:
                target_position = self.max_position_size

            position_change = target_position - self.position
            shares_to_buy = int(position_change * self.initial_cash / price)

            if shares_to_buy > 0 and shares_to_buy <= max_shares:
                cost = shares_to_buy * price * (1 + self.transaction_cost)
                self.cash -= cost
                self.shares_held += shares_to_buy
                self.position = self.shares_held * price / self.initial_cash

                if self.shares_held > 0:
                    self.entry_price = ((self.entry_price * (self.shares_held - shares_to_buy)) +
                                       (price * shares_to_buy)) / self.shares_held

                self.total_trades += 1
                trade_info.update({
                    'executed': True,
                    'type': 'buy',
                    'shares': shares_to_buy,
                    'cost': cost
                })

                self.trades_history.append({
                    'step': self.current_step,
                    'action': 'buy',
                    'price': price,
                    'shares': shares_to_buy,
                    'cost': cost,
                    'portfolio_value': self.cash + self.shares_held * price
                })

        elif action == 2:  # Sell
            if self.shares_held > 0:
                # Calculate shares to sell (reduce position by 50%)
                target_position = max(0, self.position - 0.5)
                shares_to_sell = int((self.position - target_position) * self.initial_cash / price)
                shares_to_sell = min(shares_to_sell, self.shares_held)

                if shares_to_sell > 0:
                    revenue = shares_to_sell * price * (1 - self.transaction_cost)
                    pnl = (price - self.entry_price) * shares_to_sell

                    self.cash += revenue
                    self.shares_held -= shares_to_sell
                    self.position = self.shares_held * price / self.initial_cash

                    if pnl > 0:
                        self.winning_trades += 1
                    else:
                        self.losing_trades += 1

                    self.total_trades += 1
                    trade_info.update({
                        'executed': True,
                        'type': 'sell',
                        'shares': shares_to_sell,
                        'revenue': revenue,
                        'pnl': pnl
                    })

                    self.trades_history.append({
                        'step': self.current_step,
                        'action': 'sell',
                        'price': price,
                        'shares': shares_to_sell,
                        'revenue': revenue,
                        'pnl': pnl,
                        'portfolio_value': self.cash + self.shares_held * price
                    })

        return trade_info

    def _prepare_env_info(self, pnl_change: float, trade_info: Dict, current_price: float) -> Dict:
        """Prepare environment info for reward calculation"""
        env_info = {
            'pnl_change': pnl_change / self.initial_cash,  # Normalized
            'state_hash': self._get_state_hash(),
            'trade_info': trade_info,
            'portfolio_risk': self._calculate_portfolio_risk(),
            'stop_loss_active': False,  # TODO: Implement stop loss
            'current_price': current_price
        }

        # Add pattern signals if enabled
        if self.enable_patterns and hasattr(self, 'pattern_manager'):
            pattern_signals = self.pattern_manager.get_trading_signals(self.df, self.current_step)
            env_info.update(pattern_signals)
            env_info['pattern_signals'] = pattern_signals

        return env_info

    def _get_state_hash(self) -> str:
        """Generate hash for current state (for human feedback)"""
        obs = self._get_observation()
        # Use only the most relevant features for hashing
        key_features = obs[:10]  # Price and technical features
        hash_input = ','.join([f'{x:.3f}' for x in key_features])
        return hashlib.md5(hash_input.encode()).hexdigest()[:8]

    def _calculate_rsi(self, idx: int, period: int = 14) -> float:
        """Calculate RSI indicator"""
        if idx < period:
            return 0.5  # Neutral RSI

        price_changes = self.df['close'].iloc[idx-period:idx+1].pct_change()
        gains = price_changes.where(price_changes > 0, 0)
        losses = -price_changes.where(price_changes < 0, 0)

        avg_gain = gains.mean()
        avg_loss = losses.mean()

        if avg_loss == 0:
            return 1.0

        rs = avg_gain / avg_loss
        rsi = 1 - (1 / (1 + rs))
        return rsi

    def _calculate_macd_signal(self, idx: int) -> float:
        """Calculate MACD signal"""
        if idx < 26:
            return 0.0

        prices = self.df['close'].iloc[max(0, idx-50):idx+1]
        ema12 = prices.ewm(span=12).mean().iloc[-1]
        ema26 = prices.ewm(span=26).mean().iloc[-1]
        macd = ema12 - ema26

        # Normalize to [-1, 1] range
        return np.tanh(macd / prices.iloc[-1] * 100)

    def _calculate_portfolio_risk(self) -> float:
        """Calculate current portfolio risk"""
        if len(self.portfolio_history) < 20:
            return 0.0

        returns = np.diff(self.portfolio_history[-20:]) / self.portfolio_history[-20:-1]
        return np.std(returns) if len(returns) > 0 else 0.0

    # Human Feedback Interface
    def add_human_feedback(self, reward_value: float, for_last_action: bool = True):
        """Add human feedback for learning"""
        if for_last_action and self.trades_history:
            last_trade = self.trades_history[-1]
            state_hash = self._get_state_hash()
            action = 1 if last_trade['action'] == 'buy' else 2

            # Get human feedback component
            human_component = self.reward_manager.components.get('Human')
            if human_component:
                human_component.add_feedback(state_hash, action, reward_value)
                print(f"Feedback added: {reward_value} for {last_trade['action']} at step {last_trade['step']}")

    def set_reward_weight(self, component_name: str, weight: float):
        """Update reward component weight"""
        if self.reward_manager.set_weight(component_name, weight):
            print(f"Updated {component_name} weight to {weight}")
        else:
            print(f"Component {component_name} not found")

    def get_reward_info(self) -> Dict:
        """Get information about reward components"""
        return self.reward_manager.get_component_info()

    def save_human_feedback(self, filepath: str):
        """Save human feedback data"""
        human_component = self.reward_manager.components.get('Human')
        if human_component:
            human_component.save_feedback(filepath)

    def load_human_feedback(self, filepath: str):
        """Load human feedback data"""
        human_component = self.reward_manager.components.get('Human')
        if human_component:
            human_component.load_feedback(filepath)