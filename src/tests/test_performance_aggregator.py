"""
Tests für Performance Aggregator
Testet die optimierte Timeframe-Aggregation und Caching-Funktionalität
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Pfad für Imports hinzufügen
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.data.performance_aggregator import PerformanceAggregator, get_performance_aggregator


class TestPerformanceAggregator:
    """Test Suite für Performance Aggregator"""

    @pytest.fixture
    def sample_data(self):
        """Erstellt Test-DataFrame mit 1-Minuten OHLCV-Daten"""
        # 1000 Minuten Testdaten (ca. 16.7 Stunden)
        dates = pd.date_range(start='2024-01-01 09:30:00', periods=1000, freq='1min')

        # Simuliere realistische OHLCV-Daten
        np.random.seed(42)  # Für reproduzierbare Tests
        base_price = 100.0
        prices = [base_price]

        for i in range(999):
            change = np.random.normal(0, 0.1)  # Kleine Preisänderungen
            new_price = max(prices[-1] + change, 0.01)  # Verhindere negative Preise
            prices.append(new_price)

        test_data = []
        for i, (timestamp, price) in enumerate(zip(dates, prices)):
            # OHLC um den Preis generieren
            volatility = 0.05
            high = price + abs(np.random.normal(0, volatility))
            low = price - abs(np.random.normal(0, volatility))
            open_price = prices[i-1] if i > 0 else price
            close_price = price
            volume = np.random.randint(1000, 5000)

            test_data.append({
                'Open': open_price,
                'High': high,
                'Low': low,
                'Close': close_price,
                'Volume': volume
            })

        return pd.DataFrame(test_data, index=dates)

    @pytest.fixture
    def aggregator(self):
        """Erstellt Performance Aggregator Instanz für Tests"""
        return PerformanceAggregator(cache_dir="src/tests/test_cache")

    def test_aggregator_initialization(self, aggregator):
        """Test: Aggregator wird korrekt initialisiert"""
        assert aggregator is not None
        assert aggregator.cache_dir == "src/tests/test_cache"
        assert '1m' in aggregator.timeframe_config
        assert '5m' in aggregator.timeframe_config
        assert aggregator.timeframe_config['1m']['max_candles'] == 2000
        assert aggregator.timeframe_config['5m']['max_candles'] == 1000

    def test_singleton_pattern(self):
        """Test: Singleton Pattern funktioniert korrekt"""
        aggregator1 = get_performance_aggregator()
        aggregator2 = get_performance_aggregator()
        assert aggregator1 is aggregator2  # Gleiche Instanz

    def test_optimal_data_range_limiting(self, aggregator, sample_data):
        """Test: Adaptive Datenlimits funktionieren"""
        # Test mit großem Dataset
        large_data = sample_data.copy()

        # 5m Timeframe sollte auf max_candles limitiert werden
        limited_5m = aggregator.get_optimal_data_range(large_data, '5m')
        expected_max = aggregator.timeframe_config['5m']['max_candles'] * 2  # 2x für Aggregation
        assert len(limited_5m) <= expected_max

        # 1m Timeframe sollte auf max_candles limitiert werden
        limited_1m = aggregator.get_optimal_data_range(large_data, '1m')
        expected_max_1m = aggregator.timeframe_config['1m']['max_candles'] * 2
        assert len(limited_1m) <= expected_max_1m

    def test_fast_aggregate_1m_passthrough(self, aggregator, sample_data):
        """Test: 1m Daten werden direkt konvertiert (kein Aggregation)"""
        result = aggregator.fast_aggregate(sample_data.head(100), '1m')

        assert len(result) == 100  # Keine Aggregation bei 1m
        assert all('time' in candle for candle in result)
        assert all('open' in candle for candle in result)
        assert all('high' in candle for candle in result)
        assert all('low' in candle for candle in result)
        assert all('close' in candle for candle in result)
        assert all('volume' in candle for candle in result)

    def test_fast_aggregate_5m_grouping(self, aggregator, sample_data):
        """Test: 5m Aggregation funktioniert korrekt"""
        # Verwende exakt 10 Minuten Daten (sollte 2 x 5m Kerzen ergeben)
        test_data = sample_data.head(10)
        result = aggregator.fast_aggregate(test_data, '5m')

        # Sollte weniger Kerzen haben als Input
        assert len(result) <= len(test_data)
        assert len(result) >= 1  # Mindestens eine Kerze

        # Prüfe OHLCV-Format
        for candle in result:
            assert isinstance(candle['time'], int)  # Unix timestamp
            assert isinstance(candle['open'], float)
            assert isinstance(candle['high'], float)
            assert isinstance(candle['low'], float)
            assert isinstance(candle['close'], float)
            assert isinstance(candle['volume'], int)

            # Prüfe OHLC-Logik
            assert candle['high'] >= candle['open']
            assert candle['high'] >= candle['close']
            assert candle['low'] <= candle['open']
            assert candle['low'] <= candle['close']

    def test_caching_functionality(self, aggregator, sample_data):
        """Test: Multi-Level Caching funktioniert"""
        test_data = sample_data.head(100)

        # Erste Abfrage - sollte Cache Miss sein
        aggregator.clear_cache()  # Cache leeren für sauberen Test
        result1 = aggregator.get_aggregated_data_performance(test_data, '5m')

        # Zweite Abfrage - sollte Cache Hit sein
        result2 = aggregator.get_aggregated_data_performance(test_data, '5m')

        assert result1 == result2  # Gleiche Ergebnisse

        # Cache Info prüfen
        cache_info = aggregator.get_cache_info()
        assert cache_info['total_requests'] >= 2
        assert cache_info['hit_rate'] != '0.0%'  # Mindestens ein Hit

    def test_priority_timeframes_precomputing(self, aggregator, sample_data):
        """Test: Priority Timeframes werden korrekt precomputed"""
        test_data = sample_data.head(200)

        # Cache leeren
        aggregator.clear_cache()

        # Precompute priority timeframes
        aggregator.precompute_priority_timeframes(test_data)

        # Cache sollte jetzt 5m, 15m, 1h enthalten
        cache_info = aggregator.get_cache_info()
        assert cache_info['hot_cache_size'] > 0 or cache_info['warm_cache_size'] > 0

    def test_cache_management_priority_system(self, aggregator, sample_data):
        """Test: Cache Management nach Priorität funktioniert"""
        test_data = sample_data.head(100)
        aggregator.clear_cache()

        # Teste verschiedene Timeframes mit unterschiedlichen Prioritäten
        result_1m = aggregator.get_aggregated_data_performance(test_data, '1m')  # Priority 1
        result_5m = aggregator.get_aggregated_data_performance(test_data, '5m')  # Priority 4
        result_1h = aggregator.get_aggregated_data_performance(test_data, '1h')  # Priority 7

        cache_info = aggregator.get_cache_info()

        # High-priority timeframes sollten im hot cache sein
        assert cache_info['hot_cache_size'] > 0

        # Alle Ergebnisse sollten gültig sein
        assert len(result_1m) > 0
        assert len(result_5m) > 0
        assert len(result_1h) > 0

    def test_convert_to_chart_format(self, aggregator, sample_data):
        """Test: Chart Format Konvertierung funktioniert korrekt"""
        test_data = sample_data.head(10)
        result = aggregator.convert_to_chart_format(test_data)

        assert len(result) == 10

        for candle in result:
            # Prüfe erforderliche Felder
            assert 'time' in candle
            assert 'open' in candle
            assert 'high' in candle
            assert 'low' in candle
            assert 'close' in candle
            assert 'volume' in candle

            # Prüfe Datentypen
            assert isinstance(candle['time'], int)  # Unix timestamp
            assert isinstance(candle['open'], float)
            assert isinstance(candle['high'], float)
            assert isinstance(candle['low'], float)
            assert isinstance(candle['close'], float)
            assert isinstance(candle['volume'], int)

    def test_performance_with_large_dataset(self, aggregator):
        """Test: Performance mit großem Dataset"""
        import time

        # Erstelle großes Dataset (10.000 Kerzen)
        dates = pd.date_range(start='2024-01-01', periods=10000, freq='1min')
        large_data = pd.DataFrame({
            'Open': np.random.randn(10000).cumsum() + 100,
            'High': np.random.randn(10000).cumsum() + 102,
            'Low': np.random.randn(10000).cumsum() + 98,
            'Close': np.random.randn(10000).cumsum() + 100,
            'Volume': np.random.randint(1000, 5000, 10000)
        }, index=dates)

        # Messe Performance
        start_time = time.time()
        result = aggregator.get_aggregated_data_performance(large_data, '5m')
        end_time = time.time()

        processing_time = (end_time - start_time) * 1000  # in ms

        # Performance sollte unter 1000ms sein
        assert processing_time < 1000, f"Processing time {processing_time:.2f}ms too slow"
        assert len(result) > 0
        assert len(result) <= aggregator.timeframe_config['5m']['max_candles']

    def test_cache_clear_functionality(self, aggregator, sample_data):
        """Test: Cache Clear Funktionalität"""
        test_data = sample_data.head(50)

        # Fülle Cache
        aggregator.get_aggregated_data_performance(test_data, '5m')
        cache_info_before = aggregator.get_cache_info()

        # Cache leeren
        aggregator.clear_cache()
        cache_info_after = aggregator.get_cache_info()

        # Cache sollte leer sein
        assert cache_info_after['hot_cache_size'] == 0
        assert cache_info_after['warm_cache_size'] == 0
        assert cache_info_after['total_requests'] == 0

    def teardown_method(self):
        """Cleanup nach jedem Test"""
        # Test-Cache-Verzeichnis aufräumen
        import shutil
        test_cache_dir = "src/tests/test_cache"
        if os.path.exists(test_cache_dir):
            shutil.rmtree(test_cache_dir)


if __name__ == "__main__":
    # Direkter Test-Run für Debugging
    pytest.main([__file__, "-v"])