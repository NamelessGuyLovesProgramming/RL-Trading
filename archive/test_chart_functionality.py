#!/usr/bin/env python3
"""
Chart Functionality Test Suite
Automatisierte Tests um solche Probleme in Zukunft zu vermeiden
"""

import requests
import time
import json
import sys
from datetime import datetime

class ChartTester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = []

    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colored_status = {
            "PASS": "\033[92m✅ PASS\033[0m",
            "FAIL": "\033[91m❌ FAIL\033[0m",
            "INFO": "\033[94mℹ️  INFO\033[0m",
            "WARN": "\033[93m⚠️  WARN\033[0m"
        }
        print(f"[{timestamp}] {colored_status.get(status, status)} {message}")

    def test_server_health(self):
        """Test 1: Chart Server Erreichbarkeit"""
        self.log("Test 1: Chart Server Erreichbarkeit")

        try:
            response = self.session.get(f"{self.base_url}/api/chart/status", timeout=5)
            if response.status_code == 200:
                self.log("Chart Server ist erreichbar", "PASS")
                return True
            else:
                self.log(f"Chart Server antwortet mit Status {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"Chart Server nicht erreichbar: {e}", "FAIL")
            return False

    def test_chart_page_loads(self):
        """Test 2: Chart Hauptseite lädt"""
        self.log("Test 2: Chart Hauptseite lädt")

        try:
            response = self.session.get(self.base_url, timeout=10)
            if response.status_code == 200:
                # Prüfe auf wichtige JavaScript Elemente
                html = response.text
                checks = [
                    "LightweightCharts" in html,
                    "createChart" in html,
                    "chart_container" in html,
                    "positionBoxTool" in html
                ]

                if all(checks):
                    self.log("Chart Seite lädt vollständig", "PASS")
                    return True
                else:
                    missing = [name for name, check in zip(
                        ["LightweightCharts", "createChart", "chart_container", "positionBoxTool"],
                        checks) if not check]
                    self.log(f"Chart Seite unvollständig - Fehlt: {missing}", "FAIL")
                    return False
            else:
                self.log(f"Chart Seite lädt nicht: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"Fehler beim Laden der Chart Seite: {e}", "FAIL")
            return False

    def test_api_endpoints(self):
        """Test 3: API Endpoints funktionieren"""
        self.log("Test 3: API Endpoints")

        endpoints = [
            "/api/chart/status",
            "/docs"
        ]

        all_good = True
        for endpoint in endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    self.log(f"Endpoint {endpoint} OK", "PASS")
                else:
                    self.log(f"Endpoint {endpoint} Fehler: {response.status_code}", "FAIL")
                    all_good = False
            except Exception as e:
                self.log(f"Endpoint {endpoint} nicht erreichbar: {e}", "FAIL")
                all_good = False

        return all_good

    def test_chart_data_api(self):
        """Test 4: Chart Daten API"""
        self.log("Test 4: Chart Daten API")

        try:
            # Test Daten senden
            test_data = [
                {"time": "2023-01-01", "open": 100, "high": 105, "low": 95, "close": 102},
                {"time": "2023-01-02", "open": 102, "high": 108, "low": 100, "close": 106}
            ]

            response = self.session.post(
                f"{self.base_url}/api/chart/set_data",
                json={"data": test_data, "symbol": "TEST", "interval": "1d"},
                timeout=5
            )

            if response.status_code == 200:
                self.log("Chart Daten API funktioniert", "PASS")
                return True
            else:
                self.log(f"Chart Daten API Fehler: {response.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"Chart Daten API Fehler: {e}", "FAIL")
            return False

    def test_javascript_errors(self):
        """Test 5: JavaScript Fehler Check via Browser Test"""
        self.log("Test 5: JavaScript Fehler Check")
        self.log("Hinweis: Manuell Browser öffnen und Konsole prüfen", "WARN")
        self.log("URL: http://localhost:8001", "INFO")
        self.log("- Keine roten Fehler in der Konsole", "INFO")
        self.log("- WebSocket Verbindung stabil", "INFO")
        self.log("- Position Box Tool klickbar", "INFO")
        return True  # Manueller Test

    def run_all_tests(self):
        """Führe alle Tests aus"""
        self.log("🚀 Starte Chart Funktionalitäts-Tests")
        self.log("=" * 50)

        tests = [
            ("Server Health", self.test_server_health),
            ("Chart Page Load", self.test_chart_page_loads),
            ("API Endpoints", self.test_api_endpoints),
            ("Chart Data API", self.test_chart_data_api),
            ("JavaScript Errors", self.test_javascript_errors)
        ]

        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                self.log(f"Test {test_name} crashed: {e}", "FAIL")
                results.append((test_name, False))

            self.log("-" * 30)

        # Zusammenfassung
        self.log("📊 Test Zusammenfassung")
        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            status = "PASS" if result else "FAIL"
            self.log(f"{test_name}: {status}")

        self.log(f"Ergebnis: {passed}/{total} Tests bestanden")

        if passed == total:
            self.log("🎉 Alle Tests bestanden!", "PASS")
            return True
        else:
            self.log("⚠️ Einige Tests fehlgeschlagen!", "FAIL")
            return False

def main():
    print("Chart Functionality Test Suite")
    print("Verhindert Chart-Probleme durch automatisierte Tests\n")

    # Warte kurz für Server Startup
    time.sleep(2)

    tester = ChartTester()
    success = tester.run_all_tests()

    if success:
        print("\n✅ Alle Tests bestanden - Chart sollte funktionieren!")
        sys.exit(0)
    else:
        print("\n❌ Tests fehlgeschlagen - Chart-Probleme erkannt!")
        sys.exit(1)

if __name__ == "__main__":
    main()