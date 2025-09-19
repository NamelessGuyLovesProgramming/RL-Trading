"""
Tests für Chart-Update-Funktionalität
Validiert Live-Updates ohne Neu-Laden des Charts
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pandas as pd
from components.chart import _generate_chart_update_js


def test_chart_update_js_generation():
    """Test der JavaScript-Generierung für Chart-Updates"""

    # Test 1: Kein Update-Data (initialer Setup)
    js_code = _generate_chart_update_js(None)
    assert "window.updateChart = function" in js_code
    assert "setInterval(window.checkForUpdates, 100)" in js_code
    print("PASS: Initiale JavaScript-Setup korrekt generiert")

    # Test 2: Mit Update-Daten
    test_update_data = {
        'time': 1694952300,  # Unix timestamp
        'open': 100.0,
        'high': 105.0,
        'low': 98.0,
        'close': 103.0
    }

    js_code = _generate_chart_update_js(test_update_data)
    assert "window.streamlitUpdateFlag = true" in js_code
    assert "window.streamlitUpdateData = " in js_code
    assert '"time": 1694952300' in js_code
    print("PASS: Update-JavaScript mit Daten korrekt generiert")


def test_chart_update_data_format():
    """Test des korrekten Chart-Update-Daten-Formats"""

    # Mock DataFrame row
    timestamp = datetime(2025, 9, 17, 14, 30)
    mock_row = pd.Series({
        'Open': 15000.0,
        'High': 15050.0,
        'Low': 14980.0,
        'Close': 15025.0,
        'Volume': 1000
    })
    mock_row.name = timestamp

    # Simuliere Chart-Update-Daten-Erstellung
    chart_update_data = {
        'time': int(mock_row.name.timestamp()),
        'open': float(mock_row['Open']),
        'high': float(mock_row['High']),
        'low': float(mock_row['Low']),
        'close': float(mock_row['Close'])
    }

    # Validiere Format
    assert isinstance(chart_update_data['time'], int)
    assert isinstance(chart_update_data['open'], float)
    assert isinstance(chart_update_data['high'], float)
    assert isinstance(chart_update_data['low'], float)
    assert isinstance(chart_update_data['close'], float)

    # Validiere Werte
    assert chart_update_data['open'] == 15000.0
    assert chart_update_data['high'] == 15050.0
    assert chart_update_data['low'] == 14980.0
    assert chart_update_data['close'] == 15025.0

    print("PASS: Chart-Update-Daten-Format ist korrekt")


def test_chart_update_edge_cases():
    """Test von Edge Cases für Chart-Updates"""

    # Test 1: Leere Update-Daten
    js_code = _generate_chart_update_js({})
    assert "const updateData = {}" in js_code
    print("PASS: Leere Update-Daten korrekt behandelt")

    # Test 2: Update-Daten mit None-Werten
    invalid_data = {
        'time': None,
        'open': 100.0,
        'high': 105.0,
        'low': 98.0,
        'close': 103.0
    }

    # Sollte trotzdem JavaScript generieren (Fehlerbehandlung im Browser)
    js_code = _generate_chart_update_js(invalid_data)
    assert "window.streamlitUpdateData = " in js_code
    print("PASS: Ungültige Update-Daten werden weitergegeben (Browser-Validation)")


if __name__ == "__main__":
    # Einfache Test-Ausführung ohne pytest
    test_chart_update_js_generation()
    test_chart_update_data_format()
    test_chart_update_edge_cases()
    print("PASS: Alle Chart-Update-Tests bestanden!")