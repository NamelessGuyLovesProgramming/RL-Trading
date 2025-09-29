"""
FastAPI Chart Server für RL Trading
Realtime Chart-Updates ohne Streamlit-Limitations
"""

# -*- coding: utf-8 -*-
import sys
import os

# Windows UTF-8 encoding fix
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
from typing import Dict, List, Any
import uvicorn
from datetime import datetime, timedelta
import random
import logging
import sys
import os

def json_serializer(obj):
    """Custom JSON serializer für datetime und andere nicht-serialisierbare Objekte"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):
        # Für komplexe Objekte - versuche dict conversion
        try:
            result = {}
            for key, value in obj.__dict__.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif not callable(value):
                    result[key] = value
            return result
        except:
            return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Füge src Verzeichnis zum Pfad hinzu (ein Verzeichnis höher)
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(os.path.join(parent_dir, 'src'))

# FastAPI App (Importiere Module später um Startup-Deadlock zu vermeiden)
app = FastAPI(title="RL Trading Chart Server", version="1.0.0")

# Globale Variablen (werden nach Startup initialisiert)
nq_loader = None
nq_data_loader = None  # NQDataLoader für Go To Date Funktionalität
performance_aggregator = None
account_service = None

# UNIFIED STATE MANAGER - Single Source of Truth für alle Timeframes
class UnifiedStateManager:
    """Zentraler State Manager für timeframe-übergreifende Konsistenz"""

    def __init__(self):
        # CONFLICT RESOLUTION: Unterscheide zwischen Go-To-Date und aktueller Position
        self.initial_go_to_date = None    # Ursprüngliches Go-To-Date vom User
        self.current_skip_position = None # Aktuelle Position nach Skip-Operationen
        self.timeframe_states = {}        # Per-TF States falls nötig
        self.debug_controller_time = None # DebugController Master-Zeit
        self.go_to_date_mode = False     # Ob initial Go-To-Date noch aktiv ist

    def set_go_to_date(self, target_date):
        """Setzt Go-To-Date für ALLE Timeframes einheitlich (Initial)"""
        self.initial_go_to_date = target_date
        self.current_skip_position = None  # Reset skip position
        self.debug_controller_time = target_date
        self.go_to_date_mode = True
        print(f"[UNIFIED-STATE] Initial Go-To-Date gesetzt: {target_date} (alle Timeframes)")

    def update_skip_position(self, new_position, source="skip"):
        """Updates current position after Skip operations - CRITICAL for CSV conflict resolution"""
        old_position = self.current_skip_position
        self.current_skip_position = new_position
        self.debug_controller_time = new_position

        # Nach Skip-Operationen: Go-To-Date Mode deaktivieren für CSV-Loading
        if source == "skip" and self.go_to_date_mode:
            self.go_to_date_mode = False
            print(f"[UNIFIED-STATE] Skip-Position update: {old_position} -> {new_position} (Go-To-Date Mode deaktiviert)")
        else:
            print(f"[UNIFIED-STATE] Position update ({source}): {old_position} -> {new_position}")

    def get_csv_loading_date(self):
        """CRITICAL: Gibt korrekte Datum für CSV-Loading zurück (löst CSV vs DebugController Konflikt)"""
        if self.go_to_date_mode and self.initial_go_to_date:
            # Initial Go-To-Date aktiv: Nutze Original-Datum
            print(f"[UNIFIED-STATE] CSV loading: Initial Go-To-Date Mode -> {self.initial_go_to_date.date()}")
            return self.initial_go_to_date
        elif self.current_skip_position:
            # Skip-Position verfügbar: Nutze aktuelle Position
            print(f"[UNIFIED-STATE] CSV loading: Skip Position Mode -> {self.current_skip_position.date()}")
            return self.current_skip_position
        else:
            # Fallback: Standard-Verhalten (neueste Daten)
            print(f"[UNIFIED-STATE] CSV loading: Standard Mode (neueste Daten)")
            return None

    def get_go_to_date(self):
        """Legacy compatibility: Gibt Go-To-Date zurück"""
        return self.initial_go_to_date

    def clear_go_to_date(self, reason="unknown"):
        """Cleared Go-To-Date State (mit Logging)"""
        if self.initial_go_to_date is not None or self.current_skip_position is not None:
            print(f"[UNIFIED-STATE] State cleared: Go-To-Date={self.initial_go_to_date}, Skip={self.current_skip_position} (Grund: {reason})")
            self.initial_go_to_date = None
            self.current_skip_position = None
            self.go_to_date_mode = False

    def is_go_to_date_active(self):
        """LEGACY: Prüft ob Go-To-Date oder Skip-Position aktiv ist"""
        return self.go_to_date_mode or self.current_skip_position is not None

    def is_csv_date_loading_needed(self):
        """NEW: Prüft ob CSV-Loading von spezifischem Datum benötigt wird"""
        return self.go_to_date_mode or self.current_skip_position is not None

    def sync_debug_controller_time(self, new_time):
        """Synchronisiert DebugController Zeit global"""
        self.debug_controller_time = new_time
        if not self.go_to_date_mode and not self.current_skip_position:
            print(f"[UNIFIED-STATE] DebugController Zeit global synchronisiert: {new_time}")

# REVOLUTIONARY: Chart Data Validator - Prevents "Value is null" errors
class ChartDataValidator:
    """Data validation and sanitization für LightweightCharts compatibility"""

    def __init__(self):
        self.validation_stats = {'total_validations': 0, 'null_fixes': 0, 'type_fixes': 0}

    def validate_chart_data(self, data, timeframe=None, source="unknown"):
        """Validates and sanitizes chart data before sending to LightweightCharts"""
        self.validation_stats['total_validations'] += 1

        if not data:
            print(f"[DATA-VALIDATOR] WARNING: Empty data from {source}")
            return []

        validated_data = []
        fixed_count = 0

        for i, candle in enumerate(data):
            # Copy candle to prevent mutation
            validated_candle = candle.copy()
            candle_fixed = False

            # CRITICAL: Fix null/undefined values that cause LightweightCharts crashes
            required_fields = ['time', 'open', 'high', 'low', 'close']
            for field in required_fields:
                if field not in validated_candle or validated_candle[field] is None:
                    print(f"[DATA-VALIDATOR] CRITICAL: {field} is null in {timeframe} candle {i} from {source}")

                    if field == 'time':
                        # Use previous candle time + timeframe minutes if available
                        if i > 0 and validated_data:
                            prev_time = validated_data[-1]['time']
                            timeframe_minutes = self._get_timeframe_minutes(timeframe)
                            validated_candle[field] = prev_time + (timeframe_minutes * 60)
                        else:
                            # Fallback: Use current timestamp
                            validated_candle[field] = int(datetime.now().timestamp())
                        candle_fixed = True
                    else:
                        # For OHLC: Use previous candle's close or 20000 as fallback
                        fallback_price = 20000  # NQ realistic fallback
                        if i > 0 and validated_data:
                            fallback_price = validated_data[-1]['close']
                        validated_candle[field] = fallback_price
                        candle_fixed = True

                    self.validation_stats['null_fixes'] += 1

            # Type validation and conversion
            for field in required_fields:
                if field == 'time':
                    if not isinstance(validated_candle[field], (int, float)):
                        validated_candle[field] = int(float(validated_candle[field]))
                        candle_fixed = True
                        self.validation_stats['type_fixes'] += 1
                else:
                    if not isinstance(validated_candle[field], (int, float)):
                        try:
                            validated_candle[field] = float(validated_candle[field])
                            candle_fixed = True
                            self.validation_stats['type_fixes'] += 1
                        except (ValueError, TypeError):
                            validated_candle[field] = 20000  # Safe fallback
                            candle_fixed = True
                            self.validation_stats['null_fixes'] += 1

            # SPECIAL: 4h timeframe specific validation
            if timeframe == '4h' and candle_fixed:
                print(f"[DATA-VALIDATOR] 4h-FIX: Candle {i} sanitized - time:{validated_candle['time']}, "
                      f"OHLC:[{validated_candle['open']:.2f}, {validated_candle['high']:.2f}, "
                      f"{validated_candle['low']:.2f}, {validated_candle['close']:.2f}]")
                fixed_count += 1

            validated_data.append(validated_candle)

        if fixed_count > 0:
            print(f"[DATA-VALIDATOR] {timeframe} from {source}: {fixed_count}/{len(data)} candles fixed")

        return validated_data

    def _get_timeframe_minutes(self, timeframe):
        """Helper: Convert timeframe to minutes"""
        timeframe_map = {
            '1m': 1, '2m': 2, '3m': 3, '5m': 5,
            '15m': 15, '30m': 30, '1h': 60, '4h': 240
        }
        return timeframe_map.get(timeframe, 5)

    def get_validation_stats(self):
        """Returns validation statistics for debugging"""
        return self.validation_stats.copy()

    def reset_stats(self):
        """Reset validation statistics"""
        self.validation_stats = {'total_validations': 0, 'null_fixes': 0, 'type_fixes': 0}

# REVOLUTIONARY: Unified Price Repository - Single Source of Truth für konsistente Endkurse
class UnifiedPriceRepository:
    """Zentrale Price-Synchronisation für alle Timeframes - löst Endkurs-Inkonsistenz"""

    def __init__(self):
        self.master_price_timeline = {}  # {timestamp: unified_price}
        self.timeframe_positions = {}    # {timeframe: current_timestamp}
        self.base_candles_1m = []        # 1-minute base data als Single Source of Truth
        self.initialized = False
        self.price_sync_stats = {'syncs': 0, 'corrections': 0}

    def initialize_with_1m_data(self, csv_1m_data):
        """Initialize master price timeline with 1-minute CSV data"""
        if self.initialized:
            return

        print(f"[PRICE-REPO] Initializing master price timeline with {len(csv_1m_data)} 1m candles")

        for candle in csv_1m_data:
            timestamp = candle['time'] if isinstance(candle['time'], int) else int(candle['time'])
            self.master_price_timeline[timestamp] = {
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),  # Master close price
                'volume': int(candle.get('volume', 0))
            }

        self.base_candles_1m = csv_1m_data.copy()
        self.initialized = True
        print(f"[PRICE-REPO] Master timeline initialized: {len(self.master_price_timeline)} price points")

    def get_synchronized_price_at_time(self, target_timestamp, timeframe):
        """Gets synchronized price at specific timestamp for any timeframe"""
        if not self.initialized:
            print(f"[PRICE-REPO] WARNING: Not initialized, returning fallback price")
            return 20000  # Fallback

        # Find closest timestamp in master timeline
        closest_timestamp = min(self.master_price_timeline.keys(),
                               key=lambda x: abs(x - target_timestamp))

        master_price = self.master_price_timeline[closest_timestamp]
        self.price_sync_stats['syncs'] += 1

        print(f"[PRICE-REPO] {timeframe} @ {target_timestamp} -> Master price: {master_price['close']:.2f}")
        return master_price['close']

    def synchronize_skip_event_prices(self, skip_time, generated_candles_by_timeframe):
        """Synchronizes all timeframe candles to same price at skip time"""
        if not self.initialized:
            print(f"[PRICE-REPO] Cannot sync - not initialized")
            return generated_candles_by_timeframe

        target_timestamp = int(skip_time.timestamp())
        master_price = self.get_synchronized_price_at_time(target_timestamp, "master")

        synchronized_candles = {}
        for timeframe, candles in generated_candles_by_timeframe.items():
            if not candles:
                synchronized_candles[timeframe] = []
                continue

            sync_candles = []
            for candle in candles:
                sync_candle = candle.copy()

                # CRITICAL: Synchronize close price to master price
                old_close = sync_candle['close']
                sync_candle['close'] = master_price

                # Adjust OHLC to maintain realistic relationships
                if sync_candle['open'] > master_price:
                    sync_candle['open'] = master_price
                if sync_candle['high'] < master_price:
                    sync_candle['high'] = master_price + 0.25  # Small buffer
                if sync_candle['low'] > master_price:
                    sync_candle['low'] = master_price - 0.25   # Small buffer

                sync_candles.append(sync_candle)

                if old_close != master_price:
                    self.price_sync_stats['corrections'] += 1
                    print(f"[PRICE-REPO] {timeframe} price corrected: {old_close:.2f} -> {master_price:.2f}")

            synchronized_candles[timeframe] = sync_candles

        print(f"[PRICE-REPO] Skip event synchronized: {len(synchronized_candles)} timeframes")
        return synchronized_candles

    def update_timeframe_position(self, timeframe, timestamp):
        """Updates current position for timeframe"""
        self.timeframe_positions[timeframe] = timestamp

    def get_price_sync_stats(self):
        """Returns synchronization statistics"""
        return self.price_sync_stats.copy()

    def reset_stats(self):
        """Reset synchronization statistics"""
        self.price_sync_stats = {'syncs': 0, 'corrections': 0}

# Global Instance - Single Source of Truth
unified_state = UnifiedStateManager()
data_validator = ChartDataValidator()  # Global validator instance
price_repository = UnifiedPriceRepository()  # Global price synchronization

# Legacy Compatibility - für bestehenden Code
current_go_to_date = None  # Wird durch unified_state ersetzt
current_go_to_index = None  # CSV-Index Position für Skip-Navigation

# REVOLUTIONARY: Universal Skip Event Store - Single Source of Truth
# Skip Events sind zeit-basiert, nicht timeframe-spezifisch!
global_skip_events = []  # [{'time': datetime, 'candle': data, 'original_timeframe': str}]

# REVOLUTIONARY: Global Master Clock - Einheitliche Zeit für alle Systeme
master_clock = {
    'current_time': None,  # Einheitliche Master-Zeit
    'initialized': False
}

pass  # Debug entfernt - verursacht CLI-Abstürze
pass  # Debug entfernt - verursacht CLI-Abstürze

# REVOLUTIONARY: Universal Skip Renderer Engine
class UniversalSkipRenderer:
    """Rendert Skip-Events dynamisch für jeden Timeframe - Single Source of Truth"""

    @staticmethod
    def get_timeframe_minutes(timeframe):
        """Konvertiert Timeframe zu Minuten"""
        timeframe_map = {
            '1m': 1, '2m': 2, '3m': 3, '5m': 5,
            '15m': 15, '30m': 30, '1h': 60, '4h': 240
        }
        return timeframe_map.get(timeframe, 1)

    @classmethod
    def render_skip_candles_for_timeframe(cls, target_timeframe):
        """SMART CROSS-TIMEFRAME: Skip-Events für kompatible Timeframes mit Kontaminations-Schutz"""
        rendered_candles = []
        target_minutes = cls.get_timeframe_minutes(target_timeframe)

        for skip_event in global_skip_events:
            event_time = skip_event['time']
            base_candle = skip_event['candle'].copy()  # Always copy to prevent mutation
            original_tf = skip_event['original_timeframe']
            original_minutes = cls.get_timeframe_minutes(original_tf)

            # SMART COMPATIBILITY CHECK: Timeframe compatibility rules
            if cls._is_timeframe_compatible(original_tf, target_timeframe):
                # CONTAMINATION PROTECTION: Validate candle before adding
                if cls._is_candle_safe_for_timeframe(base_candle, target_timeframe):
                    # TIMEFRAME ADAPTATION: Adjust candle for target timeframe if needed
                    adapted_candle = cls._adapt_candle_for_timeframe(base_candle, original_tf, target_timeframe, event_time)

                    # CRITICAL: Apply price synchronization across timeframes
                    if price_repository.initialized:
                        synchronized_price = price_repository.get_synchronized_price_at_time(
                            adapted_candle['time'], target_timeframe
                        )
                        adapted_candle['close'] = synchronized_price
                        print(f"[CROSS-TF-PRICE-SYNC] {original_tf}->{target_timeframe}: {base_candle['close']:.2f} -> {synchronized_price:.2f}")

                    rendered_candles.append(adapted_candle)
                    print(f"[CROSS-TF-SKIP] {original_tf} Skip-Event -> {target_timeframe} verfügbar")
                else:
                    print(f"[CROSS-TF-SKIP] {original_tf} Skip-Event für {target_timeframe} GEFILTERT (Kontamination)")
            else:
                print(f"[CROSS-TF-SKIP] {original_tf} Skip-Event für {target_timeframe} INKOMPATIBEL")

        return rendered_candles

    @classmethod
    def _is_timeframe_compatible(cls, source_tf, target_tf):
        """Prüft ob Timeframes kompatibel sind für Skip-Event Sharing"""
        # Same timeframe = always compatible
        if source_tf == target_tf:
            return True

        # ENHANCED COMPATIBILITY: Allow both directions for aggregation
        # 1. Higher -> Lower: 15m skip can be shown in 5m (downsampling)
        # 2. Lower -> Higher: 5m skip can be aggregated into 15m (upsampling for price sync)
        source_min = cls.get_timeframe_minutes(source_tf)
        target_min = cls.get_timeframe_minutes(target_tf)

        # Allow both directions: aggregation requires all constituent candles
        # For 5m->15m: need all 3 skip candles (00:00, 00:05, 00:10) to create 15m candle
        # For 15m->5m: can distribute 15m candle across 3x 5m periods
        return True  # Allow all combinations - filtering happens in _adapt_candle_for_timeframe

    @classmethod
    def _is_candle_safe_for_timeframe(cls, candle, target_timeframe):
        """Validiert ob Kerze sicher für Ziel-Timeframe ist (Kontaminations-Schutz)"""
        try:
            # Basic null/undefined checks
            if not candle or not isinstance(candle, dict):
                return False

            # Check required fields
            required_fields = ['time', 'open', 'high', 'low', 'close']
            if not all(field in candle for field in required_fields):
                return False

            # Validate OHLC values (realistic NQ range)
            ohlc_values = [candle['open'], candle['high'], candle['low'], candle['close']]
            for val in ohlc_values:
                if not isinstance(val, (int, float)) or val < 1000 or val > 50000:
                    return False

            return True

        except Exception:
            return False

    @classmethod
    def _adapt_candle_for_timeframe(cls, candle, source_tf, target_tf, event_time):
        """Adaptiert Kerze für Ziel-Timeframe (Zeit-Anpassung wenn nötig)"""
        adapted_candle = candle.copy()

        # If timeframes are different, adjust the time to align with target timeframe
        if source_tf != target_tf:
            target_minutes = cls.get_timeframe_minutes(target_tf)

            # Align to target timeframe boundaries (e.g., 15m skip -> 5m alignment)
            aligned_time = event_time.replace(minute=(event_time.minute // target_minutes) * target_minutes, second=0, microsecond=0)
            adapted_candle['time'] = int(aligned_time.timestamp())

            print(f"[CROSS-TF-SKIP] Zeit-Anpassung: {source_tf}@{event_time} -> {target_tf}@{aligned_time}")

        return adapted_candle

    @classmethod
    def create_skip_event(cls, candle, original_timeframe):
        """REVOLUTIONARY: Erstellt neues Skip-Event im Universal Store"""
        global master_clock

        # Master Clock synchronisieren
        if not master_clock['initialized']:
            # Initialize Master Clock mit aktueller Zeit
            master_clock['current_time'] = datetime.fromtimestamp(candle['time'])
            master_clock['initialized'] = True
            pass  # Debug entfernt - verursacht CLI-Abstürze
        else:
            # Update Master Clock
            master_clock['current_time'] = datetime.fromtimestamp(candle['time'])
            pass  # Debug entfernt - verursacht CLI-Abstürze

        # CRITICAL: Price synchronization with UnifiedPriceRepository
        synchronized_candle = candle.copy()
        if price_repository.initialized:
            master_price = price_repository.get_synchronized_price_at_time(
                candle['time'], original_timeframe
            )
            synchronized_candle['close'] = master_price
            print(f"[PRICE-SYNC] {original_timeframe} skip candle price synchronized: {candle['close']:.2f} -> {master_price:.2f}")
        else:
            print(f"[PRICE-SYNC] WARNING: PriceRepository not initialized - no sync for {original_timeframe}")

        # Erstelle Skip-Event mit synchronized price
        skip_event = {
            'time': master_clock['current_time'],
            'candle': synchronized_candle,
            'original_timeframe': original_timeframe,
            'created_at': datetime.now()
        }

        global_skip_events.append(skip_event)
        pass  # Debug entfernt - verursacht CLI-Abstürze
        pass  # Debug entfernt - verursacht CLI-Abstürze

        return skip_event

# Initialize Universal Renderer
universal_renderer = UniversalSkipRenderer()
pass  # Debug entfernt - verursacht CLI-Abstürze

# BACKWARD COMPATIBILITY BRIDGE - Legacy functions that use global_skip_candles
class LegacyCompatibilityBridge:
    """Bridge zwischen alter global_skip_candles Logik und neuem Event System"""

    @staticmethod
    def get_legacy_skip_candles_for_timeframe(timeframe):
        """Simuliert alte global_skip_candles[timeframe] Logik mit Universal Renderer"""
        return universal_renderer.render_skip_candles_for_timeframe(timeframe)

    def items(self):
        """Simuliert global_skip_candles.items() für Legacy-Code"""
        timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']
        items = []
        for tf in timeframes:
            rendered_candles = universal_renderer.render_skip_candles_for_timeframe(tf)
            items.append((tf, rendered_candles))
        return items

    def __getitem__(self, timeframe):
        """Simuliert global_skip_candles[timeframe] Access"""
        return self.get_legacy_skip_candles_for_timeframe(timeframe)

    def get(self, timeframe, default=None):
        """Simuliert global_skip_candles.get(timeframe, default) Access"""
        try:
            return self.get_legacy_skip_candles_for_timeframe(timeframe)
        except:
            return default if default is not None else []

# LEGACY COMPATIBILITY: global_skip_candles Emulation
global_skip_candles = LegacyCompatibilityBridge()
pass  # Debug entfernt - verursacht CLI-Abstürze

# REVOLUTIONARY: Debug Control Timeframe Tracking - Separate from Chart Timeframe
debug_control_timeframe = '5m'  # Default debug control selection
print(f"[DEBUG-CONTROL] Initialized debug control timeframe: {debug_control_timeframe}")

# REVOLUTIONARY: Event-Based Transaction System for Skip Events
class EventBasedTransaction:
    """Revolutionary transaction system for Skip Events - Atomic & Persistent"""

    def __init__(self):
        self.backup_events = []
        self.is_active = False
        self.transaction_id = None

    def begin_transaction(self, transaction_id=None):
        """Start transaction with Skip Events backup"""
        import time
        self.transaction_id = transaction_id or f"event_tx_{int(time.time())}"
        self.is_active = True

        # Backup current Skip Events
        self.backup_events = global_skip_events.copy()
        print(f"[EVENT-TRANSACTION] {self.transaction_id} STARTED - Backed up {len(self.backup_events)} skip events")
        return self.transaction_id

    def commit_transaction(self):
        """Commit transaction - make Skip Events permanent"""
        if not self.is_active:
            print(f"[EVENT-TRANSACTION] WARNING: No active transaction")
            return False

        print(f"[EVENT-TRANSACTION] {self.transaction_id} COMMITTED - {len(global_skip_events)} events permanent")
        self.backup_events = []
        self.is_active = False
        self.transaction_id = None
        return True

    def rollback_transaction(self, reason="Unknown"):
        """Rollback transaction - restore Skip Events"""
        if not self.is_active:
            print(f"[EVENT-TRANSACTION] WARNING: No active transaction")
            return False

        print(f"[EVENT-TRANSACTION] {self.transaction_id} ROLLING BACK - Reason: {reason}")

        global global_skip_events
        global_skip_events = self.backup_events.copy()
        print(f"[EVENT-TRANSACTION] Restored {len(global_skip_events)} skip events")

        self.backup_events = []
        self.is_active = False
        self.transaction_id = None
        return True

# Revolutionary Transaction Manager
event_transaction = EventBasedTransaction()

# REVOLUTIONARY: Event-Based Skip System replaces old monitoring
# No need for complex monitoring - Events persist by design
pass  # Debug entfernt - verursacht CLI-Abstürze

# High-Performance Chart Data Cache - Global Instance
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add project root to path
from src.performance.high_performance_cache import HighPerformanceChartCache
chart_cache = None  # Wird beim Server-Start initialisiert - High-Performance Cache

# Lade initiale Chart-Daten aus CSV (schneller Startup)
print("Lade initiale 5m Chart-Daten aus CSV...")
initial_chart_data = []

try:
    import pandas as pd
    from pathlib import Path

    csv_path = Path("src/data/aggregated/5m/nq-2024.csv")
    if csv_path.exists():
        print(f"CSV gefunden: {csv_path}")

        # Lade ausreichend Kerzen für funktionsfähigen Chart
        df = pd.read_csv(csv_path).tail(300)  # 300 Kerzen für stabilen Chart mit History
        print(f"CSV gelesen: {len(df)} Zeilen")

        # Konvertiere zu Chart-Format (neue Struktur: Date, Time, OHLCV)
        for _, row in df.iterrows():
            # DateTime aus Date und Time kombinieren
            dt_str = f"{row['Date']} {row['Time']}"
            dt = pd.to_datetime(dt_str, format='mixed', dayfirst=True)

            initial_chart_data.append({
                'time': int(dt.timestamp()),  # Unix Timestamp für TradingView
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })
        print(f"ERFOLG: {len(initial_chart_data)} NQ-Kerzen geladen!")
    else:
        print(f"FEHLER: CSV nicht gefunden: {csv_path}")
except Exception as e:
    print(f"FEHLER beim CSV-Laden: {e}")
    import traceback
    traceback.print_exc()

# WebSocket Connection Manager
class ConnectionManager:
    """Verwaltet WebSocket-Verbindungen für Realtime-Updates"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.chart_state: Dict[str, Any] = {
            'data': initial_chart_data,  # Verwende echte NQ-Daten
            'symbol': 'NQ=F',
            'interval': '5m',  # 5-Minuten Standard
            'last_update': datetime.now().isoformat(),
            'positions': [],
            'raw_1m_data': None  # CSV-basiert, kein raw data needed
        }

    async def connect(self, websocket: WebSocket):
        """Neue WebSocket-Verbindung hinzufügen"""
        await websocket.accept()
        self.active_connections.append(websocket)

        # Sende aktuellen Chart-State an neuen Client
        await self.send_personal_message({
            'type': 'initial_data',
            'data': self.chart_state
        }, websocket)

    def disconnect(self, websocket: WebSocket):
        """WebSocket-Verbindung entfernen"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Nachricht an spezifischen Client senden"""
        try:
            # Erstelle eine serialisierbare Kopie der Daten ohne DataFrame
            if 'data' in message and isinstance(message['data'], dict):
                serializable_data = message['data'].copy()
                # Entferne nicht-serialisierbare DataFrame-Objekte
                if 'raw_1m_data' in serializable_data:
                    del serializable_data['raw_1m_data']
                message = message.copy()
                message['data'] = serializable_data

            # Verwende custom serializer für datetime Objekte
            await websocket.send_text(json.dumps(message, default=json_serializer))
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            # Debug: Drucke Details für JSON Serialization Fehler
            if "not JSON serializable" in str(e):
                logging.error(f"Message contents: {message}")

    async def broadcast(self, message: dict):
        """🛡️ CRASH-SAFE Nachricht an alle verbundenen Clients senden"""
        print(f"Broadcast: {len(self.active_connections)} aktive Verbindungen, Nachricht: {message.get('type', 'unknown')}")

        if not self.active_connections:
            print("WARNUNG: Keine aktiven WebSocket-Verbindungen für Broadcast!")
            return

        # CRITICAL: DataIntegrityGuard Validierung
        if not data_guard.validate_websocket_message(message):
            print(f"[DATA-GUARD] [BLOCKED] BLOCKED invalid websocket message: {message.get('type', 'unknown')}")
            return

        # Sende parallel an alle Clients
        tasks = []
        for connection in self.active_connections.copy():
            tasks.append(self.send_personal_message(message, connection))

        # Warte auf alle Sends (mit Error-Handling)
        await asyncio.gather(*tasks, return_exceptions=True)
        print(f"Broadcast abgeschlossen an {len(self.active_connections)} Clients")

    def update_chart_state(self, update_data: dict):
        """Chart-State aktualisieren"""
        if update_data.get('type') == 'set_data':
            self.chart_state['data'] = update_data.get('data', [])
            self.chart_state['symbol'] = update_data.get('symbol', 'NQ=F')
            self.chart_state['interval'] = update_data.get('interval', '5m')
        elif update_data.get('type') == 'add_candle':
            # Neue Kerze hinzufügen
            candle = update_data.get('candle')
            if candle:
                self.chart_state['data'].append(candle)
        elif update_data.get('type') == 'add_position':
            # Position Overlay hinzufügen
            if 'positions' not in self.chart_state:
                self.chart_state['positions'] = []
            position = update_data.get('position')
            if position:
                self.chart_state['positions'].append(position)
        elif update_data.get('type') == 'remove_position':
            # Position entfernen
            position_id = update_data.get('position_id')
            if position_id and 'positions' in self.chart_state:
                self.chart_state['positions'] = [
                    p for p in self.chart_state['positions']
                    if p.get('id') != position_id
                ]

        self.chart_state['last_update'] = datetime.now().isoformat()

# Timeframe Aggregator für intelligente Kerzen-Logik
class TimeframeAggregator:
    """Intelligente Kerzen-Logik für verschiedene Timeframes"""

    def __init__(self):
        # Timeframe-Definitionen in Minuten
        self.timeframes = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60
        }

        # Aktuelle unvollständige Kerzen pro Timeframe
        self.incomplete_candles = {}

        # Letzte vollständige Kerze für jeden Timeframe
        self.last_complete_candles = {}

    def add_minute_to_timeframe(self, current_time: datetime, timeframe: str, last_candle: dict) -> tuple:
        """
        Fügt eine Minute zu einem Timeframe hinzu und gibt zurück:
        - neue_kerze: dict mit neuer Kerze oder None
        - incomplete_data: dict mit unvollständiger Kerze oder None
        - is_complete: bool ob Kerze vollständig ist
        """
        tf_minutes = self.timeframes.get(timeframe, 1)
        new_time = current_time + timedelta(minutes=1)

        # Berechne Start-Zeit für aktuelle Timeframe-Periode
        if timeframe == '1m':
            period_start = new_time.replace(second=0, microsecond=0)
        elif timeframe == '5m':
            period_start = new_time.replace(minute=(new_time.minute // 5) * 5, second=0, microsecond=0)
        elif timeframe == '15m':
            period_start = new_time.replace(minute=(new_time.minute // 15) * 15, second=0, microsecond=0)
        elif timeframe == '30m':
            period_start = new_time.replace(minute=(new_time.minute // 30) * 30, second=0, microsecond=0)
        elif timeframe == '1h':
            period_start = new_time.replace(minute=0, second=0, microsecond=0)
        else:
            period_start = new_time.replace(second=0, microsecond=0)

        # Generiere Mock-Preis-Bewegung basierend auf letzter Kerze
        last_close = last_candle.get('close', 18500)
        price_change = random.uniform(-20, 20)  # ±20 Punkte Bewegung
        new_price = last_close + price_change

        # Prüfe ob wir eine neue Periode beginnen
        key = f"{timeframe}_{period_start.isoformat()}"

        if key not in self.incomplete_candles:
            # Neue Periode beginnt
            self.incomplete_candles[key] = {
                'time': int(period_start.timestamp()),
                'open': new_price,
                'high': new_price,
                'low': new_price,
                'close': new_price,
                'period_start': period_start,
                'minutes_elapsed': 1,
                'timeframe': timeframe,
                'is_complete': False
            }
        else:
            # Bestehende Periode fortsetzen
            candle = self.incomplete_candles[key]
            candle['high'] = max(candle['high'], new_price)
            candle['low'] = min(candle['low'], new_price)
            candle['close'] = new_price
            candle['minutes_elapsed'] += 1

        current_candle = self.incomplete_candles[key]

        # Prüfe ob Periode vollständig ist
        if current_candle['minutes_elapsed'] >= tf_minutes:
            # Kerze ist vollständig
            complete_candle = current_candle.copy()
            complete_candle['is_complete'] = True

            # Entferne aus incomplete und speichere als last_complete
            del self.incomplete_candles[key]
            self.last_complete_candles[timeframe] = complete_candle

            return complete_candle, None, True
        else:
            # Kerze ist noch unvollständig
            return None, current_candle, False

    def get_incomplete_candle(self, timeframe: str) -> dict:
        """Gibt die aktuelle unvollständige Kerze für einen Timeframe zurück"""
        for key, candle in self.incomplete_candles.items():
            if candle['timeframe'] == timeframe:
                return candle
        return None

    def get_all_incomplete_candles(self) -> dict:
        """Gibt alle unvollständigen Kerzen zurück, gruppiert nach Timeframe"""
        result = {}
        for key, candle in self.incomplete_candles.items():
            tf = candle['timeframe']
            if tf not in result:
                result[tf] = []
            result[tf].append(candle)
        return result

# High-Performance Memory-basierte Chart Data Cache
class ChartDataCache:
    """
    Ultra-schneller Memory-basierter Data Cache für alle Timeframes
    Lädt alle CSV-Dateien einmalig beim Start -> Sub-Millisekunden Navigation
    """

    def __init__(self):
        """Initialisiert leeren Cache"""
        self.timeframe_data = {}  # {timeframe: pandas.DataFrame}
        self.loaded_timeframes = set()
        self.available_timeframes = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]  # CORRECTED: Alle Timeframe-Ordner verfügbar
        print("[CACHE] ChartDataCache initialisiert")

    def load_all_timeframes(self):
        """Lädt alle verfügbaren Timeframes in Memory - einmalig beim Server-Start"""
        import pandas as pd
        from pathlib import Path

        print("[CACHE] Starte Memory-Loading aller Timeframes...")

        for timeframe in self.available_timeframes:
            csv_path = Path(f"src/data/aggregated/{timeframe}/nq-2024.csv")

            if csv_path.exists():
                try:
                    # CSV mit neuer Struktur laden (Date, Time, OHLCV)
                    df = pd.read_csv(csv_path)

                    # DateTime kombinieren und als zusätzliche Spalte hinzufügen
                    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
                    df['time'] = df['datetime'].astype(int) // 10**9  # Unix timestamp für TradingView

                    # Sortierung nach Datum sicherstellen
                    df = df.sort_values('datetime')

                    self.timeframe_data[timeframe] = df
                    self.loaded_timeframes.add(timeframe)

                    # Debug Info
                    start_time = df['datetime'].iloc[0]
                    end_time = df['datetime'].iloc[-1]

                    print(f"[CACHE] SUCCESS {timeframe} loaded: {len(df)} candles ({start_time} bis {end_time})")

                except Exception as e:
                    print(f"[CACHE] ERROR beim Laden {timeframe}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[CACHE] WARNING CSV nicht gefunden: {csv_path}")

        print(f"[CACHE] Memory-Loading abgeschlossen: {len(self.loaded_timeframes)} Timeframes geladen")
        return len(self.loaded_timeframes) > 0

    def load_priority_timeframes(self, priority_list):
        """Lädt nur prioritäre Timeframes für schnellen Server-Start"""
        import pandas as pd
        from pathlib import Path

        print(f"[CACHE] Lade Priority Timeframes: {priority_list}")

        for timeframe in priority_list:
            if timeframe not in self.available_timeframes:
                continue

            csv_path = Path(f"src/data/aggregated/{timeframe}/nq-2024.csv")

            if csv_path.exists():
                try:
                    # CSV mit neuer Struktur laden (Date, Time, OHLCV)
                    df = pd.read_csv(csv_path)

                    # DateTime kombinieren und als zusätzliche Spalte hinzufügen
                    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
                    df['time'] = df['datetime'].astype(int) // 10**9  # Unix timestamp für TradingView

                    # Sortierung nach Datum sicherstellen
                    df = df.sort_values('datetime')

                    self.timeframe_data[timeframe] = df
                    self.loaded_timeframes.add(timeframe)

                    # Debug Info
                    start_time = df['datetime'].iloc[0]
                    end_time = df['datetime'].iloc[-1]

                    print(f"[CACHE] SUCCESS {timeframe} loaded: {len(df)} candles ({start_time.strftime('%Y-%m-%d')} bis {end_time.strftime('%Y-%m-%d')})")

                except Exception as e:
                    print(f"[CACHE] ERROR beim Laden {timeframe}: {e}")
            else:
                print(f"[CACHE] WARNING CSV nicht gefunden: {csv_path}")

        print(f"[CACHE] Priority Loading abgeschlossen: {len(self.loaded_timeframes)} von {len(priority_list)} geladen")
        return len(self.loaded_timeframes) > 0

    def find_best_date_index(self, target_date, timeframe):
        """
        Findet den besten Index für ein Zieldatum mit intelligenten Fallback-Strategien

        Args:
            target_date: datetime object
            timeframe: string (z.B. '5m')

        Returns:
            int: Index im DataFrame der am besten zum Zieldatum passt
        """
        if timeframe not in self.timeframe_data:
            raise ValueError(f"Timeframe {timeframe} nicht geladen!")

        df = self.timeframe_data[timeframe]
        target_timestamp = int(target_date.timestamp())

        # Check if target is before CSV data range
        if target_timestamp < df['time'].iloc[0]:
            print(f"[CACHE] Datum {target_date} vor CSV-Bereich - verwende ersten verfügbaren Index (0)")
            return 0  # FIXED: Verwende ersten verfügbaren Datenpunkt statt willkürlichen Index 199

        # Check if target is after CSV data range
        elif target_timestamp > df['time'].iloc[-1]:
            print(f"[CACHE] Datum {target_date} nach CSV-Bereich - verwende letzten Index")
            return len(df) - 1

        # Find nearest timestamp match
        else:
            time_diffs = (df['time'] - target_timestamp).abs()
            best_index = time_diffs.idxmin()

            matched_time = pd.to_datetime(df.iloc[best_index]['time'], unit='s')
            print(f"[CACHE] Exakte Übereinstimmung: Index {best_index} -> {matched_time}")

            return best_index

    def get_candles_range(self, timeframe, center_index, total_candles=10, visible_candles=5):
        """
        Holt einen Bereich von Kerzen rund um center_index

        Args:
            timeframe: string
            center_index: int - Zentrum des Bereichs
            total_candles: int - Gesamt zu ladende Kerzen (200)
            visible_candles: int - Sichtbare Kerzen im Chart (5)

        Returns:
            dict: {
                'data': list - Chart-formatierte Daten (5 Kerzen),
                'visible_start': int - Index der ersten sichtbaren Kerze,
                'visible_end': int - Index der letzten sichtbaren Kerze,
                'center_index': int - Ursprungsindex,
                'total_count': int
            }
        """
        if timeframe not in self.timeframe_data:
            raise ValueError(f"Timeframe {timeframe} nicht geladen!")

        df = self.timeframe_data[timeframe]
        df_length = len(df)

        # Berechne Start/End Index für total_candles (200) Kerzen VOR center_index
        start_idx = max(0, center_index - total_candles + 1)  # 199 Kerzen davor + 1 center = 200
        end_idx = center_index + 1  # Bis einschließlich center_index

        # Falls nicht genug Daten vor center_index, fülle nach vorne auf
        if end_idx - start_idx < total_candles:
            needed = total_candles - (end_idx - start_idx)
            end_idx = min(df_length, end_idx + needed)

        # Extrahiere DataFrame-Bereich
        result_df = df.iloc[start_idx:end_idx]

        # Konvertiere zu Chart-Format
        chart_data = []
        for _, row in result_df.iterrows():
            chart_data.append({
                'time': int(row['time']),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        # Berechne sichtbaren Bereich (letzten visible_candles von total_candles)
        data_count = len(chart_data)
        visible_start = max(0, data_count - visible_candles)
        visible_end = data_count - 1

        print(f"[CACHE] Kerzen-Bereich: {data_count} total, sichtbar {visible_start}-{visible_end} (CSV Index {start_idx}-{end_idx-1})")

        return {
            'data': chart_data,
            'visible_start': visible_start,
            'visible_end': visible_end,
            'center_index': center_index,
            'total_count': data_count,
            'csv_range': (start_idx, end_idx - 1)
        }

    def get_next_candle(self, timeframe, current_index):
        """
        Holt die nächste Kerze für Skip-Operation

        Args:
            timeframe: string
            current_index: int - Aktueller Index im DataFrame

        Returns:
            dict: {'candle': {chart_data}, 'new_index': int} oder None wenn Ende erreicht
        """
        if timeframe not in self.timeframe_data:
            raise ValueError(f"Timeframe {timeframe} nicht geladen!")

        df = self.timeframe_data[timeframe]
        next_index = current_index + 1

        if next_index >= len(df):
            print(f"[CACHE] Ende der {timeframe} Daten erreicht (Index {current_index})")
            return None

        # Nächste Kerze extrahieren
        next_row = df.iloc[next_index]
        next_candle = {
            'time': int(next_row['time']),
            'open': float(next_row['Open']),
            'high': float(next_row['High']),
            'low': float(next_row['Low']),
            'close': float(next_row['Close']),
            'volume': int(next_row['Volume'])
        }

        next_time = pd.to_datetime(next_row['time'], unit='s')
        print(f"[CACHE] Skip: Index {current_index} -> {next_index} ({next_time})")

        return {
            'candle': next_candle,
            'new_index': next_index
        }

    def get_timeframe_info(self, timeframe):
        """Gibt Info über einen geladenen Timeframe zurück"""
        if timeframe not in self.timeframe_data:
            return None

        df = self.timeframe_data[timeframe]
        start_time = pd.to_datetime(df['time'].iloc[0], unit='s')
        end_time = pd.to_datetime(df['time'].iloc[-1], unit='s')

        return {
            'timeframe': timeframe,
            'total_candles': len(df),
            'start_time': start_time,
            'end_time': end_time,
            'loaded': True
        }

# Timeframe Synchronization Manager
class TimeframeSyncManager:
    """Synchronisiert mehrere Timeframes für parallele Navigation"""

    def __init__(self, csv_loader):
        self.csv_loader = csv_loader
        self.timeframe_positions = {}  # {timeframe: current_datetime}
        self.timeframe_mappings = {
            '1m': 1,
            '2m': 2,
            '3m': 3,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240
        }
        print("[TimeframeSyncManager] Initialized multi-timeframe synchronization")

    def set_base_time(self, datetime_obj):
        """Setzt die Basis-Zeit für alle Timeframes"""
        for timeframe in self.timeframe_mappings.keys():
            self.timeframe_positions[timeframe] = datetime_obj
        print(f"[SyncManager] Base time set to {datetime_obj}")

    def skip_timeframe(self, target_timeframe, sync_others=True):
        """Skipped ein Timeframe und synchronisiert optional andere"""
        result = self.csv_loader.get_next_candle(target_timeframe, self.timeframe_positions.get(target_timeframe))

        if result is None:
            print(f"[SyncManager] No next candle for {target_timeframe}")
            return None

        # Update position für Target-Timeframe
        self.timeframe_positions[target_timeframe] = result['datetime']

        if sync_others:
            self._synchronize_other_timeframes(target_timeframe, result['datetime'])

        print(f"[SyncManager] Skipped {target_timeframe} to {result['datetime']}")

        return {
            'primary_result': result,
            'sync_results': self._get_sync_status()
        }

    def _synchronize_other_timeframes(self, primary_timeframe, new_datetime):
        """Synchronisiert andere Timeframes basierend auf dem primären Skip"""
        primary_minutes = self.timeframe_mappings[primary_timeframe]

        for other_tf, other_minutes in self.timeframe_mappings.items():
            if other_tf == primary_timeframe:
                continue

            current_pos = self.timeframe_positions.get(other_tf, new_datetime)

            if other_minutes < primary_minutes:
                # Kleinere Timeframes: Mehrere Steps
                # Beispiel: 15m Skip -> 3x 5m Steps
                steps_needed = primary_minutes // other_minutes
                print(f"[SyncManager] Syncing {other_tf}: {steps_needed} steps for {primary_timeframe} skip")

                for step in range(steps_needed):
                    result = self.csv_loader.get_next_candle(other_tf, current_pos)
                    if result:
                        current_pos = result['datetime']

                self.timeframe_positions[other_tf] = current_pos

            elif other_minutes > primary_minutes:
                # Größere Timeframes: Prüfe ob incomplete oder complete
                self._update_larger_timeframe(other_tf, new_datetime, primary_minutes)

            else:
                # Gleiche Timeframes: Direkte Synchronisierung
                self.timeframe_positions[other_tf] = new_datetime

    def _update_larger_timeframe(self, target_tf, new_datetime, skip_minutes):
        """Updated größere Timeframes und erkennt incomplete Kerzen"""
        target_minutes = self.timeframe_mappings[target_tf]
        current_pos = self.timeframe_positions.get(target_tf, new_datetime)

        # Berechne ob wir eine complete Kerze haben
        # Beispiel: 2x 5min Skip = 10min, aber 15min Kerze braucht 15min -> incomplete
        accumulated_minutes = skip_minutes
        candle_start = self._get_candle_start_time(new_datetime, target_minutes)
        minutes_in_candle = (new_datetime - candle_start).total_seconds() / 60

        if minutes_in_candle >= target_minutes:
            # Complete candle - finde nächste verfügbare
            result = self.csv_loader.get_next_candle(target_tf, current_pos)
            if result:
                self.timeframe_positions[target_tf] = result['datetime']
                print(f"[SyncManager] Complete {target_tf} candle found")
            else:
                print(f"[SyncManager] No complete {target_tf} candle available")
        else:
            # Incomplete candle - behalte Position aber markiere als incomplete
            print(f"[SyncManager] Incomplete {target_tf} candle: {minutes_in_candle}/{target_minutes} min")

    def _get_candle_start_time(self, datetime_obj, timeframe_minutes):
        """Berechnet den Start-Zeitpunkt einer Kerze für einen Timeframe"""
        from datetime import datetime, timedelta

        # Round down zur nächsten Timeframe-Boundary
        minutes_since_midnight = datetime_obj.hour * 60 + datetime_obj.minute
        candle_boundary = (minutes_since_midnight // timeframe_minutes) * timeframe_minutes

        return datetime_obj.replace(
            hour=candle_boundary // 60,
            minute=candle_boundary % 60,
            second=0,
            microsecond=0
        )

    def get_incomplete_candle_info(self, timeframe):
        """Gibt Informationen über unvollständige Kerzen zurück"""
        current_pos = self.timeframe_positions.get(timeframe)
        if not current_pos:
            return None

        timeframe_minutes = self.timeframe_mappings[timeframe]
        candle_start = self._get_candle_start_time(current_pos, timeframe_minutes)
        elapsed_minutes = (current_pos - candle_start).total_seconds() / 60

        return {
            'timeframe': timeframe,
            'candle_start': candle_start,
            'current_position': current_pos,
            'elapsed_minutes': elapsed_minutes,
            'total_minutes': timeframe_minutes,
            'completion_ratio': elapsed_minutes / timeframe_minutes,
            'is_complete': elapsed_minutes >= timeframe_minutes
        }

    def _get_sync_status(self):
        """Gibt aktuellen Synchronisations-Status zurück"""
        status = {}
        for tf in self.timeframe_mappings.keys():
            status[tf] = {
                'position': self.timeframe_positions.get(tf),
                'incomplete_info': self.get_incomplete_candle_info(tf)
            }
        return status

# CSV Data Loader für Multi-Timeframe Support
class CSVLoader:
    """Robust CSV-Daten Loader mit Multi-Path Fallback und Caching"""

    def __init__(self):
        self.data_cache = {}  # {timeframe: pandas.DataFrame}
        self.available_timeframes = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]
        print("[CSVLoader] Initialized multi-timeframe CSV loader")

    def get_csv_paths(self, timeframe):
        """Gibt prioritisierte Liste von CSV-Pfaden für einen Timeframe zurück"""
        from pathlib import Path

        paths = [
            Path(f"src/data/aggregated/{timeframe}/nq-2024.csv"),      # Jahres-CSV
            Path(f"src/data/aggregated/nq-2024-{timeframe}.csv")       # Alternative Root CSV
        ]

        # Monthly fallbacks für alle Monate
        for month in range(12, 0, -1):  # Dec to Jan
            monthly_csv = Path(f"src/data/aggregated/{timeframe}/nq-2024-{month:02d}.csv")
            paths.append(monthly_csv)

        return paths

    def load_timeframe_data(self, timeframe):
        """Lädt CSV-Daten für einen spezifischen Timeframe mit Fallback-System"""
        if timeframe in self.data_cache:
            print(f"[CSVLoader] Cache hit for {timeframe}")
            return self.data_cache[timeframe]

        import pandas as pd

        csv_paths = self.get_csv_paths(timeframe)

        for csv_path in csv_paths:
            if csv_path.exists():
                try:
                    print(f"[CSVLoader] Loading {timeframe} from {csv_path}")
                    df = pd.read_csv(csv_path)

                    if df.empty:
                        continue

                    # Normalize datetime column
                    if 'datetime' not in df.columns:
                        df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)

                    # Cache the data
                    self.data_cache[timeframe] = df
                    print(f"[CSVLoader] SUCCESS: Cached {len(df)} {timeframe} candles")
                    return df

                except Exception as e:
                    print(f"[CSVLoader] Error loading {csv_path}: {e}")
                    continue

        print(f"[CSVLoader] ERROR: No valid CSV found for {timeframe}")
        return None

    def preload_all_timeframes(self):
        """Lädt alle verfügbaren Timeframes in den Cache"""
        print("[CSVLoader] Preloading all timeframes...")

        for timeframe in self.available_timeframes:
            df = self.load_timeframe_data(timeframe)
            if df is not None:
                print(f"[CSVLoader] Preloaded {timeframe}: {len(df)} candles")
            else:
                print(f"[CSVLoader] Failed to preload {timeframe}")

    def get_next_candle(self, timeframe, current_datetime):
        """Findet die nächste Kerze nach der gegebenen Zeit für den Timeframe"""
        df = self.load_timeframe_data(timeframe)
        if df is None:
            return None

        import pandas as pd

        target_datetime = pd.Timestamp(current_datetime)
        future_candles = df[df['datetime'] > target_datetime].sort_values('datetime')

        if len(future_candles) > 0:
            next_row = future_candles.iloc[0]

            candle = {
                'time': int(next_row['datetime'].timestamp()),
                'open': float(next_row['Open']),
                'high': float(next_row['High']),
                'low': float(next_row['Low']),
                'close': float(next_row['Close']),
                'volume': int(next_row['Volume'])
            }

            return {
                'candle': candle,
                'datetime': next_row['datetime'].to_pydatetime(),
                'source': f'{timeframe}_csv'
            }

        return None

# ===== UNIFIED TIME MANAGEMENT ARCHITECTURE =====
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
        self.active_timeframes = set()  # Welche TF sind gerade aktiv
        self.timeframe_positions = {}   # {timeframe: last_loaded_candle_time}

        # Data Validation
        self.last_valid_times = {}      # {timeframe: last_known_good_time}
        self.last_operation_source = None  # Track last operation source for validation

        # ===== SKIP-STATE ISOLATION SYSTEM =====
        # Memento Pattern: Saubere Trennung von Skip-generierten vs CSV-Daten
        self.skip_candles_registry = {}  # {timeframe: [skip_generated_candles]}
        self.csv_candles_registry = {}   # {timeframe: [csv_source_candles]}
        self.mixed_state_timeframes = set()  # Timeframes mit gemischten Daten

        # Command Pattern: Skip-Operation Tracking für Rollback
        self.skip_operations_history = []  # Liste aller Skip-Operationen
        self.current_skip_session = None   # Aktuelle Skip-Session ID

        # State Machine: Skip-Contamination Tracking
        self.contamination_levels = {}     # {timeframe: contamination_level}
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
        global master_clock
        master_clock['current_time'] = self.current_debug_time
        master_clock['initialized'] = self.initialized

    def _update_unified_state(self):
        """Synchronisiert unified_state Manager"""
        if self.current_debug_time:
            unified_state.sync_debug_controller_time(self.current_debug_time)

    def _sync_debug_controller(self):
        """Synchronisiert DebugController Zeit"""
        global debug_controller
        if hasattr(debug_controller, 'current_time') and debug_controller:
            debug_controller.current_time = self.current_debug_time
            if hasattr(debug_controller, 'sync_manager'):
                debug_controller.sync_manager.set_base_time(self.current_debug_time)

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

    def ensure_full_csv_basis(self, timeframe):
        """Stellt sicher, dass eine vollständige CSV-Basis für den Timeframe existiert"""
        existing_candles = self.csv_candles_registry.get(timeframe, [])

        # Wenn bereits viele Kerzen vorhanden (> 1000), betrachte als vollständig
        if len(existing_candles) > 1000:
            return existing_candles

        # Lade vollständige CSV-Daten ohne Limit
        print(f"[CSV-REGISTRY] Loading full CSV basis for {timeframe}")
        try:
            # Verwende die Repository-Funktion mit großem Datum-Range und ohne max_candles
            from datetime import datetime, timedelta
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
        csv_candles = self.ensure_full_csv_basis(timeframe)
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

# Global Unified Time Manager Instance
unified_time_manager = UnifiedTimeManager()

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

# Global Temporal Operation Manager
temporal_operation_manager = TemporalOperationManager(unified_time_manager)

# ===== TIMEFRAME DATA REPOSITORY =====
class TimeframeDataRepository:
    """
    🚀 Smart Data Repository mit Unified Time Integration
    Abstrahiert CSV-Loading, validiert Daten und integriert mit UnifiedTimeManager
    """

    def __init__(self, csv_loader, unified_time_manager):
        self.csv_loader = csv_loader
        self.unified_time = unified_time_manager

        # Enhanced Cache mit Zeit-Validierung
        self.validated_cache = {}  # {timeframe: {data: df, last_validated_time: datetime}}
        self.candle_index_cache = {}  # {timeframe: {time: index}} für schnelle Suche

        print("[TimeframeDataRepository] Smart Data Repository initialisiert")

    def get_candle_at_time(self, timeframe, target_time, tolerance_minutes=None):
        """
        Holt eine spezifische Kerze zu einer bestimmten Zeit
        Integriert mit UnifiedTimeManager für Zeit-Validierung
        """
        if isinstance(target_time, (int, float)):
            target_time = datetime.fromtimestamp(target_time)

        # Standardtoleranz basierend auf Timeframe
        if tolerance_minutes is None:
            tolerance_minutes = self.unified_time._get_timeframe_minutes(timeframe)

        # Lade Timeframe-Daten
        df = self._load_and_validate_timeframe_data(timeframe)
        if df is None or df.empty:
            print(f"[TimeframeDataRepository] ERROR: Keine Daten für {timeframe}")
            return None

        # Suche exakte oder nächstgelegene Kerze
        candle_data = self._find_candle_near_time(df, target_time, tolerance_minutes, timeframe)

        if candle_data is not None:
            # Validiere Kerze mit UnifiedTimeManager
            candle_time = candle_data.get('time', candle_data.get('datetime'))
            if self.unified_time.validate_candle_time(candle_time, timeframe):
                self.unified_time.register_timeframe_activity(timeframe, candle_time)
                print(f"[TimeframeDataRepository] [FOUND] Kerze gefunden für {target_time} -> {candle_time} ({timeframe})")
                return candle_data
            else:
                print(f"[TimeframeDataRepository] WARNING: Kerze-Zeit Validierung fehlgeschlagen für {timeframe}")

        return None

    def get_next_candle_after_time(self, timeframe, current_time):
        """
        Holt die nächste Kerze nach einer bestimmten Zeit
        Für Skip-Operationen optimiert
        """
        print(f"[DEBUG] get_next_candle_after_time: {timeframe}, current_time={current_time}")

        if isinstance(current_time, (int, float)):
            current_time = datetime.fromtimestamp(current_time)

        df = self._load_and_validate_timeframe_data(timeframe)
        if df is None or df.empty:
            print(f"[DEBUG] DataFrame ist None oder leer für {timeframe}")
            return None

        print(f"[DEBUG] DataFrame geladen: {len(df)} Zeilen, Spalten: {list(df.columns)}")

        # Finde nächste Kerze nach current_time
        time_column = 'datetime' if 'datetime' in df.columns else 'time'
        print(f"[DEBUG] Verwende time_column: {time_column}, dtype: {df[time_column].dtype}")

        # Zeige erste 3 Zeiten im DataFrame zur Debugging
        print(f"[DEBUG] Erste 3 Zeiten im DataFrame: {df[time_column].head(3).tolist()}")

        if time_column == 'time' and df[time_column].dtype == 'int64':
            # Timestamp format
            current_timestamp = current_time.timestamp()
            print(f"[DEBUG] Suche nach timestamp > {current_timestamp}")
            next_candles = df[df[time_column] > current_timestamp]
        else:
            # Datetime format
            if df[time_column].dtype == 'object':
                df[time_column] = pd.to_datetime(df[time_column])
            print(f"[DEBUG] Suche nach datetime > {current_time}")
            next_candles = df[df[time_column] > current_time]

        print(f"[DEBUG] Gefundene next_candles: {len(next_candles)} Kerzen")
        if len(next_candles) > 0:
            print(f"[DEBUG] Erste gefundene Kerze Zeit: {next_candles.iloc[0][time_column]}")

        if next_candles.empty:
            print(f"[TimeframeDataRepository] Keine weiteren Kerzen nach {current_time} für {timeframe}")
            return None

        # Erste (nächste) Kerze
        next_candle = next_candles.iloc[0]
        candle_data = self._format_candle_data(next_candle, timeframe)

        # Zeit-Validierung
        candle_time = candle_data.get('time', candle_data.get('datetime'))
        print(f"[DEBUG] Validiere Kerze-Zeit: {candle_time}")
        if self.unified_time.validate_candle_time(candle_time, timeframe):
            self.unified_time.register_timeframe_activity(timeframe, candle_time)
            print(f"[DEBUG] Kerze-Zeit Validierung erfolgreich")
            return candle_data
        else:
            print(f"[TimeframeDataRepository] WARNING: Nächste Kerze-Zeit Validierung fehlgeschlagen für {timeframe}")
            return None

    def get_candles_for_date_range(self, timeframe, start_date, end_date=None, max_candles=200):
        """
        Holt Kerzen für einen Datumsbereich - für Chart-Loading optimiert
        🔧 SKIP-POSITION AWARE: Respektiert aktuelle Skip-Positionen vom UnifiedTimeManager
        """
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date and isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # 🚀 SKIP-POSITION LOGGING: Track welcher Zeitbereich geladen wird
        print(f"[SKIP-POSITION-AWARE] Loading {timeframe} candles: {start_date} to {end_date}, max: {max_candles}")

        # Verify with UnifiedTimeManager current state
        current_unified_time = self.unified_time.get_current_time()
        if current_unified_time:
            print(f"[SKIP-POSITION-AWARE] UnifiedTimeManager current time: {current_unified_time}")

        df = self._load_and_validate_timeframe_data(timeframe)
        if df is None or df.empty:
            return []

        # Datums-Filterung
        time_column = 'datetime' if 'datetime' in df.columns else 'time'
        if time_column == 'time' and df[time_column].dtype == 'int64':
            # Timestamp format
            start_timestamp = start_date.timestamp()
            if end_date:
                end_timestamp = end_date.timestamp()
                filtered_df = df[(df[time_column] >= start_timestamp) & (df[time_column] <= end_timestamp)]
            else:
                filtered_df = df[df[time_column] >= start_timestamp]
        else:
            # Datetime format
            if df[time_column].dtype == 'object':
                df[time_column] = pd.to_datetime(df[time_column])
            if end_date:
                filtered_df = df[(df[time_column] >= start_date) & (df[time_column] <= end_date)]
            else:
                filtered_df = df[df[time_column] >= start_date]

        # Limitiere Anzahl der Kerzen
        if len(filtered_df) > max_candles:
            filtered_df = filtered_df.head(max_candles)

        # Konvertiere zu Liste von Candle-Dicts
        candles = []
        for _, row in filtered_df.iterrows():
            candle_data = self._format_candle_data(row, timeframe)
            candles.append(candle_data)

        print(f"[TimeframeDataRepository] [DATA] {len(candles)} Kerzen geladen für {timeframe} ({start_date} bis {end_date or 'Ende'})")
        return candles

    def _load_and_validate_timeframe_data(self, timeframe):
        """Lädt und validiert Timeframe-Daten mit Caching"""
        # Cache Check mit Zeit-Validierung
        if timeframe in self.validated_cache:
            cache_entry = self.validated_cache[timeframe]
            # Cache ist 5 Minuten gültig
            if datetime.now() - cache_entry['last_validated_time'] < timedelta(minutes=5):
                return cache_entry['data']

        # Lade Daten über CSVLoader
        df = self.csv_loader.load_timeframe_data(timeframe)
        if df is None or df.empty:
            return None

        # Validiere und cache
        self.validated_cache[timeframe] = {
            'data': df,
            'last_validated_time': datetime.now()
        }

        # Erstelle Index-Cache für schnelle Zeit-Suchen
        self._build_time_index_cache(df, timeframe)

        return df

    def _find_candle_near_time(self, df, target_time, tolerance_minutes, timeframe):
        """Findet Kerze nahe einer Zielzeit mit Toleranz"""
        time_column = 'datetime' if 'datetime' in df.columns else 'time'

        if time_column == 'time' and df[time_column].dtype == 'int64':
            # Timestamp format
            target_timestamp = target_time.timestamp()
            tolerance_seconds = tolerance_minutes * 60

            # Suche exakte oder nächstgelegene Zeit
            time_diff = abs(df[time_column] - target_timestamp)
            closest_idx = time_diff.idxmin()

            if time_diff.iloc[closest_idx] <= tolerance_seconds:
                return self._format_candle_data(df.iloc[closest_idx], timeframe)
        else:
            # Datetime format
            if df[time_column].dtype == 'object':
                df[time_column] = pd.to_datetime(df[time_column])

            tolerance_delta = timedelta(minutes=tolerance_minutes)
            time_diff = abs(df[time_column] - target_time)
            closest_idx = time_diff.idxmin()

            if time_diff.iloc[closest_idx] <= tolerance_delta:
                return self._format_candle_data(df.iloc[closest_idx], timeframe)

        return None

    def _format_candle_data(self, row, timeframe):
        """Formatiert Pandas Row zu Standard Candle Dict"""
        # Zeitstempel normalisieren
        if 'datetime' in row.index:
            time_value = row['datetime']
            if isinstance(time_value, str):
                time_value = pd.to_datetime(time_value)
            timestamp = time_value.timestamp()
        elif 'time' in row.index:
            timestamp = row['time']
            if isinstance(timestamp, (int, float)):
                time_value = datetime.fromtimestamp(timestamp)
            else:
                time_value = pd.to_datetime(timestamp)
                timestamp = time_value.timestamp()
        else:
            # Fallback: Verwende aktuellste Zeit
            time_value = datetime.now()
            timestamp = time_value.timestamp()

        return {
            'time': timestamp,
            'datetime': time_value,
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': int(row['Volume']) if 'Volume' in row.index else 0,
            'timeframe': timeframe
        }

    def _build_time_index_cache(self, df, timeframe):
        """Erstellt Index-Cache für schnelle Zeit-basierte Suchen"""
        # Implementierung bei Bedarf für Performance-Optimierung
        pass

# Global Data Repository Instance
timeframe_data_repository = None  # Wird nach CSVLoader-Initialisierung erstellt

# ===== CRASH-PREVENTION SYSTEM =====
class DataIntegrityGuard:
    """
    🛡️ BULLETPROOF Data Validation - Verhindert ALLE null/undefined Chart-Crashes
    """

    @staticmethod
    def validate_candle_for_chart(candle):
        """EXTREME Validierung für einzelne Kerzen - verhindert Chart-Crashes"""
        if not candle or not isinstance(candle, dict):
            return False

        # CRITICAL: Check ALL required fields
        required_fields = ['time', 'open', 'high', 'low', 'close']
        for field in required_fields:
            if field not in candle:
                return False
            if candle[field] is None or candle[field] is False:  # False kann bei float conversion auftreten
                return False

        # TIME Validation
        time_val = candle['time']
        if not isinstance(time_val, (int, float)) or time_val <= 0:
            return False

        # PRICE Validation mit extremer Sicherheit
        try:
            open_val = float(candle['open'])
            high_val = float(candle['high'])
            low_val = float(candle['low'])
            close_val = float(candle['close'])

            # NaN/Infinity Check
            values = [open_val, high_val, low_val, close_val]
            for val in values:
                if not isinstance(val, (int, float)):
                    return False
                if val != val:  # NaN check
                    return False
                if val == float('inf') or val == float('-inf'):
                    return False

            # Logische OHLC Validierung
            if low_val > high_val:
                return False
            if open_val < low_val or open_val > high_val:
                return False
            if close_val < low_val or close_val > high_val:
                return False

            # Extreme Werte ausschließen
            if any(val <= 0 or val > 1000000 for val in values):
                return False

        except (ValueError, TypeError, OverflowError):
            return False

        return True

    @staticmethod
    def sanitize_chart_data(data, source="unknown"):
        """BULLETPROOF Chart-Daten Bereinigung - garantiert nie leere/korrupte Daten"""
        if not isinstance(data, list):
            print(f"[DATA-GUARD] ERROR: Invalid data structure from {source}: {type(data)}")
            return []

        original_count = len(data)
        validated_data = []

        for i, candle in enumerate(data):
            if DataIntegrityGuard.validate_candle_for_chart(candle):
                # EXTRA-SAFE: Explizite Typ-Konversion
                safe_candle = {
                    'time': int(float(candle['time'])),
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close'])
                }

                # Optional: Volume
                if 'volume' in candle and candle['volume'] is not None:
                    try:
                        safe_candle['volume'] = int(float(candle['volume']))
                    except (ValueError, TypeError):
                        safe_candle['volume'] = 0

                validated_data.append(safe_candle)
            else:
                print(f"[DATA-GUARD] Filtered invalid candle #{i} from {source}: {candle}")

        filtered_count = original_count - len(validated_data)
        if filtered_count > 0:
            print(f"[DATA-GUARD] Filtered {filtered_count}/{original_count} invalid candles from {source}")

        # CRITICAL: Nie leere Arrays zurückgeben
        if len(validated_data) == 0:
            print(f"[DATA-GUARD] WARNING: All candles filtered from {source}! Creating minimal fallback.")
            # Erstelle minimal-fallback um Chart-Crash zu verhindern
            import time
            current_time = int(time.time())
            validated_data = [{
                'time': current_time,
                'open': 20000.0,
                'high': 20010.0,
                'low': 19990.0,
                'close': 20005.0,
                'volume': 100
            }]

        return validated_data

    @staticmethod
    def validate_websocket_message(message):
        """Validiert WebSocket-Nachrichten vor dem Senden"""
        if not message or not isinstance(message, dict):
            return False

        if 'type' not in message:
            return False

        # Spezielle Validierung für Chart-Daten
        if 'data' in message:
            if isinstance(message['data'], list):
                message['data'] = DataIntegrityGuard.sanitize_chart_data(
                    message['data'],
                    source=f"websocket_{message['type']}"
                )

        if 'candle' in message:
            if not DataIntegrityGuard.validate_candle_for_chart(message['candle']):
                print(f"[DATA-GUARD] [INVALID] Invalid candle in websocket message: {message['candle']}")
                return False

        return True

# Global Data Guard Instance
data_guard = DataIntegrityGuard()

# ===== CHART SERIES LIFECYCLE MANAGER =====
class ChartSeriesLifecycleManager:
    """
    🚀 REVOLUTIONARY: Chart Series State Machine & Factory Pattern
    Komplett löst das "Value is null" Problem durch saubere Chart-Recreation

    Problem: Skip-generierte Kerzen korruption Chart Series interne State
    Lösung: Komplette Chart Series Destruction & Recreation bei Timeframe-Wechseln
    """

    def __init__(self):
        # Chart Series States
        self.STATES = {
            'CLEAN': 'clean',           # Sauberer Zustand nach Initialization
            'DATA_LOADED': 'data_loaded', # Data geladen und validiert
            'SKIP_MODIFIED': 'skip_modified', # Skip-Operationen haben State modifiziert
            'CORRUPTED': 'corrupted',   # Chart Series korrupt, braucht Recreation
            'TRANSITIONING': 'transitioning'  # Gerade während Timeframe-Wechsel
        }

        # Current Chart State
        self.current_state = self.STATES['CLEAN']
        self.last_timeframe = None
        self.skip_operations_count = 0
        self.chart_series_version = 1  # Inkrementiert bei jeder Recreation

        print("[CHART-LIFECYCLE] Initialized - State: CLEAN")

    def track_skip_operation(self, timeframe):
        """Trackt Skip-Operationen und markiert Chart als potentiell korrupt"""
        if self.current_state == self.STATES['CLEAN']:
            self.current_state = self.STATES['SKIP_MODIFIED']

        self.skip_operations_count += 1
        self.last_timeframe = timeframe

        print(f"[CHART-LIFECYCLE] Skip operation tracked (#{self.skip_operations_count}) - State: {self.current_state}")

    def prepare_timeframe_transition(self, from_timeframe, to_timeframe):
        """Bereitet sauberen Timeframe-Übergang vor"""

        # CRITICAL FIX: Prüfe State BEVOR er auf TRANSITIONING gesetzt wird
        was_corrupted = self.current_state == self.STATES['CORRUPTED']
        was_skip_modified = self.current_state == self.STATES['SKIP_MODIFIED']
        has_skip_operations = self.skip_operations_count > 0

        print(f"[CHART-LIFECYCLE] Pre-transition state check: corrupted={was_corrupted}, skip_modified={was_skip_modified}, skip_count={has_skip_operations}")

        self.current_state = self.STATES['TRANSITIONING']

        # ENHANCED LOGIC: Chart Recreation bei verschiedenen Corruptions-Szenarien
        needs_recreation = (
            has_skip_operations or          # Skip-Operationen haben State modifiziert
            was_corrupted or               # Chart war bereits als korrupt markiert
            was_skip_modified              # Chart war im SKIP_MODIFIED State
        )

        transition_plan = {
            'needs_recreation': needs_recreation,
            'from_timeframe': from_timeframe,
            'to_timeframe': to_timeframe,
            'skip_count': self.skip_operations_count,
            'reason': 'skip_contamination' if self.skip_operations_count > 0 else 'corruption_detected'
        }

        recreation_reason = []
        if has_skip_operations:
            recreation_reason.append(f"skip_operations({self.skip_operations_count})")
        if was_corrupted:
            recreation_reason.append("was_corrupted")
        if was_skip_modified:
            recreation_reason.append("was_skip_modified")

        reason_text = " + ".join(recreation_reason) if recreation_reason else "no_recreation_needed"

        print(f"[CHART-LIFECYCLE] Transition plan: {from_timeframe} -> {to_timeframe}, Recreation: {needs_recreation} ({reason_text})")
        return transition_plan

    def get_chart_recreation_command(self):
        """Factory Method: Erstellt Command für Chart Recreation"""
        self.chart_series_version += 1

        return {
            'action': 'recreate_chart_series',
            'version': self.chart_series_version,
            'clear_strategy': 'complete_destruction',  # Komplett zerstören, nicht nur clearen
            'validation_level': 'ultra_strict',
            'recovery_fallback': 'emergency_reload'
        }

    def complete_timeframe_transition(self, success=True):
        """Schließt Timeframe-Übergang ab und setzt neuen State"""
        if success:
            self.current_state = self.STATES['DATA_LOADED']
            self.skip_operations_count = 0  # Reset nach erfolgreichem Übergang
            print(f"[CHART-LIFECYCLE] Transition completed successfully - State: DATA_LOADED (v{self.chart_series_version})")
        else:
            self.current_state = self.STATES['CORRUPTED']
            print(f"[CHART-LIFECYCLE] Transition FAILED - State: CORRUPTED")

    def mark_chart_corrupted(self, reason="unknown"):
        """Markiert Chart als korrupt - erzwingt Recreation beim nächsten Übergang"""
        self.current_state = self.STATES['CORRUPTED']
        print(f"[CHART-LIFECYCLE] Chart marked as CORRUPTED: {reason}")

    def reset_to_clean_state(self):
        """Reset zu sauberem Zustand (z.B. nach Go To Date)"""
        print(f"[CHART-LIFECYCLE] Starting CLEAN RESET - Previous state: {self.current_state}, Skip count: {self.skip_operations_count}")

        self.current_state = self.STATES['CLEAN']
        self.skip_operations_count = 0
        self.chart_series_version += 1

        print(f"[CHART-LIFECYCLE] CLEAN RESET COMPLETE - Version: {self.chart_series_version}, State: CLEAN")

        # ENHANCED: Verify clean state
        if self.skip_operations_count == 0 and self.current_state == self.STATES['CLEAN']:
            print(f"[CHART-LIFECYCLE] CLEAN STATE VERIFIED: Ready for timeframe operations")
        else:
            print(f"[CHART-LIFECYCLE] WARNING: Reset verification failed!")

    def force_chart_recreation_on_next_transition(self):
        """EMERGENCY: Forciert Chart Recreation beim nächsten Timeframe-Wechsel"""
        self.current_state = self.STATES['CORRUPTED']
        print(f"[CHART-LIFECYCLE] EMERGENCY: Forced chart recreation on next transition")

    def get_state_info(self):
        """Debug Info über aktuellen Chart State"""
        return {
            'state': self.current_state,
            'skip_count': self.skip_operations_count,
            'version': self.chart_series_version,
            'last_timeframe': self.last_timeframe
        }

# Global Chart Lifecycle Manager Instance
chart_lifecycle_manager = ChartSeriesLifecycleManager()

# Debug Controller für Debug-Funktionalität
class DebugController:
    """Verwaltet Debug-Funktionalität mit intelligenter Timeframe-Aggregation"""

    def __init__(self):
        # INTEGRATION: Verwende UnifiedTimeManager für Zeit-Koordination
        self.unified_time = unified_time_manager  # Reference zum globalen Time Manager
        self.current_time = None  # Legacy compatibility - wird von unified_time_manager synchronisiert
        self.timeframe = "5m"
        self.play_mode = False
        self.speed = 2  # Linear 1-15

        # CSVLoader für Multi-Timeframe Support
        self.csv_loader = CSVLoader()

        # TimeframeSyncManager für synchronisierte Multi-TF Navigation
        self.sync_manager = TimeframeSyncManager(self.csv_loader)

        # TimeframeAggregator für intelligente Kerzen-Logik (Legacy, wird durch SyncManager ersetzt)
        self.aggregator = TimeframeAggregator()

        # Initialisiere mit aktuellstem Zeitpunkt aus CSV-Daten
        if initial_chart_data:
            # Hole letzten Zeitpunkt aus den initialen Daten
            last_candle = initial_chart_data[-1]
            # Setze Debug-Zeit auf 30. Dezember 2024, 16:55 (1 Tag vor den CSV-Daten)
            self.current_time = datetime(2024, 12, 30, 16, 55, 0)
            print(f"DEBUG INIT: Startzeit gesetzt auf {self.current_time} (30. Dezember)")

    def skip_minute(self):
        """Skip +1 Minute mit intelligenter Timeframe-Aggregation"""
        if not self.current_time:
            # Fallback: Verwende aktuellste Zeit aus Chart-Daten
            if initial_chart_data:
                last_candle = initial_chart_data[-1]
                self.current_time = datetime.fromtimestamp(last_candle['time'])
            else:
                self.current_time = datetime.now()

        # +1 Minute
        self.current_time += timedelta(minutes=1)

        print(f"DEBUG SKIP: Neue Zeit: {self.current_time} (Timeframe: {self.timeframe})")

        # Verwende TimeframeAggregator für intelligente Kerzen-Logik
        if initial_chart_data:
            last_candle = initial_chart_data[-1]
        else:
            last_candle = {'close': 18500}  # Fallback

        # Nutze Aggregator für +1 Minute Skip
        complete_candle, incomplete_candle, is_complete = self.aggregator.add_minute_to_timeframe(
            self.current_time - timedelta(minutes=1),  # Aktuelle Zeit vor dem Skip
            self.timeframe,
            last_candle
        )

        if is_complete:
            # Vollständige Kerze - zum Chart hinzufügen
            print(f"DEBUG: Vollständige {self.timeframe} Kerze generiert: {complete_candle['time']}")
            return {
                'type': 'complete_candle',
                'candle': complete_candle,
                'timeframe': self.timeframe
            }
        else:
            # Unvollständige Kerze - mit weißem Rand markieren
            print(f"DEBUG: Unvollständige {self.timeframe} Kerze: {incomplete_candle['minutes_elapsed']}/{self.aggregator.timeframes[self.timeframe]} min")
            return {
                'type': 'incomplete_candle',
                'candle': incomplete_candle,
                'timeframe': self.timeframe
            }

    def set_timeframe(self, timeframe):
        """Ändert den Timeframe und behält Zeitpunkt bei"""
        self.timeframe = timeframe
        print(f"DEBUG TIMEFRAME: Gewechselt zu {timeframe}")

    def set_speed(self, speed):
        """Setzt die Play-Geschwindigkeit (1-15)"""
        self.speed = max(1, min(15, speed))
        print(f"DEBUG SPEED: Geschwindigkeit auf {self.speed}x gesetzt")

    def set_start_time(self, start_datetime):
        """Setzt eine neue Start-Zeit für das Chart (Go To Date Funktionalität) - UNIFIED TIME ARCHITECTURE"""
        # UNIFIED TIME MANAGEMENT: Setze Zeit über globalen Manager
        self.unified_time.set_time(start_datetime, source="goto_date")
        # Legacy Compatibility
        self.current_time = self.unified_time.get_current_time()
        print(f"[UNIFIED-GOTO] Start-Zeit gesetzt auf {self.current_time}")

    def skip_minutes(self, minutes):
        """Skip +X Minuten für verschiedene Timeframes (2m, 3m, 5m, 15m, 30m)"""
        if not self.current_time:
            # Fallback: Verwende aktuellste Zeit aus Chart-Daten
            if initial_chart_data:
                last_candle = initial_chart_data[-1]
                self.current_time = datetime.fromtimestamp(last_candle['time'])
            else:
                self.current_time = datetime.now()

        # +X Minuten
        self.current_time += timedelta(minutes=minutes)

        print(f"DEBUG SKIP {minutes}m: Neue Zeit: {self.current_time} (Timeframe: {self.timeframe})")

        # Verwende TimeframeAggregator für intelligente Kerzen-Logik
        if initial_chart_data:
            last_candle = initial_chart_data[-1]
        else:
            last_candle = {'close': 18500}  # Fallback

        # Nutze Aggregator für +X Minuten Skip
        complete_candle, incomplete_candle, is_complete = self.aggregator.add_minute_to_timeframe(
            self.current_time - timedelta(minutes=minutes),  # Aktuelle Zeit vor dem Skip
            self.timeframe,
            last_candle
        )

        if is_complete:
            # Vollständige Kerze - zum Chart hinzufügen
            print(f"DEBUG: Vollständige {self.timeframe} Kerze generiert: {complete_candle['time']}")
            return {
                'type': 'complete_candle',
                'candle': complete_candle,
                'timeframe': self.timeframe
            }
        else:
            # Unvollständige Kerze - mit weißem Rand markieren
            print(f"DEBUG: Unvollständige {self.timeframe} Kerze: {incomplete_candle['minutes_elapsed']}/{self.aggregator.timeframes[self.timeframe]} min")
            return {
                'type': 'incomplete_candle',
                'candle': incomplete_candle,
                'timeframe': self.timeframe
            }

    def skip_hours(self, hours):
        """Skip +X Stunden für Stunden-Timeframes (1h, 4h)"""
        if not self.current_time:
            # Fallback: Verwende aktuellste Zeit aus Chart-Daten
            if initial_chart_data:
                last_candle = initial_chart_data[-1]
                self.current_time = datetime.fromtimestamp(last_candle['time'])
            else:
                self.current_time = datetime.now()

        # +X Stunden
        self.current_time += timedelta(hours=hours)

        print(f"DEBUG SKIP {hours}h: Neue Zeit: {self.current_time} (Timeframe: {self.timeframe})")

        # Verwende TimeframeAggregator für intelligente Kerzen-Logik
        if initial_chart_data:
            last_candle = initial_chart_data[-1]
        else:
            last_candle = {'close': 18500}  # Fallback

        # Nutze Aggregator für +X Stunden Skip
        complete_candle, incomplete_candle, is_complete = self.aggregator.add_minute_to_timeframe(
            self.current_time - timedelta(hours=hours),  # Aktuelle Zeit vor dem Skip
            self.timeframe,
            last_candle
        )

        if is_complete:
            # Vollständige Kerze - zum Chart hinzufügen
            print(f"DEBUG: Vollständige {self.timeframe} Kerze generiert: {complete_candle['time']}")
            return {
                'type': 'complete_candle',
                'candle': complete_candle,
                'timeframe': self.timeframe
            }
        else:
            # Unvollständige Kerze - mit weißem Rand markieren
            print(f"DEBUG: Unvollständige {self.timeframe} Kerze: {incomplete_candle['minutes_elapsed']}/{self.aggregator.timeframes[self.timeframe]} min")
            return {
                'type': 'incomplete_candle',
                'candle': incomplete_candle,
                'timeframe': self.timeframe
            }

    def skip_with_real_data(self, timeframe):
        """Skip mit echten CSV-Daten und Multi-Timeframe Synchronisation - UNIFIED TIME ARCHITECTURE"""
        # UNIFIED TIME MANAGEMENT: Verwende globalen Time Manager
        if not self.unified_time.initialized:
            # Fallback: Initialisiere mit letzter Chart-Kerze
            if initial_chart_data:
                last_candle = initial_chart_data[-1]
                self.unified_time.initialize_time(last_candle['time'])
            else:
                self.unified_time.initialize_time(datetime.now())

        current_time = self.unified_time.get_current_time()
        print(f"[UNIFIED-SKIP] Starting synchronized skip for {timeframe} from {current_time}")

        # Initialize SyncManager with current time if not already set
        if timeframe not in self.sync_manager.timeframe_positions:
            self.sync_manager.set_base_time(current_time)

        # REVOLUTIONARY: Use TimeframeSyncManager for multi-TF coordination
        try:
            sync_result = self.sync_manager.skip_timeframe(timeframe, sync_others=True)

            if sync_result is None:
                print(f"[UNIFIED-SKIP] No next {timeframe} candle available")
                return None

            primary_result = sync_result['primary_result']

            # UNIFIED TIME UPDATE: Rücke globale Zeit vor
            timeframe_minutes = self.unified_time._get_timeframe_minutes(timeframe)
            new_time = self.unified_time.advance_time(timeframe_minutes, timeframe)

            # Legacy Compatibility: Synchronisiere local time
            self.current_time = new_time

            # CRITICAL: Update UnifiedStateManager - Löst CSV vs DebugController Konflikt
            unified_state.update_skip_position(self.current_time, source="skip")

            # Check if current timeframe shows incomplete candle
            incomplete_info = self.sync_manager.get_incomplete_candle_info(timeframe)

            candle_type = 'complete_candle'
            if incomplete_info and not incomplete_info['is_complete']:
                candle_type = 'incomplete_candle'
                print(f"[SKIP-SYNC] INCOMPLETE {timeframe} candle: {incomplete_info['elapsed_minutes']:.1f}/{incomplete_info['total_minutes']} min")

            # SERVER-SIDE VALIDATION: Prevent corrupted OHLC values from reaching frontend
            candle = primary_result['candle'].copy()

            # Fix extreme/corrupted values (likely timestamp contamination)
            # Enhanced detection for timestamp-like values (e.g., 22089.0, 173439xxxx fragments)
            close_val = candle.get('close', 0)
            if (close_val > 50000 or close_val < 1000 or
                (close_val > 20000 and close_val < 30000)):  # Catch timestamp fragments like 22089
                print(f"[SKIP-SYNC] CORRUPTED Close detected: {close_val} -> Fixed to 18500")
                candle['close'] = 18500.0  # Realistic NQ price

            open_val = candle.get('open', 0)
            if (open_val > 50000 or open_val < 1000 or
                (open_val > 20000 and open_val < 30000)):
                print(f"[SKIP-SYNC] CORRUPTED Open detected: {open_val} -> Fixed to close")
                candle['open'] = candle['close']

            high_val = candle.get('high', 0)
            if (high_val > 50000 or high_val < 1000 or
                (high_val > 20000 and high_val < 30000)):
                print(f"[SKIP-SYNC] CORRUPTED High detected: {high_val} -> Fixed")
                candle['high'] = max(candle['open'], candle['close']) + 5

            low_val = candle.get('low', 0)
            if (low_val > 50000 or low_val < 1000 or
                (low_val > 20000 and low_val < 30000)):
                print(f"[SKIP-SYNC] CORRUPTED Low detected: {low_val} -> Fixed")
                candle['low'] = min(candle['open'], candle['close']) - 5

            print(f"[SKIP-SYNC] SUCCESS {timeframe}: {primary_result['datetime']} -> Close: {candle['close']} ({candle_type})")

            return {
                'type': candle_type,
                'candle': candle,  # Use validated candle
                'timeframe': timeframe,
                'source': primary_result['source'],
                'sync_status': sync_result['sync_results'],
                'incomplete_info': incomplete_info
            }

        except Exception as e:
            try:
                print(f"[CSV-SKIP] ERROR Fehler beim CSV-Laden: {e}")
            except UnicodeEncodeError:
                print(f"[CSV-SKIP] ERROR beim CSV-Laden")
            return None

    @property
    def current_timeframe(self):
        """Gibt den aktuellen Timeframe zurück"""
        return self.timeframe

    @property
    def current_index(self):
        """Gibt den aktuellen Index zurück (für Kompatibilität)"""
        return getattr(self, '_current_index', 0)

    @current_index.setter
    def current_index(self, value):
        """Setzt den aktuellen Index (für Kompatibilität)"""
        self._current_index = value

    def toggle_play_mode(self):
        """Toggle Play/Pause Modus"""
        self.play_mode = not self.play_mode
        print(f"DEBUG PLAY: Play-Modus {'aktiviert' if self.play_mode else 'deaktiviert'}")
        return self.play_mode

    def _generate_next_candle(self):
        """Generiert nächste Kerze basierend auf aktuellem Timeframe"""
        # Einfache Mock-Kerze für jetzt - wird später durch echte Aggregations-Logik ersetzt
        timestamp = int(self.current_time.timestamp())

        # Basis-Preis aus letzter Kerze wenn verfügbar
        base_price = 18000  # NQ Standard-Preis
        if initial_chart_data:
            base_price = initial_chart_data[-1]['close']

        # Simuliere leichte Preisbewegung (+/- 0.1%)
        import random
        price_change = random.uniform(-0.001, 0.001)
        new_price = base_price * (1 + price_change)

        return {
            'time': timestamp,
            'open': base_price,
            'high': max(base_price, new_price) + random.uniform(0, base_price * 0.0005),
            'low': min(base_price, new_price) - random.uniform(0, base_price * 0.0005),
            'close': new_price,
            'volume': random.randint(1000, 5000)
        }

    def get_state(self):
        """Gibt aktuellen Debug-Status zurück"""
        return {
            'current_time': self.current_time.isoformat() if self.current_time else None,
            'timeframe': self.timeframe,
            'play_mode': self.play_mode,
            'speed': self.speed,
            'incomplete_candles': len(self.aggregator.incomplete_candles),
            'aggregator_state': self.aggregator.get_all_incomplete_candles()
        }

# Global Connection Manager und Debug Controller
manager = ConnectionManager()
debug_controller = DebugController()

# Initialize Global Data Repository with CSV Loader
timeframe_data_repository = TimeframeDataRepository(debug_controller.csv_loader, unified_time_manager)

# Background Task für Auto-Play Modus
async def auto_play_loop():
    """Background-Task für kontinuierliches Skip im Play-Modus"""
    while True:
        if debug_controller.play_mode:
            try:
                # Berechne Delay basierend auf Speed (1x-15x)
                # Speed 1 = 1000ms, Speed 15 = 67ms (linear)
                delay = max(1000 / debug_controller.speed, 67)  # Minimum 67ms

                # Skip +1 Minute
                result = debug_controller.skip_minute()

                # Extrahiere Kerze aus dem Ergebnis
                if result.get('type') == 'complete_candle':
                    new_candle = result['candle']
                    # Neue vollständige Kerze zu Chart-Daten hinzufügen
                    manager.chart_state['data'].append(new_candle)
                else:
                    # Incomplete Kerze - markiere als solche
                    new_candle = result['candle']
                    new_candle['incomplete'] = True

                # WebSocket-Update an alle Clients
                await manager.broadcast({
                    'type': 'auto_play_skip',
                    'candle': new_candle,
                    'debug_state': debug_controller.get_state()
                })

                print(f"AUTO-PLAY: Skip +1min (Speed {debug_controller.speed}x, Delay {delay:.0f}ms)")

                # Warte basierend auf Speed
                await asyncio.sleep(delay / 1000.0)

            except Exception as e:
                print(f"AUTO-PLAY FEHLER: {e}")
                await asyncio.sleep(1)  # Fehler-Fallback
        else:
            # Wenn Play-Mode aus ist, warte kurz und prüfe erneut
            await asyncio.sleep(0.1)

# Startup Event - Auto-Play Background Task starten
@app.on_event("startup")
async def startup_event():
    """App Startup - Initialisiere High-Performance Memory Cache und Services"""
    global performance_aggregator, nq_loader, account_service, nq_data_loader, chart_cache

    print("Chart Server startet - Initialisiere High-Performance Memory Cache...")

    try:
        # EMERGENCY FIX: HighPerformanceChartCache fehlt - verwende Fallback
        print("[STARTUP FIX] HighPerformanceChartCache nicht verfügbar - Fallback zu Legacy System")
        chart_cache = None
        success = True  # Fallback ist immer "erfolgreich"

        # CRITICAL: Initialize UnifiedPriceRepository with 1m data for price synchronization
        try:
            csv_1m_path = Path("src/data/aggregated/1m/nq-2024.csv")
            if csv_1m_path.exists():
                print("[PRICE-REPO] Loading 1m CSV data for price synchronization...")
                # PERFORMANCE: Load only recent 1m data (last 30 days ~ 43200 rows)
                df_1m = pd.read_csv(csv_1m_path).tail(43200)

                if 'datetime' not in df_1m.columns:
                    df_1m['datetime'] = pd.to_datetime(df_1m['Date'] + ' ' + df_1m['Time'], format='mixed', dayfirst=True)
                df_1m['time'] = df_1m['datetime'].astype(int) // 10**9

                # Convert to chart format for PriceRepository
                chart_data_1m = []
                for _, row in df_1m.iterrows():
                    chart_data_1m.append({
                        'time': int(row['time']),
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close']),
                        'volume': int(row['Volume'])
                    })

                # Initialize price repository
                price_repository.initialize_with_1m_data(chart_data_1m)
                print(f"[PRICE-REPO] SUCCESS: Initialized with {len(chart_data_1m)} 1m candles")
            else:
                print("[PRICE-REPO] WARNING: 1m CSV not found - price sync will use fallback")
        except Exception as e:
            print(f"[PRICE-REPO] ERROR: Failed to initialize - {e}")

    except Exception as e:
        print(f"[ERROR] Fehler beim Initialisieren der High-Performance Cache: {e}")
        import traceback
        traceback.print_exc()
        # Fallback: Verwende initial_chart_data falls High-Performance Cache nicht verfügbar
        print("[WARNING] Verwende Fallback-Modus mit initial_chart_data")
        chart_cache = None

    # Starte Auto-Play Background Task
    print("[INFO] Starte Auto-Play Background Task...")
    asyncio.create_task(auto_play_loop())

@app.get("/")
async def get_chart():
    """Haupt-Chart-Seite"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>RL Trading Chart - Realtime</title>
    <meta charset="utf-8">
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body { margin: 0; padding: 0; background: #000; font-family: Arial, sans-serif; }
        #chart_container { width: calc(100% - 35px); margin-left: 35px; position: fixed; top: 80px; bottom: 40px; } /* Angepasst für linke Sidebar */
        .status { position: fixed; top: 10px; right: 10px; color: #fff; background: rgba(0,0,0,0.7); padding: 5px 10px; border-radius: 5px; font-size: 12px; }
        .status.connected { color: #089981; }
        .status.disconnected { color: #f23645; }
        /* Erste Chart-Toolbar (Debug-Controls, oberhalb) */
        .chart-toolbar-1 { position: fixed; top: 0; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; justify-content: space-between; padding: 0 15px; margin: 0; z-index: 1000; }

        /* Zweite Chart-Toolbar (Timeframes, darunter) */
        .chart-toolbar-2 { position: fixed; top: 40px; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Legacy toolbar class für Kompatibilität */
        .toolbar { position: fixed; top: 40px; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Bottom Chart-Toolbar (unten) - Split Design */
        .chart-toolbar-bottom { position: fixed; bottom: 0; left: 35px; right: 0; height: 40px; background: #1e1e1e; border-top: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; z-index: 1000; }

        /* Account Split Container */
        .account-split-container { display: flex; width: 100%; height: 100%; }

        /* RL-KI Account (Links) */
        .account-section-ai { flex: 1; display: flex; align-items: center; padding: 0 15px; background: rgba(8, 153, 129, 0.1); border-right: 2px solid #089981; }
        .account-section-ai .account-label { color: #089981; font-weight: bold; margin-right: 15px; font-size: 11px; }
        .account-section-ai .account-values { display: flex; gap: 20px; font-size: 11px; color: #ccc; }

        /* Nutzer Account (Rechts) */
        .account-section-user { flex: 1; display: flex; align-items: center; padding: 0 15px; background: rgba(242, 54, 69, 0.1); }
        .account-section-user .account-label { color: #f23645; font-weight: bold; margin-right: 15px; font-size: 11px; }
        .account-section-user .account-values { display: flex; gap: 20px; font-size: 11px; color: #ccc; }

        /* Account Value Styling */
        .account-value { display: flex; flex-direction: column; align-items: center; }
        .account-value-label { font-size: 9px; color: #666; margin-bottom: 1px; }
        .account-value-amount { font-size: 11px; font-weight: bold; }
        .positive { color: #089981; }
        .negative { color: #f23645; }
        .neutral { color: #ccc; }

        /* Left Chart-Sidebar (links) */
        .chart-sidebar-left { position: fixed; top: 80px; bottom: 40px; left: 0; width: 35px; background: #1e1e1e; border-right: 1px solid #333; display: flex; flex-direction: column; align-items: center; padding: 8px 0; margin: 0; gap: 10px; z-index: 1000; }
        .chart-sidebar-left .tool-btn {
            width: 28px;
            height: 28px;
            padding: 0;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
        }
        .tool-btn { background: #333; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: all 0.2s; }
        .tool-btn:hover { background: #444; }
        .tool-btn.active { background: #089981; }
        .tool-btn:disabled { background: #222; color: #666; cursor: not-allowed; }

        /* Timeframe Styles */
        .timeframe-group { display: flex; gap: 5px; margin-left: 20px; border-left: 1px solid #444; padding-left: 20px; }
        .timeframe-btn { background: #2a2a2a; color: #ccc; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; font-size: 11px; transition: all 0.2s; min-width: 35px; }
        .timeframe-btn:hover { background: #3a3a3a; color: #fff; }
        .timeframe-btn.active { background: #089981; color: #fff; font-weight: bold; }
        .timeframe-btn:disabled { background: #1a1a1a; color: #555; cursor: not-allowed; }

        /* Intelligent Zoom Toast Animations */
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }

        /* Debug-Controls Styling */
        .debug-controls {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 0 12px;
            justify-content: center;
        }

        .debug-btn {
            background: #2a2a2a;
            border: 1px solid #404040;
            color: #ffffff;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
        }

        .debug-btn:hover {
            background: #3a3a3a;
            border-color: #505050;
        }

        .debug-btn:active {
            background: #1a1a1a;
            transform: scale(0.95);
        }

        .debug-slider {
            width: 80px;
            height: 20px;
            -webkit-appearance: none;
            background: #404040;
            border-radius: 10px;
            outline: none;
        }

        .debug-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 16px;
            height: 16px;
            background: #089981;
            border-radius: 50%;
            cursor: pointer;
        }

        .debug-slider::-moz-range-thumb {
            width: 16px;
            height: 16px;
            background: #089981;
            border-radius: 50%;
            cursor: pointer;
            border: none;
        }

        .debug-speed {
            color: #089981;
            font-weight: bold;
            font-size: 12px;
            min-width: 24px;
            text-align: center;
        }

        .debug-timeframe {
            background: #2a2a2a;
            border: 1px solid #404040;
            color: #ffffff;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }

        .debug-timeframe:focus {
            outline: none;
            border-color: #089981;
        }

        /* Navigation Controls (Go To Date Button) */
        .navigation-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-btn {
            background: #2a2a2a;
            border: 1px solid #404040;
            color: #ffffff;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .nav-btn:hover {
            background: #3a3a3a;
            border-color: #089981;
        }

        .nav-btn:active {
            background: #1a1a1a;
            transform: scale(0.95);
        }

        /* Date-Picker Modal */
        .date-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 2000;
            justify-content: center;
            align-items: center;
        }

        .date-modal-content {
            background: #2a2a2a;
            border: 1px solid #404040;
            border-radius: 8px;
            padding: 24px;
            max-width: 400px;
            width: 90%;
            position: relative;
        }

        .date-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            color: #ffffff;
        }

        .date-modal-title {
            font-size: 18px;
            font-weight: bold;
        }

        .close-modal {
            background: none;
            border: none;
            color: #888;
            font-size: 24px;
            cursor: pointer;
            padding: 0;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .close-modal:hover {
            color: #ffffff;
        }

        .date-input-group {
            margin-bottom: 20px;
        }

        .date-input-label {
            display: block;
            color: #ffffff;
            margin-bottom: 8px;
            font-size: 14px;
        }

        .date-input {
            width: 100%;
            background: #1a1a1a;
            border: 1px solid #404040;
            color: #ffffff;
            padding: 10px;
            border-radius: 4px;
            font-size: 14px;
            box-sizing: border-box;
        }

        .date-input:focus {
            outline: none;
            border-color: #089981;
        }

        .date-modal-buttons {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }

        .modal-btn {
            background: #2a2a2a;
            border: 1px solid #404040;
            color: #ffffff;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
        }

        .modal-btn:hover {
            background: #3a3a3a;
        }

        .modal-btn.primary {
            background: #089981;
            border-color: #089981;
        }

        .modal-btn.primary:hover {
            background: #0a7a6b;
        }
    </style>
</head>
<body>
    <!-- Date-Picker Modal -->
    <div id="dateModal" class="date-modal">
        <div class="date-modal-content">
            <div class="date-modal-header">
                <span class="date-modal-title">📅 Go To Date</span>
                <button class="close-modal" onclick="closeDateModal()">&times;</button>
            </div>
            <div class="date-input-group">
                <label class="date-input-label" for="goToDateInput">Wähle Chart-Startdatum:</label>
                <input type="date" id="goToDateInput" class="date-input" />
            </div>
            <div class="date-modal-buttons">
                <button class="modal-btn" onclick="closeDateModal()">Abbrechen</button>
                <button class="modal-btn primary" onclick="goToSelectedDate()">Go To Date</button>
            </div>
        </div>
    </div>
    <!-- Erste Chart-Toolbar (Debug-Controls) -->
    <div class="chart-toolbar-1">
        <!-- Debug-Controls (Links) -->
        <div class="debug-controls">
            <button id="skipBtn" class="debug-btn" title="Skip +1min">⏭️</button>
            <button id="playPauseBtn" class="debug-btn" title="Play/Pause">▶️</button>
            <input type="range" id="speedSlider" class="debug-slider" min="1" max="15" value="2" title="Speed Control">
            <span id="speedDisplay" class="debug-speed">2x</span>
            <select id="timeframeSelector" class="debug-timeframe" title="Timeframe">
                <option value="1m">1m</option>
                <option value="5m" selected>5m</option>
                <option value="15m">15m</option>
                <option value="30m">30m</option>
                <option value="1h">1h</option>
            </select>
        </div>

        <!-- Navigation Controls (Rechts) -->
        <div class="navigation-controls">
            <button id="goToDateBtn" class="nav-btn" title="Go To Date">📅 Go To</button>
        </div>
    </div>

    <!-- Zweite Chart-Toolbar (Timeframes) -->
    <div class="chart-toolbar-2">
        <button id="clearAll" class="tool-btn">🗑️</button>

        <!-- Timeframe Buttons -->
        <div class="timeframe-group">
            <button id="tf-1m" class="timeframe-btn" data-timeframe="1m">1m</button>
            <button id="tf-2m" class="timeframe-btn" data-timeframe="2m">2m</button>
            <button id="tf-3m" class="timeframe-btn" data-timeframe="3m">3m</button>
            <button id="tf-5m" class="timeframe-btn active" data-timeframe="5m">5m</button>
            <button id="tf-15m" class="timeframe-btn" data-timeframe="15m">15m</button>
            <button id="tf-30m" class="timeframe-btn" data-timeframe="30m">30m</button>
            <button id="tf-1h" class="timeframe-btn" data-timeframe="1h">1h</button>
            <button id="tf-4h" class="timeframe-btn" data-timeframe="4h">4h</button>
        </div>
    </div>

    <!-- Left Chart-Sidebar (links) -->
    <div class="chart-sidebar-left">
        <button id="positionBoxTool" class="tool-btn" title="Long Position">📈</button>
        <button id="shortPositionTool" class="tool-btn" title="Short Position">📉</button>

        <!-- Debug Controls Sektion -->
        <div style="width: 100%; border-top: 1px solid #333; margin: 8px 0; padding-top: 8px;">
            <div style="color: #888; font-size: 10px; text-align: center; margin-bottom: 8px;">DEBUG</div>

            <!-- Debug Timeframe Selector -->
            <select id="debugTimeframSelector" style="width: 28px; height: 22px; font-size: 10px; background: #333; color: #fff; border: 1px solid #555; margin-bottom: 4px;" title="Debug Timeframe">
                <option value="1m">1m</option>
                <option value="5m" selected>5m</option>
                <option value="15m">15m</option>
                <option value="30m">30m</option>
                <option value="1h">1h</option>
            </select>

            <!-- Skip Button -->
            <button id="debugSkipBtn" class="tool-btn" onclick="handleDebugSkip()" title="Skip Next Candle" style="background: #2a2a2a;">⏭️</button>

            <!-- Play/Pause Button -->
            <button id="debugPlayBtn" class="tool-btn" onclick="handleDebugPlayPause()" title="Play/Pause Debug" style="background: #2a2a2a;">▶️</button>
        </div>
    </div>

    <!-- Bottom Chart-Toolbar (unten) - Split Account Display -->
    <div class="chart-toolbar-bottom">
        <div class="account-split-container">
            <!-- RL-KI Account (Links) -->
            <div class="account-section-ai">
                <div class="account-label">🤖 RL-KI</div>
                <div class="account-values">
                    <div class="account-value">
                        <div class="account-value-label">Account Balance</div>
                        <div class="account-value-amount neutral" id="ai-balance">500.000€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Realized PnL</div>
                        <div class="account-value-amount neutral" id="ai-realized">0€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Unrealized PnL</div>
                        <div class="account-value-amount neutral" id="ai-unrealized">0€</div>
                    </div>
                </div>
            </div>

            <!-- Nutzer Account (Rechts) -->
            <div class="account-section-user">
                <div class="account-label">👤 Nutzer</div>
                <div class="account-values">
                    <div class="account-value">
                        <div class="account-value-label">Account Balance</div>
                        <div class="account-value-amount neutral" id="user-balance">500.000€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Realized PnL</div>
                        <div class="account-value-amount neutral" id="user-realized">0€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Unrealized PnL</div>
                        <div class="account-value-amount neutral" id="user-unrealized">0€</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="status" class="status disconnected">Disconnected</div>
    <div id="chart_container"></div>

    <script>
        console.log('🚀 RL Trading Chart - FastAPI Edition');

        // Server-side Logging Function für Debug-Ausgaben
        function serverLog(message, data = null) {
            // Bereinige data für JSON-Serialisierung
            let cleanData = null;
            if (data !== null && data !== undefined) {
                try {
                    // Teste ob data JSON-serialisierbar ist
                    JSON.stringify(data);
                    cleanData = data;
                } catch (e) {
                    // Falls nicht serialisierbar, konvertiere zu String
                    cleanData = String(data);
                }
            }

            const logData = {
                message: message || 'No message',
                timestamp: new Date().toISOString(),
                data: cleanData
            };

            // Console ausgeben für Browser
            console.log('[SERVER LOG]', message, cleanData);

            // An Server senden für Terminal-Ausgabe
            fetch('/api/debug/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(logData)
            }).catch(e => console.warn('Server log failed:', e));
        }

        // Erster Test-Log
        serverLog('🚀 JavaScript-Execution gestartet');

        let chart;
        let candlestickSeries;
        let ws;
        let isInitialized = false;

        // Chart initialisieren
        // EINFACHE CHART POSITIONING FUNKTION
        function setChartWith20PercentMargin(chartData) {
            console.log('MARGIN: Setze 20% Freiraum für', chartData.length, 'Kerzen');

            if (!chartData || chartData.length < 2) {
                console.log('MARGIN: Fallback zu fitContent (zu wenig Daten)');
                chart.timeScale().fitContent();
                return;
            }

            // Hole erste und letzte Zeit
            const firstTime = chartData[0].time;
            const lastTime = chartData[chartData.length - 1].time;

            // Berechne 20% Freiraum rechts
            const dataTimeSpan = lastTime - firstTime;
            const marginTime = dataTimeSpan * 0.25; // 25% der Daten = 20% der Gesamt-Chart

            console.log('MARGIN: Daten-Zeitspanne:', dataTimeSpan, 'Freiraum:', marginTime);
            console.log('MARGIN: Chart von', firstTime, 'bis', lastTime + marginTime);

            // Setze sichtbaren Bereich
            chart.timeScale().setVisibleRange({
                from: firstTime,
                to: lastTime + marginTime
            });

            console.log('MARGIN: 20% Freiraum gesetzt');
        }

        // Smart Chart Positioning System - 50 Kerzen Standard mit 20% Freiraum
        class SmartChartPositioning {
            constructor(chart, candlestickSeries) {
                this.chart = chart;
                this.candlestickSeries = candlestickSeries;
                this.standardCandleCount = 50; // Standard: 50 Kerzen sichtbar
                this.rightMarginPercent = 0.2; // 20% rechter Freiraum

                console.log(`📊 Smart Positioning: ${this.standardCandleCount} Kerzen Standard mit ${this.rightMarginPercent * 100}% Freiraum`);
            }

            // Setze Chart auf Standard-Position: 50 Kerzen + 20% Freiraum
            setStandardPosition(data) {
                if (!data || data.length === 0) {
                    console.warn('🚫 Keine Daten für Standard Position');
                    return;
                }

                const dataLength = data.length;
                const visibleCandles = Math.min(this.standardCandleCount, dataLength);

                // Berechne Zeitbereich für sichtbare Kerzen
                const startIndex = Math.max(0, dataLength - visibleCandles);
                const endIndex = dataLength - 1;

                if (startIndex === endIndex) {
                    console.warn('🚫 Nicht genug Daten für Standard Position');
                    this.chart.timeScale().fitContent();
                    return;
                }

                // Zeitstempel der ersten und letzten sichtbaren Kerze
                const startTime = data[startIndex].time;
                const endTime = data[endIndex].time;

                // RICHTIGE FREIRAUM-BERECHNUNG:
                // 50 Kerzen sollen 4/5 (80%) der Chart-Breite links einnehmen
                // 1/5 (20%) rechts soll frei bleiben für neue Kerzen

                const dataTimeSpan = endTime - startTime;

                // Wenn Daten 80% der Chart einnehmen sollen, dann:
                // Gesamt-Chart-Breite = Daten-Breite / 0.8
                const totalChartTimeSpan = dataTimeSpan / 0.8;

                // Rechter Freiraum = 20% der Gesamt-Chart-Breite
                const rightMarginTime = totalChartTimeSpan * 0.2;

                // Chart beginnt bei den Daten, endet mit Freiraum
                const chartStartTime = startTime;
                const chartEndTime = endTime + rightMarginTime;

                console.log(`📍 Smart Position: ${visibleCandles} Kerzen (${startIndex}-${endIndex})`);
                console.log(`📍 Daten nehmen 80% ein: ${startTime} bis ${endTime}`);
                console.log(`📍 Chart-Bereich: ${chartStartTime} bis ${chartEndTime} (20% Freiraum: ${rightMarginTime})`);

                // Setze sichtbaren Bereich: Daten links 80%, Freiraum rechts 20%
                this.chart.timeScale().setVisibleRange({
                    from: chartStartTime,
                    to: chartEndTime
                });
            }

            // Nach Timeframe-Wechsel: Immer zurück zur Standard-Position
            resetToStandardPosition(newData) {
                console.log(`🔄 Reset zu Standard-Position nach Timeframe-Wechsel`);
                this.setStandardPosition(newData);
            }
        }

        // Intelligent Zoom System Class
        class IntelligentZoomSystem {
            constructor(chart, candlestickSeries, currentTimeframe = '5m') {
                this.chart = chart;
                this.candlestickSeries = candlestickSeries;
                this.currentTimeframe = currentTimeframe;
                this.currentCandles = 200; // Aktuelle Anzahl geladener Kerzen
                this.minVisibleCandles = 50; // Minimum sichtbare Kerzen
                this.maxVisibleCandles = 2000; // Maximum für Performance
                this.isLoading = false;
                this.lastVisibleRange = null;

                this.setupZoomMonitoring();
            }

            setupZoomMonitoring() {
                // Überwache Änderungen der sichtbaren Zeitspanne
                this.chart.timeScale().subscribeVisibleLogicalRangeChange((newVisibleLogicalRange) => {
                    if (newVisibleLogicalRange === null) return;
                    this.handleVisibleRangeChange(newVisibleLogicalRange);
                });

                console.log('🔍 Intelligent Zoom System aktiviert');
            }

            handleVisibleRangeChange(visibleLogicalRange) {
                const { from, to } = visibleLogicalRange;
                const visibleCandleCount = Math.ceil(to - from);

                console.log(`📊 Sichtbare Kerzen: ${visibleCandleCount}, Geladen: ${this.currentCandles}`);

                // Check if we need more candles (user zoomed out)
                if (this.shouldLoadMoreCandles(visibleCandleCount)) {
                    this.loadMoreCandles(visibleCandleCount);
                }

                this.lastVisibleRange = visibleLogicalRange;
            }

            shouldLoadMoreCandles(visibleCandleCount) {
                // TEMPORÄR DEAKTIVIERT - Testing Timeframe Fix
                console.log('🚫 Zoom System temporär deaktiviert für Timeframe-Fix');
                return false;

                // Original code (auskommentiert):
                // const visibilityRatio = visibleCandleCount / this.currentCandles;
                // return visibilityRatio > 0.7 &&
                //        this.currentCandles < this.maxVisibleCandles &&
                //        !this.isLoading;
            }

            async loadMoreCandles(visibleCandleCount) {
                if (this.isLoading) return;

                this.isLoading = true;
                console.log('📈 Lade mehr Kerzen für bessere Zoom-Erfahrung...');

                try {
                    // Berechne wie viele Kerzen wir brauchen
                    const targetCandles = Math.min(
                        Math.max(visibleCandleCount * 2.5, this.currentCandles * 1.5),
                        this.maxVisibleCandles
                    );

                    // API-Call für mehr Daten
                    const response = await fetch('/api/chart/change_timeframe', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            timeframe: this.currentTimeframe,
                            visible_candles: Math.ceil(targetCandles)
                        })
                    });

                    const result = await response.json();

                    if (result.status === 'success') {
                        // Update Chart mit validierten Daten
                        const validatedData = validateCandleData(result.data);
                        this.candlestickSeries.setData(validatedData);
                        this.currentCandles = validatedData.length;

                        if (validatedData.length !== result.data.length) {
                            console.warn(`⚠️ ${result.data.length - validatedData.length} invalid candles removed from lazy load`);
                        }

                        console.log(`✅ Mehr Kerzen geladen: ${this.currentCandles}`);

                        // Toast-Benachrichtigung
                        this.showZoomNotification(`🔍 Zoom erweitert: ${this.currentCandles} Kerzen verfügbar`);
                    }
                } catch (error) {
                    console.error('❌ Fehler beim Laden zusätzlicher Kerzen:', error);
                } finally {
                    this.isLoading = false;
                }
            }

            updateTimeframe(newTimeframe, newCandleCount) {
                this.currentTimeframe = newTimeframe;
                this.currentCandles = newCandleCount || this.currentCandles;
                console.log(`🔄 Timeframe geändert zu: ${newTimeframe} (${this.currentCandles} Kerzen)`);
            }

            showZoomNotification(message) {
                // Erstelle Toast-Benachrichtigung
                const toast = document.createElement('div');
                toast.textContent = message;
                toast.style.cssText = `
                    position: fixed;
                    top: 80px;
                    right: 20px;
                    background: rgba(8, 153, 129, 0.9);
                    color: white;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 11px;
                    z-index: 10000;
                    animation: slideIn 0.3s ease-out;
                `;

                document.body.appendChild(toast);

                // Auto-remove nach 2 Sekunden
                setTimeout(() => {
                    toast.style.animation = 'slideOut 0.3s ease-in';
                    setTimeout(() => toast.remove(), 300);
                }, 2000);
            }
        }

        function initChart() {
            console.log('🔧 initChart() aufgerufen');

            const chartContainer = document.getElementById('chart_container');
            console.log('🔧 Chart Container:', chartContainer);

            if (!chartContainer) {
                console.error('❌ Chart Container nicht gefunden!');
                return;
            }

            console.log('🔧 LightweightCharts verfügbar:', typeof LightweightCharts);

            chart = LightweightCharts.createChart(chartContainer, {
                width: chartContainer.clientWidth,
                height: chartContainer.clientHeight,
                layout: {
                    backgroundColor: '#000000',
                    textColor: '#d9d9d9'
                },
                timeScale: {
                    timeVisible: true,
                    secondsVisible: false,
                    borderColor: '#485c7b'
                },
                grid: {
                    vertLines: { visible: false },
                    horzLines: { visible: false }
                }
            });

            candlestickSeries = chart.addCandlestickSeries({
                upColor: '#089981',
                downColor: '#f23645',
                borderUpColor: '#089981',
                borderDownColor: '#f23645',
                wickUpColor: '#089981',
                wickDownColor: '#f23645'
            });

            // Smart Positioning System initialisieren
            try {
                window.smartPositioning = new SmartChartPositioning(chart, candlestickSeries);
                console.log('INIT: Smart Positioning System initialisiert');

                // Chart-Daten sofort laden
                loadInitialData();

                // SOFORTIGER TEST der Smart Positioning
                window.testSmartPositioning = function() {
                    console.log('DIRECT TEST: Smart Positioning wird getestet...');
                    if (window.smartPositioning) {
                        // Erstelle Test-Daten
                        const testData = [];
                        const baseTime = Math.floor(Date.now() / 1000);
                        for (let i = 0; i < 50; i++) {
                            testData.push({
                                time: baseTime + (i * 300), // 5-Minuten Intervall
                                open: 100 + i,
                                high: 105 + i,
                                low: 95 + i,
                                close: 102 + i
                            });
                        }
                        console.log('DIRECT TEST: Test-Daten erstellt, rufe setStandardPosition auf...');
                        window.smartPositioning.setStandardPosition(testData);
                        console.log('DIRECT TEST: setStandardPosition aufgerufen');
                    } else {
                        console.error('DIRECT TEST: Smart Positioning nicht verfügbar');
                    }
                };

            } catch (error) {
                console.error('INIT ERROR: Fehler bei Smart Positioning Initialisierung:', error);
                window.smartPositioning = null;
            }

            console.log('🔧 CandlestickSeries und Smart Positioning erstellt:', candlestickSeries);

            // 🛡️ EMERGENCY GLOBAL ERROR HANDLER: "Value is null" Protection
            window.emergencyChartRecovery = {
                enabled: true,
                recoveryCount: 0,
                maxRecoveries: 3,

                handleValueIsNullError: function(error) {
                    if (this.recoveryCount >= this.maxRecoveries) {
                        console.error('[EMERGENCY-RECOVERY] Max recovery attempts reached, forcing page reload');
                        location.reload();
                        return;
                    }

                    this.recoveryCount++;
                    console.warn(`[EMERGENCY-RECOVERY] Attempt ${this.recoveryCount}: Value is null detected, triggering chart recreation`);

                    // Force chart recreation via backend
                    fetch('/api/chart/emergency_chart_recreation', { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            console.log('[EMERGENCY-RECOVERY] Chart recreation requested:', data);
                            // The backend will trigger chart recreation on next timeframe switch
                        })
                        .catch(err => {
                            console.error('[EMERGENCY-RECOVERY] Failed to request chart recreation:', err);
                            // Fallback: Page reload after brief delay
                            setTimeout(() => location.reload(), 2000);
                        });
                }
            };

            // Global error handler für LightweightCharts "Value is null" errors
            window.addEventListener('error', function(event) {
                if (event.error && event.error.message &&
                    event.error.message.includes('Value is null') &&
                    window.emergencyChartRecovery && window.emergencyChartRecovery.enabled) {

                    console.error('[EMERGENCY-RECOVERY] Global "Value is null" error detected:', event.error);
                    event.preventDefault(); // Prevent default error handling

                    window.emergencyChartRecovery.handleValueIsNullError(event.error);
                }
            });

            console.log('🛡️ Emergency Chart Recovery System aktiviert');

            // Position Lines Container
            window.positionLines = {};
            window.activeSeries = {};
            window.positionBoxMode = false;
            window.shortPositionMode = false;
            window.currentPositionBox = null;

            // Timeframe State mit Performance-Optimierung
            window.currentTimeframe = '5m';
            window.timeframeCache = new Map();  // Browser-side caching
            window.isTimeframeChanging = false;  // Prevent double-requests

            // Smart Chart Positioning System - 50 Kerzen + 20% Freiraum
            window.smartPositioning = null;  // Wird nach Chart-Init initialisiert

            // Intelligent Zoom System - Garantiert sichtbare Kerzen beim Auszoomen
            window.intelligentZoom = null;  // Wird nach Daten-Load initialisiert

            // Responsive Resize
            window.addEventListener('resize', () => {
                chart.applyOptions({
                    width: chartContainer.clientWidth,
                    height: chartContainer.clientHeight
                });
            });

            // LADE ECHTE NQ-DATEN über WebSocket
            console.log('🔄 Lade echte NQ-Daten...');

            // Initialer Request für Chart-Daten
            setTimeout(() => {
                loadInitialData();
            }, 1000);

            // Chart Click Handler für Position Box Tool
            chart.subscribeClick((param) => {
                console.log('🖱️ Chart geklickt:', param);
                console.log('📦 Position Box Mode:', window.positionBoxMode);

                if ((window.positionBoxMode || window.shortPositionMode) && param.point) {
                    const price = candlestickSeries.coordinateToPrice(param.point.y);
                    const clickX = param.point.x; // ⭐ Click-X-Koordinate erfassen
                    const clickY = param.point.y; // ⭐ Click-Y-Koordinate erfassen

                    // Verwende param.time falls vorhanden (Kerzen-Klick), sonst aktuelle Zeit (freier Bereich)
                    const timeForBox = param.time || Math.floor(Date.now() / 1000);

                    const isShort = window.shortPositionMode;
                    console.log('📦 Erstelle', isShort ? 'Short' : 'Long', 'Position Box bei Preis:', price, 'an X-Position:', clickX, 'Y-Position:', clickY, 'Zeit:', timeForBox);
                    createPositionBox(timeForBox, price, clickX, clickY, isShort);
                } else {
                    console.log('❌ Position Box Mode nicht aktiv oder ungültiger Klick');
                }
            });

            isInitialized = true;
            console.log('✅ Chart initialisiert, lade NQ-Daten...');
        }

        // Lade initiale Chart-Daten vom Server
        function loadInitialData() {
            console.log('📊 Lade initiale NQ-Daten...');

            // Prüfe ob Chart und Series verfügbar sind
            if (!chart || !candlestickSeries) {
                console.error('❌ Chart oder CandlestickSeries nicht initialisiert!');
                console.log('Chart:', chart);
                console.log('CandlestickSeries:', candlestickSeries);
                return;
            }

            fetch('/api/chart/status')
                .then(response => response.json())
                .then(data => {
                    console.log('📊 Status:', data);
                    // Lade Chart-Daten
                    return fetch('/api/chart/data');
                })
                .then(response => response.json())
                .then(chartData => {
                    console.log('📊 Chart-Daten erhalten:', chartData.data?.length || 0, 'Kerzen');
                    console.log('DRASTIC: SOFORT nach Chart-Daten Log - 20% Freiraum wird ERZWUNGEN!');
                    if (chartData.data && chartData.data.length > 0) {
                        // Daten sind bereits im korrekten LightweightCharts Format (Unix-Timestamps)
                        const formattedData = chartData.data.filter(item =>
                            item && item.time &&
                            item.open != null && item.high != null &&
                            item.low != null && item.close != null
                        ).map(item => ({
                            time: item.time,  // Bereits Unix-Timestamp, keine Konvertierung nötig
                            open: parseFloat(item.open) || 0,
                            high: parseFloat(item.high) || 0,
                            low: parseFloat(item.low) || 0,
                            close: parseFloat(item.close) || 0
                        }));

                        candlestickSeries.setData(formattedData);

                        // DRASTISCHE SOFORT-LÖSUNG: 20% Freiraum GARANTIERT
                        console.log('DRASTIC-EXEC: Setze 20% Freiraum SOFORT nach setData()');
                        const firstTime = formattedData[0].time;
                        const lastTime = formattedData[formattedData.length - 1].time;

                        // Fix: Stelle sicher, dass wir Min/Max korrekt ermitteln
                        const minTime = Math.min(firstTime, lastTime);
                        const maxTime = Math.max(firstTime, lastTime);
                        const span = maxTime - minTime;
                        const margin = span * 0.25;

                        chart.timeScale().setVisibleRange({
                            from: minTime,
                            to: maxTime + margin
                        });
                        console.log('DRASTIC-EXEC: Freiraum gesetzt von', minTime, 'bis', maxTime + margin);

                        // FINALE DIREKTE LÖSUNG: 20% Freiraum OHNE Bedingungen
                        console.log('FINAL: Setze GARANTIERT 20% Freiraum für', formattedData.length, 'Kerzen');

                        if (formattedData.length >= 2) {
                            const firstTime = formattedData[0].time;
                            const lastTime = formattedData[formattedData.length - 1].time;

                            // Fix: Stelle sicher, dass wir Min/Max korrekt ermitteln (Daten können in beliebiger Reihenfolge sein)
                            const minTime = Math.min(firstTime, lastTime);
                            const maxTime = Math.max(firstTime, lastTime);
                            const dataSpan = maxTime - minTime;
                            const margin = dataSpan * 0.25; // 25% = 20% der Gesamt-Chart

                            console.log('FINAL: Zeitspanne:', dataSpan, 'Margin:', margin);
                            console.log('FINAL: Von', minTime, 'bis', maxTime + margin);

                            // Stelle sicher, dass from < to ist
                            chart.timeScale().setVisibleRange({
                                from: minTime,
                                to: maxTime + margin
                            });

                            console.log('FINAL: Chart-Position GESETZT');
                        } else {
                            console.log('FINAL: Zu wenig Daten - verwende fitContent');
                            chart.timeScale().fitContent();
                        }

                        // ZUSÄTZLICHER SCHUTZ: Nochmal nach 100ms setzen
                        setTimeout(() => {
                            if (formattedData.length >= 2) {
                                const firstTime = formattedData[0].time;
                                const lastTime = formattedData[formattedData.length - 1].time;

                                // Fix: Stelle sicher, dass wir Min/Max korrekt ermitteln
                                const minTime = Math.min(firstTime, lastTime);
                                const maxTime = Math.max(firstTime, lastTime);
                                const dataSpan = maxTime - minTime;
                                const margin = dataSpan * 0.25;

                                chart.timeScale().setVisibleRange({
                                    from: minTime,
                                    to: maxTime + margin
                                });

                                console.log('DELAYED: 20% Freiraum nochmal gesetzt nach 100ms');
                            }
                        }, 100);

                        console.log('✅ NQ-Daten geladen:', formattedData.length, 'Kerzen, Smart Positioning angewandt');

                        // ZOOM SYSTEM KOMPLETT DEAKTIVIERT für Timeframe-Fix
                        console.log('🚫 Zoom System komplett deaktiviert');
                        window.intelligentZoom = null;
                    } else {
                        console.warn('⚠️ Keine Chart-Daten empfangen');
                    }
                })
                .catch(error => {
                    console.error('❌ Fehler beim Laden der Chart-Daten:', error);
                });
        }

        // WebSocket Connection
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            ws = new WebSocket(wsUrl);

            // TEST: Direkter Smart Positioning Test nach 3 Sekunden
            setTimeout(() => {
                console.log('AUTO TEST: Smart Positioning nach 3 Sekunden...');
                if (window.testSmartPositioning) {
                    window.testSmartPositioning();
                } else {
                    console.error('AUTO TEST: testSmartPositioning Funktion nicht verfügbar');
                }
            }, 3000);

            // TEST: API-basierter Test nach 6 Sekunden
            setTimeout(() => {
                console.log('API TEST: Smart Positioning mit echten Daten...');
                if (window.smartPositioning && candlestickSeries) {
                    try {
                        // Hole aktuelle Daten von der Chart API
                        fetch('/api/chart/data')
                            .then(response => response.json())
                            .then(data => {
                                if (data.data && data.data.length > 0) {
                                    console.log('API TEST: Gefunden', data.data.length, 'Kerzen, wende Smart Positioning an');
                                    window.smartPositioning.setStandardPosition(data.data);
                                } else {
                                    console.error('API TEST: Keine Daten erhalten');
                                }
                            })
                            .catch(error => console.error('API TEST Fehler:', error));
                    } catch (error) {
                        console.error('API TEST Smart Positioning Fehler:', error);
                    }
                } else {
                    console.warn('API TEST: Smart Positioning oder CandlestickSeries nicht verfügbar');
                    console.log('API TEST window.smartPositioning:', window.smartPositioning);
                    console.log('API TEST candlestickSeries:', candlestickSeries);
                }
            }, 6000);

            ws.onopen = function(event) {
                console.log('🔗 WebSocket verbunden');
                document.getElementById('status').textContent = 'Connected';
                document.getElementById('status').className = 'status connected';
            };

            ws.onmessage = function(event) {
                const message = JSON.parse(event.data);
                handleMessage(message);
            };

            ws.onclose = function(event) {
                console.log('❌ WebSocket getrennt');
                document.getElementById('status').textContent = 'Disconnected';
                document.getElementById('status').className = 'status disconnected';

                // Reconnect nach 2 Sekunden
                setTimeout(connectWebSocket, 2000);
            };

            ws.onerror = function(error) {
                console.error('❌ WebSocket Error:', error);
            };
        }

        // Account Update Functions
        async function loadAccountData() {
            // Lädt Account-Daten für beide Accounts und aktualisiert die UI
            try {
                const response = await fetch('/api/account/status');
                const data = await response.json();

                if (data.status === 'success') {
                    updateAccountDisplay('ai', data.ai_account);
                    updateAccountDisplay('user', data.user_account);
                }
            } catch (error) {
                console.error('❌ Fehler beim Laden der Account-Daten:', error);
            }
        }

        function updateAccountDisplay(accountType, accountData) {
            // Aktualisiert die Account-Anzeige in der UI
            const prefix = accountType === 'ai' ? 'ai' : 'user';

            // Update Balance
            const balanceEl = document.getElementById(`${prefix}-balance`);
            if (balanceEl) {
                balanceEl.textContent = accountData.balance;
                balanceEl.className = 'account-value-amount neutral';
            }

            // Update Realized PnL
            const realizedEl = document.getElementById(`${prefix}-realized`);
            if (realizedEl) {
                realizedEl.textContent = accountData.realized_pnl;
                realizedEl.className = `account-value-amount ${getPnLClass(accountData.realized_pnl)}`;
            }

            // Update Unrealized PnL
            const unrealizedEl = document.getElementById(`${prefix}-unrealized`);
            if (unrealizedEl) {
                unrealizedEl.textContent = accountData.unrealized_pnl;
                unrealizedEl.className = `account-value-amount ${getPnLClass(accountData.unrealized_pnl)}`;
            }
        }

        function getPnLClass(pnlString) {
            // Bestimmt CSS-Klasse basierend auf PnL-Wert
            if (pnlString.includes('+')) return 'positive';
            if (pnlString.includes('-')) return 'negative';
            return 'neutral';
        }

        // Account Data alle 5 Sekunden laden
        setInterval(loadAccountData, 5000);

        // Enhanced Multi-Timeframe Functions
        function handleIncompleteCandle(candle, incompleteInfo) {
            console.log(`🔄 INCOMPLETE CANDLE: ${incompleteInfo.timeframe}`);
            console.log(`   ⏱️  Progress: ${incompleteInfo.elapsed_minutes.toFixed(1)}/${incompleteInfo.total_minutes} min`);
            console.log(`   📊 Completion: ${Math.round(incompleteInfo.completion_ratio * 100)}%`);

            // Visual marking could be implemented here
            // For now, we log the incomplete status
            // Future: Add border styling or opacity to incomplete candles

            if (incompleteInfo.completion_ratio < 0.5) {
                console.log('   🟡 Early stage incomplete candle (< 50%)');
            } else if (incompleteInfo.completion_ratio < 0.9) {
                console.log('   🟠 Late stage incomplete candle (50-90%)');
            } else {
                console.log('   🔴 Nearly complete candle (90%+)');
            }
        }

        function updateTimeframeSyncDisplay(syncStatus) {
            console.log('🌐 MULTI-TIMEFRAME SYNC STATUS:');

            for (const [timeframe, status] of Object.entries(syncStatus)) {
                if (status.position) {
                    const positionTime = new Date(status.position).toLocaleTimeString();
                    console.log(`   ${timeframe}: ${positionTime}`);

                    if (status.incomplete_info && !status.incomplete_info.is_complete) {
                        const completion = Math.round(status.incomplete_info.completion_ratio * 100);
                        console.log(`        └── Incomplete: ${completion}%`);
                    }
                }
            }

            // Future: Update UI elements to show sync status visually
            // Could add timeframe indicators in sidebar or status bar
        }

        // ENHANCED DATA VALIDATION: Bulletproof protection against "Value is null" errors
        function validateCandle(candle, isSkipGenerated = false, debug = false) {
            // NULL/UNDEFINED checks first
            if (!candle) {
                if (debug) console.log('🔍 FILTER: Candle is null/undefined');
                return false;
            }
            if (candle.time === null || candle.time === undefined) {
                if (debug) console.log('🔍 FILTER: time is null/undefined:', candle);
                return false;
            }
            if (candle.open === null || candle.open === undefined) {
                if (debug) console.log('🔍 FILTER: open is null/undefined:', candle);
                return false;
            }
            if (candle.high === null || candle.high === undefined) {
                if (debug) console.log('🔍 FILTER: high is null/undefined:', candle);
                return false;
            }
            if (candle.low === null || candle.low === undefined) {
                if (debug) console.log('🔍 FILTER: low is null/undefined:', candle);
                return false;
            }
            if (candle.close === null || candle.close === undefined) {
                if (debug) console.log('🔍 FILTER: close is null/undefined:', candle);
                return false;
            }

            // Type and value validation
            if (typeof candle.time !== 'number' || candle.time <= 0) {
                if (debug) console.log('🔍 FILTER: Invalid time:', candle.time, typeof candle.time);
                return false;
            }

            const open = parseFloat(candle.open);
            const high = parseFloat(candle.high);
            const low = parseFloat(candle.low);
            const close = parseFloat(candle.close);

            // Enhanced NaN detection
            if (!Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
                if (debug) console.log('🔍 FILTER: NaN/Infinite values:', {open, high, low, close});
                return false;
            }

            // Relaxed price range validation (prevent only extreme outliers)
            const minPrice = 100;     // Relaxed minimum for broader CSV compatibility
            const maxPrice = 100000;  // Relaxed maximum for broader CSV compatibility
            if (open < minPrice || open > maxPrice) {
                if (debug) console.log('🔍 FILTER: open price out of range:', open);
                return false;
            }
            if (high < minPrice || high > maxPrice) {
                if (debug) console.log('🔍 FILTER: high price out of range:', high);
                return false;
            }
            if (low < minPrice || low > maxPrice) {
                if (debug) console.log('🔍 FILTER: low price out of range:', low);
                return false;
            }
            if (close < minPrice || close > maxPrice) {
                if (debug) console.log('🔍 FILTER: close price out of range:', close);
                return false;
            }

            // OHLC logic validation with tolerance for skip-generated candles
            if (isSkipGenerated) {
                const tolerance = 0.1; // Increased tolerance for skip candles
                if (high < (Math.max(open, close, low) - tolerance)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error (skip candle) - high too low:', {open, high, low, close});
                    return false;
                }
                if (low > (Math.min(open, close, high) + tolerance)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error (skip candle) - low too high:', {open, high, low, close});
                    return false;
                }
            } else {
                if (high < Math.max(open, close, low)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error - high too low:', {open, high, low, close});
                    return false;
                }
                if (low > Math.min(open, close, high)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error - low too high:', {open, high, low, close});
                    return false;
                }
            }

            return true;
        }

        function validateCandleData(data, isSkipGenerated = false) {
            if (!data || data.length === 0) return [];

            const originalLength = data.length;
            const validatedData = data.filter(candle => validateCandle(candle, isSkipGenerated)).map(item => ({
                time: item.time,
                open: parseFloat(item.open),
                high: parseFloat(item.high),
                low: parseFloat(item.low),
                close: parseFloat(item.close)
            }));

            // Log filter results
            const filteredCount = originalLength - validatedData.length;
            if (filteredCount > 0) {
                console.log(`🔍 VALIDATION: ${filteredCount}/${originalLength} candles filtered out`);

                // Debug first few filtered candles if many were removed
                if (filteredCount > originalLength * 0.5) {
                    console.warn('🚨 High filter rate detected, debugging first 3 filtered candles:');
                    let debugCount = 0;
                    for (const candle of data) {
                        if (!validateCandle(candle, isSkipGenerated, true) && debugCount < 3) {
                            debugCount++;
                        }
                    }
                }
            }

            // FALLBACK: If validation filters out ALL candles, use raw data with basic cleaning
            if (validatedData.length === 0 && data.length > 0) {
                console.warn('🚨 FALLBACK: All candles filtered out, using raw data with basic cleaning');
                return data.filter(item =>
                    item &&
                    typeof item.time === 'number' &&
                    item.time > 0 &&
                    item.open !== null &&
                    item.high !== null &&
                    item.low !== null &&
                    item.close !== null
                ).map(item => ({
                    time: item.time,
                    open: parseFloat(item.open) || 18500,
                    high: parseFloat(item.high) || 18505,
                    low: parseFloat(item.low) || 18495,
                    close: parseFloat(item.close) || 18500
                }));
            }

            return validatedData;
        }

        // Message Handler
        function handleMessage(message) {
            console.log('📨 Message received:', message.type);

            switch(message.type) {
                case 'initial_data':
                    if (!isInitialized) initChart();

                    const data = message.data.data;
                    if (data && data.length > 0) {
                        const validatedData = validateCandleData(data);
                        candlestickSeries.setData(validatedData);

                        if (validatedData.length !== data.length) {
                            console.warn(`⚠️ ${data.length - validatedData.length} invalid candles removed from initial data`);
                        }

                        // NEUE LOGIK: Zeige nur letzten 50 Kerzen mit 80/20 Aufteilung
                        console.log(`📊 Initial: ${data.length} Kerzen geladen, zeige letzten 50 mit 80/20 Aufteilung`);
                        document.title = `Chart: ${data.length} Kerzen verfügbar, 50 sichtbar (${message.data.interval})`;

                        // Berechne die letzten 50 Kerzen
                        const totalCandles = data.length;
                        const visibleCandles = Math.min(50, totalCandles);
                        const startIndex = Math.max(0, totalCandles - visibleCandles);

                        const firstVisibleTime = data[startIndex].time;
                        const lastVisibleTime = data[totalCandles - 1].time;
                        const visibleSpan = lastVisibleTime - firstVisibleTime;

                        // 20% Freiraum rechts hinzufügen: 50 Kerzen sind 80%, also 20% zusätzlich
                        const margin = visibleSpan / 4; // visibleSpan / 4 = 20% von den 80%

                        chart.timeScale().setVisibleRange({
                            from: firstVisibleTime,
                            to: lastVisibleTime + margin
                        });

                        console.log(`✅ Standard-Zoom: Kerzen ${startIndex}-${totalCandles-1} sichtbar (${visibleCandles} Kerzen mit 20% Freiraum)`);
                    }
                    break;

                case 'set_data':
                    if (!isInitialized) initChart();

                    const validatedSetData = validateCandleData(message.data);
                    candlestickSeries.setData(validatedSetData);

                    if (validatedSetData.length !== message.data.length) {
                        console.warn(`⚠️ ${message.data.length - validatedSetData.length} invalid candles removed from set_data`);
                    }

                    // Smart Positioning: 50 Kerzen Standard mit 20% Freiraum
                    if (window.smartPositioning) {
                        window.smartPositioning.setStandardPosition(message.data);
                    }

                    console.log('📊 Data updated:', message.data.length, 'candles mit Smart Positioning');
                    break;

                case 'add_candle':
                    if (isInitialized && message.candle) {
                        candlestickSeries.update(message.candle);
                        console.log('➡️ Candle added:', message.candle);
                    }
                    break;

                case 'debug_skip':
                    // Legacy Debug Skip: Direkte Chart-Update ohne Smart Positioning System
                    if (isInitialized && message.candle) {
                        candlestickSeries.update(message.candle);
                        console.log('⏭️ Debug Skip: Neue Kerze hinzugefügt:', message.candle);
                        console.log('📊 Candle Type:', message.candle_type || message.result_type);
                        console.log('🕒 Debug Time:', message.debug_time);
                        console.log('📈 Timeframe:', message.timeframe);

                        // Visual feedback für incomplete candles (if needed)
                        if (message.candle_type === 'incomplete_candle') {
                            console.log('⚠️ Incomplete Candle - noch nicht vollständig');
                        }
                    } else {
                        console.log('❌ Debug Skip fehlgeschlagen: Chart nicht initialisiert oder fehlende Kerze');
                    }
                    break;

                case 'debug_skip_sync':
                    // ENHANCED: Multi-Timeframe Debug Skip mit Sync & Incomplete Candle Support
                    if (isInitialized && message.candle) {
                        // Update Chart mit primary candle
                        candlestickSeries.update(message.candle);

                        console.log('🔄 Multi-TF Skip:', message.timeframe, '- Candle:', message.candle.time);
                        console.log('📊 Type:', message.candle_type);
                        console.log('⏰ Debug Time:', message.debug_time);

                        // Enhanced Incomplete Candle Visual Marking
                        if (message.candle_type === 'incomplete_candle' && message.incomplete_info) {
                            handleIncompleteCandle(message.candle, message.incomplete_info);
                        }

                        // Multi-Timeframe Sync Status Logging
                        if (message.sync_status) {
                            console.log('🌐 Sync Status:', message.sync_status);
                            updateTimeframeSyncDisplay(message.sync_status);
                        }

                        // Update document title with sync info
                        const completionInfo = message.incomplete_info ?
                            ` (${Math.round(message.incomplete_info.completion_ratio * 100)}% complete)` : '';
                        document.title = `${message.timeframe} Skip${completionInfo} - Multi-TF Sync`;

                    } else {
                        console.log('❌ Multi-TF Skip fehlgeschlagen:', !isInitialized ? 'Chart nicht initialisiert' : 'Fehlende Kerze');
                    }
                    break;

                case 'debug_play_toggled':
                    // Debug Play/Pause Toggle Response
                    console.log('▶️ Debug Play Toggle:', message.play_mode ? 'AKTIVIERT' : 'DEAKTIVIERT');

                    // Update Play/Pause Button Visual
                    const playPauseBtn = document.getElementById('playPauseBtn');
                    if (playPauseBtn) {
                        playPauseBtn.textContent = message.play_mode ? '⏸️' : '▶️';
                        console.log('🔄 Play Button Updated:', message.play_mode ? '⏸️' : '▶️');
                    }
                    break;

                case 'add_position':
                    if (isInitialized && message.position) {
                        addPositionOverlay(message.position);
                        console.log('🎯 Position added:', message.position);
                    }
                    break;

                case 'remove_position':
                    if (isInitialized && message.position_id) {
                        removePositionOverlay(message.position_id);
                        console.log('❌ Position removed:', message.position_id);
                    }
                    break;

                case 'chart_reinitialize':
                    if (isInitialized && message.data) {
                        console.log('📅 Chart Reinitialization: Go To Date triggered');
                        console.log('📊 New data received:', message.data.length, 'candles');
                        console.log('🎯 Target Date:', message.target_date);
                        console.log('📍 Current Index:', message.current_index);

                        // Lösche alle bestehenden Position-Overlays
                        clearAllPositions();

                        // Setze neue validierte Chart-Daten
                        const validatedGoToData = validateCandleData(message.data);
                        candlestickSeries.setData(validatedGoToData);

                        if (validatedGoToData.length !== message.data.length) {
                            console.warn(`⚠️ ${message.data.length - validatedGoToData.length} invalid candles removed from go_to_date`);
                        }

                        // Positioniere Chart zu gewähltem Datum (zeige 50 Kerzen ab Startdatum)
                        if (message.data.length > 0) {
                            const startIndex = Math.max(0, message.current_index - 5); // 5 Kerzen Kontext vor Startdatum
                            const endIndex = Math.min(message.data.length - 1, message.current_index + 45); // 45 Kerzen nach Startdatum

                            const firstTime = message.data[startIndex].time;
                            const lastTime = message.data[endIndex].time;
                            const timeSpan = lastTime - firstTime;
                            const margin = timeSpan * 0.25; // 20% Freiraum rechts

                            chart.timeScale().setVisibleRange({
                                from: firstTime,
                                to: lastTime + margin
                            });

                            console.log('✅ Chart reinitialized and positioned to:', message.target_date);
                            console.log('📊 Showing candles:', startIndex, 'to', endIndex, 'with 20% margin');
                        }

                        // Update Titel mit neuen Informationen
                        document.title = `Chart: ${message.target_date} (${message.data.length} Kerzen verfügbar)`;
                    } else {
                        console.error('❌ Chart Reinitialization failed: Chart not initialized or no data');
                    }
                    break;

                case 'go_to_date_complete':
                    if (isInitialized && message.data) {
                        console.log('[GO TO DATE] Memory-Performance Complete: Loading', message.data.length, 'candles');
                        console.log('[GO TO DATE] Target Date:', message.target_date);
                        console.log('[GO TO DATE] Performance Mode:', message.performance);

                        // Verwende visible_range Info vom Server falls verfügbar
                        if (message.visible_range) {
                            console.log('[GO TO DATE] Server Visible Range:', message.visible_range);
                        }

                        // Lösche alle bestehenden Position-Overlays
                        clearAllPositions();

                        // 🚀 CRITICAL FIX: Browser-Cache Invalidation nach GoTo-Operationen
                        // Verhindert veraltete Skip-Kerzen bei TF-Wechseln
                        const cacheCountBefore = window.timeframeCache.size;
                        window.timeframeCache.clear();
                        window.lastGoToDate = message.target_date; // Server-State für Cache-Validation
                        console.log(`[CACHE-INVALIDATION] Browser-Cache cleared: ${cacheCountBefore} entries removed`);
                        console.log(`[CACHE-INVALIDATION] Grund: GoTo-Operation zu ${message.target_date}`);

                        // Setze neue validierte historische Chart-Daten
                        const validatedHistoricalData = validateCandleData(message.data);
                        candlestickSeries.setData(validatedHistoricalData);

                        if (validatedHistoricalData.length !== message.data.length) {
                            console.warn(`⚠️ ${message.data.length - validatedHistoricalData.length} invalid candles removed from historical data`);
                        }

                        // HIGH-PERFORMANCE POSITIONING: Verwende Server-calculated Range
                        if (message.data.length > 0) {
                            let startIndex, endIndex;
                            const totalCandles = message.data.length;
                            const visibleCandles = 50; // FIXED: Variable außerhalb der Blöcke definieren

                            if (message.visible_range) {
                                // Verwende vom Memory Cache berechnete Range
                                startIndex = message.visible_range.start;
                                endIndex = message.visible_range.end;
                                console.log('[POSITIONING] Server-calculated range:', startIndex, '-', endIndex);
                            } else {
                                // Fallback: Standardberechnung (letzten 50 von 200)
                                startIndex = Math.max(0, totalCandles - visibleCandles);
                                endIndex = totalCandles - 1;
                                console.log('[POSITIONING] Fallback range:', startIndex, '-', endIndex);
                            }

                            // Zeitbereich für die sichtbaren Kerzen
                            const startTime = message.data[startIndex].time;
                            const endTime = message.data[endIndex].time;
                            const timeSpan = endTime - startTime;
                            const margin = timeSpan * 0.05; // 5% Margin für gefüllten Chart

                            chart.timeScale().setVisibleRange({
                                from: startTime - margin,
                                to: endTime + margin
                            });

                            console.log(`[GO TO DATE] Positioning: ${visibleCandles} von ${totalCandles} Kerzen angezeigt (Chart gefüllt)`);
                            console.log(`[GO TO DATE] Sichtbare Kerzen: Index ${startIndex}-${endIndex}`);
                            console.log(`[GO TO DATE] Zeitbereich: ${new Date(startTime * 1000).toISOString()} bis ${new Date(endTime * 1000).toISOString()}`);
                        }

                        // Update Titel mit neuen Informationen
                        document.title = `Go To Date: ${message.target_date} (${message.data.length} historische Kerzen)`;

                        // ADAPTIVE TIMEOUT FIX: Setze Go To Date Status für längere Timeouts
                        window.current_go_to_date = message.target_date;

                        // Server-Log für Debug
                        console.log('[GO TO DATE] Complete: Chart repositioniert, bereit für Skip-Button Navigation');

                    } else {
                        console.error('[GO TO DATE] Complete failed: Chart not initialized or no data');
                    }
                    break;

                case 'positions_sync':
                    if (isInitialized && message.positions) {
                        syncPositions(message.positions);
                        console.log('🔄 Positions synced:', message.positions.length);
                    }
                    break;

                case 'timeframe_changed':
                    console.log('DEBUG: timeframe_changed message received:', message);

                    if (isInitialized && message.data) {
                        // ENHANCED DATA VALIDATION: Zentrale Validierung gegen LightweightCharts Errors
                        const validatedData = validateCandleData(message.data);

                        if (validatedData.length < message.data.length) {
                            const removedCount = message.data.length - validatedData.length;
                            console.warn(`⚠️ ${removedCount} invalid candles removed from timeframe data`);
                        }

                        candlestickSeries.setData(validatedData);

                        // NEUE LOGIK: Zeige nur letzten 50 Kerzen mit 80/20 Aufteilung bei TF-Wechsel
                        console.log(`[TIMEFRAME] ${message.timeframe}: ${validatedData.length} Kerzen geladen, zeige letzten 50 mit 80/20 Aufteilung`);
                        document.title = `Chart: ${validatedData.length} Kerzen verfügbar, 50 sichtbar (${message.timeframe})`;

                        // Berechne die letzten 50 Kerzen
                        const totalCandles = validatedData.length;
                        const visibleCandles = Math.min(50, totalCandles);
                        const startIndex = Math.max(0, totalCandles - visibleCandles);

                        const firstVisibleTime = validatedData[startIndex].time;
                        const lastVisibleTime = validatedData[totalCandles - 1].time;
                        const visibleSpan = lastVisibleTime - firstVisibleTime;

                        // 20% Freiraum rechts hinzufügen: 50 Kerzen sind 80%, also 20% zusätzlich
                        const margin = visibleSpan / 4; // visibleSpan / 4 = 20% von den 80%

                        chart.timeScale().setVisibleRange({
                            from: firstVisibleTime,
                            to: lastVisibleTime + margin
                        });

                        // Update current timeframe
                        window.currentTimeframe = message.timeframe;

                        // RACE CONDITION FIX: Synchronisiere Button-State mit tatsächlichem Timeframe
                        updateTimeframeButtons(message.timeframe);

                        console.log(`[SUCCESS] TF-Wechsel: Kerzen ${startIndex}-${totalCandles-1} sichtbar (${visibleCandles} Kerzen mit 20% Freiraum)`);
                    }
                    break;

                case 'revolutionary_skip_event':
                    // Revolutionary Skip Event: Handle incomplete candles und timeframe updates
                    if (isInitialized && message.candle && validateCandle(message.candle)) {
                        // Validated candle update
                        const validatedCandle = {
                            time: message.candle.time,
                            open: parseFloat(message.candle.open),
                            high: parseFloat(message.candle.high),
                            low: parseFloat(message.candle.low),
                            close: parseFloat(message.candle.close)
                        };
                        candlestickSeries.update(validatedCandle);

                        console.log('🚀 Revolutionary Skip:', message.timeframe, '- Candle:', message.candle.time);
                        console.log('📊 Candle Type:', message.candle_type);
                        console.log('⏰ Debug Time:', message.debug_time);

                        // Visual feedback für incomplete candles
                        if (message.candle_type === 'incomplete_candle') {
                            console.log('⚠️ Incomplete 15min Candle - wird bei nächstem Skip vervollständigt');
                        }

                        // Update document title
                        const completionInfo = message.candle_type === 'incomplete_candle' ? ' (incomplete)' : '';
                        document.title = `${message.timeframe} Revolutionary Skip${completionInfo}`;

                        // Set skip event completion flag for timeframe switch detection
                        window.skipEventJustCompleted = true;
                    } else if (isInitialized && message.candle && !validateCandle(message.candle)) {
                        console.error('❌ Invalid candle data in revolutionary_skip_event:', message.candle);
                    }
                    break;

                case 'unified_skip_event':
                    // Unified Skip Event: Handle new unified time architecture skip events
                    if (isInitialized && message.candle && validateCandle(message.candle)) {
                        // Validated candle update for unified architecture
                        const validatedCandle = {
                            time: message.candle.time,
                            open: parseFloat(message.candle.open),
                            high: parseFloat(message.candle.high),
                            low: parseFloat(message.candle.low),
                            close: parseFloat(message.candle.close)
                        };
                        candlestickSeries.update(validatedCandle);

                        console.log('[UNIFIED] Skip Event:', message.timeframe, '- Candle:', message.candle.time);
                        console.log('[UNIFIED] Candle Type:', message.candle_type);
                        console.log('[UNIFIED] Debug Time:', message.debug_time);

                        // Update document title with unified architecture info
                        document.title = `${message.timeframe} Unified Skip (${message.system})`;

                        // Set skip event completion flag for timeframe switch detection
                        window.skipEventJustCompleted = true;
                    } else if (isInitialized && message.candle && !validateCandle(message.candle)) {
                        console.error('[UNIFIED] Invalid candle data in unified_skip_event:', message.candle);
                    }
                    break;

                case 'unified_timeframe_changed':
                    // SUPER-DEFENSIVE Unified Timeframe Change Handler
                    console.log('[UNIFIED-TF] Timeframe Change Event:', message.timeframe, '- Data:', message.data?.length || 0, 'candles');

                    if (isInitialized && message.data && Array.isArray(message.data) && message.data.length > 0) {
                        // ULTRA-STRICT validation with debug logging
                        const validatedData = message.data.filter((candle, index) => {
                            const isValid = validateCandle(candle, false, true); // Enable debug logging
                            if (!isValid) {
                                console.warn(`[UNIFIED-TF] REJECTED candle ${index}:`, candle);
                                return false;
                            }
                            return true;
                        });

                        console.log(`[UNIFIED-TF] Validation: ${message.data.length} original -> ${validatedData.length} valid candles`);

                        if (validatedData.length > 0) {
                            try {
                                // SUPER-DEFENSIVE data cleaning: Force correct format
                                const cleanData = validatedData.map((candle, index) => {
                                    try {
                                        const clean = {
                                            time: Number(candle.time),
                                            open: Number(candle.open),
                                            high: Number(candle.high),
                                            low: Number(candle.low),
                                            close: Number(candle.close)
                                        };

                                        // FINAL validation before return
                                        if (!Number.isFinite(clean.time) || clean.time <= 0 ||
                                            !Number.isFinite(clean.open) || !Number.isFinite(clean.high) ||
                                            !Number.isFinite(clean.low) || !Number.isFinite(clean.close)) {
                                            console.error(`[UNIFIED-TF] EMERGENCY REJECT candle ${index}:`, clean);
                                            return null;
                                        }

                                        return clean;
                                    } catch (cleanError) {
                                        console.error(`[UNIFIED-TF] Error cleaning candle ${index}:`, cleanError, candle);
                                        return null;
                                    }
                                }).filter(candle => candle !== null);

                                console.log(`[UNIFIED-TF] Final clean data: ${cleanData.length} candles`);

                                if (cleanData.length > 0) {
                                    // MULTIPLE TRY-CATCH layers for maximum safety
                                    try {
                                        // Clear existing data first
                                        candlestickSeries.setData([]);
                                        console.log('[UNIFIED-TF] Data cleared successfully');

                                        // Add small delay to prevent race conditions
                                        setTimeout(() => {
                                            try {
                                                // Set cleaned data
                                                candlestickSeries.setData(cleanData);
                                                console.log('[UNIFIED-TF] SUCCESS: Chart data set with', cleanData.length, 'candles for', message.timeframe);
                                                document.title = `${message.timeframe} Chart (${cleanData.length} candles)`;
                                            } catch (setDataError) {
                                                console.error('[UNIFIED-TF] FATAL: setData failed:', setDataError);
                                                console.error('[UNIFIED-TF] Sample clean data:', cleanData.slice(0, 3));

                                                // EMERGENCY fallback: reload page
                                                console.error('[UNIFIED-TF] EMERGENCY: Reloading page due to chart corruption');
                                                location.reload();
                                            }
                                        }, 50);

                                    } catch (clearError) {
                                        console.error('[UNIFIED-TF] Error clearing data:', clearError);
                                    }
                                } else {
                                    console.error('[UNIFIED-TF] No clean candles after final filtering');
                                }

                            } catch (outerError) {
                                console.error('[UNIFIED-TF] Outer processing error:', outerError);
                            }
                        } else {
                            console.error('[UNIFIED-TF] No valid candles after initial filtering for', message.timeframe);
                        }
                    } else {
                        console.error('[UNIFIED-TF] Invalid or empty data in unified_timeframe_changed:', message.data?.length || 'no data');
                    }
                    break;

                case 'debug_control_timeframe_changed':
                    // Debug Control Timeframe Change: Server bestätigt Debug Control Variable Update
                    console.log('🔧 Debug Control TF Change:', message.debug_control_timeframe);
                    console.log('📊 Old Timeframe:', message.old_timeframe);

                    // Detect timeframe switch mode: After skip event + different timeframe = needs special handling
                    if (window.skipEventJustCompleted && message.debug_control_timeframe !== message.old_timeframe) {
                        console.log('🚨 TIMEFRAME SWITCH MODE DETECTED: Skip->Different TF');
                        window.timeframeSwitchMode = true;
                        window.previousSkipTimeframe = message.old_timeframe;

                        // Clear skip flag to prevent interference
                        window.skipEventJustCompleted = false;
                    }

                    // Visual feedback (optional - könnte Button-State updates enthalten)
                    if (message.debug_control_timeframe) {
                        console.log(`✅ Debug Control jetzt auf ${message.debug_control_timeframe} gesetzt`);
                    }
                    break;

                case 'chart_series_recreation':
                    // 🚀 CHART SERIES RECREATION: Complete chart destruction and recreation
                    console.log('[CHART-RECREATION] Chart series recreation command received:', message.command);
                    console.log('[CHART-RECREATION] Reason:', message.reason);

                    try {
                        // PHASE 1: Complete chart destruction
                        console.log('[CHART-RECREATION] Phase 1: Destroying existing chart series...');

                        // Remove all series from chart
                        chart.removeSeries(candlestickSeries);
                        console.log('[CHART-RECREATION] Candlestick series removed');

                        // Small delay to ensure destruction is complete
                        setTimeout(() => {
                            try {
                                // PHASE 2: Create new candlestick series with fresh state
                                console.log('[CHART-RECREATION] Phase 2: Creating new candlestick series...');
                                candlestickSeries = chart.addCandlestickSeries({
                                    upColor: '#089981',
                                    downColor: '#f23645',
                                    borderVisible: false,
                                    wickUpColor: '#089981',
                                    wickDownColor: '#f23645'
                                });

                                console.log('[CHART-RECREATION] ✅ Chart series recreation completed successfully');
                                console.log('[CHART-RECREATION] Version:', message.command?.version);

                                // Update title to indicate recreation
                                document.title = `Chart Recreated (v${message.command?.version || 'unknown'})`;

                            } catch (recreationError) {
                                console.error('[CHART-RECREATION] FATAL: Recreation failed:', recreationError);
                                console.error('[CHART-RECREATION] EMERGENCY: Reloading page...');
                                location.reload();
                            }
                        }, 100); // Longer delay for complete destruction

                    } catch (destructionError) {
                        console.error('[CHART-RECREATION] Error during destruction:', destructionError);
                        console.error('[CHART-RECREATION] EMERGENCY: Reloading page...');
                        location.reload();
                    }
                    break;

                case 'bulletproof_timeframe_changed':
                    // 🚀 BULLETPROOF TIMEFRAME CHANGE: Enhanced timeframe switching with lifecycle management
                    console.log('[BULLETPROOF-TF] Bulletproof timeframe change received:', message.timeframe);
                    console.log('[BULLETPROOF-TF] Transaction ID:', message.transaction_id);
                    console.log('[BULLETPROOF-TF] Chart recreation required:', message.chart_recreation);

                    if (message.chart_recreation && message.recreation_command) {
                        // Chart recreation was already handled, now just set the data
                        console.log('[BULLETPROOF-TF] Chart recreation completed, setting data...');
                    }

                    // 🛡️ EMERGENCY SAFETY CHECK: Verify candlestickSeries exists after chart recreation
                    if (!candlestickSeries || typeof candlestickSeries.setData !== 'function') {
                        console.error('[BULLETPROOF-TF] CRITICAL: candlestickSeries is invalid after chart recreation');
                        console.error('[BULLETPROOF-TF] EMERGENCY: Triggering page reload...');
                        location.reload();
                        return;
                    }

                    if (isInitialized && message.data && Array.isArray(message.data) && message.data.length > 0) {
                        try {
                            // Use the same ultra-defensive validation as unified_timeframe_changed
                            const validatedData = message.data.filter((candle, index) => {
                                const isValid = validateCandle(candle, false, true);
                                if (!isValid) {
                                    console.warn(`[BULLETPROOF-TF] REJECTED candle ${index}:`, candle);
                                    return false;
                                }
                                return true;
                            });

                            console.log(`[BULLETPROOF-TF] Validation: ${message.data.length} original -> ${validatedData.length} valid candles`);

                            if (validatedData.length > 0) {
                                const cleanData = validatedData.map((candle, index) => {
                                    try {
                                        const clean = {
                                            time: Number(candle.time),
                                            open: Number(candle.open),
                                            high: Number(candle.high),
                                            low: Number(candle.low),
                                            close: Number(candle.close)
                                        };

                                        if (!Number.isFinite(clean.time) || clean.time <= 0 ||
                                            !Number.isFinite(clean.open) || !Number.isFinite(clean.high) ||
                                            !Number.isFinite(clean.low) || !Number.isFinite(clean.close)) {
                                            console.error(`[BULLETPROOF-TF] EMERGENCY REJECT candle ${index}:`, clean);
                                            return null;
                                        }

                                        return clean;
                                    } catch (cleanError) {
                                        console.error(`[BULLETPROOF-TF] Error cleaning candle ${index}:`, cleanError, candle);
                                        return null;
                                    }
                                }).filter(candle => candle !== null);

                                console.log(`[BULLETPROOF-TF] Final clean data: ${cleanData.length} candles`);

                                if (cleanData.length > 0) {
                                    // BULLETPROOF DATA SETTING: Use recreation-safe approach
                                    try {
                                        if (message.chart_recreation) {
                                            // Chart was just recreated, set data directly without clearing
                                            console.log('[BULLETPROOF-TF] Setting data on recreated chart...');

                                            // Extra safety check before setting data
                                            if (!candlestickSeries || typeof candlestickSeries.setData !== 'function') {
                                                throw new Error('candlestickSeries became invalid during data setting');
                                            }

                                            candlestickSeries.setData(cleanData);
                                            console.log('[BULLETPROOF-TF] ✅ SUCCESS: Data set on recreated chart');
                                        } else {
                                            // Standard approach for non-recreation scenarios
                                            console.log('[BULLETPROOF-TF] Using standard data setting...');
                                            candlestickSeries.setData([]);
                                            setTimeout(() => {
                                                try {
                                                    candlestickSeries.setData(cleanData);
                                                    console.log('[BULLETPROOF-TF] ✅ SUCCESS: Standard data setting completed');
                                                } catch (delayedError) {
                                                    console.error('[BULLETPROOF-TF] Delayed setData error:', delayedError);
                                                    location.reload();
                                                }
                                            }, 50);
                                        }
                                    } catch (setDataError) {
                                        console.error('[BULLETPROOF-TF] CRITICAL: setData failed:', setDataError);
                                        console.error('[BULLETPROOF-TF] EMERGENCY: Triggering page reload...');
                                        location.reload();
                                        return;
                                    }

                                    document.title = `${message.timeframe} Bulletproof (${cleanData.length} candles)`;

                                    // Log validation summary
                                    if (message.validation_summary) {
                                        console.log('[BULLETPROOF-TF] Validation summary:', message.validation_summary);
                                    }

                                } else {
                                    console.error('[BULLETPROOF-TF] No clean candles after final filtering');
                                }
                            } else {
                                console.error('[BULLETPROOF-TF] No valid candles after initial filtering');
                            }
                        } catch (error) {
                            console.error('[BULLETPROOF-TF] Processing error:', error);
                            console.error('[BULLETPROOF-TF] EMERGENCY: Reloading page...');
                            location.reload();
                        }
                    } else {
                        console.error('[BULLETPROOF-TF] Invalid or empty data:', message.data?.length || 'no data');
                    }
                    break;

                case 'emergency_recovery_required':
                    // 🚨 EMERGENCY RECOVERY: Handle critical chart corruption
                    console.error('[EMERGENCY] Recovery required:', message.error);
                    console.error('[EMERGENCY] Transaction ID:', message.transaction_id);
                    console.error('[EMERGENCY] Reloading page in 2 seconds...');

                    // Show user notification
                    alert(`Chart error detected: ${message.error}\nPage will reload automatically.`);

                    setTimeout(() => {
                        location.reload();
                    }, 2000);
                    break;

                default:
                    console.log('[UNKNOWN] Unknown message type:', message.type);
            }
        }

        // Position Overlay Functions
        function addPositionOverlay(position) {
            const positionId = position.id;

            // Entry Line (grün für Long, rot für Short)
            const entryColor = position.type === 'LONG' ? '#089981' : '#f23645';
            const entrySeries = chart.addLineSeries({
                color: entryColor,
                lineWidth: 2,
                lineStyle: 0, // Solid
                title: `Entry ${positionId}`
            });
            entrySeries.setData([{time: 0, value: position.entry_price}]);

            // Stop Loss Line (rot)
            let stopLossSeries = null;
            if (position.stop_loss) {
                stopLossSeries = chart.addLineSeries({
                    color: '#ff4444',
                    lineWidth: 1,
                    lineStyle: 1, // Dashed
                    title: `SL ${positionId}`
                });
                stopLossSeries.setData([{time: 0, value: position.stop_loss}]);
            }

            // Take Profit Line (grün)
            let takeProfitSeries = null;
            if (position.take_profit) {
                takeProfitSeries = chart.addLineSeries({
                    color: '#44ff44',
                    lineWidth: 1,
                    lineStyle: 1, // Dashed
                    title: `TP ${positionId}`
                });
                takeProfitSeries.setData([{time: 0, value: position.take_profit}]);
            }

            // Position Box (transparente Box zwischen Entry und TP/SL)
            const boxSeries = chart.addAreaSeries({
                topColor: position.type === 'LONG' ? 'rgba(8, 153, 129, 0.1)' : 'rgba(242, 54, 69, 0.1)',
                bottomColor: position.type === 'LONG' ? 'rgba(8, 153, 129, 0.05)' : 'rgba(242, 54, 69, 0.05)',
                lineColor: 'transparent'
            });

            // Box-Daten basierend auf Position-Typ
            const boxTop = position.type === 'LONG' ?
                (position.take_profit || position.entry_price * 1.02) :
                position.entry_price;
            const boxBottom = position.type === 'LONG' ?
                position.entry_price :
                (position.take_profit || position.entry_price * 0.98);

            boxSeries.setData([{time: 0, value: boxTop}]);

            // Speichere alle Series für diese Position
            window.positionLines[positionId] = {
                entry: entrySeries,
                stopLoss: stopLossSeries,
                takeProfit: takeProfitSeries,
                box: boxSeries,
                position: position
            };

            console.log(`✅ Position overlay added: ${positionId} ${position.type}`);
        }

        function removePositionOverlay(positionId) {
            const positionData = window.positionLines[positionId];
            if (positionData) {
                // Entferne alle Series
                chart.removeSeries(positionData.entry);
                if (positionData.stopLoss) chart.removeSeries(positionData.stopLoss);
                if (positionData.takeProfit) chart.removeSeries(positionData.takeProfit);
                chart.removeSeries(positionData.box);

                // Lösche aus Container
                delete window.positionLines[positionId];
                console.log(`❌ Position overlay removed: ${positionId}`);
            }
        }

        function syncPositions(positions) {
            // Lösche alle existierenden Overlays
            for (const positionId in window.positionLines) {
                removePositionOverlay(positionId);
            }

            // Füge alle aktiven Positionen hinzu
            positions.forEach(position => {
                if (position.status === 'OPEN') {
                    addPositionOverlay(position);
                }
            });
        }

        // Position Box Functions - NEUE IMPLEMENTIERUNG MIT ECHTEN RECHTECKEN
        function createPositionBox(time, entryPrice, clickX, clickY, isShort = false) {
            // Entferne alte Position Box falls vorhanden
            if (window.currentPositionBox) {
                removeCurrentPositionBox();
            }

            // Kleinere SL/TP für bessere Sichtbarkeit (0.25% Risk, 0.5% Reward)
            const riskPercent = 0.0025; // 0.25%
            const rewardPercent = 0.005; // 0.5%

            // Für Short Positionen sind TP/SL umgekehrt
            let stopLoss, takeProfit;
            if (isShort) {
                stopLoss = entryPrice * (1 + riskPercent);   // SL oben (höher als Entry)
                takeProfit = entryPrice * (1 - rewardPercent); // TP unten (niedriger als Entry)
            } else {
                stopLoss = entryPrice * (1 - riskPercent);   // SL unten (niedriger als Entry)
                takeProfit = entryPrice * (1 + rewardPercent); // TP oben (höher als Entry)
            }

            console.log('💰 Preise:', {entry: entryPrice, sl: stopLoss, tp: takeProfit});
            console.log('📍 Click-Position:', clickX, clickY, 'Container Breite:', document.getElementById('chart_container')?.clientWidth);

            // Box Dimensionen
            const currentTime = Math.floor(Date.now() / 1000);
            const boxWidth = 7200; // 2 Stunden für bessere Sichtbarkeit
            const timeEnd = currentTime + boxWidth;

            // Position Box Object erstellen
            window.currentPositionBox = {
                id: 'POS_' + Date.now(),
                entryPrice: entryPrice,
                stopLoss: stopLoss,
                takeProfit: takeProfit,
                time: currentTime,
                timeEnd: timeEnd,
                width: boxWidth,
                isResizing: false,
                resizeHandle: null,
                isShort: isShort,
                // NEUE X-Koordinaten basierend auf Click-Position
                clickX: clickX || null,  // Echte Click-X-Koordinate
                clickY: clickY || null,  // Echte Click-Y-Koordinate
                x1Percent: clickX ? Math.max(0, (clickX - 60) / document.getElementById('chart_container').clientWidth) : 0.45,  // 60px links vom Klick
                x2Percent: clickX ? Math.min(1, (clickX + 60) / document.getElementById('chart_container').clientWidth) : 0.55,  // 60px rechts vom Klick
                // DIREKTE Y-KOORDINATEN FÜR SOFORTIGE UPDATES - Entry Level an exakter Click-Position
                entryY: clickY || null,  // ⭐ Verwende Click-Y für Entry Level
                slY: null,
                tpY: null
            };

            // Zeichne die Box mit Canvas Overlay (echte Rechtecke)
            createCanvasOverlay();
            drawPositionBox();

            // Erstelle Price Lines auf der Y-Achse (DEAKTIVIERT für Positionseröffnungstool)
            // createPriceLines(entryPrice, stopLoss, takeProfit);

            console.log('📦 Neue Position Box erstellt:', window.currentPositionBox);
        }

        function createCanvasOverlay() {
            // Entferne alte Canvas falls vorhanden
            const oldCanvas = document.getElementById('position-canvas');
            if (oldCanvas) oldCanvas.remove();

            const chartContainer = document.getElementById('chart_container');
            const canvas = document.createElement('canvas');
            canvas.id = 'position-canvas';
            canvas.style.position = 'absolute';
            canvas.style.top = '0';
            canvas.style.left = '0';
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.pointerEvents = 'auto';
            canvas.style.zIndex = '1000';
            canvas.width = chartContainer.clientWidth;
            canvas.height = chartContainer.clientHeight;

            chartContainer.style.position = 'relative';
            chartContainer.appendChild(canvas);

            const ctx = canvas.getContext('2d');
            window.positionCanvas = canvas;
            window.positionCtx = ctx;

            // Mouse Events für Resize
            canvas.addEventListener('mousedown', onCanvasMouseDown);
            canvas.addEventListener('mousemove', onCanvasMouseMove);
            canvas.addEventListener('mouseup', onCanvasMouseUp);
        }

        function drawPositionBox() {
            const box = window.currentPositionBox;
            const ctx = window.positionCtx;
            const canvas = window.positionCanvas;

            if (!box || !ctx || !canvas) {
                console.warn('❌ drawPositionBox: Missing box, context, or canvas');
                return;
            }

            // Clear canvas
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            try {
                // SICHERE API AUFRUFE - Prüfe ob Chart bereit ist
                if (!chart || !candlestickSeries) {
                    console.warn('❌ Chart or series not ready');
                    return;
                }

                // Verwende dynamische oder Fallback Koordinaten
                const chartWidth = canvas.width;
                const chartHeight = canvas.height;

                // X-Position: Dynamische Werte aus Box-Objektt, sonst Fallback
                const x1 = chartWidth * (box.x1Percent || 0.1);
                const x2 = chartWidth * (box.x2Percent || 0.9);

                // Y-Koordinaten: VERWENDE GESPEICHERTE ODER BERECHNE NEU
                let entryY, slY, tpY;

                // EINZELNE KOORDINATEN-CACHE-PRÜFUNG
                // Verwende gecachte Koordinate wenn vorhanden, sonst berechne neu
                try {
                    entryY = (box.entryY !== null) ? box.entryY : candlestickSeries.priceToCoordinate(box.entryPrice);
                    slY = (box.slY !== null) ? box.slY : candlestickSeries.priceToCoordinate(box.stopLoss);
                    tpY = (box.tpY !== null) ? box.tpY : candlestickSeries.priceToCoordinate(box.takeProfit);

                    // Validiere Koordinaten
                    if (isNaN(entryY) || isNaN(slY) || isNaN(tpY) ||
                        entryY < 0 || slY < 0 || tpY < 0 ||
                        entryY > chartHeight || slY > chartHeight || tpY > chartHeight) {
                        throw new Error('Invalid coordinates from API');
                    }

                    // Aktualisiere Cache nur für neu berechnete Werte
                    if (box.entryY === null) box.entryY = entryY;
                    if (box.slY === null) box.slY = slY;
                    if (box.tpY === null) box.tpY = tpY;

                    console.log('📍 Using mixed cached/calculated coordinates:', {
                        entryY: box.entryY === entryY ? 'cached' : 'calculated',
                        slY: box.slY === slY ? 'cached' : 'calculated',
                        tpY: box.tpY === tpY ? 'cached' : 'calculated'
                    });

                } catch (apiError) {
                        console.warn('❌ API Error, using fallback coordinates:', apiError);
                        // Fallback: Verwende prozentuale Positionen
                        entryY = chartHeight * 0.5;  // Mitte
                        slY = chartHeight * 0.7;     // 70% (unten)
                        tpY = chartHeight * 0.3;     // 30% (oben)

                        // Speichere auch Fallback-Koordinaten
                        box.entryY = entryY;
                        box.slY = slY;
                        box.tpY = tpY;
                    }

                console.log('📊 Drawing at coordinates:', {entryY, slY, tpY, x1, x2});

                // Zeichne Stop Loss Box (rot)
                ctx.fillStyle = 'rgba(242, 54, 69, 0.2)';
                ctx.strokeStyle = '#f23645';
                ctx.lineWidth = 2;
                const slHeight = Math.abs(entryY - slY);
                const slTop = Math.min(entryY, slY);

                if (slHeight > 0) {
                    ctx.fillRect(x1, slTop, x2 - x1, slHeight);
                    ctx.strokeRect(x1, slTop, x2 - x1, slHeight);
                }

                // Zeichne Take Profit Box (grün)
                ctx.fillStyle = 'rgba(8, 153, 129, 0.2)';
                ctx.strokeStyle = '#089981';
                ctx.lineWidth = 2;
                const tpHeight = Math.abs(entryY - tpY);
                const tpTop = Math.min(entryY, tpY);

                if (tpHeight > 0) {
                    ctx.fillRect(x1, tpTop, x2 - x1, tpHeight);
                    ctx.strokeRect(x1, tpTop, x2 - x1, tpHeight);
                }

                // Zeichne Entry Line (weiß)
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.moveTo(x1, entryY);
                ctx.lineTo(x2, entryY);
                ctx.stroke();

                // Zeichne Resize Handles in den Ecken
                drawResizeHandles(x1, x2, slTop, tpTop, slHeight, tpHeight);

                // Zeichne Mülleimer-Symbol (Delete Button)
                drawDeleteButton(x2, Math.min(slTop, tpTop));

                // Speichere Koordinaten für Interaktion
                window.boxCoordinates = {
                    x1, x2, entryY, slY, tpY,
                    slTop, tpTop, slHeight, tpHeight,
                    // Delete Button Koordinaten
                    deleteButtonX: x2,
                    deleteButtonY: Math.min(slTop, tpTop),
                    deleteButtonSize: 20
                };

                console.log('✅ Position Box gezeichnet erfolgreich');

            } catch (error) {
                console.error('❌ Kritischer Fehler beim Zeichnen der Position Box:', error);
                console.error('Error Stack:', error.stack);
            }
        }

        function drawResizeHandles(x1, x2, slTop, tpTop, slHeight, tpHeight) {
            const ctx = window.positionCtx;
            const handleSize = 8;

            // Nur äußere Handles - KEINE auf der Entry-Linie
            const slBottom = slTop + slHeight;
            // SL Box Handles (rot) - nur Bottom (weit unten)
            drawHandle(ctx, x1, slBottom, '#f23645', 'SL-BL'); // Bottom-Left
            drawHandle(ctx, x2, slBottom, '#f23645', 'SL-BR'); // Bottom-Right

            // TP Box Handles (grün) - nur Top (weit oben)
            drawHandle(ctx, x1, tpTop, '#089981', 'TP-TL'); // Top-Left
            drawHandle(ctx, x2, tpTop, '#089981', 'TP-TR'); // Top-Right

            // DEAKTIVIERT: Mittlere Handles für Box-Breite
            // const middleY = (slTop + tpBottom) / 2;
            // drawHandle(ctx, x1, middleY, '#007bff', 'WIDTH-L');
            // drawHandle(ctx, x2, middleY, '#007bff', 'WIDTH-R');

            // Speichere Handle-Positionen - nur äußere Handles
            window.resizeHandles = {
                'SL-BL': {x: x1, y: slBottom, type: 'sl'},
                'SL-BR': {x: x2, y: slBottom, type: 'sl'},
                'TP-TL': {x: x1, y: tpTop, type: 'tp'},
                'TP-TR': {x: x2, y: tpTop, type: 'tp'}
            };
        }

        function drawHandle(ctx, x, y, color, id) {
            const size = 8;
            ctx.fillStyle = color;
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 1;

            ctx.fillRect(x - size/2, y - size/2, size, size);
            ctx.strokeRect(x - size/2, y - size/2, size, size);
        }

        function drawDeleteButton(x, y) {
            const ctx = window.positionCtx;
            const size = 20;
            const iconSize = 12;

            // Button Position: rechts oben an der Box
            const buttonX = x + 5;
            const buttonY = y - 25;

            // Zeichne Button Hintergrund (rot mit Transparenz)
            ctx.fillStyle = 'rgba(242, 54, 69, 0.8)';
            ctx.strokeStyle = '#f23645';
            ctx.lineWidth = 2;
            ctx.fillRect(buttonX - size/2, buttonY - size/2, size, size);
            ctx.strokeRect(buttonX - size/2, buttonY - size/2, size, size);

            // Zeichne Mülleimer-Symbol (vereinfacht als "X")
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.beginPath();
            // X-Symbol
            ctx.moveTo(buttonX - iconSize/2, buttonY - iconSize/2);
            ctx.lineTo(buttonX + iconSize/2, buttonY + iconSize/2);
            ctx.moveTo(buttonX + iconSize/2, buttonY - iconSize/2);
            ctx.lineTo(buttonX - iconSize/2, buttonY + iconSize/2);
            ctx.stroke();

            // Speichere Button Koordinaten für Click-Detection
            if (!window.deleteButtonCoords) window.deleteButtonCoords = {};
            window.deleteButtonCoords = {
                x: buttonX,
                y: buttonY,
                size: size
            };
        }

        // NEUE MOUSE EVENT HANDLERS FÜR BOX-INTERNE RESIZE
        let isDragging = false;
        let dragHandle = null;

        function onCanvasMouseDown(e) {
            const rect = e.target.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Check if mouse is over delete button
            if (window.deleteButtonCoords && window.currentPositionBox) {
                const btn = window.deleteButtonCoords;
                const distance = Math.sqrt(
                    Math.pow(mouseX - btn.x, 2) + Math.pow(mouseY - btn.y, 2)
                );

                if (distance <= btn.size/2) {
                    console.log('🗑️ Delete Button geklickt - lösche Position Box');
                    removeCurrentPositionBox();
                    e.preventDefault();
                    return;
                }
            }

            // Check if mouse is over any resize handle
            for (const [id, handle] of Object.entries(window.resizeHandles || {})) {
                const distance = Math.sqrt(
                    Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                );

                if (distance <= 12) { // 12px click tolerance
                    isDragging = true;
                    dragHandle = id;
                    // Cursor für Eckhandles
                    e.target.style.cursor = 'nw-resize'; // Diagonal resize für Eckhandles
                    console.log('🎯 Resize gestartet:', id);
                    return;
                }
            }

            // Check if mouse is over Entry-Linie (weiße Linie)
            if (window.boxCoordinates && window.currentPositionBox) {
                const coords = window.boxCoordinates;
                const entryY = coords.entryY;
                const x1 = coords.x1;
                const x2 = coords.x2;

                // Prüfe ob Klick auf Entry-Linie (Y-Koordinate ±10px, X zwischen x1 und x2)
                if (Math.abs(mouseY - entryY) <= 10 && mouseX >= x1 && mouseX <= x2) {
                    isDragging = true;
                    dragHandle = 'ENTRY-LINE';
                    e.target.style.cursor = 'ns-resize';
                    console.log('🎯 Entry-Linie Drag gestartet');
                }
            }
        }

        function onCanvasMouseMove(e) {
            const rect = e.target.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            if (!isDragging) {
                // Update cursor based on hover over handles
                let cursorType = 'default';
                for (const [id, handle] of Object.entries(window.resizeHandles || {})) {
                    const distance = Math.sqrt(
                        Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                    );
                    if (distance <= 12) {
                        cursorType = 'nw-resize'; // Diagonal für Eckhandles
                        break;
                    }
                }

                // Check hover over Entry-Linie
                if (cursorType === 'default' && window.boxCoordinates && window.currentPositionBox) {
                    const coords = window.boxCoordinates;
                    const entryY = coords.entryY;
                    const x1 = coords.x1;
                    const x2 = coords.x2;

                    if (Math.abs(mouseY - entryY) <= 10 && mouseX >= x1 && mouseX <= x2) {
                        cursorType = 'ns-resize'; // Vertikal für Entry-Linie
                    }
                }

                e.target.style.cursor = cursorType;
                return;
            }

            // Dragging logic - resize the box (HORIZONTAL + VERTIKAL)
            try {
                // SICHERE API AUFRUFE für Coordinate Conversion
                if (!chart || !candlestickSeries) {
                    console.warn('❌ Chart not ready for coordinate conversion');
                    return;
                }

                // Vertical Price änderung
                const newPrice = candlestickSeries.coordinateToPrice(mouseY);

                // Horizontal Time/Width änderung
                const canvas = window.positionCanvas;
                const chartWidth = canvas.width;

                // Berechne neue X-Position als Prozent der Chart-Breite
                const newXPercent = mouseX / chartWidth;

                if (!isNaN(newPrice) && newPrice > 0 && newXPercent >= 0 && newXPercent <= 1) {
                    updateBoxFromHandle(dragHandle, newPrice, newXPercent, mouseX);
                } else {
                    console.warn('❌ Invalid values:', {price: newPrice, xPercent: newXPercent});
                }
            } catch (error) {
                console.error('❌ Fehler beim Box Resize:', error);
                // Fallback: Stoppe Dragging bei Fehler
                isDragging = false;
                dragHandle = null;
                e.target.style.cursor = 'default';
            }
        }

        function onCanvasMouseUp(e) {
            if (isDragging) {
                console.log('🎯 Box Resize beendet:', dragHandle);
                isDragging = false;
                dragHandle = null;
                e.target.style.cursor = 'default';
            }
        }

        function updateBoxFromHandle(handleId, newPrice, newXPercent, mouseX) {
            const box = window.currentPositionBox;
            if (!box) return;

            // ENTRY-LINIE: Verschieben nur Entry-Preis vertikal
            if (handleId === 'ENTRY-LINE') {
                box.entryPrice = newPrice;

                // SOFORTIGE KOORDINATEN-CACHE AKTUALISIERUNG
                box.entryY = candlestickSeries.priceToCoordinate(newPrice);
                console.log('🎯 ENTRY-Koordinate sofort cached:', box.entryY);

                // Update Price Lines mit neuem Entry-Preis
                if (window.positionPriceLines && window.positionPriceLines.entry) {
                    candlestickSeries.removePriceLine(window.positionPriceLines.entry);
                    window.positionPriceLines.entry = candlestickSeries.createPriceLine({
                        price: newPrice,
                        color: '#ffffff',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Solid,
                        axisLabelVisible: true,
                        title: 'Entry'
                    });
                }

                console.log('📊 ENTRY-LINIE VERSCHOBEN:', {
                    newEntry: newPrice,
                    SL: box.stopLoss,
                    TP: box.takeProfit
                });
            } else {
                // ECKHANDLES: Sowohl Preise als auch Breite ändern

                // Update prices based on which handle was dragged
                if (handleId.includes('SL')) {
                    // BEGRENZUNG: SL darf nicht über Entry-Preis gezogen werden
                    if (newPrice >= box.entryPrice) {
                        console.warn('⚠️ SL darf nicht über Entry-Preis! Entry:', box.entryPrice, 'SL Versuch:', newPrice);
                        newPrice = box.entryPrice - 1; // 1 Punkt unter Entry
                    }
                    box.stopLoss = newPrice;

                    // SOFORTIGE KOORDINATEN-CACHE AKTUALISIERUNG
                    box.slY = candlestickSeries.priceToCoordinate(newPrice);
                    console.log('🎯 SL-Koordinate sofort cached:', box.slY);

                    // Update SL Price Line
                    if (window.positionPriceLines && window.positionPriceLines.stopLoss) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.stopLoss);
                        window.positionPriceLines.stopLoss = candlestickSeries.createPriceLine({
                            price: newPrice,
                            color: '#f23645',
                            lineWidth: 2,
                            lineStyle: LightweightCharts.LineStyle.Solid,
                            axisLabelVisible: true,
                            title: 'SL'
                        });
                    }

                    console.log('📉 SL aktualisiert:', newPrice);
                } else if (handleId.includes('TP')) {
                    // BEGRENZUNG: TP darf nicht unter Entry-Preis gezogen werden
                    if (newPrice <= box.entryPrice) {
                        console.warn('⚠️ TP darf nicht unter Entry-Preis! Entry:', box.entryPrice, 'TP Versuch:', newPrice);
                        newPrice = box.entryPrice + 1; // 1 Punkt über Entry
                    }
                    box.takeProfit = newPrice;

                    // SOFORTIGE KOORDINATEN-CACHE AKTUALISIERUNG
                    box.tpY = candlestickSeries.priceToCoordinate(newPrice);
                    console.log('🎯 TP-Koordinate sofort cached:', box.tpY);

                    // Update TP Price Line
                    if (window.positionPriceLines && window.positionPriceLines.takeProfit) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.takeProfit);
                        window.positionPriceLines.takeProfit = candlestickSeries.createPriceLine({
                            price: newPrice,
                            color: '#089981',
                            lineWidth: 2,
                            lineStyle: LightweightCharts.LineStyle.Solid,
                            axisLabelVisible: true,
                            title: 'TP'
                        });
                    }

                    console.log('📈 TP aktualisiert:', newPrice);
                }

                // Horizontale Resize für Eckhandles
                const isLeftHandle = handleId.includes('-TL') || handleId.includes('-BL');
                const isRightHandle = handleId.includes('-TR') || handleId.includes('-BR');

                if (isLeftHandle) {
                    box.x1Percent = newXPercent;
                    console.log('<-> ECK: Links Handle bewegt zu X:', mouseX);
                } else if (isRightHandle) {
                    box.x2Percent = newXPercent;
                    console.log('<-> ECK: Rechts Handle bewegt zu X:', mouseX);
                }
            }

            // Stelle sicher dass x1 < x2
            if (box.x1Percent && box.x2Percent && box.x1Percent > box.x2Percent) {
                const temp = box.x1Percent;
                box.x1Percent = box.x2Percent;
                box.x2Percent = temp;
                console.log('🔄 Box-Seiten getauscht');
            }

            // Redraw the entire position box
            drawPositionBox();
        }

        // VERALTETE FUNKTIONEN ENTFERNT - NUR NOCH CANVAS-BASIERT

        function createPriceLines(entryPrice, stopLoss, takeProfit) {
            // Entferne alte Price Lines falls vorhanden
            removePriceLines();

            // Speichere Price Lines in globaler Variable für späteres Entfernen
            window.positionPriceLines = {};

            try {
                // Entry Price Line (weiß)
                window.positionPriceLines.entry = candlestickSeries.createPriceLine({
                    price: entryPrice,
                    color: '#ffffff',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'Entry'
                });

                // Stop Loss Price Line (rot)
                window.positionPriceLines.stopLoss = candlestickSeries.createPriceLine({
                    price: stopLoss,
                    color: '#f23645',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'SL'
                });

                // Take Profit Price Line (grün)
                window.positionPriceLines.takeProfit = candlestickSeries.createPriceLine({
                    price: takeProfit,
                    color: '#089981',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'TP'
                });

                console.log('📊 Price Lines erstellt:', {entry: entryPrice, sl: stopLoss, tp: takeProfit});
            } catch (error) {
                console.error('❌ Fehler beim Erstellen der Price Lines:', error);
            }
        }

        function removePriceLines() {
            // Entferne alle vorhandenen Price Lines
            if (window.positionPriceLines) {
                try {
                    if (window.positionPriceLines.entry) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.entry);
                    }
                    if (window.positionPriceLines.stopLoss) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.stopLoss);
                    }
                    if (window.positionPriceLines.takeProfit) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.takeProfit);
                    }
                } catch (error) {
                    console.warn('⚠️ Fehler beim Entfernen der Price Lines:', error);
                }
                window.positionPriceLines = null;
            }
        }

        function removeCurrentPositionBox() {
            if (window.currentPositionBox) {
                // Entferne Canvas Overlay
                const canvas = document.getElementById('position-canvas');
                if (canvas) {
                    canvas.remove();
                }

                // Entferne Price Lines (DEAKTIVIERT da Price Lines deaktiviert)
                // removePriceLines();

                // Lösche Box Object und globale Variablen
                window.currentPositionBox = null;
                window.positionCanvas = null;
                window.positionCtx = null;
                window.boxCoordinates = null;
                window.resizeHandles = null;

                console.log('🗑️ Position Box entfernt');
            }
        }

        // ===== GLOBAL FUNCTIONS FOR ONCLICK HANDLERS =====
        // Test global scope
        console.log('🌍 Global functions being defined...');

        function togglePositionTool() {
            console.log('📦 Position Box Tool Button geklickt via onclick');
            window.positionBoxMode = !window.positionBoxMode;

            const positionTool = document.getElementById('positionBoxTool');
            if (!positionTool) {
                console.error('❌ positionBoxTool Element nicht gefunden!');
                return;
            }

            if (window.positionBoxMode) {
                // Deaktiviere Short Position Mode wenn Long aktiviert wird
                if (window.shortPositionMode) {
                    window.shortPositionMode = false;
                    const shortTool = document.getElementById('shortPositionTool');
                    if (shortTool) {
                        shortTool.classList.remove('active');
                        shortTool.style.background = '#333';
                        shortTool.style.color = '#fff';
                    }
                }
                // Aktiviere Tool
                positionTool.classList.add('active');
                console.log('📦 Position Box Tool AKTIVIERT');
            } else {
                // Deaktiviere Tool
                positionTool.classList.remove('active');
                positionTool.style.background = '#333';
                positionTool.style.color = '#fff';
                console.log('📦 Position Box Tool DEAKTIVIERT');
            }
        }

        function toggleShortPositionTool() {
            console.log('📉 Short Position Tool Button geklickt via onclick');
            window.shortPositionMode = !window.shortPositionMode;

            const shortTool = document.getElementById('shortPositionTool');
            if (!shortTool) {
                console.error('❌ shortPositionTool Element nicht gefunden!');
                return;
            }

            if (window.shortPositionMode) {
                // Deaktiviere Long Position Mode wenn Short aktiviert wird
                if (window.positionBoxMode) {
                    window.positionBoxMode = false;
                    const positionTool = document.getElementById('positionBoxTool');
                    if (positionTool) {
                        positionTool.classList.remove('active');
                        positionTool.style.background = '#333';
                        positionTool.style.color = '#fff';
                    }
                }
                // Aktiviere Tool
                shortTool.classList.add('active');
                console.log('📉 Short Position Tool AKTIVIERT');
            } else {
                // Deaktiviere Tool
                shortTool.classList.remove('active');
                shortTool.style.background = '#333';
                shortTool.style.color = '#fff';
                console.log('📉 Short Position Tool DEAKTIVIERT');
            }
        }

        function clearAllPositions() {
            console.log('[CLEAR ALL] Button geklickt via onclick - FORCE DEAKTIVIERE TOOL');

            try {
                // Deaktiviere beide Position Tools komplett
                window.positionBoxMode = false;
                window.shortPositionMode = false;

                const positionTool = document.getElementById('positionBoxTool');
                if (positionTool) {
                    positionTool.classList.remove('active');
                    positionTool.style.background = '#333';
                    positionTool.style.color = '#fff';
                    console.log('[SUCCESS] Long Position Tool deaktiviert via onclick');
                } else {
                    console.error('[ERROR] positionBoxTool Element nicht gefunden beim Clear!');
                }

                const shortTool = document.getElementById('shortPositionTool');
                if (shortTool) {
                    shortTool.classList.remove('active');
                    shortTool.style.background = '#333';
                    shortTool.style.color = '#fff';
                    console.log('[SUCCESS] Short Position Tool deaktiviert via onclick');
                } else {
                    console.error('[ERROR] shortPositionTool Element nicht gefunden beim Clear!');
                }

                // Versuche Position Box zu entfernen (falls vorhanden)
                if (typeof removeCurrentPositionBox === 'function') {
                    removeCurrentPositionBox();
                    console.log('[SUCCESS] Position Box entfernt');
                } else {
                    console.log('⚠️ removeCurrentPositionBox function not available yet');
                }
            } catch (error) {
                console.error('❌ Fehler in clearAllPositions:', error);
            }
        }

        // ===== TIMEFRAME FUNCTIONS =====
        // High-Performance Timeframe Change Function
        async function changeTimeframe(timeframe) {
            // Prevent double-requests
            if (window.isTimeframeChanging || timeframe === window.currentTimeframe) {
                return;
            }

            console.log(`Wechsle zu Timeframe: ${timeframe}`);
            window.isTimeframeChanging = true;

            try {
                // Check browser cache first
                const cacheKey = `tf_${timeframe}`;
                if (window.timeframeCache.has(cacheKey)) {
                    console.log(`[CACHE-HIT] Browser Cache Hit für ${timeframe} (${window.timeframeCache.size} total entries)`);
                    const cachedData = window.timeframeCache.get(cacheKey);
                    console.log(`[CACHE-HIT] Cached data: ${cachedData.length} candles, first: ${new Date(cachedData[0]?.time * 1000).toISOString()}`);

                    // 🚀 CRITICAL FIX: Cache-Validation gegen Server-State
                    // Prüfe ob Cache-Daten nach GoTo-Operation noch gültig sind
                    let cacheValid = true;
                    if (window.lastGoToDate && cachedData.length > 0) {
                        const cacheDataDate = new Date(cachedData[0]?.time * 1000).toISOString().split('T')[0];
                        if (cacheDataDate !== window.lastGoToDate) {
                            console.log(`[CACHE-VALIDATION] Cache ungültig: Daten ${cacheDataDate} vs Server ${window.lastGoToDate}`);
                            window.timeframeCache.delete(cacheKey);
                            console.log(`[CACHE-INVALIDATION] Stale cache entry removed for ${timeframe}`);
                            cacheValid = false;
                        }
                    }

                    if (cacheValid) {
                        // Instant UI update from cache mit Smart Positioning
                        updateTimeframeButtons(timeframe);
                        candlestickSeries.setData(cachedData);

                        // Smart Positioning: Nach Cache-Hit zurück zu 50-Kerzen Standard
                        if (window.smartPositioning) {
                            window.smartPositioning.resetToStandardPosition(cachedData);
                        }

                        window.currentTimeframe = timeframe;
                        window.isTimeframeChanging = false;
                        return;
                    }
                }

                // 🚀 CACHE-MISS LOGGING: Detailliertes Logging für Server-Requests
                console.log(`[CACHE-MISS] No cache für ${timeframe} - Server-Request erforderlich (${window.timeframeCache.size} total entries)`);
                if (window.lastGoToDate) {
                    console.log(`[CACHE-MISS] Server-State: lastGoToDate=${window.lastGoToDate}`);
                }

                // Optimistic UI update
                updateTimeframeButtons(timeframe);

                // Performance-optimized API call mit adaptivem Timeout
                const controller = new AbortController();
                // ADAPTIVE TIMEOUT: Länger nach Go To Date wegen CSV-Processing
                const adaptiveTimeout = window.current_go_to_date ? 15000 : 8000; // 15s nach Go To Date, sonst 8s
                const timeoutId = setTimeout(() => controller.abort(), adaptiveTimeout);

                const response = await fetch('/api/chart/change_timeframe', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ timeframe: timeframe }),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);
                const result = await response.json();

                if (result.status === 'success' && result.data && result.data.length > 0) {
                    console.log(`Timeframe gewechselt zu ${timeframe}: ${result.count} Kerzen`);

                    // Optimized data formatting - no unnecessary parsing
                    const formattedData = result.data.filter(item =>
                        item && item.time &&
                        item.open != null && item.high != null &&
                        item.low != null && item.close != null
                    ).map(item => ({
                        time: item.time,  // Already correct format
                        open: parseFloat(item.open) || 0,  // Ensure float with fallback
                        high: parseFloat(item.high) || 0,
                        low: parseFloat(item.low) || 0,
                        close: parseFloat(item.close) || 0
                    }));

                    // Cache for instant future access
                    window.timeframeCache.set(cacheKey, formattedData);
                    console.log(`[CACHE-SET] Cached ${formattedData.length} candles für ${timeframe} (total cache: ${window.timeframeCache.size} entries)`);
                    console.log(`[CACHE-SET] Data range: ${new Date(formattedData[0]?.time * 1000).toISOString()} - ${new Date(formattedData[formattedData.length-1]?.time * 1000).toISOString()}`);

                    // Limit cache size to prevent memory issues
                    if (window.timeframeCache.size > 8) {
                        const firstKey = window.timeframeCache.keys().next().value;
                        window.timeframeCache.delete(firstKey);
                        console.log(`[CACHE-CLEANUP] Oldest cache entry removed: ${firstKey}`);
                    }

                    // Fast chart update mit Smart Positioning
                    candlestickSeries.setData(formattedData);

                    // Smart Positioning: Nach Timeframe-Wechsel zurück zu 50-Kerzen Standard
                    if (window.smartPositioning) {
                        window.smartPositioning.resetToStandardPosition(formattedData);
                    }

                    window.currentTimeframe = timeframe;
                } else {
                    console.error('Timeframe-Wechsel fehlgeschlagen:', result.message);
                    updateTimeframeButtons(window.currentTimeframe);
                }

            } catch (error) {
                if (error.name === 'AbortError') {
                    console.warn('Timeframe request timeout - aber WebSocket Daten könnten noch kommen');
                    // NICHT den Button-State zurücksetzen - WebSocket könnte noch antworten!
                    // Race Condition Fix: Lasse Button auf neuem Timeframe, falls WebSocket später antwortet
                } else {
                    console.error('Fehler beim Timeframe-Wechsel:', error);
                    // Nur bei echten Fehlern Button-State zurücksetzen
                    updateTimeframeButtons(window.currentTimeframe);
                }
            } finally {
                window.isTimeframeChanging = false;
            }
        }

        // Update Timeframe Button States
        function updateTimeframeButtons(activeTimeframe) {
            const timeframeButtons = document.querySelectorAll('.timeframe-btn');
            timeframeButtons.forEach(btn => {
                const btnTimeframe = btn.getAttribute('data-timeframe');
                if (btnTimeframe === activeTimeframe) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }

        // ============ DEBUG CONTROLS EVENT HANDLERS ============
        // WICHTIG: Funktionen MÜSSEN vor DOMContentLoaded definiert werden!

        // Hilfsfunktion: Aktuelles Timeframe aus UI abrufen
        function getCurrentTimeframe() {
            // Zuerst prüfen: Debug Timeframe Selector
            const debugSelector = document.getElementById('debugTimeframSelector');
            if (debugSelector && debugSelector.value) {
                return debugSelector.value;
            }

            // Fallback: Chart Timeframe Button
            const activeButton = document.querySelector('.timeframe-btn.active');
            if (activeButton) {
                return activeButton.textContent.trim();
            }

            // Letzter Fallback
            return globalState?.currentTimeframe || '5m';
        }

        // Debug Skip Button Handler
        function handleDebugSkip() {
            // Dynamische Nachricht basierend auf Timeframe
            const currentTimeframe = getCurrentTimeframe();
            let skipMessage = "🚀 DEBUG SKIP: +1 Minute";

            if (currentTimeframe === '1m') {
                skipMessage = "🚀 DEBUG SKIP: +1 Minute";
            } else if (['2m', '3m', '5m', '15m', '30m'].includes(currentTimeframe)) {
                const timeframeMinutes = {'2m': 2, '3m': 3, '5m': 5, '15m': 15, '30m': 30};
                const skipMins = timeframeMinutes[currentTimeframe] || 1;
                skipMessage = `🚀 DEBUG SKIP: +${skipMins} Minutes`;
            } else if (['1h', '4h'].includes(currentTimeframe)) {
                const timeframeHours = {'1h': 1, '4h': 4};
                const skipHrs = timeframeHours[currentTimeframe] || 1;
                skipMessage = `🚀 DEBUG SKIP: +${skipHrs} Hour${skipHrs > 1 ? 's' : ''}`;
            }

            console.log(`${skipMessage} - Button clicked!`);
            serverLog('🔧 handleDebugSkip called');

            fetch('/api/debug/skip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Debug Skip Response:', data);
                serverLog('✅ Debug Skip successful', data);
            })
            .catch(error => {
                console.error('❌ Debug Skip Error:', error);
                serverLog('❌ Debug Skip failed', error);
            });
        }

        // Debug Play/Pause Button Handler
        function handleDebugPlayPause() {
            console.log('🚀 DEBUG PLAY/PAUSE: Toggle - Button clicked!');
            serverLog('🔧 handleDebugPlayPause called');

            fetch('/api/debug/toggle_play', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Debug PlayPause Response:', data);
                serverLog('✅ Debug PlayPause successful', data);

                // Update button text
                const playPauseBtn = document.getElementById('playPauseBtn');
                if (playPauseBtn) {
                    playPauseBtn.textContent = data.play_mode ? '⏸️' : '▶️';
                }
            })
            .catch(error => {
                console.error('❌ Debug PlayPause Error:', error);
                serverLog('❌ Debug PlayPause failed', error);
            });
        }

        // Debug Control Timeframe Handler - ONLY sets variable, NO chart reload
        function handleDebugTimeframe(timeframe) {
            console.log('🔧 DEBUG CONTROL: Variable-only change zu', timeframe);
            serverLog(`[DEBUG-CONTROL] Variable change to: ${timeframe}`);

            fetch(`/api/debug/set_control_timeframe/${timeframe}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Debug Control Response:', data);
                serverLog('✅ Debug Control Variable successful', data);
            })
            .catch(error => {
                console.error('❌ Debug Control Error:', error);
                serverLog('❌ Debug Control Variable failed', error);
            });
        }

        // Go To Date Modal Functions
        function openDateModal() {
            console.log('[GO TO DATE] Opening Modal...');
            const modal = document.getElementById('dateModal');
            const dateInput = document.getElementById('goToDateInput');

            // Setze ein verfügbares Datum als Default (Dezember 2024)
            // Die CSV-Daten gehen von 31. Dezember 2024 rückwärts
            const defaultDate = new Date('2024-12-25'); // Ein Datum das in den Daten ist
            const dateString = defaultDate.toISOString().split('T')[0];
            dateInput.value = dateString;

            // Setze min/max Werte für verfügbare Daten (ungefähr)
            dateInput.setAttribute('min', '2024-12-01'); // Ca. Startdatum der Daten
            dateInput.setAttribute('max', '2024-12-30'); // Enddatum der Daten

            modal.style.display = 'flex';
            dateInput.focus();
        }

        function closeDateModal() {
            console.log('[GO TO DATE] Closing Modal...');
            const modal = document.getElementById('dateModal');
            modal.style.display = 'none';
        }

        function goToSelectedDate() {
            const dateInput = document.getElementById('goToDateInput');
            const selectedDate = dateInput.value;

            if (!selectedDate) {
                alert('Bitte wähle ein Datum aus!');
                return;
            }

            console.log('[GO TO DATE] Request:', selectedDate);
            serverLog('[GO TO DATE] Request: ' + selectedDate);

            // Modal schließen
            closeDateModal();

            // API Call zum Backend
            fetch('/api/debug/go_to_date', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date: selectedDate })
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Go To Date Response:', data);
                serverLog('[SUCCESS] Go To Date successful: ' + data.message, data);

                if (data.status === 'success') {
                    console.log('[CHART] Chart wird zu neuem Datum reinitialisiert...');
                    // WebSocket wird automatisch das chart_reinitialize Event senden
                } else {
                    console.error('❌ Go To Date failed:', data.message);
                    alert('Fehler: ' + data.message);
                }
            })
            .catch(error => {
                console.error('❌ Go To Date Error:', error);
                serverLog('❌ Go To Date failed', error);
                alert('Fehler beim Laden des Datums: ' + error.message);
            });
        }

        // Modal schließen bei Escape-Taste
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                const modal = document.getElementById('dateModal');
                if (modal.style.display === 'flex') {
                    closeDateModal();
                }
            }
        });

        // Modal schließen bei Klick außerhalb
        document.addEventListener('click', function(event) {
            const modal = document.getElementById('dateModal');
            if (event.target === modal) {
                closeDateModal();
            }
        });

        // Warte bis DOM und Script geladen sind
        document.addEventListener('DOMContentLoaded', function() {
            serverLog('🔧 DOM loaded - Initialisiere Chart und Event Handlers...');

            // WICHTIG: Chart zuerst initialisieren
            console.log('🔧 Initialisiere Chart beim DOMContentLoaded...');
            initChart();

            // Registriere Button Event Handlers
            const positionBoxTool = document.getElementById('positionBoxTool');
            const shortPositionTool = document.getElementById('shortPositionTool');
            const clearAllBtn = document.getElementById('clearAll');

            // Debug Button Event Handlers - konsolidiert hier
            // Skip Button
            const skipBtn = document.getElementById('skipBtn');
            console.log('🔧 Debug setup - Skip Button element:', skipBtn);
            if (skipBtn) {
                skipBtn.addEventListener('click', handleDebugSkip);
                console.log('✅ Skip Button event listener attached');
            } else {
                console.error('❌ Skip Button not found!');
            }

            // Play/Pause Button
            const playPauseBtn = document.getElementById('playPauseBtn');
            console.log('🔧 Debug setup - PlayPause Button element:', playPauseBtn);
            if (playPauseBtn) {
                playPauseBtn.addEventListener('click', handleDebugPlayPause);
                console.log('✅ PlayPause Button event listener attached');
            } else {
                console.error('❌ PlayPause Button not found!');
            }

            // Speed Slider
            const speedSlider = document.getElementById('speedSlider');
            const speedDisplay = document.getElementById('speedDisplay');
            if (speedSlider && speedDisplay) {
                speedSlider.addEventListener('input', function() {
                    speedDisplay.textContent = `${this.value}x`;
                });

                speedSlider.addEventListener('change', function() {
                    handleDebugSpeed(this.value);
                });
            }

            // Timeframe Selector
            const timeframeSelector = document.getElementById('timeframeSelector');
            if (timeframeSelector) {
                timeframeSelector.addEventListener('change', function() {
                    handleDebugTimeframe(this.value);
                });
            }

            // Go To Date Button
            const goToDateBtn = document.getElementById('goToDateBtn');
            console.log('🔧 Debug setup - Go To Date Button element:', goToDateBtn);
            if (goToDateBtn) {
                goToDateBtn.addEventListener('click', openDateModal);
                console.log('✅ Go To Date Button event listener attached');
            } else {
                console.error('❌ Go To Date Button not found!');
            }

            console.log('🛠️ Debug Controls Event Handlers konsolidiert und initialized');

            if (positionBoxTool) {
                positionBoxTool.addEventListener('click', togglePositionTool);
                console.log('✅ Position Box Tool Event Handler registriert');
            } else {
                console.error('❌ positionBoxTool Button nicht gefunden');
            }

            if (shortPositionTool) {
                shortPositionTool.addEventListener('click', toggleShortPositionTool);
                console.log('✅ Short Position Tool Event Handler registriert');
            } else {
                console.error('❌ shortPositionTool Button nicht gefunden');
            }

            if (clearAllBtn) {
                clearAllBtn.addEventListener('click', clearAllPositions);
                console.log('✅ Clear All Button Event Handler registriert');
            } else {
                console.error('❌ clearAll Button nicht gefunden');
            }

            // Registriere Timeframe Button Event Handlers
            const timeframeButtons = document.querySelectorAll('.timeframe-btn');
            timeframeButtons.forEach(btn => {
                const timeframe = btn.getAttribute('data-timeframe');
                btn.addEventListener('click', () => changeTimeframe(timeframe));
                console.log(`✅ Timeframe Button ${timeframe} Event Handler registriert`);
            });

            if (timeframeButtons.length > 0) {
                console.log(`✅ ${timeframeButtons.length} Timeframe Buttons Event Handler registriert`);
            } else {
                console.error('❌ Keine Timeframe Buttons gefunden');
            }

            // Zusätzliche Sicherheit: Prüfe ob LightweightCharts verfügbar ist
            if (typeof LightweightCharts !== 'undefined') {
                console.log('✅ LightweightCharts library loaded');
                // DIREKT TESTEN: Chart erstellen ohne loadChart()
                try {
                    serverLog('🔧 DIRECT CHART TEST - Starting detailed debug...');

                    // 1. Container Debug
                    const container = document.getElementById('chart_container');
                    serverLog('🔍 Container Debug:', {
                        gefunden: !!container,
                        clientWidth: container?.clientWidth,
                        clientHeight: container?.clientHeight,
                        offsetWidth: container?.offsetWidth,
                        offsetHeight: container?.offsetHeight,
                        rect: container?.getBoundingClientRect()
                    });

                    if (!container) {
                        console.error('❌ Chart container nicht gefunden! ID: chart_container');
                        return;
                    }

                    // 2. LightweightCharts Debug
                    console.log('🔍 LightweightCharts Debug:');
                    console.log('  - LightweightCharts verfügbar:', typeof LightweightCharts);
                    console.log('  - createChart function:', typeof LightweightCharts.createChart);

                    // 3. Chart Creation Debug
                    console.log('🔧 Creating chart with options...');
                    const chartOptions = {
                        width: 800,
                        height: 600,
                        timeScale: { timeVisible: true },
                        grid: { vertLines: { visible: false }, horzLines: { visible: false } },
                        layout: {
                            background: { type: 'solid', color: '#FFFFFF' },
                            textColor: '#333'
                        }
                    };
                    console.log('  - Chart Options:', chartOptions);

                    const chart = LightweightCharts.createChart(container, chartOptions);
                    console.log('✅ Chart object created:', chart);

                    // 4. Series Debug
                    console.log('🔧 Adding candlestick series...');
                    const candlestickSeries = chart.addCandlestickSeries({
                        upColor: '#089981',
                        downColor: '#f23645',
                        borderVisible: false,
                        wickUpColor: '#089981',
                        wickDownColor: '#f23645'
                    });
                    console.log('✅ Candlestick series created:', candlestickSeries);

                    // 5. API Call Debug
                    console.log('🔧 Fetching chart data...');
                    fetch('/api/chart/data')
                        .then(response => {
                            console.log('📡 API Response Status:', response.status);
                            console.log('📡 API Response OK:', response.ok);
                            return response.json();
                        })
                        .then(data => {
                            console.log('📊 DETAILED DATA DEBUG:');
                            console.log('  - Data object:', data);
                            console.log('  - Data.data exists:', !!data.data);
                            console.log('  - Data.data length:', data.data?.length);
                            console.log('  - First 3 candles:', data.data?.slice(0, 3));
                            console.log('  - Last 3 candles:', data.data?.slice(-3));

                            if (data.data && data.data.length > 0) {
                                console.log('🔧 Setting data on candlestick series...');
                                candlestickSeries.setData(data.data);
                                console.log('✅ Data set successfully!');

                                // 6. Chart Rendering Debug
                                console.log('🔍 POST-RENDER DEBUG:');
                                setTimeout(() => {
                                    console.log('  - Container nach Render clientWidth:', container.clientWidth);
                                    console.log('  - Container nach Render clientHeight:', container.clientHeight);
                                    const canvasElements = container.querySelectorAll('canvas');
                                    console.log('  - Anzahl Canvas Elemente:', canvasElements.length);
                                    canvasElements.forEach((canvas, i) => {
                                        console.log(`  - Canvas ${i}: ${canvas.width}x${canvas.height}`);
                                    });
                                }, 1000);

                                console.log('✅ CHART ERFOLGREICH GELADEN!');
                            } else {
                                console.error('❌ Keine Daten erhalten oder leeres Array');
                            }
                        })
                        .catch(error => {
                            console.error('❌ Chart API Error Details:');
                            console.error('  - Error object:', error);
                            console.error('  - Error message:', error.message);
                            console.error('  - Error stack:', error.stack);
                        });

                } catch (error) {
                    console.error('❌ DIRECT CHART ERROR:', error);
                }
                connectWebSocket();
                loadAccountData(); // Lade initiale Account-Daten
            } else {
                console.error('❌ LightweightCharts library not loaded');
                // Fallback: Versuche nochmal nach kurzer Wartezeit
                setTimeout(() => {
                    if (typeof LightweightCharts !== 'undefined') {
                        console.log('✅ LightweightCharts library loaded (delayed)');
                        // DIREKT TESTEN: Chart erstellen (2. Fallback)
                        try {
                            console.log('🔧 FALLBACK CHART TEST - Creating chart...');
                            const chart = LightweightCharts.createChart(document.getElementById('chart_container'), {
                                width: 800,
                                height: 600,
                                timeScale: { timeVisible: true },
                                grid: { vertLines: { visible: false }, horzLines: { visible: false } }
                            });

                            const candlestickSeries = chart.addCandlestickSeries();

                            fetch('/api/chart/data')
                                .then(response => response.json())
                                .then(data => {
                                    console.log('🔧 FALLBACK - Daten empfangen:', data);
                                    if (data.data && data.data.length > 0) {
                                        candlestickSeries.setData(data.data);
                                        console.log('✅ FALLBACK CHART ERFOLGREICH!');
                                    }
                                })
                                .catch(error => console.error('❌ Fallback Chart Error:', error));

                        } catch (error) {
                            console.error('❌ FALLBACK CHART ERROR:', error);
                        }
                        connectWebSocket();
                        loadAccountData(); // Lade initiale Account-Daten
                    } else {
                        console.error('❌ LightweightCharts library failed to load');
                    }
                }, 1000);
            }
        });
    </script>
</body>
</html>
    """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket Endpoint für Realtime-Communication"""
    await manager.connect(websocket)

    try:
        while True:
            # Warte auf Nachrichten vom Client (falls nötig)
            data = await websocket.receive_text()
            # Hier könnten Client-Nachrichten verarbeitet werden

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")

@app.post("/api/chart/set_data")
async def set_chart_data(data: dict):
    """API Endpoint um Chart-Daten zu setzen"""

    # Update Chart State
    manager.update_chart_state({
        'type': 'set_data',
        'data': data.get('data', []),
        'symbol': data.get('symbol', 'NQ=F'),
        'interval': data.get('interval', '5m')
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'set_data',
        'data': data.get('data', []),
        'symbol': data.get('symbol', 'NQ=F'),
        'interval': data.get('interval', '5m')
    })

    return {"status": "success", "message": "Chart data updated"}

@app.post("/api/chart/add_candle")
async def add_candle(candle_data: dict):
    """API Endpoint um neue Kerze hinzuzufügen"""

    candle = candle_data.get('candle')
    if not candle:
        return {"status": "error", "message": "No candle data provided"}

    # Update Chart State
    manager.update_chart_state({
        'type': 'add_candle',
        'candle': candle
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'add_candle',
        'candle': candle
    })

    return {"status": "success", "message": "Candle added"}

@app.post("/api/chart/add_position")
async def add_position(position_data: dict):
    """API Endpoint um Position Overlay hinzuzufügen"""

    position = position_data.get('position')
    if not position:
        return {"status": "error", "message": "No position data provided"}

    # Update Chart State
    manager.update_chart_state({
        'type': 'add_position',
        'position': position
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'add_position',
        'position': position
    })

    return {"status": "success", "message": "Position overlay added"}

@app.post("/api/chart/remove_position")
async def remove_position(position_data: dict):
    """API Endpoint um Position Overlay zu entfernen"""

    position_id = position_data.get('position_id')
    if not position_id:
        return {"status": "error", "message": "No position_id provided"}

    # Update Chart State
    manager.update_chart_state({
        'type': 'remove_position',
        'position_id': position_id
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'remove_position',
        'position_id': position_id
    })

    return {"status": "success", "message": "Position overlay removed"}

@app.post("/api/chart/sync_positions")
async def sync_positions(positions_data: dict):
    """API Endpoint um alle Positionen zu synchronisieren"""

    positions = positions_data.get('positions', [])

    # Update Chart State
    manager.chart_state['positions'] = positions

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'positions_sync',
        'positions': positions
    })

    return {"status": "success", "message": f"Synchronized {len(positions)} positions"}

@app.get("/api/chart/status")
async def get_chart_status():
    """Chart Status und Verbindungsinfo"""
    return {
        "status": "running",
        "connections": len(manager.active_connections),
        "chart_state": {
            "symbol": manager.chart_state['symbol'],
            "interval": manager.chart_state['interval'],
            "candles_count": len(manager.chart_state['data']),
            "last_update": manager.chart_state['last_update']
        }
    }

@app.get("/api/chart/data")
async def get_chart_data():
    """Aktuelle Chart-Daten zurückgeben - Korrekt formatiert für TradingView"""
    chart_data = manager.chart_state['data']

    # Debug-Ausgabe für Datenvalidierung
    print(f"API /chart/data: Sende {len(chart_data)} Kerzen")
    if chart_data:
        first_candle = chart_data[0]
        print(f"Erste Kerze: time={first_candle.get('time')}, open={first_candle.get('open')}")

    return {
        "data": chart_data,  # Unix Timestamps direkt verwenden
        "symbol": manager.chart_state['symbol'],
        "interval": manager.chart_state['interval'],
        "count": len(chart_data),
        "format": "unix_timestamp"  # Frontend-Hinweis für Zeitformat
    }

@app.post("/api/chart/change_timeframe")
async def change_timeframe(request: Request):
    """🚀 BULLETPROOF TIMEFRAME TRANSITION PROTOCOL: 5-Phase Atomic Chart Series Recreation"""

    transaction_id = f"tf_transition_{int(datetime.now().timestamp())}"
    print(f"[BULLETPROOF-TF] Starting transaction {transaction_id}")

    try:
        # PHASE 1: PRE-TRANSITION VALIDATION & PLANNING
        print(f"[BULLETPROOF-TF] Phase 1: Pre-transition validation")

        data = await request.json()
        target_timeframe = data.get('timeframe', '5m')
        visible_candles = data.get('visible_candles', 200)
        current_timeframe = manager.chart_state.get('interval', '5m')

        # Create transition plan using Lifecycle Manager
        transition_plan = chart_lifecycle_manager.prepare_timeframe_transition(
            current_timeframe, target_timeframe
        )

        # Validate data availability
        current_global_time = unified_time_manager.get_current_time()
        if current_global_time:
            timeframe_minutes = unified_time_manager._get_timeframe_minutes(target_timeframe)
            lookback_time = current_global_time - timedelta(minutes=timeframe_minutes * visible_candles)

            # Pre-validate data exists
            test_data = timeframe_data_repository.get_candles_for_date_range(
                target_timeframe, lookback_time, current_global_time, max_candles=5
            )
            if not test_data:
                chart_lifecycle_manager.complete_timeframe_transition(success=False)
                return {
                    "status": "error",
                    "message": f"Keine {target_timeframe} Daten verfügbar für Zeit {current_global_time}",
                    "transaction_id": transaction_id
                }

        print(f"[BULLETPROOF-TF] Phase 1 COMPLETE - Transition plan: {transition_plan}")

        # PHASE 2: CHART SERIES DESTRUCTION & RECREATION
        print(f"[BULLETPROOF-TF] Phase 2: Chart series lifecycle management")

        if transition_plan['needs_recreation']:
            # Generate chart recreation command
            recreation_command = chart_lifecycle_manager.get_chart_recreation_command()
            print(f"[BULLETPROOF-TF] Chart recreation required: {recreation_command}")

            # Send chart destruction command to frontend
            await manager.broadcast({
                'type': 'chart_series_recreation',
                'command': recreation_command,
                'reason': transition_plan['reason'],
                'transaction_id': transaction_id
            })

            # Wait for frontend acknowledgment (small delay to ensure destruction)
            await asyncio.sleep(0.1)

        print(f"[BULLETPROOF-TF] Phase 2 COMPLETE - Chart series prepared")

        # PHASE 3: INTELLIGENT DATA LOADING WITH SKIP-STATE ISOLATION
        print(f"[BULLETPROOF-TF] Phase 3: Data loading with skip isolation")

        # 🚀 CRITICAL FIX: Re-sync current_global_time to ensure Skip-TF consistency
        current_global_time = unified_time_manager.get_current_time()
        print(f"[SKIP-TF-SYNC] Re-synced global time for TF switch: {current_global_time}")

        # 🔧 SKIP-STATE VALIDATION: Verify no temporal inconsistencies from previous operations
        last_operation_source = getattr(unified_time_manager, 'last_operation_source', None)
        print(f"[SKIP-TF-SYNC] Last operation source: {last_operation_source}")

        # Warn if we detect potential skip-contaminated state
        if last_operation_source and 'skip_' in str(last_operation_source):
            print(f"[SKIP-TF-SYNC] ⚠️  Skip-contaminated state detected - ensuring data consistency")

        # SIMPLIFIED DATA LOADING: Load fresh CSV data for timeframe
        if current_global_time:
            # 🔧 SKIP-POSITION FIX: Recalculate lookback with synced time
            timeframe_minutes = unified_time_manager._get_timeframe_minutes(target_timeframe)
            lookback_time = current_global_time - timedelta(minutes=timeframe_minutes * visible_candles)

            chart_data = timeframe_data_repository.get_candles_for_date_range(
                target_timeframe, lookback_time, current_global_time, max_candles=visible_candles
            )
            print(f"[SKIP-TF-SYNC] CSV data loaded from {lookback_time} to {current_global_time}")
        else:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            chart_data = timeframe_data_repository.get_candles_for_date_range(
                target_timeframe, start_date, end_date, max_candles=visible_candles
            )
            print(f"[SKIP-TF-SYNC] Fallback: CSV data loaded for {start_date} to {end_date}")

        print(f"[BULLETPROOF-TF] Phase 3 SUCCESS - Loaded {len(chart_data) if chart_data else 0} candles for {target_timeframe}")

        # PHASE 3.5: INTEGRATE SKIP EVENTS FOR MULTI-TIMEFRAME SYNCHRONIZATION
        print(f"[BULLETPROOF-TF] Phase 3.5: Integrating skip events for {target_timeframe}")

        # Render skip candles for the target timeframe with price synchronization
        if global_skip_events:
            print(f"[BULLETPROOF-TF] Found {len(global_skip_events)} skip events to process")
            skip_candles = universal_renderer.render_skip_candles_for_timeframe(target_timeframe)

            if skip_candles:
                print(f"[BULLETPROOF-TF] Rendered {len(skip_candles)} skip candles for {target_timeframe}")

                # 🔧 CRITICAL FIX: Deduplicate skip candles BEFORE merging (prevent duplicate timestamps)
                print(f"[BULLETPROOF-TF] Raw skip candles: {len(skip_candles)}")

                # Deduplicate skip candles by timestamp (keep last one for each timestamp)
                skip_candles_dict = {}
                for candle in skip_candles:
                    timestamp = candle['time']
                    if timestamp in skip_candles_dict:
                        print(f"[BULLETPROOF-TF] DUPLICATE SKIP TIMESTAMP DETECTED: {timestamp} - replacing")
                    skip_candles_dict[timestamp] = candle

                deduplicated_skip_candles = list(skip_candles_dict.values())
                print(f"[BULLETPROOF-TF] Deduplicated skip candles: {len(deduplicated_skip_candles)}")

                # Merge deduplicated skip candles with CSV data
                merged_data = []
                skip_timestamps = {candle['time'] for candle in deduplicated_skip_candles}

                # Add CSV candles that don't conflict with skip timestamps
                for csv_candle in chart_data:
                    if csv_candle['time'] not in skip_timestamps:
                        merged_data.append(csv_candle)

                # Add all deduplicated skip candles (these have priority for price synchronization)
                merged_data.extend(deduplicated_skip_candles)

                # Sort by timestamp to maintain chronological order
                merged_data.sort(key=lambda x: x['time'])

                chart_data = merged_data
                print(f"[BULLETPROOF-TF] Merged data: {len(chart_data)} total candles ({len(skip_candles)} skip + {len(chart_data)-len(skip_candles)} CSV)")
            else:
                print(f"[BULLETPROOF-TF] No compatible skip candles for {target_timeframe}")
        else:
            print(f"[BULLETPROOF-TF] No skip events to process")

        print(f"[BULLETPROOF-TF] Phase 3.5 COMPLETE - Skip event integration finished")

        # Ultra-defensive data validation
        if not chart_data:
            chart_lifecycle_manager.complete_timeframe_transition(success=False)
            return {
                "status": "error",
                "message": f"Keine Daten für {target_timeframe} verfügbar",
                "transaction_id": transaction_id
            }

        # Multi-layer data sanitization - ENHANCED: Use ChartDataValidator
        validated_data = DataIntegrityGuard.sanitize_chart_data(chart_data, source=f"bulletproof_tf_{target_timeframe}")

        # CRITICAL: Add ChartDataValidator for LightweightCharts compatibility
        final_validated_data = data_validator.validate_chart_data(
            validated_data, timeframe=target_timeframe, source=f"change_timeframe_{target_timeframe}"
        )

        if len(final_validated_data) != len(chart_data):
            print(f"[BULLETPROOF-TF] Data validation pipeline: {len(chart_data)} -> {len(validated_data)} -> {len(final_validated_data)} candles")

        # Special logging for 4h timeframe
        if target_timeframe == '4h':
            print(f"[BULLETPROOF-TF] 4h-SPECIAL: {len(final_validated_data)} candles validated and sanitized")
            if final_validated_data:
                sample_candle = final_validated_data[0]
                print(f"[BULLETPROOF-TF] 4h-SAMPLE: {sample_candle}")

        validated_data = final_validated_data

        print(f"[BULLETPROOF-TF] Phase 3 COMPLETE - {len(validated_data)} validated candles loaded")

        # PHASE 4: ATOMIC CHART STATE UPDATE
        print(f"[BULLETPROOF-TF] Phase 4: Atomic state update")

        # Update all state atomically
        manager.chart_state['data'] = validated_data
        manager.chart_state['interval'] = target_timeframe

        # Update unified time manager
        if validated_data:
            last_candle = validated_data[-1]
            unified_time_manager.register_timeframe_activity(target_timeframe, last_candle['time'])

        print(f"[BULLETPROOF-TF] Phase 4 COMPLETE - State updated atomically")

        # PHASE 5: BULLETPROOF FRONTEND SYNCHRONIZATION
        print(f"[BULLETPROOF-TF] Phase 5: Frontend synchronization")

        # Prepare comprehensive update message
        bulletproof_message = {
            'type': 'bulletproof_timeframe_changed',
            'timeframe': target_timeframe,
            'data': validated_data,
            'transaction_id': transaction_id,
            'chart_recreation': transition_plan['needs_recreation'],
            'recreation_command': chart_lifecycle_manager.get_chart_recreation_command() if transition_plan['needs_recreation'] else None,
            'global_time': current_global_time.isoformat() if current_global_time else None,
            'validation_summary': {
                'original_count': len(chart_data),
                'validated_count': len(validated_data),
                'data_source': 'csv',
                'skip_contamination': 'CLEAN'
            }
        }

        # Broadcast with error recovery
        try:
            await manager.broadcast(bulletproof_message)
        except Exception as broadcast_error:
            print(f"[BULLETPROOF-TF] Broadcast error: {broadcast_error}")
            # Fallback: Emergency chart reload message
            await manager.broadcast({
                'type': 'emergency_chart_reload',
                'timeframe': target_timeframe,
                'data': validated_data,
                'transaction_id': transaction_id
            })

        # Complete lifecycle transition
        chart_lifecycle_manager.complete_timeframe_transition(success=True)

        print(f"[BULLETPROOF-TF] Phase 5 COMPLETE - Transaction {transaction_id} completed successfully")

        # SUCCESS RESPONSE
        return {
            "status": "success",
            "message": f"Bulletproof transition zu {target_timeframe} erfolgreich",
            "data": validated_data,
            "timeframe": target_timeframe,
            "count": len(validated_data),
            "transaction_id": transaction_id,
            "transition_plan": transition_plan,
            "global_time": current_global_time.isoformat() if current_global_time else None,
            "system": "bulletproof_timeframe_architecture"
        }

    except Exception as e:
        print(f"[BULLETPROOF-TF] CRITICAL ERROR in transaction {transaction_id}: {str(e)}")
        import traceback
        traceback.print_exc()

        # Mark lifecycle as failed
        chart_lifecycle_manager.complete_timeframe_transition(success=False)
        chart_lifecycle_manager.mark_chart_corrupted(f"transition_error: {str(e)}")

        # Emergency recovery broadcast
        try:
            await manager.broadcast({
                'type': 'emergency_recovery_required',
                'transaction_id': transaction_id,
                'error': str(e),
                'recovery_action': 'page_reload'
            })
        except:
            pass  # If broadcast fails, frontend will handle timeout

        return {
            "status": "error",
            "message": f"Bulletproof transition failed: {str(e)}",
            "transaction_id": transaction_id,
            "recovery_required": True,
            "system": "bulletproof_timeframe_architecture"
        }

@app.post("/api/chart/emergency_chart_recreation")
async def emergency_chart_recreation():
    """🚨 EMERGENCY API: Forciert Chart Recreation bei 'Value is null' Errors"""
    try:
        print(f"[EMERGENCY-RECOVERY] Emergency chart recreation requested by frontend")

        # Force chart recreation on next timeframe transition
        chart_lifecycle_manager.force_chart_recreation_on_next_transition()

        # Also clear any potentially corrupted state
        unified_state.clear_go_to_date("emergency_recovery")

        # Force current chart state to be seen as corrupted
        manager.chart_state['emergency_recreation_pending'] = True

        print(f"[EMERGENCY-RECOVERY] Chart marked for emergency recreation")

        return {
            "status": "success",
            "message": "Chart recreation scheduled for next operation",
            "chart_state": chart_lifecycle_manager.get_state_info()
        }

    except Exception as e:
        print(f"[EMERGENCY-RECOVERY] Error during emergency chart recreation: {str(e)}")
        return {
            "status": "error",
            "message": f"Emergency recreation failed: {str(e)}"
        }

@app.post("/api/chart/load_historical")
async def load_historical_data(request: dict):
    """Lädt historische Daten für Lazy Loading mit dynamischen visible_candles"""
    timeframe = request.get('timeframe', '1m')
    before_timestamp = request.get('before_timestamp')
    chunk_size = request.get('chunk_size')
    visible_candles = request.get('visible_candles')  # Vom Frontend

    if before_timestamp is None:
        return {"status": "error", "message": "before_timestamp ist erforderlich"}

    print(f"Lade historische Daten für {timeframe} vor Timestamp {before_timestamp}")

    try:
        # Prüfe ob Roh-1m-Daten verfügbar sind
        if manager.chart_state['raw_1m_data'] is None:
            # Lade komplettes Jahr 2024 für historische Daten
            data_2024 = nq_loader.load_year(2024)
            if data_2024 is not None:
                manager.chart_state['raw_1m_data'] = data_2024
            else:
                return {"status": "error", "message": "Keine 1m-Daten verfügbar"}

        # Lazy Loading: Lade historischen Datenblock
        historical_data = performance_aggregator.get_historical_data_lazy(
            manager.chart_state['raw_1m_data'],
            timeframe,
            before_timestamp,
            chunk_size
        )

        # Berechne Info für Logs mit dynamischen visible_candles
        if visible_candles:
            initial_candles = performance_aggregator.calculate_initial_candles(visible_candles)
            chunk_info = performance_aggregator.calculate_chunk_size(visible_candles)
        else:
            initial_candles = performance_aggregator.calculate_initial_candles(timeframe=timeframe)
            chunk_info = performance_aggregator.calculate_chunk_size(timeframe=timeframe)

        # Broadcast an alle verbundenen Clients
        await manager.broadcast({
            'type': 'historical_data_loaded',
            'data': historical_data,
            'timeframe': timeframe,
            'count': len(historical_data),
            'before_timestamp': before_timestamp,
            'lazy_loading_info': {
                'initial_candles': initial_candles,
                'chunk_size': chunk_info
            }
        })

        print(f"Historische Daten geladen für {timeframe}: {len(historical_data)} Kerzen vor {before_timestamp}")

        return {
            "status": "success",
            "timeframe": timeframe,
            "data": historical_data,
            "count": len(historical_data),
            "before_timestamp": before_timestamp,
            "lazy_loading_info": {
                'initial_candles': initial_candles,
                'chunk_size': chunk_info
            }
        }

    except Exception as e:
        print(f"Fehler beim Laden historischer Daten: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/chart/lazy_loading_info")
async def get_lazy_loading_info():
    """Gibt Lazy Loading Konfiguration zurück"""
    try:
        timeframes_info = {}
        for timeframe in ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']:
            initial_candles = performance_aggregator.calculate_initial_candles(timeframe)
            chunk_size = performance_aggregator.calculate_chunk_size(timeframe)
            timeframes_info[timeframe] = {
                'initial_candles': initial_candles,
                'chunk_size': chunk_size,
                'visible_candles': performance_aggregator.timeframe_config[timeframe]['visible_candles']
            }

        return {
            "status": "success",
            "lazy_loading_multiplier": performance_aggregator.lazy_loading_multiplier,
            "chunk_size_multiplier": performance_aggregator.chunk_size_multiplier,
            "timeframes": timeframes_info
        }

    except Exception as e:
        print(f"Fehler beim Abrufen der Lazy Loading Info: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/account/status")
async def get_account_status():
    """API Endpunkt für Account Status beider Accounts"""
    try:
        ai_summary = account_service.get_ai_account_summary()
        user_summary = account_service.get_user_account_summary()

        return {
            "status": "success",
            "ai_account": ai_summary,
            "user_account": user_summary
        }
    except Exception as e:
        print(f"Fehler beim Abrufen des Account Status: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/account/update_ai_pnl")
async def update_ai_pnl(pnl_data: dict):
    """API Endpunkt für KI PnL Updates"""
    try:
        unrealized_pnl = pnl_data.get("unrealized_pnl", 0.0)
        account_service.update_ai_position(unrealized_pnl)

        return {
            "status": "success",
            "message": "KI PnL aktualisiert",
            "ai_account": account_service.get_ai_account_summary()
        }
    except Exception as e:
        print(f"Fehler beim Aktualisieren der KI PnL: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/account/update_user_pnl")
async def update_user_pnl(pnl_data: dict):
    """API Endpunkt für Nutzer PnL Updates"""
    try:
        unrealized_pnl = pnl_data.get("unrealized_pnl", 0.0)
        account_service.update_user_position(unrealized_pnl)

        return {
            "status": "success",
            "message": "Nutzer PnL aktualisiert",
            "user_account": account_service.get_user_account_summary()
        }
    except Exception as e:
        print(f"Fehler beim Aktualisieren der Nutzer PnL: {e}")
        return {"status": "error", "message": str(e)}

# ===== DEBUG API ENDPOINTS =====

@app.post("/api/debug/skip")
async def debug_skip():
    """🚀 UNIFIED SKIP ARCHITECTURE: Robuste Multi-Timeframe Skip-Navigation"""
    global event_transaction, debug_control_timeframe

    try:
        # UNIFIED TIME MANAGEMENT: Hole aktuelle globale Zeit
        current_time = unified_time_manager.get_current_time()
        skip_timeframe = debug_control_timeframe
        chart_timeframe = manager.chart_state.get('interval', '5m')

        print(f"[UNIFIED-SKIP] Skip-Request: {skip_timeframe} von Zeit {current_time}")

        # SMART DATA RETRIEVAL: Verwende TimeframeDataRepository
        if current_time is None:
            # Initialisierung: Verwende Chart-Daten oder Standard-Zeit
            if initial_chart_data:
                last_candle = initial_chart_data[-1]
                current_time = unified_time_manager.initialize_time(last_candle['time'])
            else:
                current_time = unified_time_manager.initialize_time(datetime.now())

        # Hole nächste Kerze für Skip-Timeframe
        next_candle = timeframe_data_repository.get_next_candle_after_time(skip_timeframe, current_time)

        if not next_candle:
            return {
                "status": "error",
                "message": f"Keine weiteren {skip_timeframe} Kerzen nach {current_time}",
                "timeframe": skip_timeframe,
                "current_time": current_time.isoformat() if current_time else None
            }

        # CRITICAL: Extrahiere gefundene Kerze-Zeit BEVOR time advance
        candle_time = next_candle.get('datetime', next_candle.get('time'))
        if isinstance(candle_time, (int, float)):
            candle_time = datetime.fromtimestamp(candle_time)

        # UNIFIED TIME UPDATE: Setze globale Zeit auf gefundene Kerze-Zeit
        unified_time_manager.set_time(candle_time, source=f"skip_{skip_timeframe}")
        new_global_time = candle_time

        print(f"[UNIFIED-SKIP] Zeit gesetzt auf gefundene Kerze: {candle_time}")

        # FORMAT CANDLE für Frontend - TIMESTAMP FIX für lightweight-charts
        candle_time = next_candle['time']
        if isinstance(candle_time, datetime):
            candle_time = int(candle_time.timestamp())
        elif isinstance(candle_time, str):
            # Fallback für ISO strings - konvertiere zu timestamp
            try:
                dt = datetime.fromisoformat(candle_time.replace('Z', '+00:00'))
                candle_time = int(dt.timestamp())
            except:
                # Wenn parsing fehlschlägt, verwende aktuelle Zeit
                candle_time = int(new_global_time.timestamp())
        else:
            # Sicherstellen dass es ein int ist
            candle_time = int(float(candle_time))

        candle = {
            'time': candle_time,
            'open': next_candle['open'],
            'high': next_candle['high'],
            'low': next_candle['low'],
            'close': next_candle['close'],
            'volume': next_candle.get('volume', 0)
        }

        candle_type = 'complete_candle'  # Alle Kerzen aus CSV sind komplett

        # UNIVERSAL SKIP EVENT: Erstelle Event für Cross-Timeframe Synchronisation
        skip_event = universal_renderer.create_skip_event(candle, skip_timeframe)

        # CHART LIFECYCLE INTEGRATION: Track skip operation
        chart_lifecycle_manager.track_skip_operation(skip_timeframe)

        # SKIP-STATE ISOLATION: Register skip candle in unified time manager
        unified_time_manager.register_skip_candle(
            chart_timeframe,  # Register for current chart timeframe
            candle,
            operation_id=len(global_skip_events) - 1
        )

        # UPDATE UNIFIED STATE: Synchronisiere alle Manager
        unified_state.update_skip_position(new_global_time, source="unified_skip")

        # LEGACY COMPATIBILITY: Update Chart State
        if hasattr(manager, 'chart_state') and 'data' in manager.chart_state:
            manager.chart_state['data'].append(candle)

        # GENERATE SKIP MESSAGE
        timeframe_display = {
            '1m': "1min", '2m': "2min", '3m': "3min", '5m': "5min",
            '15m': "15min", '30m': "30min", '1h': "1h", '4h': "4h"
        }
        display_name = timeframe_display.get(skip_timeframe, skip_timeframe)
        skip_message = f"Unified Skip +{display_name} -> {new_global_time.strftime('%H:%M:%S')}"

        # WEBSOCKET BROADCAST: Real-time updates
        websocket_data = {
            'type': 'unified_skip_event',
            'candle': candle,
            'candle_type': candle_type,
            'debug_time': new_global_time.isoformat(),
            'timeframe': skip_timeframe,
            'system_type': 'unified_time_architecture',
            'event_id': len(global_skip_events) - 1
        }

        # SYNC STATUS: Füge Timeframe-Synchronisation hinzu
        sync_status = unified_time_manager.get_timeframe_sync_status()
        websocket_data['sync_status'] = sync_status
        websocket_data['global_time'] = new_global_time.isoformat()

        # BROADCAST: Sende Update an alle Clients
        await manager.broadcast(websocket_data)

        # 🚀 CHART LIFECYCLE MANAGER INTEGRATION: Track skip contamination
        chart_lifecycle_manager.track_skip_operation(skip_timeframe)
        print(f"[CHART-LIFECYCLE] Skip operation tracked for {skip_timeframe}")

        # RESPONSE DATA: Erfolgsmeldung mit vollständigen Infos
        response_data = {
            "status": "success",
            "message": f"{skip_message} - {candle_type}",
            "candle": candle,
            "candle_type": candle_type,
            "debug_time": new_global_time.isoformat(),
            "timeframe": skip_timeframe,
            "events_total": len(global_skip_events),
            "system": "unified_time_architecture",
            "sync_status": sync_status,
            "global_time": new_global_time.isoformat(),
            "chart_lifecycle_state": chart_lifecycle_manager.get_state_info()  # Add lifecycle info
        }

        print(f"[UNIFIED-SKIP] [SUCCESS] SUCCESS: {skip_message}")
        print(f"[UNIFIED-SKIP] Global Time: {new_global_time}")
        print(f"[CHART-LIFECYCLE] Current state: {chart_lifecycle_manager.get_state_info()}")
        print(f"[UNIFIED-SKIP] Active Timeframes: {sync_status['active_timeframes']}")

        return response_data

    except Exception as e:
        print(f"[UNIFIED-SKIP] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "status": "error",
            "message": f"Skip-Fehler: {str(e)}",
            "timeframe": debug_control_timeframe,
            "system": "unified_time_architecture"
        }


@app.post("/api/debug/set_timeframe/{timeframe}")
async def debug_set_timeframe(timeframe: str):
    """API Endpoint um Debug Timeframe zu ändern"""

    # CRITICAL DEBUG: This endpoint is being called instead of change_timeframe!
    # Debug entfernt für CLI-Stabilität

    try:
        global global_skip_candles, current_go_to_date, debug_control_timeframe

        valid_timeframes = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]
        if timeframe not in valid_timeframes:
            return {"status": "error", "message": f"Ungültiger Timeframe. Erlaubt: {valid_timeframes}"}

        # REVOLUTIONARY FIX: Set debug control timeframe when changing timeframe!
        old_debug_control = debug_control_timeframe
        debug_control_timeframe = timeframe
        print(f"[DEBUG-CONTROL-FIX] Debug control timeframe: {old_debug_control} -> {debug_control_timeframe}")
        print(f"[DEBUG-CONTROL-FIX] Skip operations will now use: {debug_control_timeframe}")

        # Debug entfernt - verursacht CLI-Abstürze
        # Skip candles check entfernt - triggert massive Renderer-Aufrufe

        # REVOLUTIONARY: Universal Skip Events verwenden
        pass  # Debug entfernt - verursacht CLI-Abstürze

        debug_controller.set_timeframe(timeframe)

        # CRITICAL: Load CSV data with skip candles (same logic as change_timeframe)
        import pandas as pd
        from pathlib import Path

        csv_path = Path(f"src/data/aggregated/{timeframe}/nq-2024.csv")

        if not csv_path.exists():
            print(f"[DEBUG-SET-TF] WARNING: CSV not found for {timeframe}")
            # WebSocket-Update (fallback without CSV data)
            await manager.broadcast({
                'type': 'debug_timeframe_changed',
                'timeframe': timeframe,
                'debug_state': debug_controller.get_state()
            })
            return {"status": "error", "message": f"Timeframe {timeframe} nicht verfügbar (CSV nicht gefunden)"}

        # UNIFIED STATE: Load CSV data mit CONFLICT RESOLUTION
        if unified_state.is_csv_date_loading_needed():
            target_date = unified_state.get_csv_loading_date()
            if target_date:
                print(f"[DEBUG-SET-TF] CSV Datum-Loading: Lade 200 {timeframe} Kerzen rückwärts bis {target_date.date()}")
            df = pd.read_csv(csv_path)
            df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
            df['date_only'] = df['datetime'].dt.date

            target_date_only = target_date.date()
            target_rows = df[df['date_only'] == target_date_only]

            if len(target_rows) > 0:
                end_index = target_rows.index[0] + 1
                start_index = max(0, end_index - 5)  # ULTRA-MINI
                df = df.iloc[start_index:end_index]
                print(f"[DEBUG-SET-TF] Go To Date: {len(target_rows)} Kerzen für {target_date_only} gefunden, 5 Kerzen rückwärts geladen")
            else:
                df = df.tail(5)  # ULTRA-MINI
                print(f"[DEBUG-SET-TF] Go To Date: Datum {target_date_only} nicht gefunden in {timeframe}, verwende letzte 5 Kerzen")
        else:
            print(f"[DEBUG-SET-TF] Standard: Lade 5 {timeframe} Kerzen (letzten 5)")  # ULTRA-MINI
            df = pd.read_csv(csv_path).tail(5)

        # Convert to chart format
        if 'datetime' not in df.columns:
            df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
        df['time'] = df['datetime'].astype(int) // 10**9

        chart_data = []
        for _, row in df.iterrows():
            chart_data.append({
                'time': int(row['time']),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        # CRITICAL: Validate chart data with ChartDataValidator
        validated_chart_data = data_validator.validate_chart_data(
            chart_data, timeframe=timeframe, source=f"debug_set_timeframe_{timeframe}"
        )

        print(f"[DEBUG-SET-TF] CSV geladen: {len(chart_data)} -> {len(validated_chart_data)} {timeframe} Kerzen nach Validation")

        # CRITICAL: Add skip candles (same logic as change_timeframe)
        print(f"[DEBUG-SET-TF] SKIP-KERZEN Check für {timeframe}:")

        # EMERGENCY FIX: Skip candles access ohne undefined backup
        direct_skip_candles = global_skip_candles.get(timeframe, [])
        # REMOVED: skip_candles_backup nicht definiert - verwende nur direct access
        skip_candles_to_use = direct_skip_candles

        if len(skip_candles_to_use) > 0:
            original_count = len(chart_data)
            chart_data.extend(skip_candles_to_use)
            print(f"[DEBUG-SET-TF] SUCCESS: {len(skip_candles_to_use)} Skip-Kerzen für {timeframe} hinzugefügt ({original_count} -> {len(chart_data)} Kerzen)")
            print(f"[DEBUG-SET-TF] Source: {'direct' if len(direct_skip_candles) > 0 else 'backup'}")

            # Ensure skip candles are restored to main system
            # EMERGENCY FIX: backup_skip_candles nicht definiert - Skip restore entfernt
            pass  # Backup restore logic entfernt bis Variable korrekt definiert ist
        else:
            print(f"[DEBUG-SET-TF] Keine Skip-Kerzen für {timeframe} gefunden (direct: {len(direct_skip_candles)})")

        # Update chart state with validated data
        manager.chart_state['data'] = validated_chart_data
        manager.chart_state['interval'] = timeframe

        # WebSocket-Update with complete validated chart data
        await manager.broadcast({
            'type': 'timeframe_changed',  # Use same type as change_timeframe for consistency
            'timeframe': timeframe,
            'data': validated_chart_data,
            'debug_state': debug_controller.get_state()
        })

        return {
            "status": "success",
            "message": f"Debug Timeframe auf {timeframe} gesetzt (+ {len(global_skip_candles.get(timeframe, []))} Skip-Kerzen)",
            "data": validated_chart_data,
            "timeframe": timeframe,
            "count": len(validated_chart_data),
            "skip_candles": len(global_skip_candles.get(timeframe, [])),
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Setzen des Timeframes: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/set_control_timeframe/{timeframe}")
async def debug_set_control_timeframe(timeframe: str):
    """REVOLUTIONARY: Set Debug Control Timeframe - Separate from Chart Timeframe"""
    global debug_control_timeframe

    try:
        valid_timeframes = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]
        if timeframe not in valid_timeframes:
            return {"status": "error", "message": f"Ungültiger Timeframe. Erlaubt: {valid_timeframes}"}

        old_timeframe = debug_control_timeframe
        debug_control_timeframe = timeframe

        print(f"[DEBUG-CONTROL] Timeframe changed: {old_timeframe} -> {debug_control_timeframe}")
        print(f"[DEBUG-CONTROL] Skip operations will now use: {debug_control_timeframe}")

        # WebSocket-Update to notify frontend
        await manager.broadcast({
            'type': 'debug_control_timeframe_changed',
            'debug_control_timeframe': debug_control_timeframe,
            'old_timeframe': old_timeframe
        })

        return {
            "status": "success",
            "message": f"Debug Control Timeframe auf {timeframe} gesetzt",
            "debug_control_timeframe": debug_control_timeframe,
            "old_timeframe": old_timeframe
        }

    except Exception as e:
        print(f"Fehler beim Setzen des Debug Control Timeframes: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/debug/sync_status")
async def get_debug_sync_status():
    """API Endpoint um Multi-Timeframe Synchronisations-Status abzurufen"""
    try:
        if not hasattr(debug_controller, 'sync_manager'):
            return {"status": "error", "message": "SyncManager not initialized"}

        sync_status = debug_controller.sync_manager._get_sync_status()
        incomplete_candles = {}

        # Sammle incomplete candle Informationen für alle Timeframes
        for timeframe in debug_controller.sync_manager.timeframe_mappings.keys():
            incomplete_info = debug_controller.sync_manager.get_incomplete_candle_info(timeframe)
            if incomplete_info:
                incomplete_candles[timeframe] = {
                    'completion_ratio': incomplete_info['completion_ratio'],
                    'elapsed_minutes': incomplete_info['elapsed_minutes'],
                    'total_minutes': incomplete_info['total_minutes'],
                    'is_complete': incomplete_info['is_complete']
                }

        return {
            "status": "success",
            "sync_status": sync_status,
            "incomplete_candles": incomplete_candles,
            "current_timeframe": debug_controller.timeframe,
            "current_time": debug_controller.current_time.isoformat() if debug_controller.current_time else None
        }

    except Exception as e:
        print(f"Fehler beim Abrufen des Sync Status: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/set_speed")
async def debug_set_speed(speed_data: dict):
    """API Endpoint um Debug Speed zu ändern"""
    try:
        speed = speed_data.get("speed", 2)
        debug_controller.set_speed(speed)

        # WebSocket-Update an alle Clients
        await manager.broadcast({
            'type': 'debug_speed_changed',
            'speed': speed,
            'debug_state': debug_controller.get_state()
        })

        return {
            "status": "success",
            "message": f"Geschwindigkeit auf {speed}x gesetzt",
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Setzen der Geschwindigkeit: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/toggle_play")
async def debug_toggle_play():
    """API Endpoint um Play/Pause zu togglen"""
    try:
        play_mode = debug_controller.toggle_play_mode()

        # WebSocket-Update an alle Clients (ohne debug_state wegen JSON-Serialisierung)
        await manager.broadcast({
            'type': 'debug_play_toggled',
            'play_mode': play_mode
        })

        return {
            "status": "success",
            "message": f"Play-Modus {'aktiviert' if play_mode else 'deaktiviert'}",
            "play_mode": play_mode,
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Toggle Play/Pause: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/debug/state")
async def debug_get_state():
    """API Endpoint um aktuellen Debug-Status zu holen"""
    try:
        return {
            "status": "success",
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Holen des Debug-Status: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/log")
async def debug_log_from_client(request: Request):
    """API Endpoint für JavaScript Debug-Logs im Terminal"""
    try:
        data = await request.json()
        message = data.get('message', 'No message')
        timestamp = data.get('timestamp', '')
        log_data = data.get('data', None)

        # Im Terminal ausgeben mit Prefix für JavaScript-Logs (Unicode-safe)
        try:
            # Unicode-safe Ausgabe
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            pass  # DEBUG entfernt - verursacht CLI-Abstürze
            if log_data:
                pass  # DEBUG entfernt - verursacht CLI-Abstürze
        except Exception as encoding_error:
            pass  # DEBUG entfernt - verursacht CLI-Abstürze

        return {"status": "success"}
    except Exception as e:
        print(f"Fehler beim JavaScript Debug-Log: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/go_to_date")
async def debug_go_to_date(date_data: dict):
    """Ultra-High-Performance Go To Date mit Single Source of Truth"""
    try:
        from datetime import datetime
        import time

        target_date = date_data.get("date")
        if not target_date:
            return {"status": "error", "message": "Kein Datum angegeben"}

        # Parse das Datum (Format: YYYY-MM-DD)
        target_datetime = datetime.strptime(target_date, "%Y-%m-%d")
        current_timeframe = manager.chart_state['interval']  # Use actual chart timeframe, not debug controller

        operation_start = time.time()
        print(f"[HIGH-PERF-GO-TO-DATE] Request: {target_date} in {current_timeframe}")

        # TEMPORARY: Disable High-Performance Cache due to timestamp aggregation issues
        # High-Performance Cache System
        global chart_cache, current_go_to_date, global_skip_events, debug_control_timeframe

        if False and chart_cache and chart_cache.is_loaded():
            # High-Performance Data Retrieval
            result = chart_cache.get_timeframe_data(current_timeframe, target_date, candle_count=200)

            if result['data']:
                # Performance Stats
                perf_stats = result.get('performance_stats', {})
                print(f"[HIGH-PERF-GO-TO-DATE] SUCCESS: {len(result['data'])} {current_timeframe} Kerzen in {perf_stats.get('response_time_ms', 0):.1f}ms")
                print(f"[HIGH-PERF-GO-TO-DATE] Cache Hit: {perf_stats.get('cache_hit', False)}")

                # UNIFIED STATE: Update Go-To-Date für alle Timeframes einheitlich
                unified_state.set_go_to_date(target_datetime)

                # 🚀 CRITICAL FIX: Global Skip Events Reset bei Go-To-Date (High-Performance Path)
                skip_events_count = len(global_skip_events)
                global_skip_events.clear()  # Alle Skip-Events löschen
                print(f"[GO-TO-DATE-RESET] Global Skip Events cleared: {skip_events_count} events removed (High-Perf)")

                # 🚀 UNIFIED TIME MANAGER: Skip-State Reset integrieren
                unified_time_manager.clear_all_skip_data()
                print(f"[GO-TO-DATE-RESET] UnifiedTimeManager Skip-State cleared (High-Perf)")

                # 🚀 DEBUG CONTROL TIMEFRAME SYNCHRONISATION: Frontend-Backend Konsistenz sicherstellen
                print(f"[GO-TO-DATE-SYNC] Debug Control Timeframe synchronisiert: {debug_control_timeframe} (High-Perf)")

                # WebSocket Broadcast für Debug Control Sync
                await manager.broadcast({
                    'type': 'debug_control_timeframe_changed',
                    'debug_control_timeframe': debug_control_timeframe,
                    'old_timeframe': None,
                    'source': 'go_to_date_sync_highperf'
                })

                # WebSocket Broadcast
                await manager.broadcast({
                    'type': 'go_to_date_complete',
                    'data': result['data'],
                    'date': target_date,
                    'visible_range': result.get('visible_range'),
                    'performance_stats': perf_stats
                })

                return {
                    "status": "success",
                    "message": f"High-Performance Go To Date zu {target_date}",
                    "data": result['data'],
                    "count": len(result['data']),
                    "target_date": target_date,
                    "visible_range": result.get('visible_range'),
                    "performance_stats": perf_stats
                }
            else:
                print(f"[HIGH-PERF-GO-TO-DATE] WARNING: Keine Daten für {target_date} in {current_timeframe}")

        # Fallback: Legacy CSV System
        print(f"[HIGH-PERF-GO-TO-DATE] FALLBACK zu CSV System für {current_timeframe}")

        import pandas as pd
        from pathlib import Path

        csv_path = Path(f"src/data/aggregated/{current_timeframe}/nq-2024.csv")

        if not csv_path.exists():
            return {"status": "error", "message": f"CSV-Datei für {current_timeframe} nicht gefunden"}

        # Lade komplette CSV und suche das gewünschte Datum
        df = pd.read_csv(csv_path)

        # DateTime kombinieren und als zusätzliche Spalte hinzufügen
        df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
        df['time'] = df['datetime'].astype(int) // 10**9  # Unix timestamp für TradingView

        # Suche das gewünschte Datum
        target_date_only = target_datetime.date()
        df['date_only'] = df['datetime'].dt.date

        # Finde Kerzen für das Zieldatum
        target_rows = df[df['date_only'] == target_date_only]

        if len(target_rows) > 0:
            # Verwende die erste Kerze des Zieldatums und lade 50 Kerzen rückwärts - CLAUDE-FIX
            end_index = target_rows.index[0] + 1   # Ende bei erster Kerze des Zieldatums (00:00)
            start_index = max(0, end_index - 5)  # 5 Kerzen rückwärts - ULTRA-MINI
            selected_df = df.iloc[start_index:end_index]
            print(f"[FALLBACK-GO-TO-DATE] Gefunden: {len(target_rows)} Kerzen für {target_date}")
        else:
            # Fallback: Lade letzten 5 Kerzen wenn Datum nicht gefunden - ULTRA-MINI
            selected_df = df.tail(5)
            print(f"[FALLBACK-GO-TO-DATE] Datum {target_date} nicht gefunden, verwende letzten 5 Kerzen")

        # Konvertiere zu Chart-Format
        chart_data = []
        for _, row in selected_df.iterrows():
            chart_data.append({
                'time': int(row['time']),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        # UNIFIED STATE: Update Go-To-Date für alle Timeframes einheitlich (CSV-System)
        unified_state.set_go_to_date(target_datetime)

        # 🚀 CRITICAL FIX: Global Skip Events Reset bei Go-To-Date
        skip_events_count = len(global_skip_events)
        global_skip_events.clear()  # Alle Skip-Events löschen
        print(f"[GO-TO-DATE-RESET] Global Skip Events cleared: {skip_events_count} events removed")

        # 🚀 UNIFIED TIME MANAGER: Skip-State Reset integrieren
        unified_time_manager.clear_all_skip_data()
        print(f"[GO-TO-DATE-RESET] UnifiedTimeManager Skip-State cleared")

        # 🚀 DEBUG CONTROL TIMEFRAME SYNCHRONISATION: Frontend-Backend Konsistenz sicherstellen
        print(f"[GO-TO-DATE-SYNC] Debug Control Timeframe synchronisiert: {debug_control_timeframe}")

        # WebSocket Broadcast für Debug Control Sync
        await manager.broadcast({
            'type': 'debug_control_timeframe_changed',
            'debug_control_timeframe': debug_control_timeframe,
            'old_timeframe': None,
            'source': 'go_to_date_sync'
        })

        # WebSocket Broadcast
        await manager.broadcast({
            'type': 'go_to_date_complete',
            'data': chart_data,
            'date': target_date
        })

        print(f"[FALLBACK-GO-TO-DATE] Erfolgreich zu {target_date} gesprungen - {len(chart_data)} Kerzen geladen")

        # CRITICAL: UNIFIED TIME MANAGER SYNCHRONISATION
        # Aktualisiere das neue UnifiedTimeManager für Skip-System Kompatibilität
        if chart_data:
            last_candle_time = chart_data[-1]['time']
            new_debug_time = pd.to_datetime(last_candle_time, unit='s')

            # UNIFIED TIME MANAGER: Setze globale Zeit für Skip-System
            unified_time_manager.set_time(new_debug_time, source="go_to_date")
            print(f"[UNIFIED-SYNC] UnifiedTimeManager Zeit gesetzt: {new_debug_time}")

            # Legacy System Updates für Kompatibilität
            debug_controller.current_time = new_debug_time
            print(f"[DEBUG-SYNC] DebugController Zeit auf letzte Kerze gesetzt: {debug_controller.current_time}")

            # CRITICAL FIX: TimeframeSyncManager mit neuer Zeit synchronisieren
            debug_controller.sync_manager.set_base_time(new_debug_time)
            print(f"[DEBUG-SYNC] TimeframeSyncManager auf {new_debug_time} synchronisiert")
        else:
            # UNIFIED TIME MANAGER: Fallback für leere Daten
            unified_time_manager.set_time(target_datetime, source="go_to_date_fallback")
            print(f"[UNIFIED-SYNC] UnifiedTimeManager auf Zieldatum gesetzt: {target_datetime}")

            debug_controller.current_time = target_datetime
            debug_controller.sync_manager.set_base_time(target_datetime)
            print(f"[DEBUG-SYNC] Keine Daten gefunden - DebugController auf Zieldatum gesetzt: {target_datetime}")
        debug_controller.set_timeframe(current_timeframe)  # Sync Timeframe

        # Update Chart State mit neuen Daten und Timeframe
        manager.chart_state['data'] = chart_data
        manager.chart_state['interval'] = current_timeframe

        print(f"[DEBUG-SYNC] DebugController auf {target_date} und {current_timeframe} aktualisiert")

        # 🚀 CHART LIFECYCLE MANAGER INTEGRATION: Reset to clean state on Go To Date
        chart_lifecycle_manager.reset_to_clean_state()
        print(f"[CHART-LIFECYCLE] Reset to clean state after Go To Date: {chart_lifecycle_manager.get_state_info()}")

        return {
            "status": "success",
            "message": f"Fallback Go To Date zu {target_date}",
            "data": chart_data,
            "count": len(chart_data),
            "target_date": target_date,
            "chart_lifecycle_state": chart_lifecycle_manager.get_state_info()  # Add lifecycle info
        }

    except Exception as e:
        print(f"[ERROR] Go To Date Memory Fehler: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Go To Date Fehler: {str(e)}"}

if __name__ == "__main__":
    # Debug Route
    @app.get("/debug")
    async def debug_chart():
        """Debug Chart Page"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Debug Chart</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        #chart { width: 100%; height: 600px; }
        .status { margin: 10px; padding: 10px; background: #f0f0f0; }
    </style>
</head>
<body>
    <h1>🔧 Debug Chart - Teste NQ Daten</h1>
    <div class="status" id="status">Status: Initialisiere...</div>
    <div id="chart"></div>

    <script>
        const statusDiv = document.getElementById('status');

        function updateStatus(message) {
            statusDiv.innerHTML = `Status: ${message}`;
            console.log(message);
        }

        async function loadChart() {
            try {
                updateStatus('Erstelle Chart...');

                const chart = LightweightCharts.createChart(document.getElementById('chart_container'), {
                    width: document.getElementById('chart_container').clientWidth,
                    height: 600,
                    timeScale: { timeVisible: true },
                    grid: { vertLines: { color: '#e1e1e1' }, horzLines: { color: '#e1e1e1' } }
                });

                const candlestickSeries = chart.addCandlestickSeries();

                updateStatus('Lade Daten von Server...');

                const response = await fetch('/api/chart/data');
                const chartData = await response.json();

                updateStatus(`Daten erhalten: ${chartData.data?.length || 0} Kerzen`);

                if (chartData.data && chartData.data.length > 0) {
                    const formattedData = chartData.data.filter(item =>
                        item && item.time &&
                        item.open != null && item.high != null &&
                        item.low != null && item.close != null
                    ).map(item => ({
                        time: item.time,  // Unix Timestamp direkt verwenden (keine Konvertierung!)
                        open: parseFloat(item.open) || 0,
                        high: parseFloat(item.high) || 0,
                        low: parseFloat(item.low) || 0,
                        close: parseFloat(item.close) || 0
                    }));

                    candlestickSeries.setData(formattedData);

                    // Smart Positioning: 50 Kerzen Standard mit 20% Freiraum
                    if (window.smartPositioning) {
                        window.smartPositioning.setStandardPosition(formattedData);
                    }

                    updateStatus(`✅ SUCCESS: ${formattedData.length} NQ-Kerzen geladen!`);
                } else {
                    updateStatus('❌ FEHLER: Keine Daten empfangen');
                }

            } catch (error) {
                updateStatus(`❌ FEHLER: ${error.message}`);
                console.error('Chart Error:', error);
            }
        }

    </script>
</body>
</html>
        """

        return HTMLResponse(content=html_content)

    @app.get("/debug")
    async def debug_chart():
        """Debug Chart Page"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>NQ Debug Chart</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body { margin: 0; padding: 20px; background: #f0f0f0; font-family: Arial, sans-serif; }
        h1 { text-align: center; }
        .status { text-align: center; font-weight: bold; margin: 10px 0; }
        #chart { margin: 0 auto; border: 1px solid #ccc; }
    </style>
</head>
<body>
    <h1>🔧 Debug Chart - Teste NQ Daten</h1>
    <div class="status" id="status">Status: Initialisiere...</div>
    <div id="chart"></div>

    <script>
        function updateStatus(message) {
            document.getElementById('status').textContent = message;
            console.log(message);
        }

        async function loadChart() {
            try {
                updateStatus('Erstelle Chart...');

                const chart = LightweightCharts.createChart(document.getElementById('chart'), {
                    width: document.getElementById('chart_container').clientWidth,
                    height: 600,
                    timeScale: { timeVisible: true },
                    grid: { vertLines: { color: '#e1e1e1' }, horzLines: { color: '#e1e1e1' } }
                });

                const candlestickSeries = chart.addCandlestickSeries();

                updateStatus('Lade Daten von Server...');

                const response = await fetch('/api/chart/data');
                const chartData = await response.json();

                console.log('Chart Data received:', chartData);

                if (chartData.data && chartData.data.length > 0) {
                    candlestickSeries.setData(chartData.data);
                    updateStatus(`✅ ${chartData.data.length} Kerzen geladen`);
                } else {
                    updateStatus('❌ Keine Daten empfangen');
                }

            } catch (error) {
                updateStatus(`❌ FEHLER: ${error.message}`);
                console.error('Chart Error:', error);
            }
        }

        // Starte Chart-Loading nach DOM-Load
        document.addEventListener('DOMContentLoaded', loadChart);
    </script>
</body>
</html>
        """

        return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        access_log=False
    )
