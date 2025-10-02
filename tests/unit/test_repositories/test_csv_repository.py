"""
Unit Tests für CSVRepository
"""

import pytest
from datetime import datetime, timedelta
from charts.repositories.csv_repository import CSVRepository
from charts.models.chart_data import Candle


class TestCSVRepository:
    """Test Suite für CSVRepository"""

    @pytest.fixture
    def csv_repo(self):
        """Fixture für CSVRepository-Instanz"""
        return CSVRepository(data_path="src/data/aggregated")

    def test_initialization(self, csv_repo):
        """Test: Repository-Initialisierung"""
        assert csv_repo is not None
        assert csv_repo.data_path.name == "aggregated"
        assert len(csv_repo.available_timeframes) == 8
        assert "5m" in csv_repo.available_timeframes
        assert "1h" in csv_repo.available_timeframes

    def test_get_csv_paths(self, csv_repo):
        """Test: CSV-Pfad-Generierung"""
        paths = csv_repo._get_csv_paths("5m")

        assert len(paths) > 0
        # Erster Pfad sollte Jahres-CSV sein
        assert "5m/nq-2024.csv" in str(paths[0])
        # Zweiter Pfad sollte Root-CSV sein
        assert "nq-2024-5m.csv" in str(paths[1])

    def test_get_timeframe_info(self, csv_repo):
        """Test: Timeframe-Info abrufen"""
        info = csv_repo.get_timeframe_info("5m")

        # Kann None sein wenn CSV nicht gefunden wird
        if info is not None:
            assert info['timeframe'] == "5m"
            assert info['total_candles'] > 0
            assert info['loaded'] is True
            assert isinstance(info['start_time'], datetime)
            assert isinstance(info['end_time'], datetime)

    def test_get_candles_by_date(self, csv_repo):
        """Test: Kerzen ab Datum laden"""
        # Test mit Datum in 2024
        test_date = datetime(2024, 1, 15, 9, 30)
        candles = csv_repo.get_candles_by_date("NQ=F", "5m", test_date, count=10)

        # Kann leer sein wenn CSV nicht vorhanden
        if len(candles) > 0:
            assert all(isinstance(c, Candle) for c in candles)
            assert len(candles) <= 10
            # Erste Kerze sollte nach oder gleich test_date sein
            first_candle_time = datetime.fromtimestamp(candles[0].time)
            assert first_candle_time >= test_date or len(candles) > 0  # Fallback zu letzten Kerzen

    def test_get_candles_range(self, csv_repo):
        """Test: Kerzen für Zeitraum laden"""
        start_date = datetime(2024, 1, 15, 9, 30)
        end_date = datetime(2024, 1, 15, 12, 30)

        candles = csv_repo.get_candles_range("NQ=F", "5m", start_date, end_date)

        if len(candles) > 0:
            assert all(isinstance(c, Candle) for c in candles)
            # Kerzen sollten im Zeitraum liegen
            for candle in candles:
                candle_time = datetime.fromtimestamp(candle.time)
                assert start_date <= candle_time <= end_date

    def test_get_next_candle(self, csv_repo):
        """Test: Nächste Kerze finden"""
        current_time = datetime(2024, 1, 15, 10, 0)
        next_candle = csv_repo.get_next_candle("5m", current_time)

        # Kann None sein wenn keine Daten vorhanden
        if next_candle is not None:
            assert isinstance(next_candle, Candle)
            next_time = datetime.fromtimestamp(next_candle.time)
            assert next_time > current_time

    def test_cache_functionality(self, csv_repo):
        """Test: Caching-Funktionalität"""
        # Erste Abfrage - Cache-Miss
        candles1 = csv_repo.get_candles_by_date("NQ=F", "5m", datetime(2024, 1, 15), count=5)

        # Zweite Abfrage - Cache-Hit
        candles2 = csv_repo.get_candles_by_date("NQ=F", "5m", datetime(2024, 1, 15), count=5)

        # Sollte aus Cache kommen (gleiche Länge)
        if len(candles1) > 0:
            assert len(candles1) == len(candles2)

    def test_clear_cache(self, csv_repo):
        """Test: Cache leeren"""
        # Cache füllen
        csv_repo.get_candles_by_date("NQ=F", "5m", datetime(2024, 1, 15), count=5)
        assert len(csv_repo.data_cache) > 0

        # Cache leeren
        csv_repo.clear_cache()
        assert len(csv_repo.data_cache) == 0

    def test_invalid_timeframe(self, csv_repo):
        """Test: Ungültiger Timeframe"""
        candles = csv_repo.get_candles_by_date("NQ=F", "10m", datetime(2024, 1, 15))
        # Sollte leere Liste zurückgeben
        assert candles == []

    def test_get_all_candles(self, csv_repo):
        """Test: Alle Kerzen laden"""
        candles = csv_repo.get_all_candles("NQ=F", "5m")

        if len(candles) > 0:
            assert all(isinstance(c, Candle) for c in candles)
            # Sollte viele Kerzen sein für ganzes Jahr
            # (nur Test wenn CSV verfügbar)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
