"""
Navigation Service - Business Logic für Chart-Navigation
Koordiniert GoTo, Skip, Next Operationen mit Zeit-Synchronisation
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


class NavigationService:
    """
    Service für Chart-Navigation Operationen
    Verwaltet GoTo-Date, Skip-Forward, Next-Candle mit globaler Zeit-Koordination
    """

    def __init__(self,
                 timeframe_repo,  # TimeframeDataRepository
                 debug_controller,  # DebugController
                 unified_time_manager,  # UnifiedTimeManager
                 unified_state,  # UnifiedStateManager
                 validator):  # ChartDataValidator
        """
        Initialisiert NavigationService mit Dependencies

        Args:
            timeframe_repo: Repository für Timeframe-Daten
            debug_controller: Debug-Mode Controller (für Skip mit echten Daten)
            unified_time_manager: Globale Zeit-Koordination
            unified_state: Globaler State Manager
            validator: Chart-Daten Validierung
        """
        self.timeframe_repo = timeframe_repo
        self.debug_controller = debug_controller
        self.unified_time = unified_time_manager
        self.unified_state = unified_state
        self.validator = validator

        print("[NavigationService] Initialized with dependency injection")

    def go_to_date(self, target_date: datetime, timeframe: str,
                   visible_candles: int = 200) -> Dict[str, Any]:
        """
        Springt zu einem bestimmten Datum im Chart

        Args:
            target_date: Ziel-Datum/-Zeit
            timeframe: Aktueller Timeframe
            visible_candles: Anzahl sichtbarer Kerzen

        Returns:
            Dict mit chart_data, actual_date, success
        """
        print(f"[NavigationService] Go to date: {target_date} ({timeframe})")

        # Update globale Zeit
        self.unified_time.set_time(target_date, source="goto_date")

        # Update DebugController Start-Zeit
        self.debug_controller.set_start_time(target_date)

        # Berechne Zeit-Bereich
        timeframe_minutes = self.unified_time._get_timeframe_minutes(timeframe)
        lookback_time = target_date - timedelta(minutes=timeframe_minutes * visible_candles)

        # Lade Chart-Daten
        chart_data = self.timeframe_repo.get_candles_for_date_range(
            timeframe, lookback_time, target_date, max_candles=visible_candles
        )

        # Validiere
        validated_data = self.validator.sanitize_chart_data(chart_data, source="goto_date")

        # Update State
        if self.unified_state:
            self.unified_state.update_skip_position(target_date, source="goto")

        print(f"[NavigationService] Go to date completed: {len(validated_data)} candles loaded")

        return {
            'chart_data': validated_data,
            'actual_date': target_date,
            'candles_count': len(validated_data),
            'success': len(validated_data) > 0
        }

    def skip_forward(self, timeframe: str) -> Dict[str, Any]:
        """
        Springt eine Kerze vorwärts (Skip-Operation)

        Args:
            timeframe: Aktueller Timeframe

        Returns:
            Dict mit candle, candle_type (complete/incomplete), success
        """
        print(f"[NavigationService] Skip forward: {timeframe}")

        # Nutze DebugController für Skip mit echten CSV-Daten
        skip_result = self.debug_controller.skip_with_real_data(timeframe)

        if not skip_result:
            print(f"[NavigationService] Skip failed: No more data available")
            return {
                'candle': None,
                'candle_type': None,
                'success': False,
                'error': 'No more data available'
            }

        # Validiere Kerze
        candle = skip_result['candle']
        validated_candle = self.validator.validate_candle_for_chart(candle)

        if not validated_candle:
            print(f"[NavigationService] Skip validation failed")
            return {
                'candle': None,
                'candle_type': None,
                'success': False,
                'error': 'Candle validation failed'
            }

        print(f"[NavigationService] Skip completed: {skip_result['type']}")

        return {
            'candle': candle,
            'candle_type': skip_result['type'],  # 'complete_candle' oder 'incomplete_candle'
            'timeframe': timeframe,
            'incomplete_info': skip_result.get('incomplete_info'),
            'success': True
        }

    def next_candle(self, timeframe: str) -> Dict[str, Any]:
        """
        Lädt nächste Kerze (alias für skip_forward)

        Args:
            timeframe: Aktueller Timeframe

        Returns:
            Dict mit candle, success
        """
        return self.skip_forward(timeframe)

    def skip_multiple(self, count: int, timeframe: str) -> Dict[str, Any]:
        """
        Springt mehrere Kerzen vorwärts

        Args:
            count: Anzahl Kerzen zu skippen
            timeframe: Aktueller Timeframe

        Returns:
            Dict mit candles, success, skipped_count
        """
        print(f"[NavigationService] Skip multiple: {count} candles ({timeframe})")

        skipped_candles = []
        success_count = 0

        for i in range(count):
            skip_result = self.skip_forward(timeframe)

            if skip_result['success']:
                skipped_candles.append(skip_result['candle'])
                success_count += 1
            else:
                print(f"[NavigationService] Skip stopped after {success_count}/{count} candles")
                break

        return {
            'candles': skipped_candles,
            'success': success_count > 0,
            'skipped_count': success_count,
            'requested_count': count
        }

    def get_current_position(self, timeframe: str) -> Optional[datetime]:
        """
        Gibt aktuelle Position im Chart zurück

        Args:
            timeframe: Timeframe

        Returns:
            Aktuelle Zeit oder None
        """
        return self.unified_time.get_current_time()

    def can_skip_forward(self, timeframe: str) -> bool:
        """
        Prüft ob Skip-Forward möglich ist (noch Daten verfügbar)

        Args:
            timeframe: Timeframe

        Returns:
            True wenn Skip möglich
        """
        current_time = self.unified_time.get_current_time()

        if not current_time:
            return True  # Keine Zeit gesetzt, Skip möglich

        # Hole Timeframe-Info
        tf_info = self.timeframe_repo.csv_loader.timeframe_data.get(timeframe)

        if not tf_info or tf_info.empty:
            return False

        # Prüfe ob wir am Ende der Daten sind
        last_candle_time = tf_info.iloc[-1]['datetime']

        return current_time < last_candle_time
