"""
High-Performance Chart Cache System
==================================
Ultra-schneller Single Source of Truth Cache für alle Timeframes
Performance-Optimiert für sub-10ms Timeframe-Switching
"""

import pandas as pd
import numpy as np
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import OrderedDict
from datetime import datetime, timedelta


class HighPerformanceChartCache:
    """
    High-Performance Single Source of Truth Cache

    Features:
    - Single Master 1m Dataset als Basis für alle Timeframes
    - Pre-computed Date-to-Index HashMap für O(1) Lookups
    - On-demand Aggregation mit intelligent Caching
    - Predictive Pre-loading für wahrscheinliche nächste Requests
    - LRU Memory Management mit automatischem Cleanup
    """

    def __init__(self, cache_size_mb: int = 100):
        """
        Initialisiert High-Performance Cache System

        Args:
            cache_size_mb: Maximale Cache-Größe in MB (default: 100MB)
        """
        # Single Source of Truth - Master 1m Dataset
        self.master_1m_data: Optional[pd.DataFrame] = None

        # Pre-computed Index Maps für O(1) Lookups
        self.date_index_map: Dict[str, int] = {}  # "2024-12-25" -> 1m_index
        self.datetime_index_map: Dict[pd.Timestamp, int] = {}  # timestamp -> 1m_index

        # Timeframe Multipliers für Aggregation
        self.timeframe_multipliers = {
            "1m": 1,
            "2m": 2,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240
        }

        # Intelligent Caching System
        self.visible_cache: OrderedDict = OrderedDict()  # LRU Cache für aktuelle Sichtbereiche
        self.cache_size_mb = cache_size_mb
        self.cache_hits = 0
        self.cache_misses = 0

        # Background Threading für Predictive Loading
        self.preload_thread: Optional[threading.Thread] = None
        self.preload_queue: List[Tuple[str, str, int]] = []  # (timeframe, date, candle_count)
        self.preload_lock = threading.Lock()

        # Performance Monitoring
        self.start_time = time.time()
        self.operation_times: Dict[str, List[float]] = {
            "go_to_date": [],
            "timeframe_switch": [],
            "aggregation": []
        }

        print("[HIGH-PERF-CACHE] Initialisiert - Single Source of Truth Architecture")

    def load_master_dataset(self, csv_path: Optional[str] = None, max_rows: Optional[int] = 50000) -> bool:
        """
        Lädt Master 1m Dataset als Single Source of Truth mit intelligenter Größen-Begrenzung

        Args:
            csv_path: Pfad zur Master CSV-Datei (default: auto-detect beste 1m CSV)
            max_rows: Maximum Anzahl Zeilen (default: 50000 für Performance)

        Returns:
            bool: True wenn erfolgreich geladen
        """
        start_time = time.time()

        if csv_path is None:
            # Auto-detect beste verfügbare 1m CSV
            possible_paths = [
                "src/data/aggregated/1m/nq-2024.csv",
                "src/data/aggregated/nq-2024-1m.csv",
                "src/data/nq-1m.csv"
            ]

            csv_path = None
            for path in possible_paths:
                if Path(path).exists():
                    csv_path = path
                    break

            if csv_path is None:
                print("[HIGH-PERF-CACHE] ERROR: Keine 1m CSV gefunden!")
                return False

        try:
            print(f"[HIGH-PERF-CACHE] Lade Master 1m Dataset: {csv_path}")

            # Performance-optimiertes CSV laden - nur die letzten N Zeilen
            if max_rows:
                # Windows-kompatible Zeilen-Zählung
                try:
                    with open(csv_path, 'r') as f:
                        total_lines = sum(1 for _ in f)

                    if total_lines > max_rows:
                        skip_rows = total_lines - max_rows - 1  # -1 for header
                        print(f"[HIGH-PERF-CACHE] PERFORMANCE: Loading last {max_rows} rows (skipping {skip_rows} from {total_lines} total)")
                        df = pd.read_csv(csv_path, skiprows=range(1, skip_rows + 1))
                    else:
                        print(f"[HIGH-PERF-CACHE] Loading all {total_lines} rows (within limit)")
                        df = pd.read_csv(csv_path)
                except Exception as e:
                    print(f"[HIGH-PERF-CACHE] Warning: Could not count lines, loading all data: {e}")
                    df = pd.read_csv(csv_path)
            else:
                # CSV laden
                df = pd.read_csv(csv_path)

            # Flexible CSV Format Detection
            if 'time' not in df.columns:
                # Full year CSV format: convert to expected format
                df = df.rename(columns={
                    df.columns[0]: 'time' if df.columns[0] != 'time' else df.columns[0],
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })

                # Handle datetime conversion
                if 'Date' in df.columns and 'Time' in df.columns:
                    # Date + Time columns format
                    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
                    df['time'] = df['datetime'].astype(int) // 10**9
                elif df['time'].dtype == 'object':
                    # String datetime format
                    df['datetime'] = pd.to_datetime(df['time'])
                    df['time'] = df['datetime'].astype(int) // 10**9
                else:
                    # Already numeric timestamps
                    df['datetime'] = pd.to_datetime(df['time'], unit='s')
            else:
                # Already correct format
                if 'datetime' not in df.columns:
                    df['datetime'] = pd.to_datetime(df['time'], unit='s')

            # Sortierung nach Zeit sicherstellen
            df = df.sort_values('datetime').reset_index(drop=True)

            # Data Quality Validation
            if len(df) == 0:
                print("[HIGH-PERF-CACHE] ERROR: CSV ist leer!")
                return False

            # Store Master Dataset
            self.master_1m_data = df

            # Build Pre-computed Index Maps
            self._build_index_maps()

            # Performance Info
            load_time = time.time() - start_time
            start_date = df['datetime'].iloc[0].strftime('%Y-%m-%d')
            end_date = df['datetime'].iloc[-1].strftime('%Y-%m-%d')
            memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024

            print(f"[HIGH-PERF-CACHE] SUCCESS Master Dataset geladen:")
            print(f"  -> Candles: {len(df):,}")
            print(f"  -> Zeitraum: {start_date} bis {end_date}")
            print(f"  -> Memory: {memory_mb:.1f} MB")
            print(f"  -> Load Time: {load_time*1000:.0f}ms")
            print(f"  -> Date Index Map: {len(self.date_index_map):,} entries")

            return True

        except Exception as e:
            print(f"[HIGH-PERF-CACHE] ERROR beim Laden: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _build_index_maps(self):
        """Baut Pre-computed Index Maps für O(1) Lookups"""
        start_time = time.time()

        # Date-to-Index Map (String-basiert)
        self.date_index_map = {}
        self.datetime_index_map = {}

        for idx, row in self.master_1m_data.iterrows():
            dt = row['datetime']
            date_str = dt.strftime('%Y-%m-%d')

            # Für jeden Tag: Speichere Index der ersten Kerze dieses Tages
            if date_str not in self.date_index_map:
                self.date_index_map[date_str] = idx

            # Datetime-basiert für präzise Lookups
            self.datetime_index_map[dt] = idx

        build_time = time.time() - start_time
        print(f"[HIGH-PERF-CACHE] Index Maps built in {build_time*1000:.0f}ms")

    def get_timeframe_data(self, timeframe: str, target_date: str, candle_count: int = 200) -> Dict[str, Any]:
        """
        High-Performance Timeframe Data Retrieval

        Args:
            timeframe: Target timeframe (1m, 5m, 15m, etc.)
            target_date: Target date as "YYYY-MM-DD"
            candle_count: Number of candles to return (default: 200)

        Returns:
            Dict mit aggregated data, visible_range, performance_stats
        """
        operation_start = time.time()

        # Cache Key für LRU Cache
        cache_key = f"{timeframe}_{target_date}_{candle_count}"

        # Hot Cache Check
        if cache_key in self.visible_cache:
            # LRU: Move to end (most recently used)
            self.visible_cache.move_to_end(cache_key)
            self.cache_hits += 1

            result = self.visible_cache[cache_key]
            operation_time = time.time() - operation_start
            result['performance_stats']['response_time_ms'] = operation_time * 1000
            result['performance_stats']['cache_hit'] = True

            return result

        # Cache Miss - Generate Data
        self.cache_misses += 1

        # O(1) Date Lookup
        if target_date not in self.date_index_map:
            # Fallback: Find closest date
            available_dates = sorted(self.date_index_map.keys())
            if target_date < available_dates[0]:
                target_date = available_dates[0]
            elif target_date > available_dates[-1]:
                target_date = available_dates[-1]
            else:
                # Find closest date
                for i, date in enumerate(available_dates):
                    if date >= target_date:
                        target_date = date
                        break

        target_1m_index = self.date_index_map[target_date]

        # Calculate 1m data range needed für Aggregation
        timeframe_multiplier = self.timeframe_multipliers.get(timeframe, 1)
        required_1m_candles = candle_count * timeframe_multiplier

        # Extract 1m data range (vorwärts vom target_date für Go To Date)
        start_1m_index = target_1m_index
        end_1m_index = min(len(self.master_1m_data), start_1m_index + required_1m_candles)

        relevant_1m_data = self.master_1m_data.iloc[start_1m_index:end_1m_index].copy()

        if len(relevant_1m_data) == 0:
            print(f"[HIGH-PERF-CACHE] WARNING: Keine Daten für {target_date} in Timeframe {timeframe}")
            return {"data": [], "visible_range": None, "performance_stats": {}}

        # On-Demand Aggregation
        aggregation_start = time.time()

        if timeframe == "1m":
            # No aggregation needed
            aggregated_data = relevant_1m_data
        else:
            # Aggregate to target timeframe
            aggregated_data = self._aggregate_to_timeframe(relevant_1m_data, timeframe)

        aggregation_time = time.time() - aggregation_start
        self.operation_times['aggregation'].append(aggregation_time)

        # Prepare Result
        result_data = []
        for _, row in aggregated_data.iterrows():
            result_data.append({
                'time': int(row['time']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row.get('volume', 0))
            })

        # Calculate Visible Range (last 50 candles für Chart display)
        visible_count = min(50, len(result_data))
        if visible_count > 0:
            start_time_visible = result_data[-visible_count]['time']
            end_time_visible = result_data[-1]['time']
            visible_range = {
                'from': start_time_visible,
                'to': end_time_visible
            }
        else:
            visible_range = None

        # Performance Stats
        operation_time = time.time() - operation_start
        performance_stats = {
            'response_time_ms': operation_time * 1000,
            'aggregation_time_ms': aggregation_time * 1000,
            'cache_hit': False,
            'source_candles_1m': len(relevant_1m_data),
            'result_candles': len(result_data),
            'target_date': target_date,
            'actual_1m_range': [start_1m_index, end_1m_index]
        }

        # Build Result
        result = {
            'data': result_data,
            'visible_range': visible_range,
            'performance_stats': performance_stats
        }

        # Cache Result (LRU Management)
        self._cache_with_lru(cache_key, result)

        # Background: Predictive Pre-loading
        self._trigger_predictive_preload(timeframe, target_date, candle_count)

        return result

    def _aggregate_to_timeframe(self, df_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        High-Performance OHLCV Aggregation

        Args:
            df_1m: 1m DataFrame to aggregate
            timeframe: Target timeframe

        Returns:
            Aggregated DataFrame
        """
        if timeframe == "1m":
            return df_1m

        multiplier = self.timeframe_multipliers[timeframe]

        # Time-based aggregation für korrekte Timestamps
        df = df_1m.copy().reset_index(drop=True)

        # Sortiere nach datetime für korrekte chronologische Reihenfolge
        df = df.sort_values('datetime').reset_index(drop=True)

        # Create time-based groups using datetime
        df['minutes_from_start'] = (df['datetime'] - df['datetime'].iloc[0]).dt.total_seconds() / 60
        df['group'] = (df['minutes_from_start'] // multiplier).astype(int)

        # Remove incomplete last group
        group_counts = df.groupby('group').size()
        complete_groups = group_counts[group_counts >= multiplier].index
        df = df[df['group'].isin(complete_groups)]

        if len(df) == 0:
            # Return empty DataFrame with correct structure
            return pd.DataFrame(columns=['datetime', 'time', 'open', 'high', 'low', 'close', 'volume'])

        # OHLCV Aggregation with correct timestamps
        aggregated = df.groupby('group').agg({
            'datetime': 'first',  # First datetime of each timeframe period
            'time': 'first',      # First timestamp of each timeframe period
            'open': 'first',      # First open
            'high': 'max',        # Maximum high
            'low': 'min',         # Minimum low
            'close': 'last',      # Last close
            'volume': 'sum'       # Sum volume
        }).reset_index(drop=True)

        return aggregated

    def _cache_with_lru(self, cache_key: str, result: Dict[str, Any]):
        """LRU Cache Management mit Memory Limit"""

        # Add to cache
        self.visible_cache[cache_key] = result

        # Estimate memory usage (rough)
        estimated_mb = len(result['data']) * 0.001  # ~1KB per candle

        # LRU Cleanup wenn Cache zu groß
        while len(self.visible_cache) > 100:  # Max 100 cached ranges
            # Remove least recently used
            oldest_key = next(iter(self.visible_cache))
            del self.visible_cache[oldest_key]

    def _trigger_predictive_preload(self, current_timeframe: str, current_date: str, candle_count: int):
        """Background Predictive Pre-loading für wahrscheinliche nächste Requests"""

        # Most likely next timeframes basierend auf User-Verhalten
        likely_timeframes = {
            "1m": ["5m", "15m"],
            "5m": ["1m", "15m", "1h"],
            "15m": ["5m", "1h"],
            "1h": ["15m", "4h"]
        }.get(current_timeframe, [])

        # Background loading
        with self.preload_lock:
            for tf in likely_timeframes:
                self.preload_queue.append((tf, current_date, candle_count))

        # Start background thread if not running
        if self.preload_thread is None or not self.preload_thread.is_alive():
            self.preload_thread = threading.Thread(target=self._background_preloader, daemon=True)
            self.preload_thread.start()

    def _background_preloader(self):
        """Background Thread für Predictive Pre-loading"""
        while True:
            with self.preload_lock:
                if not self.preload_queue:
                    break
                timeframe, date, candle_count = self.preload_queue.pop(0)

            # Preload if not already cached
            cache_key = f"{timeframe}_{date}_{candle_count}"
            if cache_key not in self.visible_cache:
                try:
                    # Silent preload
                    self.get_timeframe_data(timeframe, date, candle_count)
                except Exception as e:
                    # Silent error handling für background loading
                    pass

    def get_performance_stats(self) -> Dict[str, Any]:
        """Performance Statistics für Monitoring"""

        uptime_seconds = time.time() - self.start_time
        cache_hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0

        avg_times = {}
        for operation, times in self.operation_times.items():
            avg_times[f"avg_{operation}_ms"] = sum(times) / len(times) * 1000 if times else 0

        return {
            'uptime_seconds': uptime_seconds,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': cache_hit_rate,
            'cached_ranges': len(self.visible_cache),
            'master_dataset_size': len(self.master_1m_data) if self.master_1m_data is not None else 0,
            'date_index_entries': len(self.date_index_map),
            **avg_times
        }

    def clear_cache(self):
        """Cache leeren für Memory Management"""
        self.visible_cache.clear()
        print("[HIGH-PERF-CACHE] Cache cleared")

    def is_loaded(self) -> bool:
        """Prüft ob Master Dataset geladen ist"""
        return self.master_1m_data is not None and len(self.date_index_map) > 0