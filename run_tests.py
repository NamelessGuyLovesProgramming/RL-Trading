"""
Automatischer Test-Runner für alle Trading App Tests
Führt Charts und Menu Tests aus und zeigt detaillierte Ergebnisse
"""

import subprocess
import sys
import os
from datetime import datetime

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def run_test_file(test_file):
    """Führe eine Test-Datei aus und sammle Ergebnisse"""
    print(f"\n[RUN] Running: {test_file}")
    print("-" * 50)

    try:
        result = subprocess.run([
            sys.executable, test_file
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))

        print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        success = result.returncode == 0
        return success, result.stdout, result.stderr

    except Exception as e:
        print(f"[FAIL] Failed to run {test_file}: {str(e)}")
        return False, "", str(e)

def main():
    """Haupt-Test-Runner"""
    print_header("TRADING APP - COMPREHENSIVE TEST SUITE")
    print(f"[TIME] Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Test-Dateien
    test_files = [
        "test_chart_functionality.py",
        "test_menu_functionality.py"
    ]

    results = {}
    all_passed = True

    # Führe alle Tests aus
    for test_file in test_files:
        if os.path.exists(test_file):
            success, stdout, stderr = run_test_file(test_file)
            results[test_file] = {
                'success': success,
                'stdout': stdout,
                'stderr': stderr
            }
            if not success:
                all_passed = False
        else:
            print(f"[FAIL] Test file not found: {test_file}")
            all_passed = False

    # Zusammenfassung
    print_header("FINAL TEST SUMMARY")
    print(f"[TIME] Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    for test_file, result in results.items():
        status = "[PASS] PASSED" if result['success'] else "[FAIL] FAILED"
        print(f"{status} {test_file}")

        if not result['success'] and result['stderr']:
            print(f"   Error: {result['stderr'][:200]}...")

    # Gesamt-Status
    if all_passed:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("[OK] Chart functionality is working correctly")
        print("[OK] Menu and observer pattern is working correctly")
        print("\n[NEXT] NEXT STEPS:")
        print("• Your trading app should be fully functional")
        print("• Try clicking on the asset symbol (e.g., AAPL dropdown)")
        print("• The modal should open and allow symbol selection")
        print("• Chart should update without page reload")
    else:
        print("\n[ERROR] SOME TESTS FAILED!")
        print("[FAIL] Check the detailed output above for specific issues")
        print("\n[DEBUG] DEBUGGING STEPS:")
        print("• Check if yfinance is working (internet connection)")
        print("• Verify AVAILABLE_ASSETS structure")
        print("• Check JavaScript console in browser for errors")
        print("• Ensure Streamlit app is running on port 8504")

    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)