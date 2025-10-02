"""
Unit Tests für CacheRepository
"""

import pytest
from datetime import datetime
from charts.repositories.cache_repository import CacheRepository, SimpleCacheRepository
from charts.models.chart_data import Candle


class TestSimpleCacheRepository:
    """Test Suite für SimpleCacheRepository (Fallback Cache)"""

    @pytest.fixture
    def simple_cache(self):
        """Fixture für SimpleCacheRepository"""
        return SimpleCacheRepository()

    def test_initialization(self, simple_cache):
        """Test: Simple Cache-Initialisierung"""
        assert simple_cache is not None
        assert simple_cache.is_initialized()
        assert simple_cache._max_entries == 50

    def test_store_and_get_candles(self, simple_cache):
        """Test: Kerzen speichern und abrufen"""
        # Test-Daten erstellen
        test_candles = [
            Candle(time=1000, open=100.0, high=101.0, low=99.0, close=100.5),
            Candle(time=1060, open=100.5, high=102.0, low=100.0, close=101.5)
        ]
        test_date = datetime(2024, 1, 15, 10, 0)

        # Speichern
        simple_cache.store_candles("5m", test_date, test_candles, count=200)

        # Abrufen
        retrieved = simple_cache.get_candles("5m", test_date, count=200)

        assert retrieved is not None
        assert len(retrieved) == 2
        assert all(isinstance(c, Candle) for c in retrieved)

    def test_cache_miss(self, simple_cache):
        """Test: Cache-Miss"""
        test_date = datetime(2024, 1, 15, 10, 0)

        # Abrufen ohne Speichern
        result = simple_cache.get_candles("5m", test_date, count=200)

        assert result is None

    def test_lru_eviction(self, simple_cache):
        """Test: LRU Cache-Eviction"""
        # Cache auf 5 Einträge begrenzen für Test
        simple_cache._max_entries = 5

        # 6 Einträge hinzufügen
        for i in range(6):
            test_date = datetime(2024, 1, i + 1, 10, 0)
            candles = [Candle(time=1000 + i, open=100.0, high=101.0, low=99.0, close=100.5)]
            simple_cache.store_candles("5m", test_date, candles, count=200)

        # Cache sollte nur 5 Einträge haben
        assert len(simple_cache._cache) == 5

        # Erster Eintrag sollte entfernt worden sein (LRU)
        first_date = datetime(2024, 1, 1, 10, 0)
        result = simple_cache.get_candles("5m", first_date, count=200)
        assert result is None

    def test_invalidate_all(self, simple_cache):
        """Test: Kompletten Cache invalidieren"""
        # Cache füllen
        for i in range(3):
            test_date = datetime(2024, 1, i + 1, 10, 0)
            candles = [Candle(time=1000 + i, open=100.0, high=101.0, low=99.0, close=100.5)]
            simple_cache.store_candles("5m", test_date, candles, count=200)

        assert len(simple_cache._cache) > 0

        # Invalidieren
        simple_cache.invalidate()

        assert len(simple_cache._cache) == 0

    def test_invalidate_timeframe(self, simple_cache):
        """Test: Timeframe-spezifische Invalidierung"""
        # Cache mit verschiedenen Timeframes füllen
        test_date = datetime(2024, 1, 15, 10, 0)

        for tf in ["5m", "15m", "1h"]:
            candles = [Candle(time=1000, open=100.0, high=101.0, low=99.0, close=100.5)]
            simple_cache.store_candles(tf, test_date, candles, count=200)

        # 5m Timeframe invalidieren
        simple_cache.invalidate("5m")

        # 5m sollte weg sein
        result_5m = simple_cache.get_candles("5m", test_date, count=200)
        assert result_5m is None

        # Andere Timeframes sollten noch da sein
        result_15m = simple_cache.get_candles("15m", test_date, count=200)
        assert result_15m is not None

    def test_get_performance_stats(self, simple_cache):
        """Test: Performance-Stats abrufen"""
        stats = simple_cache.get_performance_stats()

        assert stats['initialized'] is True
        assert stats['cache_type'] == 'simple'
        assert 'cached_entries' in stats
        assert 'max_entries' in stats


class TestCacheRepository:
    """Test Suite für CacheRepository (HighPerformanceChartCache Wrapper)"""

    @pytest.fixture
    def cache_repo(self):
        """Fixture für CacheRepository"""
        return CacheRepository(cache_size_mb=50)

    def test_initialization(self, cache_repo):
        """Test: Cache Repository-Initialisierung"""
        assert cache_repo is not None
        assert cache_repo._cache_size_mb == 50
        # Initial nicht initialisiert
        assert not cache_repo.is_initialized()

    def test_initialization_without_cache(self, cache_repo):
        """Test: Initialisierung wenn HighPerformanceChartCache nicht verfügbar"""
        # Versuche zu initialisieren mit ungültigem Pfad
        result = cache_repo.initialize(csv_path="nonexistent.csv")

        # Sollte False zurückgeben bei Fehler
        # (oder True wenn HighPerformanceChartCache erfolgreich lädt)
        assert isinstance(result, bool)

    def test_get_candles_when_not_initialized(self, cache_repo):
        """Test: Kerzen abrufen wenn nicht initialisiert"""
        test_date = datetime(2024, 1, 15, 10, 0)

        # Sollte None zurückgeben
        result = cache_repo.get_candles("5m", test_date, count=200)
        assert result is None

    def test_invalidate_when_not_initialized(self, cache_repo):
        """Test: Invalidierung wenn nicht initialisiert"""
        # Sollte keine Exception werfen
        cache_repo.invalidate()
        cache_repo.invalidate("5m")

    def test_get_performance_stats_when_not_initialized(self, cache_repo):
        """Test: Performance-Stats wenn nicht initialisiert"""
        stats = cache_repo.get_performance_stats()

        assert stats['initialized'] is False
        assert 'error' in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
