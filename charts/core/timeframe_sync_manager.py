"""
Timeframe Sync Manager
Synchronisiert mehrere Timeframes für parallele Navigation
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta


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
