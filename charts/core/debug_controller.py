"""
Debug Controller für Debug-Funktionalität
Verwaltet Debug-Modus mit intelligenter Timeframe-Aggregation
"""

from datetime import datetime, timedelta


class DebugController:
    """Verwaltet Debug-Funktionalität mit intelligenter Timeframe-Aggregation"""

    def __init__(self, unified_time_manager=None, csv_loader=None, initial_chart_data=None, unified_state=None):
        # INTEGRATION: Verwende UnifiedTimeManager für Zeit-Koordination
        self.unified_time = unified_time_manager  # Reference zum globalen Time Manager
        self.current_time = None  # Legacy compatibility - wird von unified_time_manager synchronisiert
        self.timeframe = "5m"
        self.play_mode = False
        self.speed = 2  # Linear 1-15

        # CSVLoader für Multi-Timeframe Support
        self.csv_loader = csv_loader

        # TimeframeSyncManager für synchronisierte Multi-TF Navigation
        from .timeframe_sync_manager import TimeframeSyncManager
        if self.csv_loader:
            self.sync_manager = TimeframeSyncManager(self.csv_loader)
        else:
            self.sync_manager = None

        # TimeframeAggregator für intelligente Kerzen-Logik (Legacy, wird durch SyncManager ersetzt)
        from .timeframe_aggregator import TimeframeAggregator
        self.aggregator = TimeframeAggregator()

        # Unified State Reference
        self.unified_state = unified_state

        # Store initial_chart_data als Attribut für skip_minute() Zugriff
        self.initial_chart_data = initial_chart_data

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
            if hasattr(self, 'initial_chart_data') and self.initial_chart_data:
                last_candle = self.initial_chart_data[-1]
                self.current_time = datetime.fromtimestamp(last_candle['time'])
            else:
                self.current_time = datetime.now()

        # +1 Minute
        self.current_time += timedelta(minutes=1)

        print(f"DEBUG SKIP: Neue Zeit: {self.current_time} (Timeframe: {self.timeframe})")

        # Verwende TimeframeAggregator für intelligente Kerzen-Logik
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
        if self.unified_time:
            self.unified_time.set_time(start_datetime, source="goto_date")
            # Legacy Compatibility
            self.current_time = self.unified_time.get_current_time()
            print(f"[UNIFIED-GOTO] Start-Zeit gesetzt auf {self.current_time}")
        else:
            self.current_time = start_datetime
            print(f"[DEBUG] Start-Zeit gesetzt auf {self.current_time}")

    def skip_minutes(self, minutes):
        """Skip +X Minuten für verschiedene Timeframes (2m, 3m, 5m, 15m, 30m)"""
        if not self.current_time:
            # Fallback: Verwende aktuellste Zeit aus Chart-Daten
            if hasattr(self, 'initial_chart_data') and self.initial_chart_data:
                last_candle = self.initial_chart_data[-1]
                self.current_time = datetime.fromtimestamp(last_candle['time'])
            else:
                self.current_time = datetime.now()

        # +X Minuten
        self.current_time += timedelta(minutes=minutes)

        print(f"DEBUG SKIP {minutes}m: Neue Zeit: {self.current_time} (Timeframe: {self.timeframe})")

        # Verwende TimeframeAggregator für intelligente Kerzen-Logik
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
            if hasattr(self, 'initial_chart_data') and self.initial_chart_data:
                last_candle = self.initial_chart_data[-1]
                self.current_time = datetime.fromtimestamp(last_candle['time'])
            else:
                self.current_time = datetime.now()

        # +X Stunden
        self.current_time += timedelta(hours=hours)

        print(f"DEBUG SKIP {hours}h: Neue Zeit: {self.current_time} (Timeframe: {self.timeframe})")

        # Verwende TimeframeAggregator für intelligente Kerzen-Logik
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
        if self.unified_time and not self.unified_time.initialized:
            # Fallback: Initialisiere mit letzter Chart-Kerze
            if hasattr(self, 'initial_chart_data') and self.initial_chart_data:
                last_candle = self.initial_chart_data[-1]
                self.unified_time.initialize_time(last_candle['time'])
            else:
                self.unified_time.initialize_time(datetime.now())

        if self.unified_time:
            current_time = self.unified_time.get_current_time()
        else:
            current_time = self.current_time or datetime.now()

        print(f"[UNIFIED-SKIP] Starting synchronized skip for {timeframe} from {current_time}")

        if not self.sync_manager:
            print("[UNIFIED-SKIP] ERROR: No sync_manager available")
            return None

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
            if self.unified_time:
                timeframe_minutes = self.unified_time._get_timeframe_minutes(timeframe)
                new_time = self.unified_time.advance_time(timeframe_minutes, timeframe)
                # Legacy Compatibility: Synchronisiere local time
                self.current_time = new_time
            else:
                self.current_time = primary_result.get('datetime', current_time)

            # CRITICAL: Update UnifiedStateManager - Löst CSV vs DebugController Konflikt
            if self.unified_state:
                self.unified_state.update_skip_position(self.current_time, source="skip")

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

            print(f"[SKIP-SYNC] SUCCESS {timeframe}: {primary_result.get('datetime', 'N/A')} -> Close: {candle['close']} ({candle_type})")

            return {
                'type': candle_type,
                'candle': candle,  # Use validated candle
                'timeframe': timeframe,
                'source': primary_result.get('source', 'csv'),
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
