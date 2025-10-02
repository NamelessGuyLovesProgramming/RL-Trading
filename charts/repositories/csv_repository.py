"""
CSV Repository - Data Access Layer für CSV-Daten
Abstrahiert CSV-Zugriff mit Multi-Path Fallback und Memory-Caching
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from charts.models.chart_data import Candle, ChartData, CandleFactory


class CSVRepository:
    """
    Repository für CSV-basierten Datenzugriff

    Verantwortlichkeiten:
    - CSV-Daten laden mit Fallback-System
    - Memory-Caching für Performance
    - Daten-Konvertierung zu Domain Models
    - Date-based und Range-based Queries
    """

    def __init__(self, data_path: str = "src/data/aggregated"):
        """
        Initialisiert CSV Repository

        Args:
            data_path: Basis-Pfad für CSV-Daten
        """
        self.data_path = Path(data_path)
        self.data_cache: Dict[str, pd.DataFrame] = {}  # {timeframe: DataFrame}
        self.available_timeframes = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]
        print(f"[CSVRepository] Initialisiert mit data_path: {self.data_path}")

    def _get_csv_paths(self, timeframe: str) -> List[Path]:
        """
        Gibt prioritisierte Liste von CSV-Pfaden für einen Timeframe

        Args:
            timeframe: Timeframe (z.B. "5m")

        Returns:
            Liste von Path-Objekten, sortiert nach Priorität
        """
        paths = [
            self.data_path / timeframe / "nq-2024.csv",      # Jahres-CSV im Timeframe-Ordner
            self.data_path / f"nq-2024-{timeframe}.csv"      # Alternative Root CSV
        ]

        # Monthly fallbacks für alle Monate (Dezember bis Januar)
        for month in range(12, 0, -1):
            monthly_csv = self.data_path / timeframe / f"nq-2024-{month:02d}.csv"
            paths.append(monthly_csv)

        return paths

    def _load_dataframe(self, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Lädt DataFrame für Timeframe mit Fallback-System

        Args:
            timeframe: Timeframe string

        Returns:
            DataFrame oder None bei Fehler
        """
        # Cache Check
        if timeframe in self.data_cache:
            print(f"[CSVRepository] Cache Hit für {timeframe}")
            return self.data_cache[timeframe]

        # Versuche CSV zu laden
        csv_paths = self._get_csv_paths(timeframe)

        for csv_path in csv_paths:
            if not csv_path.exists():
                continue

            try:
                print(f"[CSVRepository] Lade {timeframe} aus {csv_path}")
                df = pd.read_csv(csv_path)

                if df.empty:
                    continue

                # Normalize datetime column
                if 'datetime' not in df.columns:
                    # CSV mit Date + Time Spalten
                    if 'Date' in df.columns and 'Time' in df.columns:
                        df['datetime'] = pd.to_datetime(
                            df['Date'] + ' ' + df['Time'],
                            format='mixed',
                            dayfirst=True
                        )
                    # CSV mit time column (Unix timestamp)
                    elif 'time' in df.columns:
                        df['datetime'] = pd.to_datetime(df['time'], unit='s')
                    else:
                        print(f"[CSVRepository] ERROR: Keine datetime-Spalte gefunden in {csv_path}")
                        continue

                # Unix timestamp erstellen falls nicht vorhanden
                if 'time' not in df.columns:
                    df['time'] = df['datetime'].astype(int) // 10**9

                # Sortierung nach Zeit sicherstellen
                df = df.sort_values('datetime').reset_index(drop=True)

                # Cache speichern
                self.data_cache[timeframe] = df

                start_time = df['datetime'].iloc[0]
                end_time = df['datetime'].iloc[-1]
                print(f"[CSVRepository] SUCCESS: {len(df)} {timeframe} candles cached ({start_time} - {end_time})")

                return df

            except Exception as e:
                print(f"[CSVRepository] ERROR beim Laden {csv_path}: {e}")
                continue

        print(f"[CSVRepository] ERROR: Keine gültige CSV gefunden für {timeframe}")
        return None

    def get_candles_by_date(
        self,
        symbol: str,
        timeframe: str,
        date: datetime,
        count: int = 300
    ) -> List[Candle]:
        """
        Lädt Kerzen ab bestimmtem Datum aus CSV

        Args:
            symbol: Trading Symbol (z.B. "NQ=F")
            timeframe: Timeframe (z.B. "5m")
            date: Start-Datum
            count: Anzahl Kerzen

        Returns:
            Liste von Candle-Objekten
        """
        df = self._load_dataframe(timeframe)

        if df is None or df.empty:
            print(f"[CSVRepository] Keine Daten verfügbar für {timeframe}")
            return []

        # Finde Index für Startdatum
        target_timestamp = int(date.timestamp())

        # Suche nächste Kerze >= target_timestamp
        future_candles = df[df['time'] >= target_timestamp]

        if len(future_candles) == 0:
            print(f"[CSVRepository] Keine Daten nach {date} verfügbar")
            # Fallback: Letzte verfügbare Kerzen zurückgeben
            future_candles = df.tail(count)

        # Begrenze auf count Kerzen
        result_df = future_candles.head(count)

        # Konvertiere zu Candle-Objekten
        candles = []
        for _, row in result_df.iterrows():
            candle = CandleFactory.from_dataframe_row(row)
            candles.append(candle)

        print(f"[CSVRepository] Geladen: {len(candles)} candles ab {date} für {timeframe}")
        return candles

    def get_candles_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> List[Candle]:
        """
        Lädt Kerzen für bestimmten Zeitraum aus CSV

        Args:
            symbol: Trading Symbol
            timeframe: Timeframe
            start: Start-Zeit
            end: End-Zeit

        Returns:
            Liste von Candle-Objekten
        """
        df = self._load_dataframe(timeframe)

        if df is None or df.empty:
            return []

        # Zeitraum filtern
        start_timestamp = int(start.timestamp())
        end_timestamp = int(end.timestamp())

        mask = (df['time'] >= start_timestamp) & (df['time'] <= end_timestamp)
        result_df = df[mask]

        # Konvertiere zu Candle-Objekten
        candles = []
        for _, row in result_df.iterrows():
            candle = CandleFactory.from_dataframe_row(row)
            candles.append(candle)

        print(f"[CSVRepository] Geladen: {len(candles)} candles ({start} - {end}) für {timeframe}")
        return candles

    def get_all_candles(self, symbol: str, timeframe: str) -> List[Candle]:
        """
        Lädt alle verfügbaren Kerzen für Symbol und Timeframe

        Args:
            symbol: Trading Symbol
            timeframe: Timeframe

        Returns:
            Liste aller verfügbaren Candles
        """
        df = self._load_dataframe(timeframe)

        if df is None or df.empty:
            return []

        # Konvertiere alle zu Candle-Objekten
        candles = []
        for _, row in df.iterrows():
            candle = CandleFactory.from_dataframe_row(row)
            candles.append(candle)

        print(f"[CSVRepository] Geladen: {len(candles)} total candles für {timeframe}")
        return candles

    def get_next_candle(
        self,
        timeframe: str,
        current_datetime: datetime
    ) -> Optional[Candle]:
        """
        Findet die nächste Kerze nach der gegebenen Zeit

        Args:
            timeframe: Timeframe
            current_datetime: Aktuelle Zeit

        Returns:
            Nächste Candle oder None
        """
        df = self._load_dataframe(timeframe)

        if df is None:
            return None

        target_timestamp = int(current_datetime.timestamp())
        future_candles = df[df['time'] > target_timestamp].sort_values('datetime')

        if len(future_candles) > 0:
            next_row = future_candles.iloc[0]
            candle = CandleFactory.from_dataframe_row(next_row)
            return candle

        return None

    def preload_all_timeframes(self) -> bool:
        """
        Lädt alle verfügbaren Timeframes in den Cache

        Returns:
            True wenn mindestens ein Timeframe geladen wurde
        """
        print("[CSVRepository] Preloading all timeframes...")

        loaded_count = 0
        for timeframe in self.available_timeframes:
            df = self._load_dataframe(timeframe)
            if df is not None:
                loaded_count += 1
                print(f"[CSVRepository] Preloaded {timeframe}: {len(df)} candles")
            else:
                print(f"[CSVRepository] Failed to preload {timeframe}")

        print(f"[CSVRepository] Preloading abgeschlossen: {loaded_count}/{len(self.available_timeframes)} timeframes")
        return loaded_count > 0

    def get_timeframe_info(self, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Gibt Informationen über einen Timeframe zurück

        Args:
            timeframe: Timeframe

        Returns:
            Dict mit Timeframe-Info oder None
        """
        df = self._load_dataframe(timeframe)

        if df is None or df.empty:
            return None

        return {
            'timeframe': timeframe,
            'total_candles': len(df),
            'start_time': df['datetime'].iloc[0].to_pydatetime(),
            'end_time': df['datetime'].iloc[-1].to_pydatetime(),
            'loaded': True
        }

    def clear_cache(self):
        """Leert den Memory-Cache"""
        self.data_cache.clear()
        print("[CSVRepository] Cache cleared")
