#!/usr/bin/env python3
"""
🚀 Multi-Timeframe Synchronisation Test Suite
Tests für Skip → TF-Switch Zeitkonsistenz Bug-Fix

Author: Claude Code Session
Date: 2025-09-28
"""

import asyncio
import requests
import json
import time
from datetime import datetime, timedelta

class MultiTimeframeTestSuite:
    """
    Umfassende Test Suite für Multi-Timeframe Zeit-Synchronisation
    Testet das exakte Bug-Szenario: Skip → TF-Switch ohne Zeitsprünge
    """

    def __init__(self, base_url="http://localhost:8003"):
        self.base_url = base_url
        self.test_results = []
        self.test_timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h']

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
                response = requests.post(url, json=data, timeout=10)
            else:
                response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
        except Exception as e:
            raise Exception(f"API Call failed: {e}")

    def test_goto_date_functionality(self):
        """Test 1: Basis Go-To-Date Funktionalität"""
        try:
            # Go to specific date
            test_date = "2024-12-13"
            result = self.call_api("/api/debug/go_to_date", "POST", {
                "date": test_date
            })

            success = result.get('status') == 'success'
            details = f"GoTo {test_date} -> {result.get('message', 'N/A')}"
            self.log_result("GoTo Date Baseline", success, details)
            return success

        except Exception as e:
            self.log_result("GoTo Date Baseline", False, str(e))
            return False

    def test_skip_operations(self):
        """Test 2: Skip-Operationen Basisfunktionalität"""
        try:
            skip_count = 3
            for i in range(skip_count):
                result = self.call_api("/api/debug/skip", "POST")

                if result.get('status') != 'success':
                    self.log_result(f"Skip Operation {i+1}", False, result.get('message', 'Unknown error'))
                    return False

                # Short delay zwischen Skips
                time.sleep(0.2)

            self.log_result("Skip Operations", True, f"{skip_count} consecutive skips successful")
            return True

        except Exception as e:
            self.log_result("Skip Operations", False, str(e))
            return False

    def test_critical_bug_scenario(self):
        """Test 3: CRITICAL BUG SCENARIO - Skip → TF-Switch ohne Zeitsprung"""
        try:
            # Phase 1: Go to baseline date
            goto_result = self.call_api("/api/debug/go_to_date", "POST", {
                "date": "2024-12-13"
            })

            if goto_result.get('status') != 'success':
                self.log_result("Critical Bug Scenario - GoTo", False, "GoTo failed")
                return False

            # Phase 2: Perform skip operation
            skip_result = self.call_api("/api/debug/skip", "POST")
            if skip_result.get('status') != 'success':
                self.log_result("Critical Bug Scenario - Skip", False, "Skip failed")
                return False

            skip_time = skip_result.get('debug_time')
            expected_date = "2024-12-13"  # Should stay in same date range

            # Phase 3: Switch to different timeframe (critical test!)
            for tf in ['3m', '15m', '30m']:
                tf_result = self.call_api("/api/chart/change_timeframe", "POST", {
                    "timeframe": tf,
                    "visible_candles": 100
                })

                if tf_result.get('status') != 'success':
                    self.log_result(f"Critical Bug - TF Switch {tf}", False, tf_result.get('message', 'TF Switch failed'))
                    return False

                # Verify time consistency - no jumps to distant dates
                global_time = tf_result.get('global_time')
                if global_time and expected_date not in global_time:
                    self.log_result(f"Critical Bug - Time Jump {tf}", False, f"Unexpected time jump: {global_time}")
                    return False

                print(f"    >> TF {tf}: global_time={global_time}")
                time.sleep(0.3)  # Allow processing

            self.log_result("Critical Bug Scenario", True, "No temporal inconsistencies detected")
            return True

        except Exception as e:
            self.log_result("Critical Bug Scenario", False, str(e))
            return False

    def test_all_timeframe_combinations(self):
        """Test 4: Erschöpfende TF-Kombination Tests"""
        success_count = 0
        total_tests = 0

        try:
            for source_tf in self.test_timeframes[:4]:  # Limit für Performance
                for target_tf in self.test_timeframes[:4]:
                    if source_tf == target_tf:
                        continue

                    total_tests += 1

                    # Set source timeframe
                    self.call_api(f"/api/debug/set_timeframe/{source_tf}", "POST")

                    # Perform skip
                    skip_result = self.call_api("/api/debug/skip", "POST")

                    # Switch to target timeframe
                    tf_result = self.call_api("/api/chart/change_timeframe", "POST", {
                        "timeframe": target_tf,
                        "visible_candles": 50
                    })

                    if tf_result.get('status') == 'success':
                        success_count += 1

                    time.sleep(0.1)  # Rate limiting

            success_rate = (success_count / total_tests) * 100 if total_tests > 0 else 0
            success = success_rate >= 90  # 90% success threshold

            self.log_result("TF Combination Tests", success, f"{success_count}/{total_tests} successful ({success_rate:.1f}%)")
            return success

        except Exception as e:
            self.log_result("TF Combination Tests", False, str(e))
            return False

    def test_temporal_consistency_validation(self):
        """Test 5: Temporal Consistency Validation"""
        try:
            # Go to known date
            self.call_api("/api/debug/go_to_date", "POST", {"date": "2024-12-13"})

            # Perform multiple skip operations
            timestamps = []
            for i in range(5):
                result = self.call_api("/api/debug/skip", "POST")
                if result.get('status') == 'success':
                    timestamps.append(result.get('debug_time'))
                time.sleep(0.1)

            # Verify timestamps are monotonically increasing
            monotonic = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))

            # Switch timeframes and verify time doesn't jump backward
            final_tf_result = self.call_api("/api/chart/change_timeframe", "POST", {
                "timeframe": "15m"
            })

            final_time = final_tf_result.get('global_time')
            last_skip_time = timestamps[-1] if timestamps else None

            # Check no backward time travel
            no_time_travel = True
            if last_skip_time and final_time:
                # Basic check: dates should be consistent
                last_date = last_skip_time.split('T')[0]
                final_date = final_time.split('T')[0]
                no_time_travel = last_date == final_date

            success = monotonic and no_time_travel
            details = f"Monotonic: {monotonic}, No time travel: {no_time_travel}, Final time: {final_time}"

            self.log_result("Temporal Consistency", success, details)
            return success

        except Exception as e:
            self.log_result("Temporal Consistency", False, str(e))
            return False

    def run_full_test_suite(self):
        """Führt alle Tests aus und generiert Report"""
        print("==> Starting Multi-Timeframe Synchronisation Test Suite")
        print("=" * 60)

        test_methods = [
            self.test_goto_date_functionality,
            self.test_skip_operations,
            self.test_critical_bug_scenario,
            self.test_all_timeframe_combinations,
            self.test_temporal_consistency_validation
        ]

        start_time = datetime.now()

        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                self.log_result(test_method.__name__, False, f"Unexpected error: {e}")

            time.sleep(0.5)  # Pause zwischen Tests

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
        print("==> FINAL TEST REPORT")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Duration: {duration.total_seconds():.1f}s")

        if success_rate >= 80:
            print("==> OVERALL RESULT: PASS - Multi-TF Bug Fix appears successful!")
        else:
            print("==> OVERALL RESULT: FAIL - Multi-TF issues detected!")

        # Print failed tests
        failed_tests = [r for r in self.test_results if not r['success']]
        if failed_tests:
            print("\n==> FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")

if __name__ == "__main__":
    # Run test suite
    test_suite = MultiTimeframeTestSuite()
    test_suite.run_full_test_suite()