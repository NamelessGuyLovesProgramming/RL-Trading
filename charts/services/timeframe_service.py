"""
Timeframe Service - Business Logic für Timeframe-Switching
Koordiniert Timeframe-Wechsel, Aggregation und Synchronisation
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


class TimeframeService:
    """
    Service für Timeframe-bezogene Operationen
    Verwaltet Timeframe-Wechsel mit Chart Recreation und Skip-Integration
    """

    def __init__(self,
                 timeframe_repo,  # TimeframeDataRepository
                 sync_manager,  # TimeframeSyncManager
                 aggregator,  # TimeframeAggregator
                 series_lifecycle,  # ChartSeriesLifecycleManager
                 unified_time_manager,  # UnifiedTimeManager
                 validator):  # ChartDataValidator
        """
        Initialisiert TimeframeService mit Dependencies

        Args:
            timeframe_repo: Repository für Timeframe-Daten
            sync_manager: Multi-Timeframe Synchronisation
            aggregator: Timeframe-Aggregation Logic
            series_lifecycle: Chart Series State Machine
            unified_time_manager: Globale Zeit-Koordination
            validator: Chart-Daten Validierung
        """
        self.timeframe_repo = timeframe_repo
        self.sync_manager = sync_manager
        self.aggregator = aggregator
        self.series_lifecycle = series_lifecycle
        self.unified_time = unified_time_manager
        self.validator = validator

        print("[TimeframeService] Initialized with dependency injection")

    def switch_timeframe(self, from_timeframe: str, to_timeframe: str,
                        visible_candles: int = 200) -> Dict[str, Any]:
        """
        Wechselt zwischen Timeframes mit Chart Recreation und Skip-Integration

        Args:
            from_timeframe: Aktueller Timeframe
            to_timeframe: Ziel-Timeframe
            visible_candles: Anzahl sichtbarer Kerzen

        Returns:
            Dict mit chart_data, needs_recreation, sync_status
        """
        print(f"[TimeframeService] Switching: {from_timeframe} -> {to_timeframe}")

        # PHASE 1: Pre-Transition Validation
        transition_plan = self.series_lifecycle.prepare_timeframe_transition(
            from_timeframe, to_timeframe
        )

        # PHASE 2: Data Loading mit Zeit-Synchronisation
        current_time = self.unified_time.get_current_time()

        if current_time:
            # Zeit-synchronisiertes Laden
            timeframe_minutes = self.unified_time._get_timeframe_minutes(to_timeframe)
            lookback_time = current_time - timedelta(minutes=timeframe_minutes * visible_candles)

            chart_data = self.timeframe_repo.get_candles_for_date_range(
                to_timeframe, lookback_time, current_time, max_candles=visible_candles
            )
            print(f"[TimeframeService] Time-synced load: {lookback_time} -> {current_time}")
        else:
            # Fallback: Lade ohne Zeit-Filter
            chart_data = self.timeframe_repo.load_timeframe_data(
                to_timeframe, start_date=None, end_date=None, max_candles=visible_candles
            )
            print(f"[TimeframeService] Fallback load: {len(chart_data)} candles")

        # PHASE 3: Validierung
        validated_data = self.validator.sanitize_chart_data(chart_data, source="timeframe_switch")

        # PHASE 4: Lifecycle Update
        self.series_lifecycle.complete_timeframe_transition(success=len(validated_data) > 0)

        return {
            'chart_data': validated_data,
            'needs_recreation': transition_plan['needs_recreation'],
            'from_timeframe': from_timeframe,
            'to_timeframe': to_timeframe,
            'candles_count': len(validated_data)
        }

    def aggregate_candles(self, candles: List[Dict[str, Any]], source_tf: str,
                         target_tf: str) -> List[Dict[str, Any]]:
        """
        Aggregiert Kerzen von einem Timeframe zu einem höheren

        Args:
            candles: Quell-Kerzen
            source_tf: Quell-Timeframe (z.B. '1m')
            target_tf: Ziel-Timeframe (z.B. '5m')

        Returns:
            Aggregierte Kerzen
        """
        print(f"[TimeframeService] Aggregating: {source_tf} -> {target_tf} ({len(candles)} candles)")

        # Nutze TimeframeAggregator für Aggregation
        aggregated = []

        for candle in candles:
            candle_time = datetime.fromtimestamp(candle['time'])

            complete_candle, incomplete_candle, is_complete = self.aggregator.add_minute_to_timeframe(
                candle_time, target_tf, candle
            )

            if is_complete:
                aggregated.append(complete_candle)

        print(f"[TimeframeService] Aggregated to {len(aggregated)} {target_tf} candles")
        return aggregated

    def get_incomplete_candle_info(self, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Gibt Info über unvollständige Kerze zurück (für weißen Rand)

        Args:
            timeframe: Timeframe

        Returns:
            Dict mit is_complete, elapsed_minutes, total_minutes oder None
        """
        if not self.sync_manager:
            return None

        return self.sync_manager.get_incomplete_candle_info(timeframe)

    def preload_adjacent_timeframes(self, current_timeframe: str):
        """
        Pre-lädt benachbarte Timeframes für schnelleres Switching

        Args:
            current_timeframe: Aktueller Timeframe
        """
        print(f"[TimeframeService] Preloading adjacent timeframes for {current_timeframe}")

        # Definiere Timeframe-Reihenfolge
        timeframe_sequence = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]

        try:
            current_index = timeframe_sequence.index(current_timeframe)

            # Preload vorherigen und nächsten Timeframe
            adjacent_timeframes = []
            if current_index > 0:
                adjacent_timeframes.append(timeframe_sequence[current_index - 1])
            if current_index < len(timeframe_sequence) - 1:
                adjacent_timeframes.append(timeframe_sequence[current_index + 1])

            for tf in adjacent_timeframes:
                # Cache vorbereiten (im Hintergrund)
                self.timeframe_repo.load_timeframe_data(tf, start_date=None, end_date=None, max_candles=200)
                print(f"[TimeframeService] Preloaded {tf}")

        except ValueError:
            print(f"[TimeframeService] WARNING: Unknown timeframe {current_timeframe}")
