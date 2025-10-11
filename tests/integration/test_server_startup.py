"""
Pre-Start Test fuer chart_server.py (Refactored System)
Validiert dass alle Komponenten korrekt initialisiert werden BEVOR der Server startet
"""

import sys
import os
from pathlib import Path
import io

# Windows UTF-8 encoding fix
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Pfad-Setup
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_initial_chart_data_loading():
    """Test 1: Initial Chart Data Loading"""
    print("\n" + "="*60)
    print("TEST 1: Initial Chart Data Loading")
    print("="*60)

    # Simuliere die Logik aus chart_server.py initialize_components()
    import pandas as pd

    csv_path = Path("src/data/aggregated/5m/nq-2024.csv")

    if not csv_path.exists():
        print(f"❌ FEHLER: CSV nicht gefunden: {csv_path}")
        return False

    print(f"✅ CSV gefunden: {csv_path}")

    # Lade Daten
    df = pd.read_csv(csv_path).tail(300)
    print(f"✅ CSV gelesen: {len(df)} Zeilen")

    if len(df) != 300:
        print(f"❌ FEHLER: Erwartet 300 Zeilen, bekommen {len(df)}")
        return False

    # Validiere Struktur
    required_columns = ['Date', 'Time', 'Open', 'High', 'Low', 'Close']
    for col in required_columns:
        if col not in df.columns:
            print(f"❌ FEHLER: Spalte '{col}' fehlt in CSV")
            return False

    print(f"✅ Alle erforderlichen Spalten vorhanden: {required_columns}")

    # Konvertiere zu Chart-Format
    initial_chart_data = []
    for _, row in df.iterrows():
        dt_str = f"{row['Date']} {row['Time']}"
        dt = pd.to_datetime(dt_str, format='mixed', dayfirst=True)

        candle = {
            'time': int(dt.timestamp()),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': int(row['Volume']) if 'Volume' in row else 0
        }

        # Validiere Kerze
        if candle['time'] <= 0:
            print(f"❌ FEHLER: Ungültiger Timestamp: {candle['time']}")
            return False

        if candle['high'] < max(candle['open'], candle['close'], candle['low']):
            print(f"❌ FEHLER: High < max(O,C,L): {candle}")
            return False

        if candle['low'] > min(candle['open'], candle['close'], candle['high']):
            print(f"❌ FEHLER: Low > min(O,C,H): {candle}")
            return False

        initial_chart_data.append(candle)

    print(f"✅ {len(initial_chart_data)} Kerzen erfolgreich konvertiert und validiert")

    if len(initial_chart_data) != 300:
        print(f"❌ FEHLER: Erwartet 300 Kerzen, bekommen {len(initial_chart_data)}")
        return False

    print(f"✅ Erste Kerze: {initial_chart_data[0]['time']} -> Close: {initial_chart_data[0]['close']}")
    print(f"✅ Letzte Kerze: {initial_chart_data[-1]['time']} -> Close: {initial_chart_data[-1]['close']}")

    return True


def test_core_imports():
    """Test 2: Core Imports"""
    print("\n" + "="*60)
    print("TEST 2: Core Imports Validation")
    print("="*60)

    try:
        from charts.core import (
            UnifiedStateManager,
            ChartDataValidator,
            ChartDataCache,
            ChartSeriesLifecycleManager,
            DebugController,
            UnifiedTimeManager,
            UnifiedPriceRepository,
            TimeframeDataRepository,
            CSVLoader,
            ConnectionManager,
            UniversalSkipRenderer
        )
        print("✅ Alle Core-Imports erfolgreich")
        return True
    except ImportError as e:
        print(f"❌ FEHLER beim Import: {e}")
        return False


def test_service_imports():
    """Test 3: Service Imports"""
    print("\n" + "="*60)
    print("TEST 3: Service Imports Validation")
    print("="*60)

    try:
        from charts.services import (
            ChartService,
            TimeframeService,
            NavigationService,
            DebugService,
            PositionService
        )
        print("✅ Alle Service-Imports erfolgreich")
        return True
    except ImportError as e:
        print(f"❌ FEHLER beim Import: {e}")
        return False


def test_router_imports():
    """Test 4: Router Imports"""
    print("\n" + "="*60)
    print("TEST 4: Router Imports Validation")
    print("="*60)

    try:
        from charts.routes import chart as chart_routes
        from charts.routes import debug as debug_routes
        from charts.routes import static as static_routes
        print("✅ Alle Router-Imports erfolgreich")
        return True
    except ImportError as e:
        print(f"❌ FEHLER beim Import: {e}")
        return False


def run_all_tests():
    """Führt alle Tests aus"""
    print("\n" + "="*70)
    print("🧪 PRE-START VALIDATION für chart_server.py (Refactored System)")
    print("="*70)

    tests = [
        ("Core Imports", test_core_imports),
        ("Service Imports", test_service_imports),
        ("Router Imports", test_router_imports),
        ("Initial Chart Data Loading", test_initial_chart_data_loading),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
        if not result:
            all_passed = False

    print("="*70)

    if all_passed:
        print("✅ ALLE TESTS ERFOLGREICH - Server kann gestartet werden!")
        print("="*70)
        return True
    else:
        print("❌ TESTS FEHLGESCHLAGEN - Server sollte NICHT gestartet werden!")
        print("="*70)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
