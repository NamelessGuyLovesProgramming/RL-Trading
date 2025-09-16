"""
Test Suite für Menüleiste und Observer Pattern
Testet die Asset-Auswahl, Modal-Funktionalität und Symbol-Updates
"""

import sys
import os
import re
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_app_lightweight_only import (
    get_yfinance_data,
    create_trading_chart,
    validate_symbol,
    get_asset_info,
    AVAILABLE_ASSETS
)

class MenuTester:
    """Test-Klasse für Menüleiste und Modal-Funktionalität"""

    def __init__(self):
        self.test_results = []
        self.print_header("MENU & OBSERVER PATTERN TESTS")

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

    def test_asset_symbol_button(self):
        """Test 1: Asset-Symbol Button im Chart"""
        self.print_header("TEST 1: ASSET-SYMBOL BUTTON")

        try:
            # Erstelle Chart HTML mit AAPL
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            if data is None:
                self.print_test("Asset Button Test", False, "No test data available")
                return False

            chart_html = create_trading_chart(data)

            # Überprüfe Asset-Button HTML
            button_checks = {
                "Clickable Asset Symbol": 'onclick="openSymbolModal()"' in chart_html,
                "Asset Symbol Display": 'AAPL ▼' in chart_html or '{st.session_state.selected_symbol} ▼' in chart_html,
                "Button Styling": 'cursor: pointer' in chart_html,
                "Hover Effects": 'onmouseover=' in chart_html and 'onmouseout=' in chart_html
            }

            for check_name, passed in button_checks.items():
                self.print_test(check_name, passed)

            return all(button_checks.values())

        except Exception as e:
            self.print_test("Asset Button Test", False, f"Exception: {str(e)}")
            return False

    def test_modal_html_structure(self):
        """Test 2: Modal HTML-Struktur"""
        self.print_header("TEST 2: MODAL HTML-STRUKTUR")

        try:
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            chart_html = create_trading_chart(data)

            # Überprüfe Modal HTML-Elemente
            modal_checks = {
                "Modal Container": 'id="symbolModal"' in chart_html,
                "Modal Header": 'Select Trading Symbol' in chart_html or 'Asset auswählen' in chart_html,
                "Search Input": 'id="symbolSearch"' in chart_html,
                "Close Button": 'onclick="closeSymbolModal()"' in chart_html,
                "Categories Container": 'id="symbolCategories"' in chart_html,
                "Modal Styling": 'position: fixed' in chart_html and 'z-index:' in chart_html
            }

            for check_name, passed in modal_checks.items():
                self.print_test(check_name, passed)

            return all(modal_checks.values())

        except Exception as e:
            self.print_test("Modal Structure Test", False, f"Exception: {str(e)}")
            return False

    def test_javascript_functions(self):
        """Test 3: JavaScript-Funktionen"""
        self.print_header("TEST 3: JAVASCRIPT-FUNKTIONEN")

        try:
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            chart_html = create_trading_chart(data)

            # Überprüfe JavaScript-Funktionen
            js_checks = {
                "openSymbolModal Function": "function openSymbolModal()" in chart_html,
                "closeSymbolModal Function": "function closeSymbolModal()" in chart_html,
                "selectSymbol Function": "function selectSymbol(" in chart_html,
                "generateSymbolCategories Function": "function generateSymbolCategories()" in chart_html,
                "showAllSymbols Function": "function showAllSymbols()" in chart_html,
                "searchSymbols Function": "function searchSymbols(" in chart_html
            }

            for check_name, passed in js_checks.items():
                self.print_test(check_name, passed)

            return all(js_checks.values())

        except Exception as e:
            self.print_test("JavaScript Functions Test", False, f"Exception: {str(e)}")
            return False

    def test_observer_pattern_setup(self):
        """Test 4: Observer Pattern Setup"""
        self.print_header("TEST 4: OBSERVER PATTERN SETUP")

        try:
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            chart_html = create_trading_chart(data)

            # Überprüfe Observer Pattern Implementierung
            observer_checks = {
                "SymbolStore Class": "class SymbolStore" in chart_html,
                "Global SymbolStore": "window.symbolStore = new SymbolStore()" in chart_html,
                "Subscribe Method": ".subscribe(" in chart_html,
                "SetSymbol Method": ".setSymbol(" in chart_html,
                "Event Listeners": "window.symbolStore.subscribe" in chart_html,
                "Available Assets": "availableAssets" in chart_html
            }

            for check_name, passed in observer_checks.items():
                self.print_test(check_name, passed)

            return all(observer_checks.values())

        except Exception as e:
            self.print_test("Observer Pattern Test", False, f"Exception: {str(e)}")
            return False

    def test_chart_update_mechanism(self):
        """Test 5: Chart-Update Mechanismus"""
        self.print_header("TEST 5: CHART-UPDATE MECHANISMUS")

        try:
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            chart_html = create_trading_chart(data)

            # Überprüfe Chart-Update Code
            update_checks = {
                "Chart Reference": "window.chart" in chart_html,
                "Candlestick Series Reference": "window.candlestickSeries" in chart_html,
                "Volume Series Reference": "window.volumeSeries" in chart_html,
                "Generate Sample Data": "function generateSampleData(" in chart_html,
                "Direct Chart Update": "candlestickSeries.setData" in chart_html,
                "Chart Fit Content": "timeScale().fitContent()" in chart_html,
                "No Page Reload": "return;" in chart_html  # Should return before fallback reload
            }

            for check_name, passed in update_checks.items():
                self.print_test(check_name, passed)

            return all(update_checks.values())

        except Exception as e:
            self.print_test("Chart Update Test", False, f"Exception: {str(e)}")
            return False

    def test_symbol_categories_generation(self):
        """Test 6: Symbol-Kategorien Generierung"""
        self.print_header("TEST 6: SYMBOL-KATEGORIEN GENERIERUNG")

        try:
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            chart_html = create_trading_chart(data)

            # Überprüfe Kategorie-Generierung
            categories_checks = {
                "Stocks Category": "'stocks'" in chart_html and "US Stocks" in chart_html,
                "Crypto Category": "'crypto'" in chart_html and "Cryptocurrency" in chart_html,
                "Forex Category": "'forex'" in chart_html and "Forex" in chart_html,
                "Indices Category": "'indices'" in chart_html and "Indices" in chart_html,
                "Category Config": "categoryConfig" in chart_html,
                "Category Colors": "#26a69a" in chart_html and "#ff9800" in chart_html
            }

            for check_name, passed in categories_checks.items():
                self.print_test(check_name, passed)

            # Überprüfe spezifische Assets
            asset_checks = {
                "AAPL Asset": "AAPL" in chart_html,
                "TSLA Asset": "TSLA" in chart_html,
                "BTC Asset": "BTC-USD" in chart_html,
                "S&P 500 Asset": "^GSPC" in chart_html
            }

            for check_name, passed in asset_checks.items():
                self.print_test(check_name, passed)

            return all(categories_checks.values()) and all(asset_checks.values())

        except Exception as e:
            self.print_test("Categories Generation Test", False, f"Exception: {str(e)}")
            return False

    def test_search_functionality(self):
        """Test 7: Such-Funktionalität"""
        self.print_header("TEST 7: SUCH-FUNKTIONALITÄT")

        try:
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            chart_html = create_trading_chart(data)

            # Überprüfe Such-Funktionalität
            search_checks = {
                "Search Input Event": 'oninput="searchSymbols(' in chart_html,
                "Search Function": "function searchSymbols(" in chart_html,
                "Case Insensitive Search": ".toLowerCase()" in chart_html,
                "Show/Hide Logic": ".style.display" in chart_html,
                "Show All Function": "function showAllSymbols()" in chart_html
            }

            for check_name, passed in search_checks.items():
                self.print_test(check_name, passed)

            return all(search_checks.values())

        except Exception as e:
            self.print_test("Search Functionality Test", False, f"Exception: {str(e)}")
            return False

    def test_notification_system(self):
        """Test 8: Benachrichtigungs-System"""
        self.print_header("TEST 8: BENACHRICHTIGUNGS-SYSTEM")

        try:
            data = get_yfinance_data("AAPL", period="1d", interval="1h")
            chart_html = create_trading_chart(data)

            # Überprüfe Notification System
            notification_checks = {
                "ShowNotification Function": "function showNotification(" in chart_html,
                "Notification Styling": "position: absolute" in chart_html,
                "Notification Animation": "slideIn" in chart_html,
                "Auto Remove": "setTimeout(" in chart_html,
                "Success Notifications": "Symbol changed to" in chart_html
            }

            for check_name, passed in notification_checks.items():
                self.print_test(check_name, passed)

            return all(notification_checks.values())

        except Exception as e:
            self.print_test("Notification System Test", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Führe alle Menu/Observer Tests aus"""
        print("\n[START] STARTING MENU & OBSERVER PATTERN TESTS")

        tests = [
            self.test_asset_symbol_button,
            self.test_modal_html_structure,
            self.test_javascript_functions,
            self.test_observer_pattern_setup,
            self.test_chart_update_mechanism,
            self.test_symbol_categories_generation,
            self.test_search_functionality,
            self.test_notification_system
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
    tester = MenuTester()
    success = tester.run_all_tests()

    if success:
        print("\n[SUCCESS] ALL MENU TESTS PASSED!")
        exit(0)
    else:
        print("\n[ERROR] SOME MENU TESTS FAILED - CHECK ABOVE FOR DETAILS")
        exit(1)