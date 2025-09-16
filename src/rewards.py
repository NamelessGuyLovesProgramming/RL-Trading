"""
Modulare Reward-Komponenten für RL Trading System
Inspired by Trackmania reward shaping - gezieltes Lernen spezifischer Patterns
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pickle


class RewardComponent:
    """Basis-Klasse für modulare Reward-Komponenten"""
    def __init__(self, name: str):
        self.name = name

    def calculate(self, state, action, env_info):
        raise NotImplementedError

    def get_info(self):
        """Gibt zusätzliche Info für Debugging zurück"""
        return {}


class PnLReward(RewardComponent):
    """Basis PnL Belohnung - Standard Trading Reward"""
    def __init__(self):
        super().__init__("PnL")

    def calculate(self, state, action, env_info):
        return env_info.get('pnl_change', 0.0)


class FVGReward(RewardComponent):
    """
    Fair Value Gap Reward - belohnt Trading in FVG-Zonen
    Wie Trackmania Drift-Punkte in Kurven
    """
    def __init__(self, bonus_multiplier=2.0, proximity_bonus=0.5):
        super().__init__("FVG")
        self.bonus_multiplier = bonus_multiplier
        self.proximity_bonus = proximity_bonus
        self.fvg_hits = 0

    def calculate(self, state, action, env_info):
        reward = 0.0

        # Hauptbelohnung: Trading IN FVG Zone
        if env_info.get('in_fvg_zone', False) and action != 0:
            pnl_change = env_info.get('pnl_change', 0)
            reward += pnl_change * self.bonus_multiplier
            self.fvg_hits += 1

        # Proximity Bonus: Nähe zu FVG Zone
        fvg_distance = env_info.get('fvg_distance', float('inf'))
        if fvg_distance < 0.01:  # Innerhalb 1%
            reward += self.proximity_bonus

        return reward

    def get_info(self):
        return {'fvg_hits': self.fvg_hits}


class OrderBlockReward(RewardComponent):
    """Belohnt Trading bei Order Blocks - Support/Resistance Zonen"""
    def __init__(self, support_bonus=0.5, resistance_bonus=0.3):
        super().__init__("OrderBlock")
        self.support_bonus = support_bonus
        self.resistance_bonus = resistance_bonus
        self.ob_trades = 0

    def calculate(self, state, action, env_info):
        reward = 0.0

        # Buy bei Support Order Block
        if env_info.get('near_support_ob', False) and action == 1:
            reward += self.support_bonus
            self.ob_trades += 1

        # Sell bei Resistance Order Block
        elif env_info.get('near_resistance_ob', False) and action == 2:
            reward += self.resistance_bonus
            self.ob_trades += 1

        return reward

    def get_info(self):
        return {'ob_trades': self.ob_trades}


class LiquidityZoneReward(RewardComponent):
    """
    Liquidity Zone Reward - wie Trackmania "Checkpoint" Punkte
    Belohnt das Ansteuern von hohen Liquiditätszonen
    """
    def __init__(self, zone_bonus=1.0, direction_bonus=0.5):
        super().__init__("LiquidityZone")
        self.zone_bonus = zone_bonus
        self.direction_bonus = direction_bonus
        self.zones_hit = 0

    def calculate(self, state, action, env_info):
        reward = 0.0

        # Haupt-Belohnung: Trade in Richtung Liquidity Zone
        liquidity_direction = env_info.get('liquidity_direction', 0)  # 1=up, -1=down
        if action == 1 and liquidity_direction > 0:  # Buy toward upside liquidity
            reward += self.zone_bonus
            self.zones_hit += 1
        elif action == 2 and liquidity_direction < 0:  # Sell toward downside liquidity
            reward += self.zone_bonus
            self.zones_hit += 1

        # Direction Bonus: Korrekte Marktrichtung
        market_structure = env_info.get('market_structure', 0)  # 1=bullish, -1=bearish
        if action == 1 and market_structure > 0:
            reward += self.direction_bonus
        elif action == 2 and market_structure < 0:
            reward += self.direction_bonus

        return reward

    def get_info(self):
        return {'zones_hit': self.zones_hit}


class HumanFeedbackReward(RewardComponent):
    """
    Sammelt und nutzt menschliches Feedback
    Kernstück des Human-in-the-Loop Systems
    """
    def __init__(self, decay_factor=0.95):
        super().__init__("Human")
        self.feedback_buffer = []
        self.pattern_rewards = {}  # state_hash -> reward
        self.decay_factor = decay_factor
        self.feedback_count = 0

    def add_feedback(self, state_hash: str, action: int, reward: float):
        """Fügt manuelles Feedback hinzu"""
        feedback_entry = {
            'state_hash': state_hash,
            'action': action,
            'reward': reward,
            'timestamp': datetime.now()
        }

        self.feedback_buffer.append(feedback_entry)

        # Update Pattern Rewards mit Decay
        key = f"{state_hash}_{action}"
        if key in self.pattern_rewards:
            # Combine old and new feedback with decay
            self.pattern_rewards[key] = (
                self.pattern_rewards[key] * self.decay_factor +
                reward * (1 - self.decay_factor)
            )
        else:
            self.pattern_rewards[key] = reward

        self.feedback_count += 1

    def calculate(self, state, action, env_info):
        state_hash = env_info.get('state_hash', '')
        key = f"{state_hash}_{action}"
        return self.pattern_rewards.get(key, 0.0)

    def get_info(self):
        return {
            'feedback_count': self.feedback_count,
            'learned_patterns': len(self.pattern_rewards)
        }

    def save_feedback(self, filepath: str):
        """Speichert Feedback für spätere Nutzung"""
        data = {
            'feedback_buffer': self.feedback_buffer,
            'pattern_rewards': self.pattern_rewards,
            'feedback_count': self.feedback_count
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)

    def load_feedback(self, filepath: str):
        """Lädt gespeichertes Feedback"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.feedback_buffer = data.get('feedback_buffer', [])
        self.pattern_rewards = data.get('pattern_rewards', {})
        self.feedback_count = data.get('feedback_count', 0)


class RiskManagementReward(RewardComponent):
    """
    Risk Management Reward - bestraft schlechtes Risk Management
    """
    def __init__(self, max_risk_penalty=-2.0, stop_loss_bonus=0.3):
        super().__init__("RiskManagement")
        self.max_risk_penalty = max_risk_penalty
        self.stop_loss_bonus = stop_loss_bonus

    def calculate(self, state, action, env_info):
        reward = 0.0

        # Bestrafung für zu hohes Risiko
        portfolio_risk = env_info.get('portfolio_risk', 0.0)
        if portfolio_risk > 0.1:  # Mehr als 10% Risiko
            reward += self.max_risk_penalty * portfolio_risk

        # Bonus für Stop Loss Usage
        if env_info.get('stop_loss_active', False):
            reward += self.stop_loss_bonus

        return reward


class RewardManager:
    """
    Verwaltet alle Reward-Komponenten und deren Gewichtungen
    """
    def __init__(self):
        self.components = {}
        self.weights = {}
        self.history = []

    def add_component(self, component: RewardComponent, weight: float = 1.0):
        """Fügt eine Reward-Komponente hinzu"""
        self.components[component.name] = component
        self.weights[component.name] = weight

    def calculate_total_reward(self, state, action, env_info) -> Tuple[float, Dict]:
        """
        Berechnet den gesamten Reward aus allen Komponenten
        Returns: (total_reward, reward_breakdown)
        """
        total_reward = 0.0
        breakdown = {}

        for name, component in self.components.items():
            component_reward = component.calculate(state, action, env_info)
            weighted_reward = component_reward * self.weights[name]
            total_reward += weighted_reward

            breakdown[name] = {
                'raw': component_reward,
                'weighted': weighted_reward,
                'weight': self.weights[name]
            }

        # Logging für Analyse
        self.history.append({
            'total_reward': total_reward,
            'breakdown': breakdown,
            'action': action,
            'timestamp': datetime.now()
        })

        return total_reward, breakdown

    def set_weight(self, component_name: str, weight: float):
        """Ändert Gewichtung einer Komponente"""
        if component_name in self.weights:
            self.weights[component_name] = weight
            return True
        return False

    def get_component_info(self) -> Dict:
        """Gibt Info über alle Komponenten zurück"""
        info = {}
        for name, component in self.components.items():
            info[name] = {
                'weight': self.weights[name],
                'info': component.get_info()
            }
        return info

    def reset_history(self):
        """Setzt History zurück"""
        self.history = []