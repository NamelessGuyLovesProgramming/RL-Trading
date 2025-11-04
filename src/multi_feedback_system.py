"""
Multi-dimensionales Feedback System
Verbindet 6-Kriterien Bewertung mit Reward System und Storage
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib

from feedback_storage import FeedbackStorage, HumanEvaluation, TradeRecord
from rewards_v2 import RewardManager


class SessionDetector:
    """
    Erkennt Trading Sessions (Asia, London, NY)
    Und ob wir nahe Open/Close sind
    """

    SESSIONS = {
        'asia': {'open': 0, 'close': 9},      # 00:00 - 09:00 UTC
        'london': {'open': 8, 'close': 17},   # 08:00 - 17:00 UTC
        'ny': {'open': 13, 'close': 22}       # 13:00 - 22:00 UTC
    }

    @classmethod
    def detect_session(cls, timestamp: pd.Timestamp) -> Dict[str, Any]:
        """
        Erkennt aktive Session und Context

        Returns:
            Dict mit session, time_in_session, near_open, near_close
        """
        hour = timestamp.hour

        active_session = None
        time_in_session = 0
        near_open = False
        near_close = False

        # Finde aktive Session
        for session_name, times in cls.SESSIONS.items():
            if times['open'] <= hour < times['close']:
                active_session = session_name
                time_in_session = hour - times['open']

                # Near open/close (innerhalb 1h)
                near_open = time_in_session <= 1
                near_close = (times['close'] - hour) <= 1
                break

        return {
            'session': active_session or 'none',
            'time_in_session': time_in_session,
            'near_open': near_open,
            'near_close': near_close,
            'hour': hour
        }


class VolumeAnalyzer:
    """
    Analysiert Volume Patterns
    """

    @staticmethod
    def analyze_volume(df: pd.DataFrame, current_idx: int, window: int = 20) -> Dict[str, Any]:
        """
        Analysiert Volume am aktuellen Index

        Returns:
            Dict mit spike, ratio, current, avg
        """
        if current_idx < window:
            return {
                'spike': False,
                'ratio': 1.0,
                'current': 0,
                'avg_20': 0
            }

        current_volume = df.iloc[current_idx]['volume']
        avg_volume = df.iloc[current_idx - window:current_idx]['volume'].mean()

        ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        spike = ratio > 1.5  # 50% über Durchschnitt = Spike

        return {
            'spike': bool(spike),
            'ratio': float(ratio),
            'current': float(current_volume),
            'avg_20': float(avg_volume)
        }


class MarketContextCollector:
    """
    Sammelt kompletten Market Context für Feedback
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.session_detector = SessionDetector()
        self.volume_analyzer = VolumeAnalyzer()

    def collect_context(self,
                       current_idx: int,
                       observation: np.ndarray,
                       pattern_signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sammelt kompletten Market Context

        Args:
            current_idx: Aktueller Index im DataFrame
            observation: Environment Observation (30 Features)
            pattern_signals: Pattern Detection Results

        Returns:
            Dict mit state_hash, observation, patterns, session_info, volume
        """
        if current_idx >= len(self.df):
            current_idx = len(self.df) - 1

        current_candle = self.df.iloc[current_idx]

        # State Hash für Pattern Recognition
        state_hash = self._generate_state_hash(observation, pattern_signals)

        # Session Info
        timestamp = current_candle.name if isinstance(current_candle.name, pd.Timestamp) else pd.Timestamp.now()
        session_info = self.session_detector.detect_session(timestamp)

        # Volume Info
        volume_info = self.volume_analyzer.analyze_volume(self.df, current_idx)

        return {
            'state_hash': state_hash,
            'observation': observation.tolist(),
            'patterns': pattern_signals,
            'session_info': session_info,
            'volume': volume_info,
            'price': float(current_candle['close']),
            'timestamp': timestamp.isoformat() if isinstance(timestamp, pd.Timestamp) else str(timestamp)
        }

    def _generate_state_hash(self, observation: np.ndarray, patterns: Dict[str, Any]) -> str:
        """
        Generiert State Hash für ähnliche Situationen

        Nutzt:
        - Pattern Flags (FVG, OB, Liquidity)
        - Market Structure
        - Grobe Price Action (normalisiert)
        """
        # Wichtigste Features für Hash
        key_features = [
            # Patterns (boolean → 1/0)
            1 if patterns.get('in_fvg_zone', False) else 0,
            1 if patterns.get('near_support_ob', False) else 0,
            1 if patterns.get('near_resistance_ob', False) else 0,
            patterns.get('liquidity_direction', 0),
            patterns.get('market_structure', 0),
            patterns.get('pattern_confluence', 0),

            # Price Features (erste 4 aus observation, gerundet)
            round(observation[0], 2) if len(observation) > 0 else 0,
            round(observation[1], 2) if len(observation) > 1 else 0,
            round(observation[2], 2) if len(observation) > 2 else 0,
            round(observation[3], 2) if len(observation) > 3 else 0,
        ]

        # Hash erstellen
        hash_input = ','.join([f'{x:.2f}' for x in key_features])
        return hashlib.md5(hash_input.encode()).hexdigest()[:8]


class MultiFeedbackSystem:
    """
    Hauptklasse - Verbindet alles:
    - 6 Kriterien Bewertung
    - Reward Manager
    - Feedback Storage
    - Market Context
    """

    def __init__(self,
                 df: pd.DataFrame,
                 reward_manager: RewardManager,
                 storage_path: str = "feedback"):
        """
        Args:
            df: Market Data DataFrame
            reward_manager: Konfigurierter RewardManager
            storage_path: Pfad für Feedback Storage
        """
        self.df = df
        self.reward_manager = reward_manager
        self.storage = FeedbackStorage(base_path=storage_path)
        self.context_collector = MarketContextCollector(df)

        # Aktuelle Session
        self.current_session_id = None
        self.current_session_trades = []

        print(f"[MultiFeedbackSystem] Initialized")
        print(f"  Reward Manager: {len(reward_manager.components)} components")
        print(f"  Storage Path: {storage_path}")

    def start_session(self, session_type: str = 'demo', symbol: str = 'NQ') -> str:
        """
        Startet neue Feedback Session

        Args:
            session_type: 'demo' oder 'training'
            symbol: Trading Symbol

        Returns:
            session_id
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session_id = f"{session_type}_{timestamp}"
        self.current_session_trades = []

        self.session_meta = {
            'session_id': self.current_session_id,
            'session_type': session_type,
            'symbol': symbol,
            'started_at': datetime.now().isoformat()
        }

        print(f"[MultiFeedbackSystem] Started session: {self.current_session_id}")
        return self.current_session_id

    def record_trade(self,
                    trade_id: str,
                    action: str,
                    entry_price: float,
                    sl_price: float,
                    tp_price: float,
                    current_idx: int,
                    observation: np.ndarray,
                    pattern_signals: Dict[str, Any],
                    exit_price: Optional[float] = None,
                    pnl: Optional[float] = None,
                    auto_rewards: Optional[Dict[str, float]] = None) -> TradeRecord:
        """
        Zeichnet Trade auf (OHNE Human Evaluation - kommt später)

        Returns:
            TradeRecord (ohne evaluation, wird später hinzugefügt)
        """
        # Sammle Market Context
        market_context = self.context_collector.collect_context(
            current_idx, observation, pattern_signals
        )

        # Erstelle Trade Record (ohne evaluation)
        trade_record = TradeRecord(
            trade_id=trade_id,
            timestamp=datetime.now().isoformat(),
            action=action,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            exit_price=exit_price,
            pnl=pnl,
            state_hash=market_context['state_hash'],
            observation=market_context['observation'],
            patterns=market_context['patterns'],
            session_info=market_context['session_info'],
            volume_info=market_context['volume'],
            human_evaluation=None,  # Kommt später
            auto_rewards=auto_rewards
        )

        # Zu Session hinzufügen
        self.current_session_trades.append(trade_record)

        print(f"[MultiFeedbackSystem] Recorded trade: {trade_id}")
        return trade_record

    def add_human_evaluation(self,
                           trade_id: str,
                           evaluation: HumanEvaluation) -> bool:
        """
        Fügt Human Evaluation zu Trade hinzu

        Args:
            trade_id: Trade ID
            evaluation: HumanEvaluation Objekt

        Returns:
            True wenn erfolgreich
        """
        # Finde Trade
        for trade in self.current_session_trades:
            if trade.trade_id == trade_id:
                trade.human_evaluation = evaluation

                # Update Reward Manager mit Feedback
                human_component = self.reward_manager.components.get('Human')
                if human_component:
                    # Konvertiere overall_score zu -1 bis +1 Range
                    # 0.0 - 1.0 → -1.0 bis +1.0
                    feedback_score = evaluation.overall_score * 2 - 1

                    # Action zu int
                    action_map = {'buy': 1, 'sell': 2, 'hold': 0}
                    action_int = action_map.get(trade.action, 0)

                    human_component.add_feedback(
                        trade.state_hash,
                        action_int,
                        feedback_score
                    )

                print(f"[MultiFeedbackSystem] Added evaluation to {trade_id}: {evaluation.overall_score:.2f}")
                return True

        print(f"[ERROR] Trade {trade_id} not found")
        return False

    def end_session(self, save: bool = True) -> Dict[str, Any]:
        """
        Beendet Session und speichert

        Args:
            save: Ob Session gespeichert werden soll

        Returns:
            Session Summary
        """
        if not self.current_session_id:
            print("[ERROR] No active session")
            return {}

        # Berechne Summary
        total_trades = len(self.current_session_trades)
        evaluated_trades = sum(1 for t in self.current_session_trades if t.human_evaluation is not None)

        if evaluated_trades > 0:
            avg_score = np.mean([
                t.human_evaluation.overall_score
                for t in self.current_session_trades
                if t.human_evaluation is not None
            ])

            total_pnl = sum([
                t.pnl for t in self.current_session_trades
                if t.pnl is not None
            ])

            winning_trades = sum([
                1 for t in self.current_session_trades
                if t.pnl is not None and t.pnl > 0
            ])
        else:
            avg_score = 0.0
            total_pnl = 0.0
            winning_trades = 0

        summary = {
            'total_trades': total_trades,
            'evaluated_trades': evaluated_trades,
            'avg_evaluation_score': avg_score,
            'total_pnl': total_pnl,
            'winning_trades': winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0
        }

        # Session Data für Storage
        session_data = {
            **self.session_meta,
            'completed_at': datetime.now().isoformat(),
            'trades': [t.to_dict() for t in self.current_session_trades],
            'summary': summary
        }

        # Speichern
        if save:
            if self.session_meta['session_type'] == 'demo':
                path = self.storage.save_demo_session(session_data)
            else:
                # Training Session Format ist etwas anders
                training_data = {
                    **self.session_meta,
                    'completed_at': datetime.now().isoformat(),
                    'training_episodes': [{
                        'episode': 0,
                        'timestep': 0,
                        'trades': [t.to_dict() for t in self.current_session_trades]
                    }],
                    'summary': summary
                }
                path = self.storage.save_training_session(training_data)

            print(f"[MultiFeedbackSystem] Session saved: {path}")

        # Reset
        self.current_session_id = None
        self.current_session_trades = []

        print(f"[MultiFeedbackSystem] Session ended")
        print(f"  Total Trades: {total_trades}")
        print(f"  Evaluated: {evaluated_trades}")
        print(f"  Avg Score: {avg_score:.2f}")
        print(f"  Win Rate: {summary['win_rate']:.1%}")

        return summary

    def get_feedback_hints(self,
                          trade_record: TradeRecord,
                          entry_price: float,
                          sl_price: float,
                          tp_price: float) -> Dict[str, Dict[str, Any]]:
        """
        Generiert Feedback-Hints für UI

        Hilft User konsistent zu bewerten

        Returns:
            Dict mit hints für jedes Kriterium
        """
        hints = {}

        # 1. Entry Timing Hints
        session = trade_record.session_info
        if session['near_open'] or session['near_close']:
            timing_hint = "Bei Session Open/Close - sehr gut!"
            timing_stars = 5
        elif session['session'] != 'none':
            timing_hint = f"Mitten in {session['session']} Session - OK"
            timing_stars = 3
        else:
            timing_hint = "Dead Zone zwischen Sessions - schlecht"
            timing_stars = 1

        hints['entry_timing'] = {
            'hint': timing_hint,
            'suggested_stars': timing_stars,
            'context': session
        }

        # 2. Pattern Recognition Hints
        patterns = trade_record.patterns
        pattern_count = sum([
            patterns.get('in_fvg_zone', False),
            patterns.get('near_support_ob', False),
            patterns.get('near_resistance_ob', False)
        ])

        if pattern_count >= 2:
            pattern_hint = f"{pattern_count} Patterns erkannt - sehr gut!"
            pattern_stars = 5
        elif pattern_count == 1:
            pattern_hint = "1 Pattern erkannt - OK"
            pattern_stars = 3
        else:
            pattern_hint = "Keine klaren Patterns - schwach"
            pattern_stars = 1

        hints['pattern_recognition'] = {
            'hint': pattern_hint,
            'suggested_stars': pattern_stars,
            'patterns': patterns
        }

        # 3. Stop Loss Hints
        sl_distance_pct = abs(entry_price - sl_price) / entry_price * 100

        if sl_distance_pct > 1.0:
            sl_hint = f"SL {sl_distance_pct:.2f}% weit - gut!"
            sl_stars = 5
        elif sl_distance_pct > 0.5:
            sl_hint = f"SL {sl_distance_pct:.2f}% - OK"
            sl_stars = 3
        else:
            sl_hint = f"SL nur {sl_distance_pct:.2f}% - zu eng!"
            sl_stars = 2

        hints['sl_placement'] = {
            'hint': sl_hint,
            'suggested_stars': sl_stars,
            'distance_pct': sl_distance_pct
        }

        # 4. Take Profit Hints
        tp_distance_pct = abs(tp_price - entry_price) / entry_price * 100
        rr_ratio = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0

        if rr_ratio >= 2.0:
            tp_hint = f"R:R {rr_ratio:.1f} - exzellent!"
            tp_stars = 5
        elif rr_ratio >= 1.5:
            tp_hint = f"R:R {rr_ratio:.1f} - gut"
            tp_stars = 4
        elif rr_ratio >= 1.0:
            tp_hint = f"R:R {rr_ratio:.1f} - OK"
            tp_stars = 3
        else:
            tp_hint = f"R:R {rr_ratio:.1f} - zu schlecht!"
            tp_stars = 1

        hints['tp_placement'] = {
            'hint': tp_hint,
            'suggested_stars': tp_stars,
            'rr_ratio': rr_ratio
        }

        # 5. Liquidity Sweeps Hints
        # TODO: Implementiere wenn Sweep Detection da ist
        hints['liquidity_sweeps'] = {
            'hint': "Prüfe ob Sweep erkannt wurde",
            'suggested_stars': 3
        }

        # 6. Volume Hints
        volume = trade_record.volume_info
        if volume['spike']:
            vol_hint = f"Volume Spike ({volume['ratio']:.1f}x) - sehr gut!"
            vol_stars = 5
        elif volume['ratio'] > 1.2:
            vol_hint = f"Erhöhtes Volume ({volume['ratio']:.1f}x) - gut"
            vol_stars = 4
        elif volume['ratio'] > 0.8:
            vol_hint = "Normales Volume - OK"
            vol_stars = 3
        else:
            vol_hint = f"Niedriges Volume ({volume['ratio']:.1f}x) - schlecht"
            vol_stars = 2

        hints['volume_analysis'] = {
            'hint': vol_hint,
            'suggested_stars': vol_stars,
            'ratio': volume['ratio']
        }

        return hints


# Example usage
if __name__ == "__main__":
    from rewards_v2 import create_default_reward_manager

    print("=== Testing Multi-Feedback System ===\n")

    # Create sample data
    dates = pd.date_range('2024-01-01', periods=100, freq='5min')
    df = pd.DataFrame({
        'open': np.random.randn(100).cumsum() + 19400,
        'high': np.random.randn(100).cumsum() + 19420,
        'low': np.random.randn(100).cumsum() + 19380,
        'close': np.random.randn(100).cumsum() + 19400,
        'volume': np.random.randint(1000, 5000, 100)
    }, index=dates)

    # Create Reward Manager
    reward_manager = create_default_reward_manager()

    # Create Multi-Feedback System
    mfs = MultiFeedbackSystem(df, reward_manager)

    # Start Demo Session
    session_id = mfs.start_session('demo', 'NQ')

    # Record a trade
    observation = np.random.randn(30)
    patterns = {
        'in_fvg_zone': True,
        'near_support_ob': True,
        'liquidity_direction': 1,
        'market_structure': 1
    }

    trade = mfs.record_trade(
        trade_id='demo_1',
        action='buy',
        entry_price=19450.0,
        sl_price=19400.0,
        tp_price=19550.0,
        current_idx=50,
        observation=observation,
        pattern_signals=patterns,
        exit_price=19485.0,
        pnl=35.0
    )

    print(f"\nTrade recorded: {trade.trade_id}")
    print(f"  State Hash: {trade.state_hash}")
    print(f"  Session: {trade.session_info['session']}")
    print(f"  Volume Spike: {trade.volume_info['spike']}")

    # Get feedback hints
    hints = mfs.get_feedback_hints(trade, 19450.0, 19400.0, 19550.0)

    print("\n=== Feedback Hints ===")
    for criterion, hint_data in hints.items():
        print(f"{criterion}: {hint_data['hint']} (Suggested: {hint_data['suggested_stars']} stars)")

    # Add human evaluation
    evaluation = HumanEvaluation.from_stars(
        entry_timing_stars=5,
        pattern_stars=5,
        sl_stars=4,
        tp_stars=5,
        liquidity_stars=4,
        volume_stars=5,
        notes="Excellent trade!"
    )

    mfs.add_human_evaluation('demo_1', evaluation)

    # End session
    summary = mfs.end_session(save=True)

    print("\n[SUCCESS] Multi-Feedback System funktioniert!")
