"""
High-Performance Timeframe Aggregator
Optimiert für maximale Geschwindigkeit und minimalen Memory-Footprint
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import os
from functools import lru_cache

class PerformanceAggregator:
    def __init__(self, cache_dir: str = "src/data/cache"):
        self.cache_dir = cache_dir
        self.aggregated_dir = "src/data/aggregated"

        # Lazy Loading Timeframe-Konfiguration
        # Formel: (sichtbare Chart-Kerzen × 5) für initiale Ladung
        self.timeframe_config = {
            '1m': {'minutes': 1, 'visible_candles': 200, 'priority': 1},
            '2m': {'minutes': 2, 'visible_candles': 200, 'priority': 2},
            '3m': {'minutes': 3, 'visible_candles': 200, 'priority': 3},
            '5m': {'minutes': 5, 'visible_candles': 200, 'priority': 4},
            '15m': {'minutes': 15, 'visible_candles': 200, 'priority': 5},
            '30m': {'minutes': 30, 'visible_candles': 200, 'priority': 6},
            '1h': {'minutes': 60, 'visible_candles': 200, 'priority': 7},
            '4h': {'minutes': 240, 'visible_candles': 200, 'priority': 8}
        }

        # Lazy Loading Parameter
        self.lazy_loading_multiplier = 5  # sichtbare_kerzen × 5
        self.chunk_size_multiplier = 2    # Nachladeblöcke = sichtbare_kerzen × 2

        # Memory-optimierte Caches
        self.hot_cache = {}  # Für aktive Timeframes
        self.warm_cache = {}  # Für kürzlich verwendete Timeframes
        self.cache_stats = {'hits': 0, 'misses': 0}

        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(self.aggregated_dir, exist_ok=True)
        print(f"PerformanceAggregator initialisiert - Dynamic Visible Candles + Pre-Aggregation")

    def calculate_initial_candles(self, visible_candles: int = None, timeframe: str = None) -> int:
        """Berechnet initiale Anzahl Kerzen basierend auf aktuell sichtbaren Kerzen: visible_candles × 5"""
        if visible_candles is None:
            # Fallback zu statischer Konfiguration
            config = self.timeframe_config.get(timeframe, {'visible_candles': 200})
            visible_candles = config['visible_candles']
        return visible_candles * self.lazy_loading_multiplier

    def calculate_chunk_size(self, visible_candles: int = None, timeframe: str = None) -> int:
        """Berechnet Chunk-Größe für Lazy Loading basierend auf aktuell sichtbaren Kerzen: visible_candles × 2"""
        if visible_candles is None:
            # Fallback zu statischer Konfiguration
            config = self.timeframe_config.get(timeframe, {'visible_candles': 200})
            visible_candles = config['visible_candles']
        return visible_candles * self.chunk_size_multiplier

    def get_lazy_loading_data_range(self, df: pd.DataFrame, timeframe: str, requested_candles: int = None) -> pd.DataFrame:
        """Gibt Datenanzahl für Lazy Loading zurück"""
        if requested_candles is None:
            requested_candles = self.calculate_initial_candles(timeframe=timeframe)

        config = self.timeframe_config.get(timeframe, {'minutes': 1})
        minutes = config['minutes']

        # Berechne wie viele 1m-Kerzen für gewünschte aggregierte Kerzen benötigt werden
        needed_1m_candles = requested_candles * minutes

        if len(df) <= needed_1m_candles:
            return df

        # Intelligent trimming - behalte neueste Daten für initiale Ladung
        return df.tail(needed_1m_candles).copy()

    def get_historical_data_chunk(self, df: pd.DataFrame, timeframe: str, before_timestamp: int, chunk_size: int = None) -> pd.DataFrame:
        """Lädt historischen Datenblock vor einem bestimmten Zeitstempel"""
        if chunk_size is None:
            chunk_size = self.calculate_chunk_size(timeframe)

        config = self.timeframe_config.get(timeframe, {'minutes': 1})
        minutes = config['minutes']
        needed_1m_candles = chunk_size * minutes

        # Konvertiere Timestamp zu datetime für Filterung
        before_datetime = pd.to_datetime(before_timestamp, unit='s')

        # Filtere Daten vor dem Zeitstempel
        filtered_df = df[df.index < before_datetime]

        if len(filtered_df) <= needed_1m_candles:
            return filtered_df

        # Gib die letzten needed_1m_candles vor dem Zeitstempel zurück
        return filtered_df.tail(needed_1m_candles).copy()

    @lru_cache(maxsize=128)
    def get_cache_key(self, timeframe: str, start_hash: int, end_hash: int, count: int) -> str:
        """LRU-cached cache key generation"""
        return f"perf_{timeframe}_{start_hash}_{end_hash}_{count}"

    def fast_aggregate(self, data: pd.DataFrame, timeframe: str, use_lazy_loading: bool = True) -> List[Dict]:
        """Ultra-fast aggregation mit NumPy-Optimierung und Lazy Loading"""
        if timeframe == '1m':
            if use_lazy_loading:
                data = self.get_lazy_loading_data_range(data, timeframe)
            return self.convert_to_chart_format(data)

        config = self.timeframe_config[timeframe]
        minutes = config['minutes']

        # Performance: Verwende Lazy Loading Datenanzahl
        if use_lazy_loading:
            data = self.get_lazy_loading_data_range(data, timeframe)

        # NumPy-optimierte Aggregation
        data_sorted = data.sort_index()

        # Zeitbasierte Gruppierung mit NumPy
        timestamps = data_sorted.index.astype(np.int64) // 10**9  # Unix seconds
        interval_seconds = minutes * 60

        # Schnelle Gruppierung
        groups = timestamps // interval_seconds
        unique_groups = np.unique(groups)

        result_data = []

        # Vektorisierte Aggregation
        for group in unique_groups:
            mask = groups == group
            group_data = data_sorted[mask]

            if len(group_data) == 0:
                continue

            # OHLCV-Berechnung
            agg_candle = {
                'time': int(group * interval_seconds),
                'open': float(group_data['Open'].iloc[0]),
                'high': float(group_data['High'].max()),
                'low': float(group_data['Low'].min()),
                'close': float(group_data['Close'].iloc[-1]),
                'volume': int(group_data['Volume'].sum() if 'Volume' in group_data else 0)
            }
            result_data.append(agg_candle)

        # Lazy Loading: Keine Limitierung hier, da bereits in get_lazy_loading_data_range gehandhabt
        return result_data

    def get_aggregated_data_performance(self, base_data: pd.DataFrame, timeframe: str) -> List[Dict]:
        """High-Performance Daten-Aggregation mit Multi-Level Caching"""

        # Cache-Key-Generierung
        start_hash = hash(str(base_data.index[0])) if len(base_data) > 0 else 0
        end_hash = hash(str(base_data.index[-1])) if len(base_data) > 0 else 0
        count = len(base_data)

        cache_key = self.get_cache_key(timeframe, start_hash, end_hash, count)

        # Hot Cache Check (Memory)
        if cache_key in self.hot_cache:
            self.cache_stats['hits'] += 1
            return self.hot_cache[cache_key]

        # Warm Cache Check (Memory)
        if cache_key in self.warm_cache:
            self.cache_stats['hits'] += 1
            # Promote to hot cache
            self.hot_cache[cache_key] = self.warm_cache[cache_key]
            del self.warm_cache[cache_key]
            return self.hot_cache[cache_key]

        # Cache Miss - berechne neu
        self.cache_stats['misses'] += 1
        result = self.fast_aggregate(base_data, timeframe)

        # Cache Management
        self.manage_cache(cache_key, result, timeframe)

        return result

    def get_historical_data_lazy(self, base_data: pd.DataFrame, timeframe: str, before_timestamp: int, chunk_size: int = None) -> List[Dict]:
        """Lädt historische Daten für Lazy Loading"""

        # Hole historischen Datenblock
        historical_df = self.get_historical_data_chunk(base_data, timeframe, before_timestamp, chunk_size)

        if historical_df.empty:
            return []

        # Aggregiere die historischen Daten
        result = self.fast_aggregate(historical_df, timeframe, use_lazy_loading=False)

        return result

    def get_aggregated_file_path(self, timeframe: str, year: int = 2024) -> str:
        """Gibt Pfad zur aggregierten CSV-Datei zurück - Option 2 Struktur"""
        return os.path.join(self.aggregated_dir, timeframe, f"nq-{year}.csv")

    def load_or_create_aggregated_data(self, base_data: pd.DataFrame, timeframe: str, year: int = 2024) -> pd.DataFrame:
        """Lädt aggregierte Daten aus CSV oder erstellt sie bei Bedarf"""
        file_path = self.get_aggregated_file_path(timeframe, year)

        if os.path.exists(file_path):
            print(f"Lade aggregierte {timeframe} Daten aus {file_path}")
            try:
                aggregated_df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                return aggregated_df
            except Exception as e:
                print(f"Fehler beim Laden von {file_path}: {e}")
                # Fallback: neu generieren

        # Erstelle aggregierte Daten
        print(f"Generiere neue aggregierte {timeframe} Daten...")
        aggregated_df = self.create_aggregated_dataframe(base_data, timeframe)

        # Speichere als CSV
        try:
            aggregated_df.to_csv(file_path)
            print(f"Aggregierte {timeframe} Daten gespeichert: {file_path} ({len(aggregated_df)} Kerzen)")
        except Exception as e:
            print(f"Fehler beim Speichern von {file_path}: {e}")

        return aggregated_df

    def create_aggregated_dataframe(self, base_data: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """Erstellt aggregierte DataFrame aus 1m-Daten"""
        if timeframe == '1m':
            return base_data

        config = self.timeframe_config[timeframe]
        minutes = config['minutes']

        # Sortiere Daten
        data_sorted = base_data.sort_index()

        # Zeitbasierte Gruppierung
        timestamps = data_sorted.index.astype(np.int64) // 10**9  # Unix seconds
        interval_seconds = minutes * 60
        groups = timestamps // interval_seconds
        unique_groups = np.unique(groups)

        aggregated_rows = []

        for group in unique_groups:
            mask = groups == group
            group_data = data_sorted[mask]

            if len(group_data) == 0:
                continue

            # OHLCV-Aggregation
            group_timestamp = pd.to_datetime(group * interval_seconds, unit='s')
            aggregated_rows.append({
                'Open': float(group_data['Open'].iloc[0]),
                'High': float(group_data['High'].max()),
                'Low': float(group_data['Low'].min()),
                'Close': float(group_data['Close'].iloc[-1]),
                'Volume': int(group_data['Volume'].sum() if 'Volume' in group_data else 0)
            })

        # Erstelle DataFrame mit Zeitindex
        timestamps_df = [pd.to_datetime(group * interval_seconds, unit='s') for group in unique_groups if len(data_sorted[groups == group]) > 0]
        aggregated_df = pd.DataFrame(aggregated_rows, index=timestamps_df)

        return aggregated_df

    def get_aggregated_data_from_csv(self, base_data: pd.DataFrame, timeframe: str, visible_candles: int = None) -> List[Dict]:
        """Lädt aggregierte Daten aus CSV und wendet Lazy Loading an"""

        # Lade oder erstelle aggregierte DataFrame
        aggregated_df = self.load_or_create_aggregated_data(base_data, timeframe)

        # Berechne gewünschte Anzahl Kerzen
        if visible_candles is not None:
            requested_candles = self.calculate_initial_candles(visible_candles)
        else:
            requested_candles = self.calculate_initial_candles(timeframe=timeframe)

        # Limitiere auf gewünschte Anzahl (neueste Daten)
        if len(aggregated_df) > requested_candles:
            aggregated_df = aggregated_df.tail(requested_candles)

        # Konvertiere zu Chart-Format
        return self.convert_to_chart_format(aggregated_df)

    def manage_cache(self, cache_key: str, data: List[Dict], timeframe: str):
        """Intelligentes Cache-Management"""
        priority = self.timeframe_config[timeframe]['priority']

        # High-priority timeframes go to hot cache
        if priority <= 4:  # 1m, 2m, 3m, 5m
            if len(self.hot_cache) >= 8:  # Limit hot cache
                # Move least recently used to warm cache
                old_key = next(iter(self.hot_cache))
                self.warm_cache[old_key] = self.hot_cache.pop(old_key)
            self.hot_cache[cache_key] = data
        else:
            # Lower priority to warm cache
            if len(self.warm_cache) >= 12:  # Limit warm cache
                # Remove oldest
                old_key = next(iter(self.warm_cache))
                del self.warm_cache[old_key]
            self.warm_cache[cache_key] = data

    def convert_to_chart_format(self, df: pd.DataFrame) -> List[Dict]:
        """Optimierte Chart-Format Konvertierung"""
        if df.empty:
            return []

        # NumPy-optimierte Konvertierung
        timestamps = df.index.astype(np.int64) // 10**9  # Unix seconds

        chart_data = []
        for i, (timestamp, row) in enumerate(zip(timestamps, df.itertuples())):
            chart_data.append({
                'time': int(timestamp),
                'open': float(row.Open),
                'high': float(row.High),
                'low': float(row.Low),
                'close': float(row.Close),
                'volume': int(row.Volume) if hasattr(row, 'Volume') else 0
            })

        return chart_data

    def precompute_priority_timeframes(self, base_data: pd.DataFrame):
        """Precompute nur die wichtigsten Timeframes für Startup-Performance"""
        priority_timeframes = ['5m', '15m', '1h']  # Nur die wichtigsten

        print("Performance Precomputing (priority timeframes only)...")
        for timeframe in priority_timeframes:
            if timeframe in self.timeframe_config:
                print(f"Precomputing {timeframe}...")
                self.get_aggregated_data_performance(base_data, timeframe)

        print("Priority timeframes precomputed")

    def get_cache_info(self) -> Dict:
        """Cache-Performance Statistiken"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            'hot_cache_size': len(self.hot_cache),
            'warm_cache_size': len(self.warm_cache),
            'hit_rate': f"{hit_rate:.1f}%",
            'total_requests': total_requests,
            'cache_stats': self.cache_stats,
            'cache_dir': self.cache_dir
        }

    def clear_cache(self):
        """Cache-Reset für Memory-Management"""
        self.hot_cache.clear()
        self.warm_cache.clear()
        self.cache_stats = {'hits': 0, 'misses': 0}
        print("Performance caches cleared")

# Singleton Pattern für Memory-Effizienz
_performance_aggregator_instance = None

def get_performance_aggregator() -> PerformanceAggregator:
    """Singleton-Access für Performance Aggregator"""
    global _performance_aggregator_instance
    if _performance_aggregator_instance is None:
        _performance_aggregator_instance = PerformanceAggregator()
    return _performance_aggregator_instance

if __name__ == "__main__":
    # Performance Test
    print("Testing Performance Aggregator...")

    # Simuliere Daten
    dates = pd.date_range(start='2024-01-01', periods=10000, freq='1min')
    test_data = pd.DataFrame({
        'Open': np.random.randn(10000).cumsum() + 100,
        'High': np.random.randn(10000).cumsum() + 102,
        'Low': np.random.randn(10000).cumsum() + 98,
        'Close': np.random.randn(10000).cumsum() + 100,
        'Volume': np.random.randint(1000, 5000, 10000)
    }, index=dates)

    aggregator = get_performance_aggregator()

    # Performance Test
    import time
    start = time.time()

    for tf in ['5m', '15m', '1h']:
        result = aggregator.get_aggregated_data_performance(test_data, tf)
        print(f"{tf}: {len(result)} candles")

    end = time.time()
    print(f"Performance test completed in {(end-start)*1000:.2f}ms")
    print(f"Cache info: {aggregator.get_cache_info()}")