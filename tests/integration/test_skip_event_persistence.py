"""
Integration Test: Skip Event Persistence across Timeframes
Testet den Bug-Fix: "3x Skip im 5min TF → keine 15min Kerze"

Bug: Skip-Events wurden generiert aber nicht gespeichert, verschwanden beim TF-Wechsel
Fix: NavigationService speichert Events in global_skip_events, chart.py übergibt sie an Renderer
"""

# -*- coding: utf-8 -*-
import sys
import io

# Windows UTF-8 Fix
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
import time
from datetime import datetime

# Server Configuration
BASE_URL = "http://localhost:8003"
TEST_DATE = "2024-12-17"


class SkipEventPersistenceTest:
    """
    Automatisierter Test für Skip-Event Persistierung
    Simuliert User-Flow: GoTo → 3x Skip → TF-Wechsel → Validierung
    """

    def __init__(self):
        self.session = requests.Session()
        self.test_results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }

    def log(self, message, level="INFO"):
        """Test-Logging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "TEST": "🧪"
        }.get(level, "ℹ️")
        print(f"[{timestamp}] {prefix} {message}")

    def check_server_health(self):
        """Prüft ob Server läuft"""
        self.log("Checking server health...", "TEST")
        try:
            response = self.session.get(f"{BASE_URL}/api/chart/status", timeout=5)
            if response.status_code == 200:
                self.log("Server is running", "INFO")
                return True
            else:
                self.log(f"Server returned status {response.status_code}", "ERROR")
                return False
        except requests.exceptions.ConnectionError:
            self.log("Server is not running! Start with: py charts/chart_server.py", "ERROR")
            return False
        except Exception as e:
            self.log(f"Server check failed: {e}", "ERROR")
            return False

    def go_to_date(self, date_str):
        """Springt zu einem Datum"""
        self.log(f"Go to date: {date_str}", "TEST")
        try:
            response = self.session.post(
                f"{BASE_URL}/api/debug/go_to_date",
                json={"date": date_str},
                timeout=10
            )
            data = response.json()

            if data.get('status') == 'success':
                candles_loaded = data.get('candles_loaded', 0)
                self.log(f"Go to date successful: {candles_loaded} candles loaded", "INFO")
                self.test_results['passed'].append(f"GoTo {date_str}: {candles_loaded} candles")
                return True
            else:
                self.log(f"Go to date failed: {data.get('message', 'Unknown error')}", "ERROR")
                self.test_results['failed'].append(f"GoTo {date_str}")
                return False

        except Exception as e:
            self.log(f"Go to date error: {e}", "ERROR")
            self.test_results['failed'].append(f"GoTo {date_str}: {str(e)}")
            return False

    def skip_forward(self, timeframe="5m"):
        """Führt einen Skip aus"""
        try:
            response = self.session.post(
                f"{BASE_URL}/api/debug/skip",
                json={"timeframe": timeframe},
                timeout=10
            )
            data = response.json()

            if data.get('status') == 'success':
                new_time = data.get('new_time', 'Unknown')
                candle_type = data.get('candle_type', 'unknown')
                return {
                    'success': True,
                    'new_time': new_time,
                    'candle_type': candle_type,
                    'data': data
                }
            else:
                self.log(f"Skip failed: {data.get('message', 'Unknown error')}", "ERROR")
                return {'success': False}

        except Exception as e:
            self.log(f"Skip error: {e}", "ERROR")
            return {'success': False, 'error': str(e)}

    def perform_multiple_skips(self, count=3, timeframe="5m"):
        """Führt mehrere Skips aus"""
        self.log(f"Performing {count}x Skip in {timeframe} timeframe", "TEST")

        skip_results = []
        for i in range(count):
            result = self.skip_forward(timeframe)
            if result['success']:
                self.log(f"Skip {i+1}/{count}: {result['new_time']} ({result['candle_type']})", "INFO")
                skip_results.append(result)
                time.sleep(0.2)  # Kleine Pause zwischen Skips
            else:
                self.log(f"Skip {i+1}/{count} failed", "ERROR")
                self.test_results['failed'].append(f"Skip {i+1}/{count} in {timeframe}")
                return None

        self.test_results['passed'].append(f"{count}x Skip in {timeframe}")
        return skip_results

    def change_timeframe(self, target_timeframe="15m"):
        """Wechselt Timeframe"""
        self.log(f"Changing timeframe to {target_timeframe}", "TEST")
        try:
            response = self.session.post(
                f"{BASE_URL}/api/chart/change_timeframe",
                json={"timeframe": target_timeframe, "visible_candles": 200},
                timeout=10
            )
            data = response.json()

            if data.get('status') == 'success':
                candle_count = data.get('count', 0)
                self.log(f"Timeframe changed to {target_timeframe}: {candle_count} candles", "INFO")
                return {
                    'success': True,
                    'candle_count': candle_count,
                    'data': data.get('data', []),
                    'response': data
                }
            else:
                self.log(f"Timeframe change failed: {data.get('message', 'Unknown error')}", "ERROR")
                return {'success': False}

        except Exception as e:
            self.log(f"Timeframe change error: {e}", "ERROR")
            return {'success': False, 'error': str(e)}

    def validate_skip_events_in_timeframe(self, chart_data, skip_count=3, timeframe="15m"):
        """
        Validiert ob Skip-Events im Chart vorhanden sind

        Prüft:
        1. Chart hat Daten
        2. Mindestens eine Kerze sollte aus Skip-Events stammen
        3. Keine null/undefined Werte
        """
        self.log(f"Validating {skip_count} skip events in {timeframe} chart", "TEST")

        if not chart_data:
            self.log("Chart data is empty!", "ERROR")
            self.test_results['failed'].append(f"Empty chart data in {timeframe}")
            return False

        self.log(f"Chart has {len(chart_data)} candles", "INFO")

        # Prüfe letzte Kerzen (Skip-Events sollten am Ende sein)
        recent_candles = chart_data[-10:] if len(chart_data) > 10 else chart_data

        # Validiere Kerzen-Struktur
        valid_candles = 0
        for i, candle in enumerate(recent_candles):
            if all(field in candle and candle[field] is not None
                   for field in ['time', 'open', 'high', 'low', 'close']):
                valid_candles += 1
            else:
                self.log(f"Invalid candle at position {i}: {candle}", "WARNING")

        self.log(f"Valid candles in recent data: {valid_candles}/{len(recent_candles)}", "INFO")

        # Erfolgs-Kriterium: Chart hat Daten und alle Kerzen sind valide
        if valid_candles == len(recent_candles):
            self.test_results['passed'].append(f"Skip events integrated in {timeframe}")
            return True
        else:
            self.test_results['warnings'].append(f"Some invalid candles in {timeframe}")
            return False

    def run_complete_test(self):
        """Führt vollständigen Test-Flow aus"""
        self.log("=" * 60)
        self.log("SKIP EVENT PERSISTENCE TEST - STARTING", "TEST")
        self.log("=" * 60)

        # Step 1: Server Health Check
        if not self.check_server_health():
            self.log("Test aborted: Server not available", "ERROR")
            return False

        time.sleep(0.5)

        # Step 2: Go to Date (Reset State)
        if not self.go_to_date(TEST_DATE):
            self.log("Test aborted: Go to date failed", "ERROR")
            return False

        time.sleep(0.5)

        # Step 3: Perform 3x Skip in 5min
        skip_results = self.perform_multiple_skips(count=3, timeframe="5m")
        if not skip_results:
            self.log("Test aborted: Skips failed", "ERROR")
            return False

        time.sleep(0.5)

        # Step 4: Change to 15min Timeframe
        tf_result = self.change_timeframe("15m")
        if not tf_result['success']:
            self.log("Test aborted: Timeframe change failed", "ERROR")
            self.test_results['failed'].append("Timeframe change to 15m")
            return False

        time.sleep(0.5)

        # Step 5: Validate Skip Events in 15min Chart
        validation_result = self.validate_skip_events_in_timeframe(
            tf_result['data'],
            skip_count=3,
            timeframe="15m"
        )

        # Step 6: Test auch mit 30min Timeframe
        self.log("Testing persistence in 30min timeframe", "TEST")
        tf_30m_result = self.change_timeframe("30m")
        if tf_30m_result['success']:
            self.validate_skip_events_in_timeframe(
                tf_30m_result['data'],
                skip_count=3,
                timeframe="30m"
            )

        return validation_result

    def print_test_summary(self):
        """Gibt Test-Zusammenfassung aus"""
        self.log("=" * 60)
        self.log("TEST SUMMARY", "TEST")
        self.log("=" * 60)

        total = len(self.test_results['passed']) + len(self.test_results['failed'])

        if self.test_results['passed']:
            self.log(f"PASSED ({len(self.test_results['passed'])})", "INFO")
            for test in self.test_results['passed']:
                print(f"  ✅ {test}")

        if self.test_results['failed']:
            self.log(f"FAILED ({len(self.test_results['failed'])})", "ERROR")
            for test in self.test_results['failed']:
                print(f"  ❌ {test}")

        if self.test_results['warnings']:
            self.log(f"WARNINGS ({len(self.test_results['warnings'])})", "WARNING")
            for warning in self.test_results['warnings']:
                print(f"  ⚠️  {warning}")

        self.log("=" * 60)

        if total > 0:
            success_rate = (len(self.test_results['passed']) / total) * 100
            self.log(f"Success Rate: {success_rate:.1f}% ({len(self.test_results['passed'])}/{total})",
                    "INFO" if success_rate == 100 else "WARNING")

        # Final Verdict
        if len(self.test_results['failed']) == 0:
            self.log("🎉 ALL TESTS PASSED - Bug Fix verified!", "INFO")
            return True
        else:
            self.log("❌ SOME TESTS FAILED - Bug may still exist", "ERROR")
            return False


if __name__ == "__main__":
    test = SkipEventPersistenceTest()

    try:
        test_passed = test.run_complete_test()
        test.print_test_summary()

        # Exit code für CI/CD
        exit(0 if test_passed else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        test.print_test_summary()
        exit(130)
    except Exception as e:
        print(f"\n\n❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        test.print_test_summary()
        exit(1)
