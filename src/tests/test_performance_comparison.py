"""
Performance Comparison Tests
===========================
Vergleicht Performance zwischen altem CSV-System und neuem High-Performance Cache
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


class LegacyCSVSystem:
    """Simuliert das alte CSV-basierte System für Performance-Vergleich"""

    def __init__(self, csv_files):
        self.csv_files = csv_files

    def change_timeframe_legacy(self, timeframe, target_date=None, candle_count=200):
        """Simuliert die alte Timeframe-Change Logic"""
        start_time = time.time()

        # Simulate CSV file reading (I/O operation)
        if timeframe in self.csv_files:
            df = pd.read_csv(self.csv_files[timeframe])

            # DateTime processing (slow)
            df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
            df['time'] = df['datetime'].astype(int) // 10**9

            if target_date:
                # Linear search through data (O(n) operation)
                df['date_only'] = df['datetime'].dt.date
                target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
                target_rows = df[df['date_only'] == target_date_obj]

                if len(target_rows) > 0:
                    end_index = target_rows.index[0] + 1
                    start_index = max(0, end_index - candle_count)
                    df = df.iloc[start_index:end_index]
                else:
                    df = df.tail(candle_count)
            else:
                df = df.tail(candle_count)

            # Convert to chart format (slow iteration)
            chart_data = []
            for _, row in df.iterrows():
                chart_data.append({
                    'time': int(row['time']),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume'])
                })

            elapsed_time = time.time() - start_time
            return {
                'data': chart_data,
                'response_time_ms': elapsed_time * 1000,
                'system': 'legacy_csv'
            }

        return {'data': [], 'response_time_ms': 0, 'system': 'legacy_csv'}

    def go_to_date_legacy(self, date_str, timeframe, candle_count=200):
        """Simuliert die alte Go To Date Logic"""
        return self.change_timeframe_legacy(timeframe, date_str, candle_count)


class TestPerformanceComparison:
    """Performance Comparison Test Suite"""

    @pytest.fixture
    def test_data_files(self):
        """Erstellt Testdaten für beide Systeme"""
        # Generate realistic test data
        timeframes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60
        }

        files = {}
        master_1m_data = None

        for tf, multiplier in timeframes.items():
            start_date = datetime(2024, 12, 1)
            candles_count = 5000 // multiplier  # Proportional data size

            data = []
            for i in range(candles_count):
                timestamp = start_date + timedelta(minutes=i * multiplier)
                base_price = 20000 + (i * 0.2)

                candle = {
                    'Date': timestamp.strftime('%d.%m.%Y'),
                    'Time': timestamp.strftime('%H:%M'),
                    'Open': base_price + np.random.uniform(-10, 10),
                    'High': base_price + np.random.uniform(0, 15),
                    'Low': base_price + np.random.uniform(-15, 0),
                    'Close': base_price + np.random.uniform(-10, 10),
                    'Volume': np.random.randint(100, 2000)
                }
                data.append(candle)

                # Master 1m data for High-Performance Cache
                if tf == "1m":
                    candle['time'] = int(timestamp.timestamp())
                    candle['datetime'] = timestamp

            df = pd.DataFrame(data)

            # Create temporary CSV file
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'_{tf}.csv')
            df.to_csv(temp_file.name, index=False)
            temp_file.close()
            files[tf] = temp_file.name

            if tf == "1m":
                master_1m_data = temp_file.name

        yield files, master_1m_data

        # Cleanup
        for file_path in files.values():
            os.unlink(file_path)

    @pytest.fixture
    def legacy_system(self, test_data_files):
        """Legacy CSV System Setup"""
        csv_files, _ = test_data_files
        return LegacyCSVSystem(csv_files)

    @pytest.fixture
    def high_perf_system(self, test_data_files):
        """High-Performance Cache System Setup"""
        _, master_csv = test_data_files
        cache = HighPerformanceChartCache(cache_size_mb=100)
        success = cache.load_master_dataset(master_csv)
        assert success, "Failed to load high-performance cache"
        return cache

    def test_timeframe_switching_speed(self, legacy_system, high_perf_system):
        """Vergleicht Timeframe-Switching Speed"""
        timeframes = ["1m", "5m", "15m", "1h"]
        iterations = 10

        print(f"\n{'='*60}")
        print("TIMEFRAME SWITCHING PERFORMANCE COMPARISON")
        print(f"{'='*60}")

        legacy_times = []
        high_perf_times = []

        for iteration in range(iterations):
            tf = timeframes[iteration % len(timeframes)]

            # Legacy System Test
            start_time = time.time()
            legacy_result = legacy_system.change_timeframe_legacy(tf)
            legacy_time = time.time() - start_time
            legacy_times.append(legacy_time * 1000)

            # High-Performance System Test
            start_time = time.time()
            hp_result = high_perf_system.get_timeframe_data(tf, "2024-12-01", 200)
            hp_time = time.time() - start_time
            high_perf_times.append(hp_time * 1000)

            print(f"Iteration {iteration+1:2d} ({tf:>2s}): Legacy {legacy_time*1000:6.1f}ms | High-Perf {hp_time*1000:6.1f}ms")

        # Performance Analysis
        avg_legacy = sum(legacy_times) / len(legacy_times)
        avg_high_perf = sum(high_perf_times) / len(high_perf_times)
        speedup_factor = avg_legacy / avg_high_perf if avg_high_perf > 0 else 0

        print(f"\n{'Results:':<12} {'Legacy':>12} {'High-Perf':>12} {'Speedup':>12}")
        print(f"{'Average:':<12} {avg_legacy:8.1f}ms {avg_high_perf:8.1f}ms {speedup_factor:8.1f}x")
        print(f"{'Maximum:':<12} {max(legacy_times):8.1f}ms {max(high_perf_times):8.1f}ms")
        print(f"{'Minimum:':<12} {min(legacy_times):8.1f}ms {min(high_perf_times):8.1f}ms")

        # Performance Assertions
        assert avg_high_perf < avg_legacy, "High-Performance system should be faster"
        assert speedup_factor >= 5, f"Should be at least 5x faster (actual: {speedup_factor:.1f}x)"

    def test_go_to_date_speed(self, legacy_system, high_perf_system):
        """Vergleicht Go To Date Speed"""
        test_dates = ["2024-12-01", "2024-12-05", "2024-12-10", "2024-12-15"]
        timeframes = ["1m", "5m", "15m"]

        print(f"\n{'='*60}")
        print("GO TO DATE PERFORMANCE COMPARISON")
        print(f"{'='*60}")

        legacy_times = []
        high_perf_times = []

        for date_str in test_dates:
            for tf in timeframes:
                # Legacy System Test
                start_time = time.time()
                legacy_result = legacy_system.go_to_date_legacy(date_str, tf)
                legacy_time = time.time() - start_time
                legacy_times.append(legacy_time * 1000)

                # High-Performance System Test
                start_time = time.time()
                hp_result = high_perf_system.get_timeframe_data(tf, date_str, 200)
                hp_time = time.time() - start_time
                high_perf_times.append(hp_time * 1000)

                print(f"{date_str} ({tf:>2s}): Legacy {legacy_time*1000:6.1f}ms | High-Perf {hp_time*1000:6.1f}ms")

        # Performance Analysis
        avg_legacy = sum(legacy_times) / len(legacy_times)
        avg_high_perf = sum(high_perf_times) / len(high_perf_times)
        speedup_factor = avg_legacy / avg_high_perf if avg_high_perf > 0 else 0

        print(f"\n{'Results:':<12} {'Legacy':>12} {'High-Perf':>12} {'Speedup':>12}")
        print(f"{'Average:':<12} {avg_legacy:8.1f}ms {avg_high_perf:8.1f}ms {speedup_factor:8.1f}x")

        # Performance Assertions
        assert avg_high_perf < avg_legacy, "High-Performance Go To Date should be faster"
        assert speedup_factor >= 10, f"Should be at least 10x faster (actual: {speedup_factor:.1f}x)"

    def test_memory_usage_efficiency(self, legacy_system, high_perf_system):
        """Vergleicht Memory Usage Efficiency"""
        import tracemalloc

        # Start memory tracing
        tracemalloc.start()

        print(f"\n{'='*60}")
        print("MEMORY USAGE COMPARISON")
        print(f"{'='*60}")

        # Test Legacy System Memory Usage
        snapshot1 = tracemalloc.take_snapshot()

        # Simulate multiple timeframe operations (Legacy)
        for i in range(50):
            tf = ["1m", "5m", "15m"][i % 3]
            legacy_system.change_timeframe_legacy(tf)

        snapshot2 = tracemalloc.take_snapshot()
        legacy_stats = snapshot2.compare_to(snapshot1, 'lineno')

        # Test High-Performance System Memory Usage
        snapshot3 = tracemalloc.take_snapshot()

        # Same operations (High-Performance)
        for i in range(50):
            tf = ["1m", "5m", "15m"][i % 3]
            high_perf_system.get_timeframe_data(tf, "2024-12-01", 200)

        snapshot4 = tracemalloc.take_snapshot()
        hp_stats = snapshot4.compare_to(snapshot3, 'lineno')

        tracemalloc.stop()

        # Memory usage analysis
        legacy_memory = sum(stat.size_diff for stat in legacy_stats[:10])
        hp_memory = sum(stat.size_diff for stat in hp_stats[:10])

        print(f"Legacy System Memory Growth:     {legacy_memory / 1024 / 1024:.1f} MB")
        print(f"High-Performance Memory Growth: {hp_memory / 1024 / 1024:.1f} MB")

        # High-Performance should use less memory due to caching
        if legacy_memory > 0:
            memory_efficiency = legacy_memory / hp_memory if hp_memory > 0 else float('inf')
            print(f"Memory Efficiency Factor:       {memory_efficiency:.1f}x")

    def test_cache_effectiveness(self, high_perf_system):
        """Test Cache Hit Rate und Effectiveness"""
        cache = high_perf_system

        print(f"\n{'='*60}")
        print("CACHE EFFECTIVENESS ANALYSIS")
        print(f"{'='*60}")

        # Clear cache for clean test
        cache.clear_cache()

        # Warm up phase - populate cache
        timeframes = ["1m", "5m", "15m", "1h"]
        dates = ["2024-12-01", "2024-12-02", "2024-12-03"]

        print("Phase 1: Cache Warm-up")
        for date in dates:
            for tf in timeframes:
                result = cache.get_timeframe_data(tf, date, 200)

        warmup_stats = cache.get_performance_stats()
        print(f"Cache Hits: {warmup_stats['cache_hits']}, Misses: {warmup_stats['cache_misses']}")

        # Test phase - repeat requests (should be cache hits)
        print("\nPhase 2: Cache Hit Testing")
        hit_times = []

        for _ in range(20):
            date = dates[_ % len(dates)]
            tf = timeframes[_ % len(timeframes)]

            start_time = time.time()
            result = cache.get_timeframe_data(tf, date, 200)
            hit_time = time.time() - start_time

            hit_times.append(hit_time * 1000)

        final_stats = cache.get_performance_stats()
        cache_hit_rate = final_stats['cache_hit_rate'] * 100

        print(f"Final Cache Hit Rate: {cache_hit_rate:.1f}%")
        print(f"Average Cache Hit Time: {sum(hit_times)/len(hit_times):.1f}ms")

        # Assertions
        assert cache_hit_rate > 80, f"Cache hit rate should be >80% (actual: {cache_hit_rate:.1f}%)"
        assert sum(hit_times)/len(hit_times) < 5, "Cache hits should be <5ms average"

    def test_concurrent_request_handling(self, high_perf_system):
        """Test Concurrent Request Performance"""
        import threading
        import queue

        print(f"\n{'='*60}")
        print("CONCURRENT REQUEST HANDLING TEST")
        print(f"{'='*60}")

        results_queue = queue.Queue()
        threads = []
        num_threads = 10
        requests_per_thread = 5

        def worker(thread_id):
            """Worker function für concurrent requests"""
            thread_times = []
            for i in range(requests_per_thread):
                tf = ["1m", "5m", "15m", "1h"][i % 4]
                date = "2024-12-01"

                start_time = time.time()
                result = high_perf_system.get_timeframe_data(tf, date, 200)
                elapsed_time = time.time() - start_time

                thread_times.append(elapsed_time * 1000)

            results_queue.put((thread_id, thread_times))

        # Start concurrent threads
        start_time = time.time()

        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # Collect results
        all_times = []
        while not results_queue.empty():
            thread_id, times = results_queue.get()
            all_times.extend(times)
            print(f"Thread {thread_id}: Avg {sum(times)/len(times):.1f}ms")

        avg_concurrent_time = sum(all_times) / len(all_times)
        total_requests = num_threads * requests_per_thread

        print(f"\nConcurrency Results:")
        print(f"Total Requests: {total_requests}")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Requests/second: {total_requests/total_time:.1f}")
        print(f"Average Response Time: {avg_concurrent_time:.1f}ms")

        # Performance assertions for concurrent handling
        assert avg_concurrent_time < 100, f"Concurrent avg time should be <100ms (actual: {avg_concurrent_time:.1f}ms)"
        assert total_requests/total_time > 20, f"Should handle >20 req/s (actual: {total_requests/total_time:.1f})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])