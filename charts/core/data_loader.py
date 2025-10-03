"""
CSV Data Loader Service
Robust CSV-Daten Loader mit Multi-Path Fallback und Caching
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime


class CSVLoader:
    """Robust CSV-Daten Loader mit Multi-Path Fallback und Caching"""

    def __init__(self):
        self.data_cache: Dict[str, Any] = {}  # {timeframe: pandas.DataFrame}
        self.available_timeframes = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]
        print("[CSVLoader] Initialized multi-timeframe CSV loader")

    def get_csv_paths(self, timeframe: str) -> List[Path]:
        """Gibt prioritisierte Liste von CSV-Pfaden für einen Timeframe zurück"""
        paths = [
            Path(f"src/data/aggregated/{timeframe}/nq-2024.csv"),      # Jahres-CSV
            Path(f"src/data/aggregated/nq-2024-{timeframe}.csv")       # Alternative Root CSV
        ]

        # Monthly fallbacks für alle Monate
        for month in range(12, 0, -1):  # Dec to Jan
            monthly_csv = Path(f"src/data/aggregated/{timeframe}/nq-2024-{month:02d}.csv")
            paths.append(monthly_csv)

        return paths

    def load_timeframe_data(self, timeframe: str) -> Optional[Any]:
        """
        Lädt CSV-Daten für einen spezifischen Timeframe mit Fallback-System

        Returns:
            pandas.DataFrame or None: DataFrame mit OHLCV-Daten oder None bei Fehler
        """
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

    def preload_all_timeframes(self) -> None:
        """Lädt alle verfügbaren Timeframes in den Cache"""
        print("[CSVLoader] Preloading all timeframes...")

        for timeframe in self.available_timeframes:
            df = self.load_timeframe_data(timeframe)
            if df is not None:
                print(f"[CSVLoader] Preloaded {timeframe}: {len(df)} candles")
            else:
                print(f"[CSVLoader] Failed to preload {timeframe}")

    def get_next_candle(self, timeframe: str, current_datetime: datetime) -> Optional[Dict[str, Any]]:
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
