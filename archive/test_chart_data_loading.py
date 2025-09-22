#!/usr/bin/env python3
"""
Comprehensive Tests for loadInitialData() Function
Tests all components before server start to prevent chart loading issues
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any

class ChartDataLoadingTester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.results = []
        self.session = requests.Session()

    def log(self, message: str, status: str = "INFO"):
        """Log test results with colored output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "PASS": "\033[92m[PASS]\033[0m",
            "FAIL": "\033[91m[FAIL]\033[0m",
            "INFO": "\033[94m[INFO]\033[0m",
            "WARN": "\033[93m[WARN]\033[0m"
        }
        print(f"[{timestamp}] {colors.get(status, status)} {message}")
        self.results.append((message, status))

    def test_nq_data_files_exist(self) -> bool:
        """Test 1: Check if NQ data files exist"""
        self.log("Test 1: NQ Data Files vorhanden")

        data_path = "src/data/nq-1m/nq-1m"
        if not os.path.exists(data_path):
            self.log(f"Data path {data_path} existiert nicht", "FAIL")
            return False

        csv_files = [f for f in os.listdir(data_path) if f.endswith('.csv') and 'nq-1m' in f]
        if not csv_files:
            self.log(f"Keine NQ CSV-Dateien in {data_path} gefunden", "FAIL")
            return False

        self.log(f"Gefunden: {len(csv_files)} NQ CSV-Dateien: {csv_files}", "PASS")
        return True

    def test_nq_data_loader_class(self) -> bool:
        """Test 2: Test NQDataLoader class functionality"""
        self.log("Test 2: NQDataLoader Klasse")

        try:
            # Import NQDataLoader
            sys.path.insert(0, 'src/data')
            from nq_data_loader import NQDataLoader

            loader = NQDataLoader()

            # Test available files
            info = loader.get_info()
            if not info['available_years']:
                self.log("Keine verfügbaren Jahre in NQDataLoader", "FAIL")
                return False

            self.log(f"NQDataLoader verfügbare Jahre: {info['available_years']}", "PASS")

            # Test loading recent data
            recent_data = loader.load_latest_days(1)  # Load 1 day for testing
            if recent_data.empty:
                self.log("Keine aktuellen Daten von NQDataLoader", "FAIL")
                return False

            self.log(f"NQDataLoader: {len(recent_data)} Kerzen für letzten Tag geladen", "PASS")

            # Test chart format conversion
            chart_data = loader.convert_to_chart_format(recent_data.head(10))
            if not chart_data:
                self.log("Chart-Format-Konvertierung fehlgeschlagen", "FAIL")
                return False

            # Validate chart data structure
            required_fields = ['time', 'open', 'high', 'low', 'close']
            first_candle = chart_data[0]
            missing_fields = [field for field in required_fields if field not in first_candle]
            if missing_fields:
                self.log(f"Fehlende Felder in Chart-Daten: {missing_fields}", "FAIL")
                return False

            self.log("Chart-Format-Konvertierung erfolgreich", "PASS")
            return True

        except Exception as e:
            self.log(f"NQDataLoader Test fehlgeschlagen: {e}", "FAIL")
            return False

    def test_server_startup(self) -> bool:
        """Test 3: Check if server starts and loads data"""
        self.log("Test 3: Server-Startup und Daten-Loading")

        max_attempts = 30  # Wait up to 30 seconds
        for attempt in range(max_attempts):
            try:
                response = self.session.get(f"{self.base_url}/api/chart/status", timeout=2)
                if response.status_code == 200:
                    status_data = response.json()
                    candles_count = status_data.get('chart_state', {}).get('candles_count', 0)
                    if candles_count > 0:
                        self.log(f"Server läuft mit {candles_count} Kerzen geladen", "PASS")
                        return True
                    else:
                        self.log(f"Server läuft, aber keine Kerzen geladen (Versuch {attempt+1}/{max_attempts})")
                        time.sleep(1)
                        continue
            except Exception:
                if attempt == 0:
                    self.log(f"Warte auf Server-Start (Versuch {attempt+1}/{max_attempts})")
                time.sleep(1)

        self.log("Server-Startup oder Daten-Loading fehlgeschlagen", "FAIL")
        return False

    def test_api_chart_data_endpoint(self) -> bool:
        """Test 4: Test /api/chart/data endpoint"""
        self.log("Test 4: /api/chart/data Endpoint")

        try:
            response = self.session.get(f"{self.base_url}/api/chart/data", timeout=10)
            if response.status_code != 200:
                self.log(f"API Endpoint Status: {response.status_code}", "FAIL")
                return False

            data = response.json()

            # Check data structure
            if 'data' not in data:
                self.log("Kein 'data' Feld in API Response", "FAIL")
                return False

            chart_data = data['data']
            if not chart_data:
                self.log("Leere Chart-Daten in API Response", "FAIL")
                return False

            self.log(f"API liefert {len(chart_data)} Kerzen", "PASS")

            # Validate first candle structure
            first_candle = chart_data[0]
            required_fields = ['time', 'open', 'high', 'low', 'close']
            missing_fields = [field for field in required_fields if field not in first_candle]
            if missing_fields:
                self.log(f"Fehlende Felder in API-Daten: {missing_fields}", "FAIL")
                return False

            # Validate data types
            try:
                float(first_candle['open'])
                float(first_candle['high'])
                float(first_candle['low'])
                float(first_candle['close'])
            except (ValueError, TypeError):
                self.log("Ungültige Datentypen in OHLC-Daten", "FAIL")
                return False

            # Validate time format
            time_str = first_candle['time']
            try:
                pd.to_datetime(time_str)
            except:
                self.log(f"Ungültiges Zeitformat: {time_str}", "FAIL")
                return False

            self.log("API-Datenstruktur und -typen valide", "PASS")
            return True

        except Exception as e:
            self.log(f"API Endpoint Test fehlgeschlagen: {e}", "FAIL")
            return False

    def test_javascript_time_conversion(self) -> bool:
        """Test 5: Test JavaScript time conversion logic"""
        self.log("Test 5: JavaScript Zeit-Konvertierung")

        try:
            response = self.session.get(f"{self.base_url}/api/chart/data", timeout=5)
            data = response.json()
            chart_data = data['data']

            # Test time conversion for first few candles
            test_samples = chart_data[:5]

            for i, candle in enumerate(test_samples):
                time_str = candle['time']

                # Simulate JavaScript conversion: Math.floor(new Date(item.time).getTime() / 1000)
                try:
                    dt = pd.to_datetime(time_str)
                    timestamp_ms = int(dt.timestamp() * 1000)
                    timestamp_s = timestamp_ms // 1000

                    # Check if timestamp is reasonable (after 2020, before 2030)
                    year_2020_ts = 1577836800  # 2020-01-01
                    year_2030_ts = 1893456000  # 2030-01-01

                    if not (year_2020_ts <= timestamp_s <= year_2030_ts):
                        self.log(f"Unrealistischer Timestamp für Kerze {i}: {timestamp_s}", "FAIL")
                        return False

                except Exception as e:
                    self.log(f"Zeit-Konvertierung fehlgeschlagen für Kerze {i}: {e}", "FAIL")
                    return False

            self.log("JavaScript Zeit-Konvertierung wird funktionieren", "PASS")
            return True

        except Exception as e:
            self.log(f"Zeit-Konvertierung Test fehlgeschlagen: {e}", "FAIL")
            return False

    def test_chart_data_quality(self) -> bool:
        """Test 6: Test data quality and realistic values"""
        self.log("Test 6: Chart-Daten Qualität")

        try:
            response = self.session.get(f"{self.base_url}/api/chart/data", timeout=5)
            data = response.json()
            chart_data = data['data']

            # Check for reasonable NQ price ranges (typically 15000-25000)
            min_reasonable_price = 10000
            max_reasonable_price = 30000

            issues = []
            for i, candle in enumerate(chart_data[:100]):  # Check first 100 candles
                try:
                    open_price = float(candle['open'])
                    high_price = float(candle['high'])
                    low_price = float(candle['low'])
                    close_price = float(candle['close'])

                    # Check price ranges
                    prices = [open_price, high_price, low_price, close_price]
                    if any(p < min_reasonable_price or p > max_reasonable_price for p in prices):
                        issues.append(f"Unrealistic prices in candle {i}: OHLC={prices}")
                        continue

                    # Check OHLC logic: high >= all others, low <= all others
                    if not (high_price >= open_price and high_price >= close_price and high_price >= low_price):
                        issues.append(f"Invalid OHLC logic in candle {i}: High not highest")
                        continue

                    if not (low_price <= open_price and low_price <= close_price and low_price <= high_price):
                        issues.append(f"Invalid OHLC logic in candle {i}: Low not lowest")
                        continue

                except (ValueError, TypeError) as e:
                    issues.append(f"Invalid data in candle {i}: {e}")

            if issues:
                for issue in issues[:5]:  # Show first 5 issues
                    self.log(issue, "FAIL")
                self.log(f"Gesamt: {len(issues)} Qualitätsprobleme gefunden", "FAIL")
                return False

            self.log("Chart-Daten Qualität ist gut", "PASS")
            return True

        except Exception as e:
            self.log(f"Datenqualität Test fehlgeschlagen: {e}", "FAIL")
            return False

    def test_loadinitialdata_simulation(self) -> bool:
        """Test 7: Simulate complete loadInitialData() process"""
        self.log("Test 7: Komplette loadInitialData() Simulation")

        try:
            # Step 1: Fetch status
            self.log("  Schritt 1: Lade Status...")
            status_response = self.session.get(f"{self.base_url}/api/chart/status", timeout=5)
            if status_response.status_code != 200:
                self.log("Status API fehlgeschlagen", "FAIL")
                return False

            # Step 2: Fetch chart data
            self.log("  Schritt 2: Lade Chart-Daten...")
            data_response = self.session.get(f"{self.base_url}/api/chart/data", timeout=10)
            if data_response.status_code != 200:
                self.log("Chart-Daten API fehlgeschlagen", "FAIL")
                return False

            chart_data = data_response.json()

            # Step 3: Simulate JavaScript processing
            self.log("  Schritt 3: Simuliere JavaScript-Verarbeitung...")
            if not chart_data.get('data'):
                self.log("Keine Daten für JavaScript-Verarbeitung", "FAIL")
                return False

            # Simulate the exact JavaScript transformation
            formatted_data = []
            for item in chart_data['data'][:10]:  # Test first 10
                try:
                    processed_item = {
                        'time': int(pd.to_datetime(item['time']).timestamp()),
                        'open': float(item['open']),
                        'high': float(item['high']),
                        'low': float(item['low']),
                        'close': float(item['close'])
                    }
                    formatted_data.append(processed_item)
                except Exception as e:
                    self.log(f"JavaScript-Simulation fehlgeschlagen: {e}", "FAIL")
                    return False

            self.log(f"  Erfolgreich {len(formatted_data)} Kerzen für LightweightCharts formatiert", "PASS")

            # Step 4: Validate final format
            self.log("  Schritt 4: Validiere finales Format...")
            if not formatted_data:
                self.log("Keine formatierten Daten", "FAIL")
                return False

            # Check sorting (timestamps should be in order)
            timestamps = [item['time'] for item in formatted_data]
            if timestamps != sorted(timestamps):
                self.log("Zeitstempel nicht sortiert", "WARN")

            self.log("loadInitialData() Simulation erfolgreich", "PASS")
            return True

        except Exception as e:
            self.log(f"loadInitialData() Simulation fehlgeschlagen: {e}", "FAIL")
            return False

    def run_all_tests(self) -> bool:
        """Run all tests and return overall success"""
        self.log(">> Starte umfassende loadInitialData() Tests")
        self.log("=" * 60)

        tests = [
            ("NQ Data Files", self.test_nq_data_files_exist),
            ("NQDataLoader Class", self.test_nq_data_loader_class),
            ("Server Startup", self.test_server_startup),
            ("API Chart Data", self.test_api_chart_data_endpoint),
            ("Time Conversion", self.test_javascript_time_conversion),
            ("Data Quality", self.test_chart_data_quality),
            ("loadInitialData() Sim", self.test_loadinitialdata_simulation)
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            self.log(f"\n>> Führe Test aus: {test_name}")
            try:
                result = test_func()
                if result:
                    passed += 1
                    self.log(f"[OK] {test_name}: BESTANDEN")
                else:
                    self.log(f"[FAIL] {test_name}: FEHLGESCHLAGEN")
            except Exception as e:
                self.log(f"[CRASH] {test_name}: CRASHED - {e}", "FAIL")

            self.log("-" * 40)

        # Summary
        self.log("\n>> TEST ZUSAMMENFASSUNG")
        self.log(f"Bestanden: {passed}/{total} Tests")

        if passed == total:
            self.log("[SUCCESS] ALLE TESTS BESTANDEN - loadInitialData() sollte funktionieren!", "PASS")
            return True
        else:
            self.log("[WARNING] EINIGE TESTS FEHLGESCHLAGEN - Chart könnte Probleme haben!", "FAIL")
            return False

def main():
    """Main test runner"""
    print("LoadInitialData() Test Suite")
    print("Verhindert Chart-Loading-Probleme durch umfassende Tests\n")

    # Wait a moment for server to be ready
    time.sleep(3)

    tester = ChartDataLoadingTester()
    success = tester.run_all_tests()

    if success:
        print("\n[SUCCESS] Alle Tests bestanden - Chart sollte korrekt laden!")
        sys.exit(0)
    else:
        print("\n[FAIL] Tests fehlgeschlagen - Chart-Probleme zu erwarten!")
        print("Bitte Probleme beheben bevor der Chart verwendet wird.")
        sys.exit(1)

if __name__ == "__main__":
    main()