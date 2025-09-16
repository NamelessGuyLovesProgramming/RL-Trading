"""
Debug Test für Asset-Menü Problem
Testet speziell die Klickbarkeit und Modal-Funktionalität
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_app_lightweight_only import (
    get_yfinance_data,
    create_trading_chart
)

def debug_asset_menu():
    """Debug das Asset-Menü Problem"""
    print("\n" + "="*60)
    print("  ASSET-MENÜ DEBUG TEST")
    print("="*60)

    try:
        # Teste Chart-Erstellung
        print("\n[DEBUG] Lade Test-Daten...")
        data = get_yfinance_data("AAPL", period="1d", interval="1h")

        if not data:
            print("[FAIL] Keine Daten erhalten")
            return False

        print(f"[PASS] Daten geladen: {len(data['data'])} Kerzen")

        # Erstelle Chart HTML
        print("\n[DEBUG] Erstelle Chart HTML...")
        chart_html = create_trading_chart(data)

        if not chart_html:
            print("[FAIL] Kein Chart HTML erstellt")
            return False

        print(f"[PASS] Chart HTML erstellt: {len(chart_html)} Zeichen")

        # Speichere HTML für Debug-Zwecke
        with open("debug_chart.html", "w", encoding="utf-8") as f:
            f.write(chart_html)
        print("[INFO] Chart HTML gespeichert als 'debug_chart.html'")

        # Überprüfe kritische Asset-Menü Elemente
        print("\n[DEBUG] Überprüfe Asset-Menü Elemente...")

        checks = {
            "Asset Symbol Button": 'onclick="openSymbolModal()"' in chart_html,
            "Asset Symbol Text": 'AAPL ▼' in chart_html,
            "Modal Container": 'id="symbolModal"' in chart_html,
            "Modal Open Function": 'function openSymbolModal()' in chart_html,
            "Modal Close Function": 'function closeSymbolModal()' in chart_html,
            "Symbol Store": 'class SymbolStore' in chart_html,
            "Global Functions": 'window.openSymbolModal = openSymbolModal' in chart_html,
            "Click Handler": 'window.onclick = function(event)' in chart_html
        }

        for name, passed in checks.items():
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} {name}")

        # Suche nach möglichen JavaScript-Fehlern
        print("\n[DEBUG] Suche nach JavaScript-Problemen...")

        js_issues = []
        if "${" in chart_html:
            js_issues.append("Template String Problem gefunden")
        if "undefined" in chart_html.lower():
            js_issues.append("Undefined Variablen gefunden")
        if chart_html.count("{") != chart_html.count("}"):
            js_issues.append("Unbalancierte geschweifte Klammern")

        if js_issues:
            print("[WARN] Mögliche JavaScript-Probleme:")
            for issue in js_issues:
                print(f"   - {issue}")
        else:
            print("[PASS] Keine offensichtlichen JavaScript-Probleme")

        # Überprüfe Modal HTML-Struktur
        print("\n[DEBUG] Überprüfe Modal-Struktur...")

        if 'id="symbolModal"' in chart_html:
            modal_start = chart_html.find('id="symbolModal"')
            modal_section = chart_html[modal_start:modal_start+2000]

            modal_elements = {
                "Search Input": 'id="symbolSearch"' in modal_section,
                "Categories Container": 'id="symbolCategories"' in modal_section,
                "Close Button": 'onclick="closeSymbolModal()"' in modal_section,
                "Modal Background": 'position: fixed' in modal_section
            }

            for name, found in modal_elements.items():
                status = "[PASS]" if found else "[FAIL]"
                print(f"{status} Modal {name}")

        return all(checks.values())

    except Exception as e:
        print(f"[ERROR] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_asset_menu()

    if success:
        print("\n[SUCCESS] Asset-Menü Debug erfolgreich!")
        print("[INFO] Öffne 'debug_chart.html' im Browser zum Testen")
    else:
        print("\n[ERROR] Asset-Menü Debug fehlgeschlagen!")

    exit(0 if success else 1)