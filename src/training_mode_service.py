"""
Training Mode Service
Koordiniert KI-Trading und Human Feedback
"""

from typing import Dict, Any, Optional, Callable
from datetime import datetime
import uuid


class TrainingModeService:
    """
    Service für Training Mode

    Workflow:
    1. User aktiviert AI Mode
    2. Bei jedem Skip: KI analysiert Market
    3. Wenn KI tradet → Position öffnen
    4. Modal automatisch öffnen
    5. User bewertet
    6. Feedback speichern
    7. KI lernt
    """

    def __init__(
        self,
        rl_agent,
        feedback_system,
        position_service,
        account_service
    ):
        """
        Args:
            rl_agent: RLTradingAgent
            feedback_system: MultiFeedbackSystem
            position_service: PositionService für Trade Execution
            account_service: AccountService für Balance Updates
        """
        self.rl_agent = rl_agent
        self.feedback_system = feedback_system
        self.position_service = position_service
        self.account_service = account_service

        self.is_active = False
        self.pending_feedback_trades = []  # Trades die noch bewertet werden müssen
        self.session_id = None
        self.session_stats = {
            'trades_count': 0,
            'long_count': 0,
            'short_count': 0,
            'hold_count': 0,
            'avg_confidence': 0.0
        }

        print("[TrainingMode] Service initialized")

    def toggle_mode(self) -> Dict[str, Any]:
        """
        Aktiviert/Deaktiviert Training Mode

        Returns:
            Status Dict
        """
        self.is_active = not self.is_active

        if self.is_active:
            # Start neue Session
            self.session_id = f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.pending_feedback_trades.clear()
            self.session_stats = {
                'trades_count': 0,
                'long_count': 0,
                'short_count': 0,
                'hold_count': 0,
                'avg_confidence': 0.0
            }
            print(f"[TrainingMode] [OK] Activated - Session: {self.session_id}")
        else:
            print(f"[TrainingMode] Deactivated - Session: {self.session_id}")
            print(f"[TrainingMode] Stats: {self.session_stats}")

        return {
            'is_active': self.is_active,
            'session_id': self.session_id,
            'stats': self.session_stats
        }

    def on_skip(self, market_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Wird bei jedem Skip aufgerufen wenn Training Mode aktiv

        Args:
            market_context: Market Context vom Chart

        Returns:
            Trade Decision oder None wenn Hold
        """
        if not self.is_active:
            return None

        # KI trifft Entscheidung
        decision = self.rl_agent.decide(market_context)

        # Update Stats
        action = decision['action']
        if action == 'long':
            self.session_stats['long_count'] += 1
        elif action == 'short':
            self.session_stats['short_count'] += 1
        else:
            self.session_stats['hold_count'] += 1

        # Update Avg Confidence
        total_decisions = sum([
            self.session_stats['long_count'],
            self.session_stats['short_count'],
            self.session_stats['hold_count']
        ])
        prev_sum = self.session_stats['avg_confidence'] * (total_decisions - 1)
        self.session_stats['avg_confidence'] = (prev_sum + decision['confidence']) / total_decisions

        # HOLD → kein Trade
        if action == 'hold':
            print(f"[TrainingMode] HOLD - Confidence: {decision['confidence']:.2%}")
            return None

        # Trade ausführen
        print(f"[TrainingMode] [TRADE] {action.upper()} @ ${decision['entry_price']:.2f}")
        print(f"[TrainingMode] Confidence: {decision['confidence']:.2%}")
        print(f"[TrainingMode] Reasoning: {decision['reasoning']}")

        # Generiere Trade ID
        trade_id = f"ai_{self.session_id}_{self.session_stats['trades_count'] + 1}"

        # Erstelle Position
        direction = 'long' if action == 'long' else 'short'
        position_result = self.position_service.create_position(
            entry_price=decision['entry_price'],
            sl_price=decision['sl_price'],
            tp_price=decision['tp_price'],
            direction=direction,
            size=1.0,
            symbol='NQ'
        )

        if not position_result['success']:
            print(f"[TrainingMode] [ERROR] Position creation failed: {position_result.get('error')}")
            return None

        position_data = position_result['position_data']
        position_data['id'] = trade_id
        position_data['source'] = 'ai'
        position_data['confidence'] = decision['confidence']
        position_data['reasoning'] = decision['reasoning']

        # Registriere bei Account Service (AI Account)
        account_result = self.account_service.execute_trade(
            position_data=position_data,
            is_rl_online=True  # AI Account
        )

        if not account_result['success']:
            print(f"[TrainingMode] [ERROR] Account execution failed: {account_result.get('error')}")
            return None

        # Trade erfolgreich
        self.session_stats['trades_count'] += 1
        self.pending_feedback_trades.append(trade_id)

        print(f"[TrainingMode] [OK] Trade executed: {trade_id}")
        print(f"[TrainingMode] Pending Feedback: {len(self.pending_feedback_trades)} trades")

        # Generiere Hints für User
        hints = self.feedback_system.get_feedback_hints(
            trade_record=None,  # Wird später verwendet
            entry_price=decision['entry_price'],
            sl_price=decision['sl_price'],
            tp_price=decision['tp_price']
        )

        return {
            'trade_id': trade_id,
            'action': action,
            'position': position_data,
            'account_summary': account_result['account_summary'],
            'hints': hints,
            'reasoning': decision['reasoning'],
            'confidence': decision['confidence']
        }

    def on_feedback_received(self, trade_id: str, feedback_reward: float):
        """
        Callback wenn User Feedback gibt

        Args:
            trade_id: ID des bewerteten Trades
            feedback_reward: Reward aus Human Evaluation
        """
        # Entferne aus pending list
        if trade_id in self.pending_feedback_trades:
            self.pending_feedback_trades.remove(trade_id)
            print(f"[TrainingMode] Feedback received for {trade_id}: {feedback_reward:+.3f}")
            print(f"[TrainingMode] Remaining pending: {len(self.pending_feedback_trades)}")

        # KI lernt aus Feedback
        self.rl_agent.learn_from_feedback(trade_id, feedback_reward)

    def get_status(self) -> Dict[str, Any]:
        """Returns current Training Mode status"""
        return {
            'is_active': self.is_active,
            'session_id': self.session_id,
            'stats': self.session_stats,
            'pending_feedback_count': len(self.pending_feedback_trades),
            'agent_stats': self.rl_agent.get_stats()
        }


# Example Usage
if __name__ == "__main__":
    from rl_agent import RLTradingAgent
    from multi_feedback_system import MultiFeedbackSystem
    from rewards_v2 import create_default_reward_manager
    import pandas as pd

    # Setup
    df = pd.read_csv("src/data/aggregated/5m/nq-2024.csv")
    reward_manager = create_default_reward_manager()
    feedback_system = MultiFeedbackSystem(df, reward_manager)
    rl_agent = RLTradingAgent(feedback_system)

    # Mock Services
    class MockPositionService:
        def create_position(self, **kwargs):
            return {'success': True, 'position_data': kwargs}

    class MockAccountService:
        def execute_trade(self, **kwargs):
            return {'success': True, 'account_summary': {'balance': 100000}}

    position_service = MockPositionService()
    account_service = MockAccountService()

    # Create Service
    training_service = TrainingModeService(
        rl_agent=rl_agent,
        feedback_system=feedback_system,
        position_service=position_service,
        account_service=account_service
    )

    # Test: Activate
    status = training_service.toggle_mode()
    print("\n[TEST] Status:", status)

    # Test: Simulate Skip
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

    result = training_service.on_skip(market_context)
    print("\n[TEST] Trade Result:", result)

    # Test: Feedback
    if result:
        training_service.on_feedback_received(result['trade_id'], 0.8)

    print("\n[TEST] Final Status:", training_service.get_status())
    print("\n[SUCCESS] Training Mode Service funktioniert!")
