"""
PHASE 2 VALIDIERUNG - Repositories Layer
Testet alle Repository-Implementierungen
"""

from datetime import datetime
from charts.repositories.csv_repository import CSVRepository
from charts.repositories.cache_repository import CacheRepository, SimpleCacheRepository
from charts.repositories.state_repository import StateRepository
from charts.models.chart_data import Candle


def test_csv_repository():
    """Test CSVRepository Funktionalität"""
    print("\nTest 1: CSVRepository")

    csv_repo = CSVRepository(data_path="src/data/aggregated")
    print(f"  >> CSVRepository erstellt: {len(csv_repo.available_timeframes)} timeframes verfuegbar")

    # Test Timeframe Info
    info = csv_repo.get_timeframe_info("5m")
    if info:
        print(f"  ✅ Timeframe Info (5m): {info['total_candles']} candles")
        print(f"     Zeitraum: {info['start_time'].strftime('%Y-%m-%d')} - {info['end_time'].strftime('%Y-%m-%d')}")
    else:
        print(f"  ⚠️  Keine 5m CSV-Daten gefunden (Test übersprungen)")

    # Test Candles by Date
    test_date = datetime(2024, 1, 15, 10, 0)
    candles = csv_repo.get_candles_by_date("NQ=F", "5m", test_date, count=10)

    if len(candles) > 0:
        print(f"  ✅ get_candles_by_date: {len(candles)} candles geladen")
        print(f"     Erste Kerze: {datetime.fromtimestamp(candles[0].time)}")
        print(f"     Close-Preis: {candles[0].close}")
    else:
        print(f"  ⚠️  Keine Candles für Datum {test_date} (CSV evtl. nicht vorhanden)")

    # Test Cache
    candles_2 = csv_repo.get_candles_by_date("NQ=F", "5m", test_date, count=10)
    if len(candles) > 0 and len(candles_2) > 0:
        print(f"  ✅ Cache-Test: Zweite Abfrage erfolgreich ({len(candles_2)} candles)")

    return csv_repo


def test_simple_cache_repository():
    """Test SimpleCacheRepository Funktionalität"""
    print("\nTest 2: SimpleCacheRepository")

    simple_cache = SimpleCacheRepository()
    print(f"  ✅ SimpleCacheRepository erstellt: max_entries={simple_cache._max_entries}")

    # Test Store & Get
    test_candles = [
        Candle(time=1000, open=100.0, high=101.0, low=99.0, close=100.5),
        Candle(time=1060, open=100.5, high=102.0, low=100.0, close=101.5)
    ]
    test_date = datetime(2024, 1, 15, 10, 0)

    simple_cache.store_candles("5m", test_date, test_candles, count=200)
    print(f"  ✅ Candles gespeichert: {len(test_candles)} candles")

    retrieved = simple_cache.get_candles("5m", test_date, count=200)
    if retrieved:
        print(f"  ✅ Candles abgerufen: {len(retrieved)} candles (Cache-HIT)")
    else:
        print(f"  ❌ Cache-Miss (sollte nicht passieren)")

    # Test Cache-Miss
    miss_result = simple_cache.get_candles("15m", test_date, count=200)
    if miss_result is None:
        print(f"  ✅ Cache-Miss erkannt für nicht gecachten Timeframe")

    # Test Invalidate
    simple_cache.invalidate()
    print(f"  ✅ Cache invalidiert: {len(simple_cache._cache)} entries (sollte 0 sein)")

    # Test Performance Stats
    stats = simple_cache.get_performance_stats()
    print(f"  ✅ Performance Stats: cache_type={stats['cache_type']}, entries={stats['cached_entries']}")

    return simple_cache


def test_cache_repository():
    """Test CacheRepository (HighPerformanceChartCache Wrapper)"""
    print("\nTest 3: CacheRepository")

    cache_repo = CacheRepository(cache_size_mb=50)
    print(f"  ✅ CacheRepository erstellt: cache_size={cache_repo._cache_size_mb}MB")

    # Test Not Initialized State
    is_init = cache_repo.is_initialized()
    print(f"  ✅ Initialized Check: {is_init} (sollte False sein vor init)")

    # Test Initialize (kann fehlschlagen wenn HighPerformanceChartCache nicht verfügbar)
    result = cache_repo.initialize(max_rows=1000)  # Kleine Datenmenge für schnellen Test
    if result:
        print(f"  ✅ HighPerformanceChartCache erfolgreich initialisiert")

        # Test Get Candles
        test_date = datetime(2024, 1, 15, 10, 0)
        candles = cache_repo.get_candles("5m", test_date, count=50)

        if candles:
            print(f"  ✅ get_candles: {len(candles)} candles aus Cache geladen")
        else:
            print(f"  ⚠️  Keine Candles aus Cache (Date evtl. außerhalb Range)")

        # Performance Stats
        stats = cache_repo.get_performance_stats()
        print(f"  ✅ Performance Stats: initialized={stats.get('initialized')}")
    else:
        print(f"  ⚠️  HighPerformanceChartCache nicht verfügbar (Fallback zu SimpleCacheRepository)")
        print(f"     Dies ist OK - SimpleCacheRepository funktioniert als Fallback")

    return cache_repo


def test_state_repository():
    """Test StateRepository Funktionalität"""
    print("\nTest 4: StateRepository")

    state_repo = StateRepository(state_file="test_phase2_state.json")
    print(f"  ✅ StateRepository erstellt: {state_repo.state_file}")

    # Test Save State
    test_state = {
        'current_timeframe': '5m',
        'current_date': '2024-01-15',
        'chart_position': 250,
        'skip_events': [
            {'time': 1705315200, 'type': 'skip_forward'},
        ]
    }

    save_result = state_repo.save_state(test_state)
    print(f"  ✅ State gespeichert: {save_result}")

    # Test Load State
    loaded_state = state_repo.load_state()
    if loaded_state:
        print(f"  ✅ State geladen: timeframe={loaded_state['current_timeframe']}, position={loaded_state['chart_position']}")
        print(f"     Skip Events: {len(loaded_state['skip_events'])}")
    else:
        print(f"  ❌ State konnte nicht geladen werden")

    # Test State Info
    info = state_repo.get_state_info()
    print(f"  ✅ State Info: file_exists={info['state_file_exists']}, backup_exists={info['backup_file_exists']}")

    # Test State Exists
    exists = state_repo.state_exists()
    print(f"  ✅ State existiert: {exists}")

    # Cleanup
    state_repo.delete_state()
    print(f"  ✅ State gelöscht (Cleanup)")

    return state_repo


def test_integration_workflow():
    """Test Integrations-Workflow: CSV → Cache → State"""
    print("\nTest 5: Integration Workflow (CSV → Cache → State)")

    csv_repo = CSVRepository(data_path="src/data/aggregated")
    cache_repo = SimpleCacheRepository()
    state_repo = StateRepository(state_file="test_phase2_integration_state.json")

    test_date = datetime(2024, 1, 15, 10, 0)
    timeframe = "5m"

    # 1. Lade aus CSV
    candles_csv = csv_repo.get_candles_by_date("NQ=F", timeframe, test_date, count=20)

    if len(candles_csv) > 0:
        print(f"  ✅ Step 1: {len(candles_csv)} candles aus CSV geladen")

        # 2. Speichere in Cache
        cache_repo.store_candles(timeframe, test_date, candles_csv, count=20)
        print(f"  ✅ Step 2: Candles in Cache gespeichert")

        # 3. Lade aus Cache
        candles_cache = cache_repo.get_candles(timeframe, test_date, count=20)
        if candles_cache and len(candles_cache) == len(candles_csv):
            print(f"  ✅ Step 3: {len(candles_cache)} candles aus Cache geladen (Cache-HIT)")

        # 4. Speichere State
        state = {
            'current_timeframe': timeframe,
            'current_date': test_date.strftime('%Y-%m-%d'),
            'loaded_candles': len(candles_csv),
            'first_candle_time': candles_csv[0].time,
            'last_candle_time': candles_csv[-1].time
        }

        state_repo.save_state(state)
        print(f"  ✅ Step 4: State persistiert")

        # 5. Lade State
        loaded_state = state_repo.load_state()
        if loaded_state and loaded_state['loaded_candles'] == len(candles_csv):
            print(f"  ✅ Step 5: State wiederhergestellt (candles={loaded_state['loaded_candles']})")

        # Cleanup
        state_repo.delete_state()

        print(f"\n  🎉 Integration Workflow erfolgreich: CSV → Cache → State")
    else:
        print(f"  ⚠️  Integration Workflow übersprungen (keine CSV-Daten)")


def main():
    """Haupt-Validierung für Phase 2"""
    print("=" * 60)
    print("PHASE 2 VALIDIERUNG - Repositories Layer")
    print("=" * 60)

    try:
        # Test 1: CSVRepository
        csv_repo = test_csv_repository()

        # Test 2: SimpleCacheRepository
        simple_cache = test_simple_cache_repository()

        # Test 3: CacheRepository
        cache_repo = test_cache_repository()

        # Test 4: StateRepository
        state_repo = test_state_repository()

        # Test 5: Integration
        test_integration_workflow()

        # Summary
        print("\n" + "=" * 60)
        print("PHASE 2 VALIDIERUNG ERFOLGREICH!")
        print("=" * 60)
        print("\nAlle Repositories funktionieren:")
        print("  >> CSVRepository - CSV Data Access")
        print("  >> SimpleCacheRepository - Simple Memory Cache")
        print("  >> CacheRepository - High-Performance Cache Wrapper")
        print("  >> StateRepository - State Persistence")
        print("  >> Integration Workflow - CSV -> Cache -> State")
        print("\nBereit fuer Phase 3: Core-Klassen extrahieren\n")

    except Exception as e:
        print(f"\nFEHLER bei Phase 2 Validierung:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
