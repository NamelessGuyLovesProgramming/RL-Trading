"""
Test Suite für Chart-Funktionalität
Testet die wichtigsten Chart-Features der Trading App
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import json

# Import der zu testenden Funktionen
from trading_app_lightweight_only import (
    get_yfinance_data,
    create_trading_chart,
    validate_symbol,
    get_asset_info,
    AVAILABLE_ASSETS
)

class ChartTester:
    """Test-Klasse für Chart-Funktionalität"""

    def __init__(self):
        self.test_results = []
        self.print_header("CHART FUNCTIONALITY TESTS")

    def print_header(self, title):
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60)

    def print_test(self, test_name, status, details=""):
        status_symbol = "[PASS]" if status else "[FAIL]"
        print(f"{status_symbol} {test_name}")
        if details:
            print(f"   -> {details}")
        self.test_results.append((test_name, status, details))

    def test_data_loading(self):
        """Test 1: Daten-Loading von Yahoo Finance"""
        self.print_header("TEST 1: DATEN-LOADING")

        # Test mit AAPL
        print("[INFO] Testing data loading for AAPL...")
        try:
            data = get_yfinance_data("AAPL", period="5d", interval="1d")

            if data is None:
                self.print_test("Data Loading", False, "get_yfinance_data returned None")
                return False

            if 'data' not in data:
                self.print_test("Data Structure", False, "'data' key missing in returned dict")
                return False

            df = data['data']
            if df.empty:
                self.print_test("DataFrame Content", False, "DataFrame is empty")
                return False

            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                self.print_test("DataFrame Columns", False, f"Missing columns: {missing_cols}")
                return False

            self.print_test("Data Loading", True, f"Loaded {len(df)} rows for AAPL")
            self.print_test("Data Structure", True, "All required keys present")
            self.print_test("DataFrame Content", True, f"Shape: {df.shape}")
            self.print_test("DataFrame Columns", True, "All required columns present")

            print(f"[INFO] Data sample:")
            print(df.head(2))

            return True

        except Exception as e:
            self.print_test("Data Loading", False, f"Exception: {str(e)}")
            return False

    def test_chart_creation(self):
        """Test 2: Chart-HTML Erstellung"""
        self.print_header("TEST 2: CHART-HTML ERSTELLUNG")

        try:
            # Lade Test-Daten
            data = get_yfinance_data("AAPL", period="5d", interval="1d")
            if data is None:
                self.print_test("Chart Creation", False, "No test data available")
                return False

            # Erstelle Chart HTML
            chart_html = create_trading_chart(data)

            if not chart_html:
                self.print_test("Chart HTML Generation", False, "create_trading_chart returned empty")
                return False

            if "Keine Daten verfügbar" in chart_html:
                self.print_test("Chart HTML Generation", False, "Chart shows 'No data available'")
                return False

            # Überprüfe wichtige HTML-Elemente
            html_checks = {
                "LightweightCharts Script": "LightweightCharts.createChart" in chart_html,
                "Chart Container": 'id="chart_' in chart_html,
                "Candlestick Series": "addCandlestickSeries" in chart_html,
                "Volume Series": "addHistogramSeries" in chart_html,
                "Asset Symbol Modal": "symbolModal" in chart_html,
                "JavaScript Functions": "function openSymbolModal" in chart_html
            }

            for check_name, passed in html_checks.items():
                self.print_test(check_name, passed)

            # HTML-Größe prüfen
            html_size = len(chart_html)
            size_ok = html_size > 10000  # Erwarte mindestens 10KB HTML
            self.print_test("Chart HTML Size", size_ok, f"{html_size} characters")

            return all(html_checks.values()) and size_ok

        except Exception as e:
            self.print_test("Chart Creation", False, f"Exception: {str(e)}")
            return False

    def test_symbol_validation(self):
        """Test 3: Symbol-Validierung"""
        self.print_header("TEST 3: SYMBOL-VALIDIERUNG")

        # Test gültige Symbole
        valid_symbols = ["AAPL", "TSLA", "BTC-USD", "EURUSD=X", "^GSPC"]
        for symbol in valid_symbols:
            is_valid = validate_symbol(symbol)
            self.print_test(f"Valid Symbol: {symbol}", is_valid)

        # Test ungültige Symbole
        invalid_symbols = ["INVALID", "FAKE123", ""]
        for symbol in invalid_symbols:
            is_valid = validate_symbol(symbol)
            self.print_test(f"Invalid Symbol: {symbol}", not is_valid)

        return True

    def test_asset_info(self):
        """Test 4: Asset-Informationen"""
        self.print_header("TEST 4: ASSET-INFORMATIONEN")

        # Test Asset-Info Abruf
        test_symbols = ["AAPL", "TSLA", "BTC-USD"]

        for symbol in test_symbols:
            asset_info = get_asset_info(symbol)

            if asset_info:
                has_required_keys = all(key in asset_info for key in ['symbol', 'name', 'description'])
                self.print_test(f"Asset Info: {symbol}", has_required_keys,
                              f"Name: {asset_info.get('name', 'N/A')}")
            else:
                self.print_test(f"Asset Info: {symbol}", False, "No info found")

        return True

    def test_available_assets_structure(self):
        """Test 5: AVAILABLE_ASSETS Datenstruktur"""
        self.print_header("TEST 5: AVAILABLE_ASSETS STRUKTUR")

        # Überprüfe Hauptkategorien
        expected_categories = ["stocks", "crypto", "forex", "indices"]
        for category in expected_categories:
            exists = category in AVAILABLE_ASSETS
            self.print_test(f"Category: {category}", exists)

            if exists:
                count = len(AVAILABLE_ASSETS[category])
                self.print_test(f"  └─ {category} count", count > 0, f"{count} assets")

        # Überprüfe Asset-Struktur
        total_assets = 0
        for category, assets in AVAILABLE_ASSETS.items():
            for asset in assets:
                total_assets += 1
                required_keys = ['symbol', 'name', 'description']
                has_all_keys = all(key in asset for key in required_keys)
                if not has_all_keys:
                    self.print_test(f"Asset Structure: {asset.get('symbol', 'Unknown')}",
                                  False, "Missing required keys")
                    break

        self.print_test("Total Assets", total_assets > 0, f"{total_assets} assets found")

        return True

    def run_all_tests(self):
        """Führe alle Tests aus"""
        print("\n[START] STARTING COMPREHENSIVE CHART TESTS")

        tests = [
            self.test_data_loading,
            self.test_chart_creation,
            self.test_symbol_validation,
            self.test_asset_info,
            self.test_available_assets_structure
        ]

        passed_tests = 0
        total_tests = len(tests)

        for test_func in tests:
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                print(f"[ERROR] Test {test_func.__name__} failed with exception: {e}")

        # Zusammenfassung
        self.print_header("TEST SUMMARY")
        success_rate = (passed_tests / total_tests) * 100
        print(f"[STATS] Tests passed: {passed_tests}/{total_tests} ({success_rate:.1f}%)")

        # Detaillierte Ergebnisse
        print(f"\n[RESULTS] Detailed Results:")
        failed_tests = [result for result in self.test_results if not result[1]]
        if failed_tests:
            print("[FAIL] Failed tests:")
            for test_name, status, details in failed_tests:
                print(f"   * {test_name}: {details}")
        else:
            print("[SUCCESS] All individual test checks passed!")

        return passed_tests == total_tests

if __name__ == "__main__":
    tester = ChartTester()
    success = tester.run_all_tests()

    if success:
        print("\n[SUCCESS] ALL CHART TESTS PASSED!")
        exit(0)
    else:
        print("\n[ERROR] SOME TESTS FAILED - CHECK ABOVE FOR DETAILS")
        exit(1)