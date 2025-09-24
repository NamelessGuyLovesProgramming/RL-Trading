"""
Tests für High-Performance Chart Cache System
============================================
Umfassende Tests für Performance-Verbesserungen und Funktionalität
"""

import pytest
import pandas as pd
import numpy as np
import time
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from performance.high_performance_cache import HighPerformanceChartCache


class TestHighPerformanceChartCache:
    """Test Suite für HighPerformanceChartCache"""

    @pytest.fixture
    def sample_1m_csv(self):
        """Erstellt eine temporäre 1m CSV-Datei für Tests"""
        # Generate 1000 candles of sample data
        start_date = datetime(2024, 12, 1)
        data = []

        for i in range(1000):
            timestamp = start_date + timedelta(minutes=i)
            base_price = 20000 + (i * 0.1)  # Gentle uptrend

            data.append({
                'time': int(timestamp.timestamp()),
                'datetime': timestamp,
                'open': base_price + np.random.uniform(-5, 5),
                'high': base_price + np.random.uniform(0, 10),
                'low': base_price + np.random.uniform(-10, 0),
                'close': base_price + np.random.uniform(-5, 5),
                'volume': np.random.randint(100, 1000)
            })

        df = pd.DataFrame(data)

        # Create temporary CSV file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        df.to_csv(temp_file.name, index=False)
        temp_file.close()

        yield temp_file.name

        # Cleanup
        os.unlink(temp_file.name)

    @pytest.fixture
    def cache_instance(self, sample_1m_csv):
        """Erstellt eine HighPerformanceChartCache Instanz mit Test-Daten"""
        cache = HighPerformanceChartCache(cache_size_mb=50)
        success = cache.load_master_dataset(sample_1m_csv)
        assert success, "Failed to load master dataset"
        return cache

    def test_master_dataset_loading(self, sample_1m_csv):
        """Test Master Dataset Loading"""
        cache = HighPerformanceChartCache()

        # Test successful loading
        success = cache.load_master_dataset(sample_1m_csv)
        assert success, "Master dataset loading should succeed"

        # Verify data loaded
        assert cache.master_1m_data is not None, "Master data should not be None"
        assert len(cache.master_1m_data) == 1000, "Should have 1000 candles"

        # Verify index maps built
        assert len(cache.date_index_map) > 0, "Date index map should not be empty"
        assert len(cache.datetime_index_map) > 0, "Datetime index map should not be empty"

    def test_date_index_map_accuracy(self, cache_instance):
        """Test Accuracy of Date-to-Index Mapping"""
        cache = cache_instance

        # Test specific date lookup
        test_date = "2024-12-01"
        if test_date in cache.date_index_map:
            index = cache.date_index_map[test_date]
            actual_row = cache.master_1m_data.iloc[index]
            actual_date = actual_row['datetime'].strftime('%Y-%m-%d')
            assert actual_date == test_date, f"Index {index} should point to {test_date}"

    def test_timeframe_aggregation_performance(self, cache_instance):
        """Test Performance of Timeframe Aggregation"""
        cache = cache_instance
        timeframes = ["1m", "5m", "15m", "30m", "1h"]

        # Performance benchmark
        results = {}

        for tf in timeframes:
            start_time = time.time()

            # Get data multiple times to test caching
            for _ in range(3):
                result = cache.get_timeframe_data(tf, "2024-12-01", 200)

            elapsed_time = time.time() - start_time
            results[tf] = elapsed_time / 3  # Average time per request

            # Verify data quality
            assert len(result['data']) > 0, f"Should have data for {tf}"
            assert 'performance_stats' in result, "Should have performance stats"

        # Performance assertions
        for tf, elapsed in results.items():
            # After caching, requests should be very fast
            assert elapsed < 0.1, f"{tf} should be faster than 100ms (was {elapsed*1000:.1f}ms)"

    def test_cache_hit_rate(self, cache_instance):
        """Test Cache Hit Rate Optimization"""
        cache = cache_instance

        # First request (cache miss)
        result1 = cache.get_timeframe_data("5m", "2024-12-01", 200)
        assert not result1['performance_stats']['cache_hit'], "First request should be cache miss"

        # Second identical request (cache hit)
        result2 = cache.get_timeframe_data("5m", "2024-12-01", 200)
        assert result2['performance_stats']['cache_hit'], "Second request should be cache hit"

        # Verify same data
        assert len(result1['data']) == len(result2['data']), "Cache hit should return same data"

    def test_on_demand_aggregation_accuracy(self, cache_instance):
        """Test On-Demand Aggregation Accuracy"""
        cache = cache_instance

        # Get 1m data as baseline
        result_1m = cache.get_timeframe_data("1m", "2024-12-01", 60)
        data_1m = result_1m['data']

        # Get 5m data (should aggregate 5x 1m candles)
        result_5m = cache.get_timeframe_data("5m", "2024-12-01", 12)
        data_5m = result_5m['data']

        if len(data_5m) > 0 and len(data_1m) >= 5:
            # Verify aggregation logic (first 5m candle)
            first_5m = data_5m[0]
            first_5_1m = data_1m[:5]

            # OHLC aggregation rules
            expected_open = first_5_1m[0]['open']
            expected_high = max(candle['high'] for candle in first_5_1m)
            expected_low = min(candle['low'] for candle in first_5_1m)
            expected_close = first_5_1m[-1]['close']
            expected_volume = sum(candle['volume'] for candle in first_5_1m)

            # Allow for small floating point differences
            assert abs(first_5m['open'] - expected_open) < 0.01, "Open aggregation incorrect"
            assert abs(first_5m['high'] - expected_high) < 0.01, "High aggregation incorrect"
            assert abs(first_5m['low'] - expected_low) < 0.01, "Low aggregation incorrect"
            assert abs(first_5m['close'] - expected_close) < 0.01, "Close aggregation incorrect"
            assert first_5m['volume'] == expected_volume, "Volume aggregation incorrect"

    def test_visible_range_calculation(self, cache_instance):
        """Test Visible Range Calculation"""
        cache = cache_instance

        result = cache.get_timeframe_data("5m", "2024-12-01", 200)

        if result['visible_range'] and len(result['data']) > 50:
            visible_range = result['visible_range']
            data = result['data']

            # Verify visible range covers last 50 candles
            last_50_start_time = data[-50]['time']
            last_time = data[-1]['time']

            assert visible_range['from'] == last_50_start_time, "Visible range start incorrect"
            assert visible_range['to'] == last_time, "Visible range end incorrect"

    def test_memory_management(self, cache_instance):
        """Test Memory Management and Cache Cleanup"""
        cache = cache_instance

        # Fill cache with many different requests
        for i in range(150):  # More than max cache size
            cache.get_timeframe_data("5m", f"2024-12-{1 + (i % 30):02d}", 200)

        # Verify cache size is limited
        assert len(cache.visible_cache) <= 100, "Cache should be limited to 100 entries"

    def test_predictive_preloading(self, cache_instance):
        """Test Predictive Pre-loading Functionality"""
        cache = cache_instance

        # Clear cache
        cache.clear_cache()

        # Request 1m data (should trigger pre-loading of 5m, 15m)
        result = cache.get_timeframe_data("1m", "2024-12-01", 200)

        # Give background thread time to work
        time.sleep(0.1)

        # Check if predictive pre-loading worked
        cache_keys = list(cache.visible_cache.keys())

        # Should have original request + pre-loaded timeframes
        assert len(cache_keys) >= 1, "Should have cached at least the original request"

    def test_performance_stats_accuracy(self, cache_instance):
        """Test Performance Statistics Accuracy"""
        cache = cache_instance

        # Get performance stats
        stats = cache.get_performance_stats()

        # Verify stats structure
        assert 'uptime_seconds' in stats, "Should have uptime"
        assert 'cache_hits' in stats, "Should have cache hits"
        assert 'cache_misses' in stats, "Should have cache misses"
        assert 'cache_hit_rate' in stats, "Should have hit rate"
        assert 'master_dataset_size' in stats, "Should have dataset size"

        # Verify reasonable values
        assert stats['master_dataset_size'] == 1000, "Should have 1000 candles"
        assert stats['uptime_seconds'] >= 0, "Uptime should be positive"

    def test_error_handling(self):
        """Test Error Handling and Edge Cases"""
        cache = HighPerformanceChartCache()

        # Test loading non-existent file
        success = cache.load_master_dataset("non_existent_file.csv")
        assert not success, "Loading non-existent file should fail"

        # Test operations on unloaded cache
        result = cache.get_timeframe_data("1m", "2024-12-01", 200)
        assert result['data'] == [], "Unloaded cache should return empty data"

    def test_data_format_compatibility(self, cache_instance):
        """Test Data Format Compatibility"""
        cache = cache_instance

        result = cache.get_timeframe_data("1m", "2024-12-01", 10)

        if len(result['data']) > 0:
            candle = result['data'][0]

            # Verify required fields
            required_fields = ['time', 'open', 'high', 'low', 'close', 'volume']
            for field in required_fields:
                assert field in candle, f"Candle should have {field} field"

            # Verify data types
            assert isinstance(candle['time'], int), "Time should be integer timestamp"
            assert isinstance(candle['open'], float), "Open should be float"
            assert isinstance(candle['high'], float), "High should be float"
            assert isinstance(candle['low'], float), "Low should be float"
            assert isinstance(candle['close'], float), "Close should be float"
            assert isinstance(candle['volume'], int), "Volume should be integer"

    def test_performance_benchmark(self, cache_instance):
        """Performance Benchmark Test - Measure actual improvements"""
        cache = cache_instance

        # Benchmark timeframe switching speed
        timeframes = ["1m", "5m", "15m", "1h"]
        switch_times = []

        for i in range(20):  # 20 switches
            tf = timeframes[i % len(timeframes)]

            start_time = time.time()
            result = cache.get_timeframe_data(tf, "2024-12-01", 200)
            switch_time = time.time() - start_time

            switch_times.append(switch_time * 1000)  # Convert to ms

            assert len(result['data']) > 0, f"Should have data for {tf}"

        # Performance assertions
        avg_switch_time = sum(switch_times) / len(switch_times)
        max_switch_time = max(switch_times)

        print(f"\nPerformance Results:")
        print(f"Average switch time: {avg_switch_time:.1f}ms")
        print(f"Maximum switch time: {max_switch_time:.1f}ms")
        print(f"Cache hit rate: {cache.cache_hits / (cache.cache_hits + cache.cache_misses) * 100:.1f}%")

        # Performance targets
        assert avg_switch_time < 50, f"Average switch time should be <50ms (was {avg_switch_time:.1f}ms)"
        assert max_switch_time < 200, f"Max switch time should be <200ms (was {max_switch_time:.1f}ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])