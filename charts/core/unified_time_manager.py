"""
Unified Time Manager
Single Source of Truth für ALLE Zeit-bezogenen Operationen
Koordiniert master_clock, debug_controller, TimeframeSyncManager und global_skip_events
"""

from typing import Dict, Set, List, Any, Optional
from datetime import datetime, timedelta


class UnifiedTimeManager:
    """
    🚀 REVOLUTIONARY: Single Source of Truth für ALLE Zeit-bezogenen Operationen
    Koordiniert master_clock, debug_controller, TimeframeSyncManager und global_skip_events
    """

    def __init__(self):
        # Core Time State - Single Source of Truth
        self.current_debug_time = None  # DIE eine globale Zeit für alle Timeframes
        self.initialized = False

        # Timeframe State Management
        self.active_timeframes: Set[str] = set()  # Welche TF sind gerade aktiv
        self.timeframe_positions: Dict[str, datetime] = {}   # {timeframe: last_loaded_candle_time}

        # Data Validation
        self.last_valid_times: Dict[str, datetime] = {}      # {timeframe: last_known_good_time}
        self.last_operation_source: Optional[str] = None  # Track last operation source for validation

        # ===== SKIP-STATE ISOLATION SYSTEM =====
        # Memento Pattern: Saubere Trennung von Skip-generierten vs CSV-Daten
        self.skip_candles_registry: Dict[str, List[Dict[str, Any]]] = {}  # {timeframe: [skip_generated_candles]}
        self.csv_candles_registry: Dict[str, List[Dict[str, Any]]] = {}   # {timeframe: [csv_source_candles]}
        self.mixed_state_timeframes: Set[str] = set()  # Timeframes mit gemischten Daten

        # Command Pattern: Skip-Operation Tracking für Rollback
        self.skip_operations_history: List[Dict[str, Any]] = []  # Liste aller Skip-Operationen
        self.current_skip_session: Optional[str] = None   # Aktuelle Skip-Session ID

        # State Machine: Skip-Contamination Tracking
        self.contamination_levels: Dict[str, int] = {}     # {timeframe: contamination_level}
        self.CONTAMINATION_LEVELS = {
            'CLEAN': 0,           # Nur CSV-Daten
            'LIGHT': 1,           # 1-2 Skip-Operationen
            'MODERATE': 2,        # 3-5 Skip-Operationen
            'HEAVY': 3,           # 6+ Skip-Operationen, braucht Recreation
            'CRITICAL': 4         # Chart State korrupt, MUSS recreation
        }

        print("[UnifiedTimeManager] Zentrale Zeit-Koordination mit Skip-State Isolation initialisiert")

    def initialize_time(self, initial_time):
        """Initialisiert die globale Zeit - wird vom ersten Skip/GoTo aufgerufen"""
        if isinstance(initial_time, (int, float)):
            initial_time = datetime.fromtimestamp(initial_time)

        self.current_debug_time = initial_time
        self.initialized = True

        # Synchronisiere alle bestehenden Systeme
        self._sync_master_clock()
        self._update_unified_state()

        print(f"[UnifiedTimeManager] Zeit initialisiert: {initial_time}")
        return initial_time

    def advance_time(self, timeframe_minutes, source_timeframe):
        """
        Rückt die globale Zeit um die angegebenen Minuten vor
        Alle Timeframes synchronisieren sich an dieser Zeit
        """
        if not self.initialized:
            raise ValueError("[UnifiedTimeManager] ERROR: Zeit nicht initialisiert - kann nicht vorrücken")

        old_time = self.current_debug_time
        self.current_debug_time += timedelta(minutes=timeframe_minutes)

        # Markiere Source-Timeframe als aktiv
        self.active_timeframes.add(source_timeframe)
        self.timeframe_positions[source_timeframe] = self.current_debug_time

        # Synchronisiere alle Systeme
        self._sync_master_clock()
        self._update_unified_state()
        self._sync_debug_controller()

        print(f"[UnifiedTimeManager] Zeit vorgerückt: {old_time} -> {self.current_debug_time} (+{timeframe_minutes}min via {source_timeframe})")
        return self.current_debug_time

    def set_time(self, new_time, source="direct"):
        """Setzt die Zeit direkt (für GoTo-Operationen)"""
        if isinstance(new_time, (int, float)):
            new_time = datetime.fromtimestamp(new_time)

        old_time = self.current_debug_time
        self.current_debug_time = new_time
        self.initialized = True
        self.last_operation_source = source  # Track source for validation

        # Reset positions für alle Timeframes - sie müssen neu geladen werden
        self.timeframe_positions.clear()

        # Synchronisiere alle Systeme
        self._sync_master_clock()
        self._update_unified_state()
        self._sync_debug_controller()

        print(f"[UnifiedTimeManager] Zeit gesetzt: {old_time} -> {new_time} (via {source})")
        return new_time

    def get_current_time(self):
        """Gibt die aktuelle globale Zeit zurück"""
        return self.current_debug_time

    def validate_candle_time(self, candle_time, timeframe):
        """
        Validiert ob eine Kerze zeitlich zu der globalen Zeit passt
        Verhindert Preisgaps durch falsche Zeitstempel
        """
        if isinstance(candle_time, (int, float)):
            candle_time = datetime.fromtimestamp(candle_time)

        if not self.initialized:
            # Erste Kerze - akzeptieren und Zeit setzen
            self.initialize_time(candle_time)
            return True

        # Toleranz: Kerze darf bis zu TF-Intervall von aktueller Zeit abweichen
        # ERWEITERTE TOLERANZ für Skip-Operationen und nach Go To Date
        tolerance_minutes = self._get_timeframe_minutes(timeframe)

        # Skip-Operationen brauchen erweiterte Toleranz da sie aus CSV-Dataset kommen
        if self.last_operation_source and ("skip" in self.last_operation_source or "go_to_date" in self.last_operation_source):
            # Erweiterte Toleranz für Skip/Go-To-Date Operationen (bis zu 2h)
            tolerance_minutes = max(tolerance_minutes, 120)  # 2 Stunden max für Dataset-Operationen
            print(f"[UnifiedTimeManager] Skip/Go-To-Date Toleranz erweitert: {tolerance_minutes} min")

        min_time = self.current_debug_time - timedelta(minutes=tolerance_minutes)
        max_time = self.current_debug_time + timedelta(minutes=tolerance_minutes)

        is_valid = min_time <= candle_time <= max_time

        if is_valid:
            self.last_valid_times[timeframe] = candle_time
            # KEEP skip sources aktiv für weitere Skip-Operationen
            # Reset nur bei echtem Timeframe-Wechsel oder Manual-Operations
            print(f"[UnifiedTimeManager] Validierung erfolgreich, behalte source: {self.last_operation_source}")
        else:
            print(f"[UnifiedTimeManager] WARNING: Kerze-Zeit Validierung FEHLGESCHLAGEN:")
            print(f"  Kerze: {candle_time} ({timeframe})")
            print(f"  Global: {self.current_debug_time}")
            print(f"  Toleranz: {min_time} - {max_time}")

        return is_valid

    def register_timeframe_activity(self, timeframe, last_candle_time=None):
        """Registriert Aktivität in einem Timeframe"""
        self.active_timeframes.add(timeframe)
        if last_candle_time:
            if isinstance(last_candle_time, (int, float)):
                last_candle_time = datetime.fromtimestamp(last_candle_time)
            self.timeframe_positions[timeframe] = last_candle_time

    def get_timeframe_sync_status(self):
        """Gibt Sync-Status aller Timeframes zurück"""
        if not self.initialized:
            return {"error": "Zeit nicht initialisiert"}

        return {
            "global_time": self.current_debug_time.isoformat(),
            "active_timeframes": list(self.active_timeframes),
            "timeframe_positions": {
                tf: time.isoformat() for tf, time in self.timeframe_positions.items()
            },
            "last_valid_times": {
                tf: time.isoformat() for tf, time in self.last_valid_times.items()
            }
        }

    def _sync_master_clock(self):
        """Synchronisiert den globalen master_clock"""
        # This will be injected from chart_server.py global state
        pass

    def _update_unified_state(self):
        """Synchronisiert unified_state Manager"""
        # This will be injected from chart_server.py global state
        pass

    def _sync_debug_controller(self):
        """Synchronisiert DebugController Zeit"""
        # This will be injected from chart_server.py global state
        pass

    def _get_timeframe_minutes(self, timeframe):
        """Hilfsfunktion: Konvertiert Timeframe zu Minuten"""
        timeframe_map = {
            '1m': 1, '2m': 2, '3m': 3, '5m': 5,
            '15m': 15, '30m': 30, '1h': 60, '4h': 240
        }
        return timeframe_map.get(timeframe, 5)  # Default 5min

    # ===== SKIP-STATE ISOLATION METHODS =====

    def register_skip_candle(self, timeframe, candle, operation_id=None):
        """Registriert Skip-generierte Kerze isoliert von CSV-Daten"""
        if timeframe not in self.skip_candles_registry:
            self.skip_candles_registry[timeframe] = []

        # Erweitere Kerze um Skip-Metadaten
        skip_candle = candle.copy()
        skip_candle['_skip_metadata'] = {
            'source': 'skip_generated',
            'operation_id': operation_id or len(self.skip_operations_history),
            'timestamp': datetime.now().isoformat(),
            'contamination_level': self._calculate_contamination_level(timeframe)
        }

        self.skip_candles_registry[timeframe].append(skip_candle)
        self.mixed_state_timeframes.add(timeframe)

        # Update contamination level
        self._update_contamination_level(timeframe)

        print(f"[SKIP-ISOLATION] Registered skip candle for {timeframe}, contamination: {self.contamination_levels.get(timeframe, 0)}")

    def register_csv_data_load(self, timeframe, candles):
        """Registriert CSV-Daten separat von Skip-Daten mit intelligenter Vollständigkeitsprüfung"""
        # Bereinige alle Skip-Metadaten aus CSV-Daten
        clean_candles = []
        for candle in candles:
            if isinstance(candle, dict):
                clean_candle = {k: v for k, v in candle.items() if not k.startswith('_skip')}
                clean_candle['_data_source'] = 'csv_file'
                clean_candles.append(clean_candle)

        # Prüfe ob bereits eine vollständige Basis existiert
        existing_candles = self.csv_candles_registry.get(timeframe, [])

        # Wenn neue Daten mehr Kerzen haben, aktualisiere die Basis
        if len(clean_candles) > len(existing_candles):
            self.csv_candles_registry[timeframe] = clean_candles
            print(f"[CSV-REGISTRY] Updated {timeframe} basis: {len(clean_candles)} candles")
        elif not existing_candles:
            # Erste Registrierung für diesen Timeframe
            self.csv_candles_registry[timeframe] = clean_candles
            print(f"[CSV-REGISTRY] Registered {timeframe} basis: {len(clean_candles)} candles")
        else:
            print(f"[CSV-REGISTRY] Kept existing {timeframe} basis: {len(existing_candles)} candles (new: {len(clean_candles)})")

    def ensure_full_csv_basis(self, timeframe, timeframe_data_repository):
        """Stellt sicher, dass eine vollständige CSV-Basis für den Timeframe existiert"""
        existing_candles = self.csv_candles_registry.get(timeframe, [])

        # Wenn bereits viele Kerzen vorhanden (> 1000), betrachte als vollständig
        if len(existing_candles) > 1000:
            return existing_candles

        # Lade vollständige CSV-Daten ohne Limit
        print(f"[CSV-REGISTRY] Loading full CSV basis for {timeframe}")
        try:
            # Verwende die Repository-Funktion mit großem Datum-Range und ohne max_candles
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=365)  # 1 Jahr Daten

            full_data = timeframe_data_repository.get_candles_for_date_range(
                timeframe, start_date, end_date, max_candles=None  # Kein Limit!
            )

            if full_data and len(full_data) > len(existing_candles):
                self.register_csv_data_load(timeframe, full_data)
                print(f"[CSV-REGISTRY] Loaded full {timeframe} basis: {len(full_data)} candles")
                return full_data
            else:
                print(f"[CSV-REGISTRY] Using existing {timeframe} basis: {len(existing_candles)} candles")
                return existing_candles

        except Exception as e:
            print(f"[CSV-REGISTRY] Error loading full basis for {timeframe}: {e}")
            return existing_candles

    def get_mixed_chart_data(self, timeframe, max_candles=200):
        """Intelligente Mischung von CSV + Skip-Daten mit Konflikt-Resolution + Vollständige Basis"""
        # Stelle sicher, dass eine vollständige CSV-Basis existiert
        csv_candles = self.csv_candles_registry.get(timeframe, [])
        skip_candles = self.skip_candles_registry.get(timeframe, [])

        print(f"[MIXED-DATA] Processing {timeframe}: {len(csv_candles)} CSV + {len(skip_candles)} skip candles")

        if not skip_candles:
            # Nur CSV-Daten, kein Mixing nötig
            return csv_candles[-max_candles:] if len(csv_candles) > max_candles else csv_candles

        # STRATEGY: Skip-Kerzen haben Priorität über CSV-Kerzen zur gleichen Zeit
        mixed_data = csv_candles.copy()

        for skip_candle in skip_candles:
            skip_time = skip_candle.get('time')
            if skip_time:
                # Suche CSV-Kerze zur gleichen Zeit
                existing_index = None
                for i, csv_candle in enumerate(mixed_data):
                    if csv_candle.get('time') == skip_time:
                        existing_index = i
                        break

                if existing_index is not None:
                    # Ersetze CSV-Kerze mit Skip-Kerze
                    mixed_data[existing_index] = skip_candle
                    print(f"[SKIP-ISOLATION] Replaced CSV candle at time {skip_time} with skip candle")
                else:
                    # Füge Skip-Kerze hinzu und sortiere
                    mixed_data.append(skip_candle)

        # Sortiere nach Zeit und begrenze
        mixed_data.sort(key=lambda x: x.get('time', 0))
        result = mixed_data[-max_candles:] if len(mixed_data) > max_candles else mixed_data

        print(f"[SKIP-ISOLATION] Mixed data for {timeframe}: {len(csv_candles)} CSV + {len(skip_candles)} skip = {len(result)} total")
        return result

    def clear_timeframe_skip_data(self, timeframe):
        """Löscht Skip-Daten für einen Timeframe (bei Go To Date)"""
        if timeframe in self.skip_candles_registry:
            del self.skip_candles_registry[timeframe]
        if timeframe in self.contamination_levels:
            del self.contamination_levels[timeframe]
        self.mixed_state_timeframes.discard(timeframe)

        print(f"[SKIP-ISOLATION] Cleared skip data for {timeframe}")

    def clear_all_skip_data(self):
        """Löscht alle Skip-Daten (bei globalem Go To Date)"""
        self.skip_candles_registry.clear()
        self.contamination_levels.clear()
        self.mixed_state_timeframes.clear()
        self.skip_operations_history.clear()

        print("[SKIP-ISOLATION] Cleared ALL skip data - reset to clean state")

    def get_contamination_analysis(self):
        """Analysiert Contamination aller Timeframes für Debugging"""
        analysis = {}
        for timeframe in self.mixed_state_timeframes:
            csv_count = len(self.csv_candles_registry.get(timeframe, []))
            skip_count = len(self.skip_candles_registry.get(timeframe, []))
            contamination = self.contamination_levels.get(timeframe, 0)

            analysis[timeframe] = {
                'csv_candles': csv_count,
                'skip_candles': skip_count,
                'contamination_level': contamination,
                'contamination_label': self._get_contamination_label(contamination),
                'needs_recreation': contamination >= self.CONTAMINATION_LEVELS['HEAVY']
            }

        return analysis

    def _calculate_contamination_level(self, timeframe):
        """Berechnet Contamination Level basierend auf Skip-Operationen"""
        skip_count = len(self.skip_candles_registry.get(timeframe, []))

        if skip_count == 0:
            return self.CONTAMINATION_LEVELS['CLEAN']
        elif skip_count <= 2:
            return self.CONTAMINATION_LEVELS['LIGHT']
        elif skip_count <= 5:
            return self.CONTAMINATION_LEVELS['MODERATE']
        else:
            return self.CONTAMINATION_LEVELS['HEAVY']

    def _update_contamination_level(self, timeframe):
        """Aktualisiert Contamination Level für einen Timeframe"""
        self.contamination_levels[timeframe] = self._calculate_contamination_level(timeframe)

    def _get_contamination_label(self, level):
        """Konvertiert Contamination Level zu lesbarem Label"""
        for label, value in self.CONTAMINATION_LEVELS.items():
            if value == level:
                return label
        return 'UNKNOWN'


# ===== TEMPORAL STATE COMMAND PATTERN =====
class TemporalCommand:
    """
    🚀 Command Pattern für atomische Zeit-Operationen mit Rollback-Capability
    Verhindert inkonsistente Multi-Timeframe Zeit-States
    """

    def __init__(self, operation_type, target_time, timeframe=None, source=None):
        self.operation_type = operation_type  # 'skip', 'goto', 'tf_switch'
        self.target_time = target_time
        self.timeframe = timeframe
        self.source = source or "temporal_command"
        self.timestamp = datetime.now()

        # Rollback state
        self.previous_time = None
        self.previous_source = None
        self.executed = False

    def execute(self, time_manager):
        """Führt die Zeit-Operation atomic aus"""
        # Backup current state for rollback
        self.previous_time = time_manager.get_current_time()
        self.previous_source = getattr(time_manager, 'last_operation_source', None)

        # Execute operation
        time_manager.set_time(self.target_time, source=self.source)
        self.executed = True

        print(f"[TEMPORAL-CMD] Executed {self.operation_type}: {self.previous_time} -> {self.target_time}")
        return True

    def rollback(self, time_manager):
        """Rollback der Operation bei Fehlern"""
        if not self.executed:
            return False

        time_manager.set_time(self.previous_time, source=self.previous_source or "rollback")
        self.executed = False

        print(f"[TEMPORAL-CMD] Rollback {self.operation_type}: {self.target_time} -> {self.previous_time}")
        return True


class TemporalOperationManager:
    """
    Manager für atomische Multi-Timeframe Operationen
    Koordiniert Skip + TF-Switch als eine einzige Transaction
    """

    def __init__(self, time_manager):
        self.time_manager = time_manager
        self.operation_history = []
        self.current_transaction = None

    def begin_transaction(self, transaction_id=None):
        """Startet eine neue atomische Zeit-Transaction"""
        self.current_transaction = {
            'id': transaction_id or f"temporal_tx_{int(datetime.now().timestamp())}",
            'commands': [],
            'started_at': datetime.now()
        }
        print(f"[TEMPORAL-TX] Transaction started: {self.current_transaction['id']}")

    def add_skip_and_tf_switch(self, skip_time, target_timeframe):
        """Fügt Skip + TF-Switch als atomische Operation hinzu"""
        if not self.current_transaction:
            self.begin_transaction()

        # Command 1: Skip-Operation
        skip_cmd = TemporalCommand('skip', skip_time, source=f"skip_tf_switch_{target_timeframe}")
        self.current_transaction['commands'].append(skip_cmd)

        print(f"[TEMPORAL-TX] Added skip+tf_switch: {skip_time} -> {target_timeframe}")

    def commit_transaction(self):
        """Führt alle Commands der Transaction atomic aus"""
        if not self.current_transaction:
            return False

        try:
            # Execute all commands
            for cmd in self.current_transaction['commands']:
                cmd.execute(self.time_manager)

            # Success: Add to history
            self.operation_history.append(self.current_transaction)
            print(f"[TEMPORAL-TX] Transaction committed: {self.current_transaction['id']}")
            self.current_transaction = None
            return True

        except Exception as e:
            # Rollback on error
            print(f"[TEMPORAL-TX] Transaction failed: {e}")
            self.rollback_transaction()
            return False

    def rollback_transaction(self):
        """Rollback der aktuellen Transaction"""
        if not self.current_transaction:
            return False

        # Rollback in reverse order
        for cmd in reversed(self.current_transaction['commands']):
            if cmd.executed:
                cmd.rollback(self.time_manager)

        print(f"[TEMPORAL-TX] Transaction rolled back: {self.current_transaction['id']}")
        self.current_transaction = None
        return True
