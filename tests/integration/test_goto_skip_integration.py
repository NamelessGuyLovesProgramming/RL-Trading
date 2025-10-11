#!/usr/bin/env python3
"""
==> Go-To-Date Skip Integration Test Suite
Tests für die beiden kritischen Probleme:
1. Debug Control Timeframe Desynchronisation nach Go-To-Date
2. Skip-generierte Kerzen persistieren nach neuen Go-To-Date Operationen

Author: Claude Code Session
Date: 2025-09-29
"""

import asyncio
import requests
import json
import time
from datetime import datetime, timedelta

class GoToDateSkipTestSuite:
    """
    Integration Tests für Go-To-Date → Skip Sequenzen
    Testet die exakten Bug-Szenarien die der User berichtet hat
    """

    def __init__(self, base_url="http://localhost:8003"):
        self.base_url = base_url
        self.test_results = []

    def log_result(self, test_name, success, details=""):
        """Loggt Testergebnis"""
        status = "[PASS]" if success else "[FAIL]"
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now()
        })
        print(f"{status} {test_name}: {details}")

    def call_api(self, endpoint, method="GET", data=None):
        """API Helper"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "POST":
                response = requests.post(url, json=data, timeout=15)
            else:
                response = requests.get(url, timeout=15)

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            raise Exception(f"API Call failed: {e}")

    def test_problem_1_debug_control_timeframe_sync(self):
        """
        Problem 1 Test: Debug Control Timeframe Desynchronisation

        Szenario:
        1. Setze 5min Timeframe
        2. GoTo 17.12.2024
        3. Skip ausführen
        4. Prüfe: Erste Skip-Kerze sollte 5min sein, NICHT 1min
        """
        try:
            print("==> Testing Problem 1: Debug Control Timeframe Sync")

            # Schritt 1: Debug Control auf 5min setzen
            self.call_api("/api/debug/set_debug_control_timeframe", "POST", {
                "timeframe": "5m"
            })
            print("    Debug Control auf 5m gesetzt")

            # Schritt 2: Go to specific date
            goto_result = self.call_api("/api/debug/go_to_date", "POST", {
                "date": "2024-12-17"
            })

            if goto_result.get('status') != 'success':
                self.log_result("Problem 1 - GoTo", False, "GoTo Operation failed")
                return False

            print("    GoTo 17.12.2024 erfolgreich")
            time.sleep(1)  # Kurze Pause für Synchronisation

            # Schritt 3: Skip ausführen
            skip_result = self.call_api("/api/debug/skip", "POST")

            if skip_result.get('status') != 'success':
                self.log_result("Problem 1 - Skip", False, "Skip Operation failed")
                return False

            # Schritt 4: Prüfe Skip-Kerze Timeframe
            skip_time = skip_result.get('debug_time')
            skip_timeframe = skip_result.get('timeframe', 'unknown')

            print(f"    Skip-Kerze erstellt: {skip_time}, Timeframe: {skip_timeframe}")

            # Erwartung: Timeframe sollte 5m sein
            success = skip_timeframe == '5m'

            if success:
                details = f"Skip-Kerze korrekt in 5m Timeframe erstellt: {skip_time}"
            else:
                details = f"FEHLER: Skip-Kerze in {skip_timeframe} statt 5m erstellt: {skip_time}"

            self.log_result("Problem 1 - Debug Control TF Sync", success, details)
            return success

        except Exception as e:
            self.log_result("Problem 1 - Debug Control TF Sync", False, str(e))
            return False

    def test_problem_2_skip_candles_persistence(self):
        """
        Problem 2 Test: Skip-generierte Kerzen persistieren nach Go-To-Date

        Szenario:
        1. GoTo 17.12.2024
        2. Mehrere Skips ausführen (generiert Kerzen für 17.12.)
        3. GoTo 13.12.2024 (anderes Datum)
        4. Prüfe: Alte Skip-Kerzen vom 17.12. sollten verschwunden sein
        """
        try:
            print("==> Testing Problem 2: Skip Candles Persistence")

            # Schritt 1: Go to first date und Skip-Kerzen generieren
            goto_result_1 = self.call_api("/api/debug/go_to_date", "POST", {
                "date": "2024-12-17"
            })

            if goto_result_1.get('status') != 'success':
                self.log_result("Problem 2 - First GoTo", False, "First GoTo failed")
                return False

            print("    GoTo 17.12.2024 erfolgreich")
            time.sleep(1)

            # Schritt 2: Mehrere Skip-Kerzen generieren
            skip_times_17th = []
            for i in range(3):
                skip_result = self.call_api("/api/debug/skip", "POST")
                if skip_result.get('status') == 'success':
                    skip_times_17th.append(skip_result.get('debug_time'))
                    print(f"    Skip {i+1} für 17.12.: {skip_result.get('debug_time')}")
                time.sleep(0.3)

            if len(skip_times_17th) < 3:
                self.log_result("Problem 2 - Skip Generation", False, "Nicht alle Skips erfolgreich")
                return False

            # Schritt 3: Go to different date (should clear old skip candles)
            goto_result_2 = self.call_api("/api/debug/go_to_date", "POST", {
                "date": "2024-12-13"
            })

            if goto_result_2.get('status') != 'success':
                self.log_result("Problem 2 - Second GoTo", False, "Second GoTo failed")
                return False

            print("    GoTo 13.12.2024 erfolgreich")
            time.sleep(1)

            # Schritt 4: Prüfe Chart-Daten - sollten keine 17.12. Skip-Kerzen enthalten
            chart_data = goto_result_2.get('data', [])

            # Check: Keine Kerzen vom 17.12. sollten sichtbar sein
            dec_17_candles = []
            for candle in chart_data:
                candle_timestamp = candle.get('time', 0)
                candle_date = datetime.fromtimestamp(candle_timestamp)
                if candle_date.day == 17 and candle_date.month == 12:
                    dec_17_candles.append(candle)

            # Erwartung: Keine 17.12. Kerzen mehr sichtbar
            success = len(dec_17_candles) == 0

            if success:
                details = f"Erfolgreich: Keine alten Skip-Kerzen vom 17.12. mehr sichtbar. Chart zeigt {len(chart_data)} Kerzen für 13.12."
            else:
                details = f"FEHLER: {len(dec_17_candles)} alte Skip-Kerzen vom 17.12. noch sichtbar nach GoTo 13.12."

            self.log_result("Problem 2 - Skip Candles Persistence", success, details)
            return success

        except Exception as e:
            self.log_result("Problem 2 - Skip Candles Persistence", False, str(e))
            return False

    def test_combined_scenario_comprehensive(self):
        """
        Kombinierter Test: Beide Probleme in einem realistischen Workflow
        """
        try:
            print("==> Testing Combined Scenario: Real-World Workflow")

            # Phase 1: Initiale Setup
            self.call_api("/api/debug/set_debug_control_timeframe", "POST", {"timeframe": "5m"})

            # Phase 2: Erstes Datum mit Skips
            goto_1 = self.call_api("/api/debug/go_to_date", "POST", {"date": "2024-12-17"})
            self.call_api("/api/debug/skip", "POST")
            self.call_api("/api/debug/skip", "POST")
            time.sleep(0.5)

            # Phase 3: Zweites Datum mit Skips (sollte alte Kerzen löschen)
            goto_2 = self.call_api("/api/debug/go_to_date", "POST", {"date": "2024-12-13"})
            time.sleep(0.5)

            skip_result = self.call_api("/api/debug/skip", "POST")

            # Verifikation
            timeframe_correct = skip_result.get('timeframe') == '5m'
            chart_data = goto_2.get('data', [])
            no_old_candles = all(
                datetime.fromtimestamp(c.get('time', 0)).day != 17
                for c in chart_data
            )

            success = timeframe_correct and no_old_candles and skip_result.get('status') == 'success'

            details = f"TF korrekt: {timeframe_correct}, Alte Kerzen entfernt: {no_old_candles}, Skip erfolgreich: {skip_result.get('status')}"

            self.log_result("Combined Scenario", success, details)
            return success

        except Exception as e:
            self.log_result("Combined Scenario", False, str(e))
            return False

    def run_integration_tests(self):
        """Führt alle Integration Tests aus"""
        print("==> Starting Go-To-Date Skip Integration Test Suite")
        print("=" * 60)

        test_methods = [
            self.test_problem_1_debug_control_timeframe_sync,
            self.test_problem_2_skip_candles_persistence,
            self.test_combined_scenario_comprehensive
        ]

        start_time = datetime.now()

        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                self.log_result(test_method.__name__, False, f"Unexpected error: {e}")

            time.sleep(1)  # Pause zwischen Tests

        # Generate final report
        self.generate_final_report(start_time)

    def generate_final_report(self, start_time):
        """Generiert finalen Test-Report"""
        end_time = datetime.now()
        duration = end_time - start_time

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        print("\n" + "=" * 60)
        print("==> GO-TO-DATE SKIP INTEGRATION TEST REPORT")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Duration: {duration.total_seconds():.1f}s")

        if success_rate >= 90:
            print("==> OVERALL RESULT: PASS - Go-To-Date Skip Integration working correctly!")
        else:
            print("==> OVERALL RESULT: FAIL - Go-To-Date Skip Integration issues detected!")

        # Print failed tests
        failed_tests = [r for r in self.test_results if not r['success']]
        if failed_tests:
            print("\n==> FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")

if __name__ == "__main__":
    # Run integration test suite
    test_suite = GoToDateSkipTestSuite()
    test_suite.run_integration_tests()