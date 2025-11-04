"""
RL Trading Agent
Simple rule-based stub that will be replaced by PPO agent

Macht Trading-Entscheidungen basierend auf Market Context
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime


class RLTradingAgent:
    """
    RL Agent für Trading Entscheidungen

    Erstmal ein einfacher rule-based Agent, später PPO
    """

    def __init__(self, feedback_system=None):
        """
        Args:
            feedback_system: MultiFeedbackSystem für Context Analysis
        """
        self.feedback_system = feedback_system
        self.last_action = None
        self.trades_count = 0
        self.confidence_threshold = 0.6  # Mindest-Confidence für Trade

        print("[RLAgent] Initialized (Rule-Based Mode)")

    def decide(self, market_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trifft Trading-Entscheidung basierend auf Market Context

        Args:
            market_context: Dictionary mit:
                - current_price: float
                - timestamp: int
                - patterns: Dict (FVG, OB, etc.)
                - session_info: Dict
                - volume: Dict

        Returns:
            Decision Dict mit:
                - action: 'long', 'short', 'hold'
                - entry_price: float
                - sl_price: float
                - tp_price: float
                - confidence: float (0-1)
                - reasoning: str
        """

        current_price = market_context.get('current_price', 0.0)
        patterns = market_context.get('patterns', {})
        session_info = market_context.get('session_info', {})
        volume = market_context.get('volume', {})

        # Decision Logic
        decision = self._analyze_and_decide(
            current_price=current_price,
            patterns=patterns,
            session_info=session_info,
            volume=volume
        )

        self.last_action = decision['action']
        if decision['action'] != 'hold':
            self.trades_count += 1

        return decision

    def _analyze_and_decide(
        self,
        current_price: float,
        patterns: Dict,
        session_info: Dict,
        volume: Dict
    ) -> Dict[str, Any]:
        """
        Analysiert Market Context und trifft Entscheidung
        """

        # Extract Pattern Info
        in_fvg = patterns.get('in_fvg_zone', False)
        fvg_distance = patterns.get('fvg_distance', 999)
        near_support_ob = patterns.get('near_support_ob', False)
        near_resistance_ob = patterns.get('near_resistance_ob', False)
        liquidity_direction = patterns.get('liquidity_direction', 0)
        market_structure = patterns.get('market_structure', 0)

        # Extract Session Info
        session = session_info.get('session', 'unknown')
        time_in_session = session_info.get('time_in_session', 0)
        near_open = session_info.get('near_open', False)
        near_close = session_info.get('near_close', False)

        # Extract Volume Info
        volume_spike = volume.get('spike', False)
        volume_ratio = volume.get('ratio', 1.0)

        # Decision Scores
        long_score = 0.0
        short_score = 0.0
        reasoning = []

        # ========== LONG SIGNALS ==========

        # FVG Pattern (Bullish)
        if in_fvg and fvg_distance < 0.005:
            long_score += 0.3
            reasoning.append("FVG Zone erkannt")

        # Support Order Block
        if near_support_ob:
            long_score += 0.2
            reasoning.append("Nahe Support OB")

        # Bullish Market Structure
        if market_structure > 0:
            long_score += 0.15
            reasoning.append("Bullish Structure")

        # Liquidity Sweep (Bullish)
        if liquidity_direction > 0:
            long_score += 0.15
            reasoning.append("Bullish Liquidity")

        # Volume Spike
        if volume_spike and volume_ratio > 1.5:
            long_score += 0.1
            reasoning.append(f"Volume Spike ({volume_ratio:.1f}x)")

        # Session Timing (avoid session close)
        if session in ['london', 'ny'] and not near_close:
            long_score += 0.1
            reasoning.append(f"Gute Session ({session})")


        # ========== SHORT SIGNALS ==========

        # Resistance Order Block
        if near_resistance_ob:
            short_score += 0.2
            reasoning.append("Nahe Resistance OB")

        # Bearish Market Structure
        if market_structure < 0:
            short_score += 0.15
            reasoning.append("Bearish Structure")

        # Liquidity Sweep (Bearish)
        if liquidity_direction < 0:
            short_score += 0.15
            reasoning.append("Bearish Liquidity")

        # Volume Spike (can be bearish too)
        if volume_spike and volume_ratio > 1.5:
            short_score += 0.1


        # ========== DECISION ==========

        if long_score > self.confidence_threshold and long_score > short_score:
            # LONG Trade
            action = 'long'
            confidence = min(long_score, 1.0)

            # Calculate Entry, SL, TP
            entry_price = current_price
            sl_distance = current_price * 0.005  # 0.5% SL
            tp_distance = current_price * 0.015  # 1.5% TP (R:R = 3:1)

            sl_price = entry_price - sl_distance
            tp_price = entry_price + tp_distance

            return {
                'action': 'long',
                'entry_price': entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'confidence': confidence,
                'reasoning': ' | '.join(reasoning)
            }

        elif short_score > self.confidence_threshold and short_score > long_score:
            # SHORT Trade
            action = 'short'
            confidence = min(short_score, 1.0)

            # Calculate Entry, SL, TP
            entry_price = current_price
            sl_distance = current_price * 0.005  # 0.5% SL
            tp_distance = current_price * 0.015  # 1.5% TP (R:R = 3:1)

            sl_price = entry_price + sl_distance
            tp_price = entry_price - tp_distance

            return {
                'action': 'short',
                'entry_price': entry_price,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'confidence': confidence,
                'reasoning': ' | '.join(reasoning)
            }

        else:
            # HOLD - keine klare Entscheidung
            return {
                'action': 'hold',
                'entry_price': 0.0,
                'sl_price': 0.0,
                'tp_price': 0.0,
                'confidence': max(long_score, short_score),
                'reasoning': 'Keine klare Setup erkannt'
            }

    def learn_from_feedback(self, trade_id: str, feedback_reward: float):
        """
        Lernt aus Human Feedback (später für PPO wichtig)

        Args:
            trade_id: ID des bewerteten Trades
            feedback_reward: Reward aus Human Evaluation
        """
        # TODO: Implementiere PPO Update hier
        print(f"[RLAgent] Feedback empfangen für {trade_id}: {feedback_reward:+.3f}")
        print("[RLAgent] Learning not implemented yet (rule-based mode)")

    def get_stats(self) -> Dict[str, Any]:
        """Returns Agent Statistics"""
        return {
            'trades_count': self.trades_count,
            'last_action': self.last_action,
            'mode': 'rule-based'
        }


# Example Usage
if __name__ == "__main__":
    agent = RLTradingAgent()

    # Test Market Context
    market_context = {
        'current_price': 19450.50,
        'timestamp': int(datetime.now().timestamp()),
        'patterns': {
            'in_fvg_zone': True,
            'fvg_distance': 0.003,
            'near_support_ob': True,
            'near_resistance_ob': False,
            'liquidity_direction': 1,
            'market_structure': 1
        },
        'session_info': {
            'session': 'london',
            'time_in_session': 120,
            'near_open': False,
            'near_close': False
        },
        'volume': {
            'spike': True,
            'ratio': 1.8
        }
    }

    decision = agent.decide(market_context)

    print("\n[TEST] Agent Decision:")
    print(f"  Action: {decision['action'].upper()}")
    print(f"  Entry: ${decision['entry_price']:.2f}")
    print(f"  SL: ${decision['sl_price']:.2f}")
    print(f"  TP: ${decision['tp_price']:.2f}")
    print(f"  Confidence: {decision['confidence']:.2%}")
    print(f"  Reasoning: {decision['reasoning']}")

    print("\n[SUCCESS] RL Agent funktioniert!")
