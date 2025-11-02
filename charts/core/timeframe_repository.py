"""
Timeframe Data Repository
Smart Data Repository mit Unified Time Integration
Abstrahiert CSV-Loading, validiert Daten und integriert mit UnifiedTimeManager
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pandas as pd


class TimeframeDataRepository:
    """
    🚀 Smart Data Repository mit Unified Time Integration
    Abstrahiert CSV-Loading, validiert Daten und integriert mit UnifiedTimeManager
    """

    def __init__(self, csv_loader, unified_time_manager):
        self.csv_loader = csv_loader
        self.unified_time = unified_time_manager

        # Enhanced Cache mit Zeit-Validierung
        self.validated_cache: Dict[str, Dict[str, Any]] = {}  # {timeframe: {data: df, last_validated_time: datetime}}
        self.candle_index_cache: Dict[str, Dict[int, int]] = {}  # {timeframe: {time: index}} für schnelle Suche

        print("[TimeframeDataRepository] Smart Data Repository initialisiert")

    def get_candle_at_time(self, timeframe: str, target_time, tolerance_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Holt eine spezifische Kerze zu einer bestimmten Zeit
        Integriert mit UnifiedTimeManager für Zeit-Validierung

        Returns:
            Dict or None: Candle-Daten (time, open, high, low, close, volume) oder None bei Fehler
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

    def get_next_candle_after_time(self, timeframe: str, current_time) -> Optional[Dict[str, Any]]:
        """
        Holt die nächste Kerze nach einer bestimmten Zeit
        Für Skip-Operationen optimiert

        Returns:
            Dict or None: Nächste Candle-Daten oder None wenn keine weiteren Kerzen
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

            # Make current_time timezone-aware if DataFrame column is timezone-aware
            current_pd = pd.Timestamp(current_time)
            if hasattr(df[time_column].dtype, 'tz') and df[time_column].dtype.tz is not None:
                current_pd = current_pd.tz_localize('UTC') if current_pd.tz is None else current_pd.tz_convert('UTC')

            print(f"[DEBUG] Suche nach datetime > {current_pd}")
            next_candles = df[df[time_column] > current_pd]

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

    def get_candles_for_date_range(self, timeframe: str, start_date, end_date=None, max_candles: int = 200) -> List[Dict[str, Any]]:
        """
        Holt Kerzen für einen Datumsbereich - für Chart-Loading optimiert
        🔧 SKIP-POSITION AWARE: Respektiert aktuelle Skip-Positionen vom UnifiedTimeManager
        """
        # Normalisiere zu datetime Objekten (nicht date!)
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        elif hasattr(start_date, 'date') and not isinstance(start_date, datetime):
            # Konvertiere date zu datetime
            import datetime as dt
            start_date = datetime.combine(start_date, dt.time.min)

        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
            elif hasattr(end_date, 'date') and not isinstance(end_date, datetime):
                # Konvertiere date zu datetime
                import datetime as dt
                end_date = datetime.combine(end_date, dt.time.max)

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
            # Datetime format - Konvertiere zu Pandas Timestamps für Vergleich
            if df[time_column].dtype == 'object':
                df[time_column] = pd.to_datetime(df[time_column])

            # CRITICAL: Konvertiere start_date und end_date zu Pandas Timestamps
            start_pd = pd.Timestamp(start_date)
            # Make timezone-aware if DataFrame column is timezone-aware
            if hasattr(df[time_column].dtype, 'tz') and df[time_column].dtype.tz is not None:
                start_pd = start_pd.tz_localize('UTC') if start_pd.tz is None else start_pd.tz_convert('UTC')

            if end_date:
                end_pd = pd.Timestamp(end_date)
                # Make timezone-aware if DataFrame column is timezone-aware
                if hasattr(df[time_column].dtype, 'tz') and df[time_column].dtype.tz is not None:
                    end_pd = end_pd.tz_localize('UTC') if end_pd.tz is None else end_pd.tz_convert('UTC')
                filtered_df = df[(df[time_column] >= start_pd) & (df[time_column] <= end_pd)]
            else:
                filtered_df = df[df[time_column] >= start_pd]

        # REFACTOR PHASE 3 FIX: Nimm LETZTE max_candles für Zeit-Synchronisation
        if len(filtered_df) > max_candles:
            filtered_df = filtered_df.tail(max_candles)  # Letzten 200 Kerzen = gleiches Ende für alle TF

        # Konvertiere zu Liste von Candle-Dicts
        candles = []
        for _, row in filtered_df.iterrows():
            candle_data = self._format_candle_data(row, timeframe)
            candles.append(candle_data)

        print(f"[TimeframeDataRepository] [DATA] {len(candles)} Kerzen geladen für {timeframe} ({start_date} bis {end_date or 'Ende'})")
        return candles

    def get_candles_before_time(self, timeframe: str, before_time, count: int = 250) -> List[Dict[str, Any]]:
        """
        Lädt historische Kerzen VOR einer bestimmten Zeit - für Lazy Loading

        Args:
            timeframe: Timeframe (z.B. '5m')
            before_time: Timestamp oder datetime - lade Kerzen VOR dieser Zeit
            count: Anzahl Kerzen die geladen werden sollen

        Returns:
            Liste von Candle-Dicts, sortiert chronologisch (älteste zuerst)
        """
        # Normalisiere before_time zu datetime
        if isinstance(before_time, (int, float)):
            before_time = datetime.fromtimestamp(before_time)

        print(f"[TimeframeDataRepository] [LAZY-LOAD] Loading {count} candles BEFORE {before_time} for {timeframe}")

        df = self._load_and_validate_timeframe_data(timeframe)
        if df is None or df.empty:
            print(f"[TimeframeDataRepository] [LAZY-LOAD] ERROR: No data for {timeframe}")
            return []

        # Filtere alle Kerzen VOR before_time
        time_column = 'datetime' if 'datetime' in df.columns else 'time'

        if time_column == 'time' and df[time_column].dtype == 'int64':
            # Timestamp format
            before_timestamp = before_time.timestamp()
            filtered_df = df[df[time_column] < before_timestamp]
        else:
            # Datetime format
            if df[time_column].dtype == 'object':
                df[time_column] = pd.to_datetime(df[time_column])

            before_pd = pd.Timestamp(before_time)
            # Make timezone-aware if DataFrame column is timezone-aware
            if hasattr(df[time_column].dtype, 'tz') and df[time_column].dtype.tz is not None:
                before_pd = before_pd.tz_localize('UTC') if before_pd.tz is None else before_pd.tz_convert('UTC')
            filtered_df = df[df[time_column] < before_pd]

        # Nimm die LETZTEN count Kerzen aus den gefilterten (= die neuesten VOR before_time)
        if len(filtered_df) > count:
            result_df = filtered_df.tail(count)
        else:
            result_df = filtered_df

        # Konvertiere zu Candle-Dicts
        candles = []
        for _, row in result_df.iterrows():
            candle_data = self._format_candle_data(row, timeframe)
            candles.append(candle_data)

        print(f"[TimeframeDataRepository] [LAZY-LOAD] ✅ {len(candles)} candles loaded (requested {count}, available before {before_time}: {len(filtered_df)})")
        return candles

    def _load_and_validate_timeframe_data(self, timeframe: str):
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

    def _find_candle_near_time(self, df, target_time, tolerance_minutes: int, timeframe: str):
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

    def _format_candle_data(self, row, timeframe: str) -> Dict[str, Any]:
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

    def _build_time_index_cache(self, df, timeframe: str) -> None:
        """Erstellt Index-Cache für schnelle Zeit-basierte Suchen"""
        # Implementierung bei Bedarf für Performance-Optimierung
        pass
