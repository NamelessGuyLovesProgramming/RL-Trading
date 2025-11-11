"""
Feedback Storage System
Speichert Human Feedback in JSON, SQLite und Pickle für konsistente Nutzung
"""

import json
import pickle
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class HumanEvaluation:
    """6 Kriterien für Trade-Bewertung"""
    entry_timing: float  # 0.0 - 1.0 (1 Stern = 0.2, 5 Sterne = 1.0)
    pattern_recognition: float
    sl_placement: float
    tp_placement: float
    liquidity_sweeps: float
    volume_analysis: float
    overall_score: float  # Durchschnitt
    notes: str = ""

    @property
    def entry_timing_stars(self) -> int:
        """Konvertiert Score zu Sternen"""
        return int(self.entry_timing * 5)

    @property
    def pattern_stars(self) -> int:
        return int(self.pattern_recognition * 5)

    @property
    def sl_stars(self) -> int:
        return int(self.sl_placement * 5)

    @property
    def tp_stars(self) -> int:
        return int(self.tp_placement * 5)

    @property
    def liquidity_stars(self) -> int:
        return int(self.liquidity_sweeps * 5)

    @property
    def volume_stars(self) -> int:
        return int(self.volume_analysis * 5)

    @classmethod
    def from_stars(cls,
                   entry_timing_stars: int,
                   pattern_stars: int,
                   sl_stars: int,
                   tp_stars: int,
                   liquidity_stars: int,
                   volume_stars: int,
                   notes: str = "") -> 'HumanEvaluation':
        """Erstellt Evaluation aus Sterne-Bewertung (1-5)"""
        scores = [
            entry_timing_stars / 5.0,
            pattern_stars / 5.0,
            sl_stars / 5.0,
            tp_stars / 5.0,
            liquidity_stars / 5.0,
            volume_stars / 5.0
        ]
        overall = np.mean(scores)

        return cls(
            entry_timing=scores[0],
            pattern_recognition=scores[1],
            sl_placement=scores[2],
            tp_placement=scores[3],
            liquidity_sweeps=scores[4],
            volume_analysis=scores[5],
            overall_score=overall,
            notes=notes
        )

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary für JSON"""
        return {
            'entry_timing': {
                'stars': self.entry_timing_stars,
                'score': self.entry_timing
            },
            'pattern_recognition': {
                'stars': self.pattern_stars,
                'score': self.pattern_recognition
            },
            'sl_placement': {
                'stars': self.sl_stars,
                'score': self.sl_placement
            },
            'tp_placement': {
                'stars': self.tp_stars,
                'score': self.tp_placement
            },
            'liquidity_sweeps': {
                'stars': self.liquidity_stars,
                'score': self.liquidity_sweeps
            },
            'volume_analysis': {
                'stars': self.volume_stars,
                'score': self.volume_analysis
            },
            'overall_score': self.overall_score,
            'notes': self.notes
        }


@dataclass
class TradeRecord:
    """Kompletter Trade-Record mit Market Context und Evaluation"""
    trade_id: str
    timestamp: str
    action: str  # 'buy', 'sell', 'hold'
    entry_price: float
    sl_price: float
    tp_price: float
    exit_price: Optional[float]
    pnl: Optional[float]

    # Market Context
    state_hash: str
    observation: List[float]
    patterns: Dict[str, Any]
    session_info: Dict[str, Any]
    volume_info: Dict[str, Any]

    # Human Evaluation
    human_evaluation: HumanEvaluation

    # Auto Rewards (optional, für Vergleich)
    auto_rewards: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary für JSON"""
        return {
            'trade_id': self.trade_id,
            'timestamp': self.timestamp,
            'action': self.action,
            'entry_price': self.entry_price,
            'sl_price': self.sl_price,
            'tp_price': self.tp_price,
            'exit_price': self.exit_price,
            'pnl': self.pnl,
            'market_context': {
                'state_hash': self.state_hash,
                'observation': self.observation,
                'patterns': self.patterns,
                'session_info': self.session_info,
                'volume': self.volume_info
            },
            'human_evaluation': self.human_evaluation.to_dict(),
            'auto_rewards': self.auto_rewards
        }


class FeedbackStorage:
    """
    Verwaltet alle Feedback-Daten
    - JSON: Menschen-lesbar
    - SQLite: Schnelle Abfragen
    - Pickle: Schnelles Laden
    """

    def __init__(self, base_path: str = "feedback"):
        self.base_path = Path(base_path)
        self.demo_path = self.base_path / "demo_sessions"
        self.training_path = self.base_path / "training_feedback"
        self.db_path = self.base_path / "human_patterns.db"

        # Erstelle Verzeichnisse
        self.demo_path.mkdir(parents=True, exist_ok=True)
        self.training_path.mkdir(parents=True, exist_ok=True)

        # Initialisiere Datenbank
        self.init_database()

        print(f"[FeedbackStorage] Initialized at {self.base_path}")
        print(f"[FeedbackStorage] Database: {self.db_path}")

    def init_database(self):
        """Initialisiert SQLite Datenbank"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state_hash TEXT NOT NULL,
                action TEXT NOT NULL,

                -- OLD Market Context Features (kept for backward compatibility)
                in_fvg_zone BOOLEAN,
                fvg_distance REAL,
                near_support_ob BOOLEAN,
                near_resistance_ob BOOLEAN,
                liquidity_direction INTEGER,
                market_structure INTEGER,
                session_type TEXT,
                time_in_session INTEGER,
                volume_spike BOOLEAN,
                volume_ratio REAL,

                -- OLD Human Evaluation Scores (kept for backward compatibility)
                entry_timing_score REAL,
                pattern_score REAL,
                sl_score REAL,
                tp_score REAL,
                liquidity_score REAL,
                volume_score REAL,
                overall_score REAL,

                -- Trade Details (Basic Features 1-9)
                entry_price REAL,
                sl_price REAL,
                tp_price REAL,
                exit_price REAL,
                pnl REAL,
                entry_time TEXT,
                exit_time TEXT,
                trade_duration_candles INTEGER,
                max_drawdown_pct REAL,

                -- NEW: Market Context Features (10-16)
                distance_to_ema20_pct REAL,
                atr_value REAL,
                recent_high_distance_pct REAL,
                recent_low_distance_pct REAL,
                position_in_range REAL,
                rr_ratio REAL,

                -- NEW: Simple Human Rating (Feature 17)
                rating REAL,

                -- Meta
                source TEXT,
                session_id TEXT,
                trade_id TEXT,
                timestamp DATETIME,
                notes TEXT,
                patterns TEXT,
                session_info TEXT,
                volume_info TEXT
            )
        """)

        # Indices für schnelle Abfragen
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_state_hash ON feedback_patterns(state_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_action ON feedback_patterns(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_overall_score ON feedback_patterns(overall_score)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON feedback_patterns(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON feedback_patterns(source)")

        conn.commit()
        conn.close()

        print("[FeedbackStorage] Database initialized with indices")

        # Run migration to add new columns if they don't exist
        self._migrate_database()

    def _migrate_database(self):
        """Migriert bestehende Datenbank - fügt neue 17-Feature Spalten hinzu"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check which columns exist
        cursor.execute("PRAGMA table_info(feedback_patterns)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # New columns to add (17 Feature System)
        new_columns = {
            'entry_time': 'TEXT',
            'exit_time': 'TEXT',
            'trade_duration_candles': 'INTEGER',
            'max_drawdown_pct': 'REAL',
            'distance_to_ema20_pct': 'REAL',
            'atr_value': 'REAL',
            'recent_high_distance_pct': 'REAL',
            'recent_low_distance_pct': 'REAL',
            'position_in_range': 'REAL',
            'rr_ratio': 'REAL',
            'rating': 'REAL',
            'patterns': 'TEXT',
            'session_info': 'TEXT',
            'volume_info': 'TEXT'
        }

        # Add missing columns
        added_columns = []
        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE feedback_patterns ADD COLUMN {col_name} {col_type}")
                    added_columns.append(col_name)
                except sqlite3.OperationalError as e:
                    # Column might already exist, ignore
                    pass

        conn.commit()
        conn.close()

        if added_columns:
            print(f"[FeedbackStorage] Migration: Added {len(added_columns)} new columns")
            print(f"[FeedbackStorage] New columns: {', '.join(added_columns)}")
        else:
            print("[FeedbackStorage] Migration: Database schema up-to-date")

    def save_demo_session(self, session_data: Dict[str, Any]) -> str:
        """
        Speichert Demo Session

        Args:
            session_data: Dict mit session_id, trades, summary

        Returns:
            Path zur gespeicherten JSON Datei
        """
        session_id = session_data['session_id']

        # 1. JSON File (Menschen-lesbar)
        json_path = self.demo_path / f"{session_id}.json"
        with open(json_path, 'w') as f:
            json.dump(session_data, f, indent=2)

        # 2. SQLite (für schnelle KI-Abfragen)
        for trade in session_data.get('trades', []):
            self._insert_feedback_pattern(
                trade=trade,
                source='demo',
                session_id=session_id
            )

        # 3. Pickle - Append zu aggregated file
        pkl_path = self.demo_path / "aggregated_demos.pkl"
        self._append_to_pickle(pkl_path, session_data)

        print(f"[OK] Demo Session gespeichert: {json_path}")
        return str(json_path)

    def save_training_feedback(self, trade_data: Dict[str, Any]) -> str:
        """
        Speichert einzelnes Training Feedback

        Args:
            trade_data: Dict mit trade_id, timestamp, action, prices, evaluation etc.

        Returns:
            Path zur gespeicherten JSON Datei
        """
        trade_id = trade_data.get('trade_id', f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        # JSON
        json_path = self.training_path / f"{trade_id}.json"
        with open(json_path, 'w') as f:
            json.dump(trade_data, f, indent=2)

        # SQLite
        self._insert_feedback_pattern(
            trade=trade_data,
            source='training',
            session_id=trade_data.get('session_id', 'training_session')
        )

        print(f"[OK] Training Feedback gespeichert: {json_path}")
        return str(json_path)

    def save_training_session(self, session_data: Dict[str, Any]) -> str:
        """Speichert Training Session (gleiche Struktur wie Demo)"""
        session_id = session_data['session_id']

        # JSON
        json_path = self.training_path / f"{session_id}.json"
        with open(json_path, 'w') as f:
            json.dump(session_data, f, indent=2)

        # SQLite
        for episode in session_data.get('training_episodes', []):
            for trade in episode.get('trades', []):
                self._insert_feedback_pattern(
                    trade=trade,
                    source='training',
                    session_id=session_id
                )

        # Pickle
        pkl_path = self.training_path / "aggregated_training.pkl"
        self._append_to_pickle(pkl_path, session_data)

        print(f"[OK] Training Session gespeichert: {json_path}")
        return str(json_path)

    def _insert_feedback_pattern(self, trade: Dict[str, Any], source: str, session_id: str):
        """Fügt Trade in SQLite Datenbank ein"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        market_ctx = trade.get('market_context', {})
        patterns = market_ctx.get('patterns', {})
        session_info = market_ctx.get('session_info', {})
        volume = market_ctx.get('volume', {})
        human_eval = trade.get('human_evaluation', {})

        # NEW: Extract 17 features
        features = trade.get('features', {})

        # Serialize JSON fields
        import json
        patterns_json = json.dumps(patterns) if patterns else None
        session_json = json.dumps(session_info) if session_info else None
        volume_json = json.dumps(volume) if volume else None

        cursor.execute("""
            INSERT INTO feedback_patterns (
                state_hash, action,
                in_fvg_zone, fvg_distance, near_support_ob, near_resistance_ob,
                liquidity_direction, market_structure,
                session_type, time_in_session,
                volume_spike, volume_ratio,
                entry_timing_score, pattern_score, sl_score,
                tp_score, liquidity_score, volume_score, overall_score,
                entry_price, sl_price, tp_price, exit_price, pnl,
                entry_time, exit_time, trade_duration_candles, max_drawdown_pct,
                distance_to_ema20_pct, atr_value, recent_high_distance_pct,
                recent_low_distance_pct, position_in_range, rr_ratio,
                rating,
                patterns, session_info, volume_info,
                source, session_id, trade_id, timestamp, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market_ctx.get('state_hash'),
            trade.get('action'),
            # OLD features (backward compatibility)
            patterns.get('in_fvg_zone', False),
            patterns.get('fvg_distance', 0.0),
            patterns.get('near_support_ob', False),
            patterns.get('near_resistance_ob', False),
            patterns.get('liquidity_direction', 0),
            patterns.get('market_structure', 0),
            session_info.get('session', ''),
            session_info.get('time_in_session', 0),
            volume.get('spike', False),
            volume.get('ratio', 1.0),
            # OLD evaluation scores (backward compatibility)
            human_eval.get('entry_timing', {}).get('score', 0.0),
            human_eval.get('pattern_recognition', {}).get('score', 0.0),
            human_eval.get('sl_placement', {}).get('score', 0.0),
            human_eval.get('tp_placement', {}).get('score', 0.0),
            human_eval.get('liquidity_sweeps', {}).get('score', 0.0),
            human_eval.get('volume_analysis', {}).get('score', 0.0),
            human_eval.get('overall_score', 0.0),
            # Trade Basic Features (1-9)
            trade.get('entry_price', 0.0),
            trade.get('sl_price', 0.0),
            trade.get('tp_price', 0.0),
            trade.get('exit_price'),
            trade.get('pnl'),
            features.get('entry_time'),
            features.get('exit_time'),
            features.get('trade_duration_candles'),
            features.get('max_drawdown_pct'),
            # Market Context Features (10-16)
            features.get('distance_to_ema20_pct'),
            features.get('atr_value'),
            features.get('recent_high_distance_pct'),
            features.get('recent_low_distance_pct'),
            features.get('position_in_range'),
            features.get('rr_ratio'),
            # Simple Rating (17)
            features.get('rating'),
            # JSON fields
            patterns_json,
            session_json,
            volume_json,
            # Meta
            source,
            session_id,
            trade.get('trade_id'),
            trade.get('timestamp'),
            human_eval.get('notes', '')
        ))

        conn.commit()
        conn.close()

    def _append_to_pickle(self, pkl_path: Path, data: Dict[str, Any]):
        """Fügt Daten zu Pickle-File hinzu"""
        existing_data = []

        # Lade existierende Daten
        if pkl_path.exists():
            try:
                with open(pkl_path, 'rb') as f:
                    existing_data = pickle.load(f)
            except:
                existing_data = []

        # Append neue Daten
        if isinstance(existing_data, list):
            existing_data.append(data)
        else:
            existing_data = [existing_data, data]

        # Speichere
        with open(pkl_path, 'wb') as f:
            pickle.dump(existing_data, f)

    def get_similar_situations(self, state_hash: str, action: Optional[str] = None,
                               min_score: float = 0.0, limit: int = 10) -> List[Dict]:
        """
        Holt ähnliche Situationen aus Datenbank

        Args:
            state_hash: State Hash zum Suchen
            action: Optional - filter nach Aktion
            min_score: Minimaler overall_score
            limit: Maximale Anzahl Ergebnisse

        Returns:
            Liste von Trade-Records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if action:
            query = """
                SELECT * FROM feedback_patterns
                WHERE state_hash = ? AND action = ? AND overall_score >= ?
                ORDER BY overall_score DESC
                LIMIT ?
            """
            cursor.execute(query, (state_hash, action, min_score, limit))
        else:
            query = """
                SELECT * FROM feedback_patterns
                WHERE state_hash = ? AND overall_score >= ?
                ORDER BY overall_score DESC
                LIMIT ?
            """
            cursor.execute(query, (state_hash, min_score, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_best_action_for_state(self, state_hash: str) -> Dict[str, Any]:
        """
        Findet beste Aktion für gegebenen State

        Returns:
            Dict mit action, avg_score, count
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT
                action,
                AVG(overall_score) as avg_score,
                COUNT(*) as count
            FROM feedback_patterns
            WHERE state_hash = ?
            GROUP BY action
            ORDER BY avg_score DESC
            LIMIT 1
        """

        cursor.execute(query, (state_hash,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'action': result[0],
                'avg_score': result[1],
                'count': result[2]
            }
        return {'action': None, 'avg_score': 0.0, 'count': 0}

    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Holt Statistiken für eine Session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT
                COUNT(*) as total_trades,
                AVG(overall_score) as avg_score,
                AVG(entry_timing_score) as avg_entry_timing,
                AVG(pattern_score) as avg_pattern,
                AVG(sl_score) as avg_sl,
                AVG(tp_score) as avg_tp,
                AVG(liquidity_score) as avg_liquidity,
                AVG(volume_score) as avg_volume,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(pnl) as total_pnl
            FROM feedback_patterns
            WHERE session_id = ?
        """

        cursor.execute(query, (session_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            total = result[0]
            return {
                'total_trades': total,
                'avg_score': result[1],
                'avg_entry_timing': result[2],
                'avg_pattern': result[3],
                'avg_sl': result[4],
                'avg_tp': result[5],
                'avg_liquidity': result[6],
                'avg_volume': result[7],
                'winning_trades': result[8],
                'win_rate': result[8] / total if total > 0 else 0,
                'total_pnl': result[9]
            }

        return {}

    def load_demo_sessions(self) -> List[Dict[str, Any]]:
        """Lädt alle Demo Sessions aus Pickle"""
        pkl_path = self.demo_path / "aggregated_demos.pkl"

        if pkl_path.exists():
            with open(pkl_path, 'rb') as f:
                return pickle.load(f)

        return []

    def load_training_sessions(self) -> List[Dict[str, Any]]:
        """Lädt alle Training Sessions aus Pickle"""
        pkl_path = self.training_path / "aggregated_training.pkl"

        if pkl_path.exists():
            with open(pkl_path, 'rb') as f:
                return pickle.load(f)

        return []

    def delete_training_feedback(self, trade_id: str) -> bool:
        """
        Löscht Feedback für einen spezifischen Trade

        Args:
            trade_id: ID des zu löschenden Trades

        Returns:
            True wenn erfolgreich gelöscht, False wenn nicht gefunden
        """
        # 1. Aus SQLite löschen
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM feedback_patterns WHERE trade_id = ?", (trade_id,))
        rows_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        # 2. JSON File löschen
        json_path = self.training_path / f"{trade_id}.json"
        if json_path.exists():
            json_path.unlink()
            print(f"[OK] Deleted training feedback JSON: {json_path.name}")

        # 3. Pickle Cache invalidieren (wird beim nächsten save neu erstellt)
        pkl_path = self.training_path / "aggregated_training.pkl"
        if pkl_path.exists():
            pkl_path.unlink()
            print(f"[OK] Invalidated training pickle cache")

        if rows_deleted > 0:
            print(f"[OK] Deleted feedback for trade: {trade_id}")
            return True
        else:
            print(f"[WARNING] No feedback found for trade: {trade_id}")
            return False

    def delete_demo_session(self, session_id: str) -> bool:
        """
        Löscht eine Demo Session

        Args:
            session_id: ID der zu löschenden Session

        Returns:
            True wenn erfolgreich gelöscht, False wenn nicht gefunden
        """
        # 1. Aus SQLite löschen (alle Trades dieser Session)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM feedback_patterns WHERE session_id = ?", (session_id,))
        rows_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        # 2. JSON File löschen
        json_path = self.demo_path / f"{session_id}.json"
        if json_path.exists():
            json_path.unlink()
            print(f"[OK] Deleted demo session JSON: {json_path.name}")

        # 3. Pickle Cache invalidieren
        pkl_path = self.demo_path / "aggregated_demos.pkl"
        if pkl_path.exists():
            pkl_path.unlink()
            print(f"[OK] Invalidated demo pickle cache")

        if rows_deleted > 0:
            print(f"[OK] Deleted demo session: {session_id}")
            return True
        else:
            print(f"[WARNING] No demo session found: {session_id}")
            return False

    def list_all_feedback(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Listet alle gespeicherten Feedbacks auf

        Args:
            limit: Maximale Anzahl an Einträgen

        Returns:
            Liste von Feedback-Einträgen mit Metadaten
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT
                trade_id,
                timestamp,
                action,
                entry_price,
                pnl,
                overall_score,
                session_id
            FROM feedback_patterns
            ORDER BY timestamp DESC
            LIMIT ?
        """

        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        conn.close()

        feedback_list = []
        for row in rows:
            feedback_list.append({
                'trade_id': row[0],
                'timestamp': row[1],
                'action': row[2],
                'entry_price': row[3],
                'pnl': row[4],
                'overall_score': row[5],
                'session_id': row[6] if row[6] else 'training'
            })

        return feedback_list


# Example usage
if __name__ == "__main__":
    # Initialisiere Storage
    storage = FeedbackStorage()

    # Test: Demo Session erstellen
    demo_session = {
        'session_id': f'demo_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        'started_at': datetime.now().isoformat(),
        'symbol': 'NQ',
        'trades': [
            {
                'trade_id': 'demo_1',
                'timestamp': datetime.now().isoformat(),
                'action': 'buy',
                'entry_price': 19450.50,
                'sl_price': 19400.00,
                'tp_price': 19550.00,
                'exit_price': 19485.00,
                'pnl': 34.50,
                'market_context': {
                    'state_hash': 'a3f8c2d1',
                    'observation': [0.1] * 30,
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
                        'time_in_session': 145
                    },
                    'volume': {
                        'spike': True,
                        'ratio': 1.8
                    }
                },
                'human_evaluation': HumanEvaluation.from_stars(
                    entry_timing_stars=5,
                    pattern_stars=4,
                    sl_stars=3,
                    tp_stars=5,
                    liquidity_stars=4,
                    volume_stars=4,
                    notes="Sehr guter Entry, SL könnte weiter sein"
                ).to_dict()
            }
        ],
        'summary': {
            'total_trades': 1,
            'avg_evaluation_score': 0.83
        }
    }

    # Speichere
    path = storage.save_demo_session(demo_session)
    print(f"\nDemo Session gespeichert: {path}")

    # Test: Abfrage
    similar = storage.get_similar_situations('a3f8c2d1', action='buy')
    print(f"\nÄhnliche Situationen gefunden: {len(similar)}")

    best_action = storage.get_best_action_for_state('a3f8c2d1')
    print(f"\nBeste Aktion für State: {best_action}")

    print("\n[SUCCESS] Feedback Storage System funktioniert!")
