"""Unit Tests für charts.core.cache_manager - Testet ChartDataCache"""
import pytest
from charts.core.cache_manager import ChartDataCache


class TestChartDataCache:
    """Tests für ChartDataCache"""

    @pytest.fixture
    def cache(self):
        return ChartDataCache()

    def test_cache_initialization(self, cache):
        """Test: Cache wird korrekt initialisiert"""
        assert cache.timeframe_data == {}
        assert cache.loaded_timeframes == set()
        assert '5m' in cache.available_timeframes

    def test_available_timeframes_complete(self, cache):
        """Test: Alle Timeframes verfügbar"""
        expected = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]
        assert cache.available_timeframes == expected

    def test_get_timeframe_info_not_loaded(self, cache):
        """Test: Info für nicht-geladenen Timeframe gibt None zurück"""
        info = cache.get_timeframe_info('5m')
        assert info is None

    # Note: Full load tests würden tatsächliche CSV-Dateien benötigen
    # Diese werden in Integration Tests getestet
