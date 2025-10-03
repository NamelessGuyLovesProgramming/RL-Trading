"""
Chart Service - Business Logic für Chart-Operationen
Koordiniert Chart-Daten-Laden, Validierung und Caching
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


class ChartService:
    """
    Service für alle Chart-bezogenen Operationen
    Dependency Injection Pattern für Repositories und Core-Komponenten
    """

    def __init__(self,
                 price_repo,  # UnifiedPriceRepository
                 timeframe_repo,  # TimeframeDataRepository
                 cache_manager,  # ChartDataCache
                 validator,  # ChartDataValidator
                 unified_time_manager):  # UnifiedTimeManager
        """
        Initialisiert ChartService mit Dependencies

        Args:
            price_repo: Repository für Preis-Synchronisation (1m-Daten)
            timeframe_repo: Repository für Multi-Timeframe CSV-Daten
            cache_manager: Memory-basierter Cache für Chart-Daten
            validator: Validierung von Chart-Daten
            unified_time_manager: Globale Zeit-Koordination
        """
        self.price_repo = price_repo
        self.timeframe_repo = timeframe_repo
        self.cache_manager = cache_manager
        self.validator = validator
        self.unified_time = unified_time_manager

        print("[ChartService] Initialized with dependency injection")

    def load_initial_chart(self, symbol: str, timeframe: str, visible_candles: int = 200) -> List[Dict[str, Any]]:
        """
        Lädt initiale Chart-Daten beim Server-Start

        Args:
            symbol: Trading-Symbol (z.B. 'NQ')
            timeframe: Timeframe (z.B. '5m')
            visible_candles: Anzahl sichtbarer Kerzen

        Returns:
            Liste von Chart-Kerzen (dict mit time, open, high, low, close, volume)
        """
        print(f"[ChartService] Loading initial chart: {symbol} {timeframe}")

        # Verwende globale Zeit falls vorhanden
        current_time = self.unified_time.get_current_time()

        if current_time:
            # Berechne Start-Zeit basierend auf Timeframe
            timeframe_minutes = self.unified_time._get_timeframe_minutes(timeframe)
            lookback_time = current_time - timedelta(minutes=timeframe_minutes * visible_candles)

            chart_data = self.timeframe_repo.get_candles_for_date_range(
                timeframe, lookback_time, current_time, max_candles=visible_candles
            )
        else:
            # Fallback: Lade aus CSV ohne Zeit-Filter
            chart_data = self.timeframe_repo.load_timeframe_data(
                timeframe, start_date=None, end_date=None, max_candles=visible_candles
            )

        # Validiere Chart-Daten
        validated_data = self.validator.sanitize_chart_data(chart_data, source="initial_load")

        print(f"[ChartService] Initial chart loaded: {len(validated_data)} candles")
        return validated_data

    def get_visible_candles(self, timeframe: str, from_time: datetime, to_time: datetime,
                           max_candles: int = 200) -> List[Dict[str, Any]]:
        """
        Lädt sichtbare Kerzen für einen Zeitbereich

        Args:
            timeframe: Timeframe (z.B. '5m')
            from_time: Start-Zeit
            to_time: End-Zeit
            max_candles: Maximale Anzahl Kerzen

        Returns:
            Liste von Chart-Kerzen
        """
        print(f"[ChartService] Loading visible candles: {timeframe} from {from_time} to {to_time}")

        # Lade Daten vom Repository
        chart_data = self.timeframe_repo.get_candles_for_date_range(
            timeframe, from_time, to_time, max_candles=max_candles
        )

        # Validiere
        validated_data = self.validator.sanitize_chart_data(chart_data, source="visible_range")

        return validated_data

    def load_chart_for_date(self, date: datetime, timeframe: str, visible_candles: int = 200) -> List[Dict[str, Any]]:
        """
        Lädt Chart-Daten für ein bestimmtes Datum (Go-To-Date)

        Args:
            date: Ziel-Datum
            timeframe: Timeframe
            visible_candles: Anzahl sichtbarer Kerzen

        Returns:
            Liste von Chart-Kerzen zentriert um das Datum
        """
        print(f"[ChartService] Loading chart for date: {date} ({timeframe})")

        # Berechne Zeit-Bereich
        timeframe_minutes = self.unified_time._get_timeframe_minutes(timeframe)
        lookback_time = date - timedelta(minutes=timeframe_minutes * visible_candles)

        chart_data = self.timeframe_repo.get_candles_for_date_range(
            timeframe, lookback_time, date, max_candles=visible_candles
        )

        # Validiere
        validated_data = self.validator.sanitize_chart_data(chart_data, source="goto_date")

        print(f"[ChartService] Loaded {len(validated_data)} candles for {date}")
        return validated_data

    def get_candle_count(self, timeframe: str) -> int:
        """
        Gibt Anzahl verfügbarer Kerzen für einen Timeframe zurück

        Args:
            timeframe: Timeframe

        Returns:
            Anzahl Kerzen
        """
        tf_info = self.cache_manager.get_timeframe_info(timeframe)
        if tf_info:
            return tf_info['total_candles']
        return 0

    def validate_timeframe(self, timeframe: str) -> bool:
        """
        Prüft ob ein Timeframe verfügbar ist

        Args:
            timeframe: Timeframe zu prüfen

        Returns:
            True wenn verfügbar
        """
        available_timeframes = self.cache_manager.available_timeframes
        return timeframe in available_timeframes
