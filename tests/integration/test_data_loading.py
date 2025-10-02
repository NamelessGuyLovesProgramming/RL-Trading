"""
Integration Tests für Data Loading
Tests die Zusammenarbeit zwischen Repositories und Models
"""

import pytest
from datetime import datetime, timedelta
from charts.repositories.csv_repository import CSVRepository
from charts.repositories.cache_repository import CacheRepository, SimpleCacheRepository
from charts.repositories.state_repository import StateRepository
from charts.models.chart_data import Candle, ChartData


class TestDataLoadingIntegration:
    """Integration Tests für komplette Data Loading Workflows"""

    @pytest.fixture
    def csv_repo(self):
        """CSV Repository"""
        return CSVRepository(data_path="src/data/aggregated")

    @pytest.fixture
    def cache_repo(self):
        """Cache Repository (Simple Fallback)"""
        return SimpleCacheRepository()

    @pytest.fixture
    def state_repo(self, tmp_path):
        """State Repository mit temp file"""
        return StateRepository(state_file=str(tmp_path / "integration_state.json"))

    def test_csv_to_model_conversion(self, csv_repo):
        """Test: CSV-Daten zu Domain Models konvertieren"""
        # Lade Daten aus CSV
        test_date = datetime(2024, 1, 15, 10, 0)
        candles = csv_repo.get_candles_by_date("NQ=F", "5m", test_date, count=10)

        if len(candles) == 0:
            pytest.skip("Keine CSV-Daten verfügbar für Test")

        # Prüfe dass alle Candles valide sind
        assert all(isinstance(c, Candle) for c in candles)

        # Erstelle ChartData aus Candles
        chart_data = ChartData(
            candles=candles,
            timeframe="5m",
            symbol="NQ=F"
        )

        assert chart_data.candle_count == len(candles)
        assert chart_data.timeframe == "5m"
        assert chart_data.symbol == "NQ=F"
        assert chart_data.first_candle is not None
        assert chart_data.last_candle is not None

    def test_csv_cache_state_workflow(self, csv_repo, cache_repo, state_repo):
        """Test: Kompletter Workflow CSV → Cache → State"""
        test_date = datetime(2024, 1, 15, 10, 0)
        timeframe = "5m"
        symbol = "NQ=F"

        # 1. Lade Daten aus CSV
        candles_from_csv = csv_repo.get_candles_by_date(symbol, timeframe, test_date, count=10)

        if len(candles_from_csv) == 0:
            pytest.skip("Keine CSV-Daten verfügbar")

        assert len(candles_from_csv) > 0

        # 2. Speichere in Cache
        cache_repo.store_candles(timeframe, test_date, candles_from_csv, count=10)

        # 3. Lade aus Cache (sollte Cache-Hit sein)
        candles_from_cache = cache_repo.get_candles(timeframe, test_date, count=10)

        assert candles_from_cache is not None
        assert len(candles_from_cache) == len(candles_from_csv)

        # 4. Speichere State
        state = {
            'current_timeframe': timeframe,
            'current_date': test_date.strftime('%Y-%m-%d'),
            'loaded_candles': len(candles_from_csv)
        }

        result = state_repo.save_state(state)
        assert result is True

        # 5. Lade State wieder
        loaded_state = state_repo.load_state()

        assert loaded_state is not None
        assert loaded_state['current_timeframe'] == timeframe
        assert loaded_state['current_date'] == test_date.strftime('%Y-%m-%d')
        assert loaded_state['loaded_candles'] == len(candles_from_csv)

    def test_multi_timeframe_loading(self, csv_repo):
        """Test: Laden mehrerer Timeframes"""
        test_date = datetime(2024, 1, 15, 10, 0)
        timeframes = ["1m", "5m", "15m"]

        loaded_data = {}

        for tf in timeframes:
            candles = csv_repo.get_candles_by_date("NQ=F", tf, test_date, count=10)

            if len(candles) > 0:
                loaded_data[tf] = candles
                assert all(isinstance(c, Candle) for c in candles)

        # Mindestens ein Timeframe sollte geladen worden sein
        if len(loaded_data) == 0:
            pytest.skip("Keine CSV-Daten verfügbar")

        print(f"Erfolgreich geladen: {list(loaded_data.keys())}")

    def test_cache_performance_benefit(self, csv_repo, cache_repo):
        """Test: Cache-Performance-Vorteil demonstrieren"""
        test_date = datetime(2024, 1, 15, 10, 0)
        timeframe = "5m"

        # Erste Abfrage - CSV Load + Cache Store
        candles_1 = csv_repo.get_candles_by_date("NQ=F", timeframe, test_date, count=50)

        if len(candles_1) == 0:
            pytest.skip("Keine CSV-Daten verfügbar")

        # In Cache speichern
        cache_repo.store_candles(timeframe, test_date, candles_1, count=50)

        # Zweite Abfrage - aus Cache (sollte schneller sein)
        candles_2 = cache_repo.get_candles(timeframe, test_date, count=50)

        assert candles_2 is not None
        assert len(candles_2) == len(candles_1)

        # Prüfe dass Daten identisch sind
        for c1, c2 in zip(candles_1, candles_2):
            assert c1.time == c2.time
            assert c1.open == c2.open
            assert c1.close == c2.close

    def test_date_range_query(self, csv_repo):
        """Test: Zeitraum-Query über mehrere Tage"""
        start_date = datetime(2024, 1, 15, 9, 30)
        end_date = datetime(2024, 1, 15, 16, 0)

        candles = csv_repo.get_candles_range("NQ=F", "5m", start_date, end_date)

        if len(candles) == 0:
            pytest.skip("Keine CSV-Daten verfügbar für Zeitraum")

        # Alle Kerzen sollten im Zeitraum liegen
        for candle in candles:
            candle_time = datetime.fromtimestamp(candle.time)
            assert start_date <= candle_time <= end_date

        # Kerzen sollten chronologisch sortiert sein
        for i in range(len(candles) - 1):
            assert candles[i].time < candles[i + 1].time

    def test_next_candle_navigation(self, csv_repo):
        """Test: Navigation durch Kerzen mit next_candle"""
        start_date = datetime(2024, 1, 15, 10, 0)

        # Hole erste Kerzen
        initial_candles = csv_repo.get_candles_by_date("NQ=F", "5m", start_date, count=5)

        if len(initial_candles) == 0:
            pytest.skip("Keine CSV-Daten verfügbar")

        # Navigiere zur nächsten Kerze
        last_candle = initial_candles[-1]
        last_time = datetime.fromtimestamp(last_candle.time)

        next_candle = csv_repo.get_next_candle("5m", last_time)

        if next_candle is not None:
            assert next_candle.time > last_candle.time
            # Für 5m Timeframe sollte Differenz ~5 Minuten sein
            time_diff = next_candle.time - last_candle.time
            assert 280 <= time_diff <= 320  # 5min ±20 sekunden

    def test_state_persistence_across_sessions(self, state_repo):
        """Test: State-Persistierung simuliert Session-Unterbrechung"""
        # Session 1: State erstellen und speichern
        session_1_state = {
            'current_timeframe': '15m',
            'current_position': 250,
            'skip_events': [
                {'time': 1705315200, 'type': 'skip_forward'},
                {'time': 1705316000, 'type': 'skip_forward'}
            ]
        }

        state_repo.save_state(session_1_state)

        # Simuliere Session-Unterbrechung (neues Repository-Objekt)
        new_state_repo = StateRepository(state_file=str(state_repo.state_file))

        # Session 2: State wiederherstellen
        restored_state = new_state_repo.load_state()

        assert restored_state is not None
        assert restored_state['current_timeframe'] == '15m'
        assert restored_state['current_position'] == 250
        assert len(restored_state['skip_events']) == 2

    def test_cache_invalidation_workflow(self, cache_repo):
        """Test: Cache-Invalidierung Workflow"""
        test_date = datetime(2024, 1, 15, 10, 0)

        # Fülle Cache mit Daten für verschiedene Timeframes
        for tf in ["5m", "15m", "1h"]:
            candles = [
                Candle(time=1000 + i, open=100.0, high=101.0, low=99.0, close=100.5)
                for i in range(5)
            ]
            cache_repo.store_candles(tf, test_date, candles, count=5)

        # Invalidiere spezifischen Timeframe
        cache_repo.invalidate("5m")

        # 5m sollte weg sein
        result_5m = cache_repo.get_candles("5m", test_date, count=5)
        assert result_5m is None

        # Andere sollten noch da sein
        result_15m = cache_repo.get_candles("15m", test_date, count=5)
        assert result_15m is not None

        # Komplette Invalidierung
        cache_repo.invalidate()

        result_1h = cache_repo.get_candles("1h", test_date, count=5)
        assert result_1h is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
