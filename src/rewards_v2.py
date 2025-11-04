"""
Verbesserte Reward-Komponenten mit Normalisierung
Research-basiert: Alle Komponenten auf -1 bis +1, Gewichte summieren zu 1.0
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pickle
from collections import deque


class RewardComponent:
    """Basis-Klasse für modulare Reward-Komponenten"""
    def __init__(self, name: str):
        self.name = name

    def calculate(self, state, action, env_info) -> float:
        """
        Berechnet Reward (MUSS -1 bis +1 zurückgeben!)

        Args:
            state: Observation
            action: Gewählte Aktion
            env_info: Environment Informationen

        Returns:
            Normalized reward zwischen -1 und +1
        """
        raise NotImplementedError

    def get_info(self) -> Dict:
        """Gibt zusätzliche Info für Debugging zurück"""
        return {}


class PnLReward(RewardComponent):
    """
    PnL Reward - normalisiert auf -1 bis +1
    Verwendet tanh für weiche Normalisierung
    """
    def __init__(self, max_pnl_percent: float = 0.05):
        """
        Args:
            max_pnl_percent: PnL Prozent für max reward (0.05 = 5%)
        """
        super().__init__("PnL")
        self.max_pnl_percent = max_pnl_percent

    def calculate(self, state, action, env_info) -> float:
        pnl_change = env_info.get('pnl_change', 0.0)

        # Normalisieren: 5% = +1.0, -5% = -1.0
        # tanh für weiche Sättigung (große Werte werden nicht zu extrem)
        normalized = np.tanh(pnl_change / self.max_pnl_percent)

        return float(normalized)  # Range: -1 bis +1


class FVGReward(RewardComponent):
    """
    Fair Value Gap Reward - normalisiert
    Feste Boni statt PnL-Multiplikation
    """
    def __init__(self, zone_bonus: float = 0.8, proximity_bonus: float = 0.2):
        super().__init__("FVG")
        self.zone_bonus = zone_bonus
        self.proximity_bonus = proximity_bonus
        self.fvg_hits = 0

    def calculate(self, state, action, env_info) -> float:
        reward = 0.0

        # Hauptbelohnung: Trading IN FVG Zone
        if env_info.get('in_fvg_zone', False) and action != 0:  # Nicht Hold
            reward += self.zone_bonus
            self.fvg_hits += 1

        # Proximity Bonus: Nähe zu FVG Zone
        fvg_distance = env_info.get('fvg_distance', float('inf'))
        if fvg_distance < 0.01:  # Innerhalb 1%
            reward += self.proximity_bonus

        # Clipping (sollte bereits <=1.0 sein, aber sicher ist sicher)
        return float(np.clip(reward, 0.0, 1.0))  # Range: 0 bis +1

    def get_info(self) -> Dict:
        return {'fvg_hits': self.fvg_hits}


class LiquidityZoneReward(RewardComponent):
    """
    Liquidity Zone Reward - normalisiert
    Belohnt Trading in Richtung Liquidity + mit Trend
    """
    def __init__(self, direction_bonus: float = 0.6, structure_bonus: float = 0.4):
        super().__init__("LiquidityZone")
        self.direction_bonus = direction_bonus
        self.structure_bonus = structure_bonus
        self.zones_hit = 0

    def calculate(self, state, action, env_info) -> float:
        reward = 0.0

        # Richtung zu Liquidity Zone
        liquidity_direction = env_info.get('liquidity_direction', 0)  # 1=up, -1=down

        if action == 1 and liquidity_direction > 0:  # Buy toward upside liquidity
            reward += self.direction_bonus
            self.zones_hit += 1
        elif action == 2 and liquidity_direction < 0:  # Sell toward downside liquidity
            reward += self.direction_bonus
            self.zones_hit += 1

        # Market Structure Bonus
        market_structure = env_info.get('market_structure', 0)  # 1=bullish, -1=bearish

        if action == 1 and market_structure > 0:  # Buy in bullish market
            reward += self.structure_bonus
        elif action == 2 and market_structure < 0:  # Sell in bearish market
            reward += self.structure_bonus

        return float(np.clip(reward, 0.0, 1.0))  # Range: 0 bis +1

    def get_info(self) -> Dict:
        return {'zones_hit': self.zones_hit}


class HumanFeedbackReward(RewardComponent):
    """
    Human Feedback Reward - bereits -1 bis +1
    Nutzt State-Hash System für Pattern Recognition
    """
    def __init__(self, decay_factor: float = 0.95):
        super().__init__("Human")
        self.feedback_buffer = []
        self.pattern_rewards = {}  # state_hash_action -> reward
        self.decay_factor = decay_factor
        self.feedback_count = 0

    def add_feedback(self, state_hash: str, action: int, reward: float):
        """
        Fügt manuelles Feedback hinzu

        Args:
            state_hash: Hash des aktuellen States
            action: Aktion (0=hold, 1=buy, 2=sell)
            reward: Reward -1 bis +1
        """
        # Clipping für Sicherheit
        reward = np.clip(reward, -1.0, 1.0)

        feedback_entry = {
            'state_hash': state_hash,
            'action': action,
            'reward': reward,
            'timestamp': datetime.now()
        }

        self.feedback_buffer.append(feedback_entry)

        # Update Pattern Rewards mit Decay (alte Erfahrungen verblassen langsam)
        key = f"{state_hash}_{action}"

        if key in self.pattern_rewards:
            # Combine old and new feedback with decay
            # 95% alter Wert + 5% neuer Wert
            self.pattern_rewards[key] = (
                self.pattern_rewards[key] * self.decay_factor +
                reward * (1 - self.decay_factor)
            )
        else:
            self.pattern_rewards[key] = reward

        self.feedback_count += 1

    def calculate(self, state, action, env_info) -> float:
        state_hash = env_info.get('state_hash', '')
        key = f"{state_hash}_{action}"

        # Lookup gespeichertes Feedback
        reward = self.pattern_rewards.get(key, 0.0)

        return float(np.clip(reward, -1.0, 1.0))  # Range: -1 bis +1

    def get_info(self) -> Dict:
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
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            self.feedback_buffer = data.get('feedback_buffer', [])
            self.pattern_rewards = data.get('pattern_rewards', {})
            self.feedback_count = data.get('feedback_count', 0)
            print(f"[HumanFeedback] Loaded {self.feedback_count} feedback entries")
        except FileNotFoundError:
            print(f"[HumanFeedback] No existing feedback found at {filepath}")


class RiskManagementReward(RewardComponent):
    """
    Risk Management Reward - normalisiert
    Bestraft hohes Risiko, belohnt SL-Usage
    """
    def __init__(self, risk_penalty_scale: float = 2.0, sl_bonus: float = 0.3):
        super().__init__("RiskManagement")
        self.risk_penalty_scale = risk_penalty_scale
        self.sl_bonus = sl_bonus

    def calculate(self, state, action, env_info) -> float:
        reward = 0.0

        # Bestrafung für zu hohes Risiko
        portfolio_risk = env_info.get('portfolio_risk', 0.0)

        if portfolio_risk > 0.1:  # Mehr als 10% Risiko
            # Quadratische Bestrafung (größeres Risiko = viel schlimmer)
            penalty = -self.risk_penalty_scale * (portfolio_risk ** 2)
            reward += penalty

        # Bonus für Stop Loss Usage
        if env_info.get('stop_loss_active', False):
            reward += self.sl_bonus

        return float(np.clip(reward, -1.0, 1.0))  # Range: -1 bis +1


class RewardManager:
    """
    Verwaltet alle Reward-Komponenten
    Research-basiert: Gewichte summieren zu 1.0, adaptive Normalisierung
    """

    def __init__(self, use_adaptive_normalization: bool = True):
        self.components = {}
        self.weights = {}
        self.history = []
        self.use_adaptive_normalization = use_adaptive_normalization

        # Für adaptive Normalisierung
        self.reward_buffer = deque(maxlen=100)  # Letzte 100 Rewards
        self.running_mean = 0.0
        self.running_std = 1.0

    def add_component(self, component: RewardComponent, weight: float = 1.0):
        """
        Fügt eine Reward-Komponente hinzu

        Args:
            component: RewardComponent Instanz
            weight: Gewicht (sollte mit anderen zu 1.0 summieren!)
        """
        self.components[component.name] = component
        self.weights[component.name] = weight

        print(f"[RewardManager] Added component: {component.name} (weight={weight})")

        # Prüfe ob Gewichte zu 1.0 summieren
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.01:
            print(f"[WARNING] Weights sum to {total_weight:.3f}, not 1.0!")
            print("Consider normalizing weights for stable training.")

    def calculate_total_reward(self, state, action, env_info) -> Tuple[float, Dict]:
        """
        Berechnet den gesamten Reward aus allen Komponenten

        Returns:
            (total_reward, reward_breakdown)
        """
        total_reward = 0.0
        breakdown = {}

        # 1. Berechne alle Komponenten
        for name, component in self.components.items():
            component_reward = component.calculate(state, action, env_info)
            weighted_reward = component_reward * self.weights[name]
            total_reward += weighted_reward

            breakdown[name] = {
                'raw': float(component_reward),
                'weighted': float(weighted_reward),
                'weight': self.weights[name]
            }

        # 2. Adaptive Normalisierung (optional)
        if self.use_adaptive_normalization and len(self.reward_buffer) > 10:
            # Standardisierung über letzte N Rewards
            self.reward_buffer.append(total_reward)

            # Berechne laufende Statistiken
            rewards_array = np.array(self.reward_buffer)
            self.running_mean = np.mean(rewards_array)
            self.running_std = np.std(rewards_array) + 1e-8  # Epsilon für Stabilität

            # Standardisieren
            normalized_reward = (total_reward - self.running_mean) / self.running_std

            # Clipping für extreme Werte
            normalized_reward = np.clip(normalized_reward, -3.0, 3.0)

            breakdown['normalization'] = {
                'original': float(total_reward),
                'normalized': float(normalized_reward),
                'running_mean': float(self.running_mean),
                'running_std': float(self.running_std)
            }

            total_reward = normalized_reward
        else:
            # Ohne adaptive Normalisierung: nur Clipping
            self.reward_buffer.append(total_reward)
            total_reward = np.clip(total_reward, -2.0, 2.0)

        # 3. Logging für Analyse
        self.history.append({
            'total_reward': float(total_reward),
            'breakdown': breakdown,
            'action': action,
            'timestamp': datetime.now()
        })

        return float(total_reward), breakdown

    def set_weight(self, component_name: str, weight: float) -> bool:
        """Ändert Gewichtung einer Komponente"""
        if component_name in self.weights:
            old_weight = self.weights[component_name]
            self.weights[component_name] = weight
            print(f"[RewardManager] Updated {component_name}: {old_weight} -> {weight}")

            # Warnung wenn Summe != 1.0
            total = sum(self.weights.values())
            if abs(total - 1.0) > 0.01:
                print(f"[WARNING] Total weights now: {total:.3f}")

            return True

        print(f"[ERROR] Component {component_name} not found")
        return False

    def get_component_info(self) -> Dict:
        """Gibt Info über alle Komponenten zurück"""
        info = {}
        for name, component in self.components.items():
            info[name] = {
                'weight': self.weights[name],
                'info': component.get_info()
            }

        # Gesamtstatistiken
        if self.history:
            recent_rewards = [h['total_reward'] for h in self.history[-100:]]
            info['statistics'] = {
                'total_rewards_logged': len(self.history),
                'recent_mean': np.mean(recent_rewards) if recent_rewards else 0,
                'recent_std': np.std(recent_rewards) if recent_rewards else 0,
                'running_mean': self.running_mean,
                'running_std': self.running_std
            }

        return info

    def reset_history(self):
        """Setzt History zurück"""
        self.history = []
        print("[RewardManager] History reset")


def create_default_reward_manager(use_adaptive_norm: bool = True,
                                   enable_fvg: bool = True) -> RewardManager:
    """
    Erstellt RewardManager mit Standard-Konfiguration

    Args:
        use_adaptive_norm: Adaptive Normalisierung nutzen
        enable_fvg: FVG Pattern Reward aktivieren

    Returns:
        Konfigurierter RewardManager
    """
    manager = RewardManager(use_adaptive_normalization=use_adaptive_norm)

    # Gewichte (summieren zu 1.0)
    weights = {
        'pnl': 0.30,
        'fvg': 0.20 if enable_fvg else 0.0,
        'liquidity': 0.15,
        'human': 0.30,  # Gleich wichtig wie PnL!
        'risk': 0.05
    }

    # Wenn FVG deaktiviert, verteile Gewicht auf andere
    if not enable_fvg:
        weights['pnl'] += 0.10
        weights['liquidity'] += 0.10

    # Komponenten hinzufügen
    manager.add_component(PnLReward(max_pnl_percent=0.05), weights['pnl'])

    if enable_fvg:
        manager.add_component(FVGReward(zone_bonus=0.8, proximity_bonus=0.2), weights['fvg'])

    manager.add_component(LiquidityZoneReward(direction_bonus=0.6, structure_bonus=0.4),
                         weights['liquidity'])

    manager.add_component(HumanFeedbackReward(decay_factor=0.95), weights['human'])

    manager.add_component(RiskManagementReward(risk_penalty_scale=2.0, sl_bonus=0.3),
                         weights['risk'])

    print("\n[RewardManager] Configuration:")
    print(f"  Adaptive Normalization: {use_adaptive_norm}")
    print(f"  FVG Pattern Enabled: {enable_fvg}")
    print(f"  Total Weight: {sum(weights.values()):.3f}")

    return manager


# Example usage
if __name__ == "__main__":
    print("=== Testing Reward System ===\n")

    # Create manager
    manager = create_default_reward_manager(
        use_adaptive_norm=True,
        enable_fvg=True
    )

    # Simulate some rewards
    print("\n=== Simulating Rewards ===")

    for i in range(5):
        env_info = {
            'pnl_change': 0.02 if i % 2 == 0 else -0.01,  # 2% oder -1%
            'in_fvg_zone': i % 3 == 0,
            'fvg_distance': 0.005,
            'liquidity_direction': 1,
            'market_structure': 1,
            'portfolio_risk': 0.05,
            'stop_loss_active': True,
            'state_hash': 'test_hash'
        }

        action = 1  # Buy
        state = np.zeros(30)

        total, breakdown = manager.calculate_total_reward(state, action, env_info)

        print(f"\nTrade {i+1}:")
        print(f"  Total Reward: {total:.3f}")
        for comp_name, details in breakdown.items():
            if comp_name != 'normalization':
                print(f"  {comp_name}: {details['raw']:.3f} × {details['weight']:.2f} = {details['weighted']:.3f}")

    # Info
    print("\n=== Component Info ===")
    info = manager.get_component_info()
    for name, details in info.items():
        if name != 'statistics':
            print(f"{name}: weight={details['weight']:.2f}, info={details['info']}")

    if 'statistics' in info:
        print(f"\nStatistics:")
        for key, value in info['statistics'].items():
            print(f"  {key}: {value:.3f}")

    print("\n[SUCCESS] Reward System V2 funktioniert!")
