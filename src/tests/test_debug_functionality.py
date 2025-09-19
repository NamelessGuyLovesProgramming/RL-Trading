"""
Tests für Debug-Funktionalität
Validiert korrekte Startdatum-Behandlung und Chart-Positionierung
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, date
import pandas as pd
from data.yahoo_finance import filter_debug_data


def test_filter_debug_data_with_start_date():
    """Test der korrekten Filterung nach Startdatum"""
    # Mock-Daten erstellen
    dates = pd.date_range('2023-09-01', periods=30, freq='D')
    mock_data = {
        'data': pd.DataFrame({
            'Open': range(100, 130),
            'High': range(105, 135),
            'Low': range(95, 125),
            'Close': range(102, 132),
            'Volume': range(1000, 1030)
        }, index=dates),
        'symbol': 'TEST',
        'last_update': datetime.now(),
        'info': {}
    }

    # Test 1: Startdatum in der Mitte, Index 0 (sollte nur das Startdatum zeigen)
    start_date = date(2023, 9, 15)
    current_index = 0

    result = filter_debug_data(mock_data, start_date, current_index)

    assert result is not None
    assert 'debug_start_index' in result
    assert result['debug_start_index'] == 14  # 15. September ist Index 14
    assert len(result['data']) == 15  # Alle Daten bis einschließlich Startdatum


def test_filter_debug_data_progression():
    """Test der Progression durch Debug-Indizes"""
    # Mock-Daten erstellen
    dates = pd.date_range('2023-09-01', periods=10, freq='D')
    mock_data = {
        'data': pd.DataFrame({
            'Open': range(100, 110),
            'High': range(105, 115),
            'Low': range(95, 105),
            'Close': range(102, 112),
            'Volume': range(1000, 1010)
        }, index=dates),
        'symbol': 'TEST',
        'last_update': datetime.now(),
        'info': {}
    }

    start_date = date(2023, 9, 5)  # 5. September = Index 4

    # Test Index 0: Sollte bis 5. September gehen
    result0 = filter_debug_data(mock_data, start_date, 0)
    assert len(result0['data']) == 5  # Indizes 0-4

    # Test Index 2: Sollte bis 7. September gehen
    result2 = filter_debug_data(mock_data, start_date, 2)
    assert len(result2['data']) == 7  # Indizes 0-6

    # Test Index 5: Sollte alle Daten zeigen
    result5 = filter_debug_data(mock_data, start_date, 5)
    assert len(result5['data']) == 10  # Alle Indizes 0-9


def test_filter_debug_data_edge_cases():
    """Test von Edge Cases"""
    dates = pd.date_range('2023-09-01', periods=5, freq='D')
    mock_data = {
        'data': pd.DataFrame({
            'Open': range(100, 105),
            'High': range(105, 110),
            'Low': range(95, 100),
            'Close': range(102, 107),
            'Volume': range(1000, 1005)
        }, index=dates),
        'symbol': 'TEST',
        'last_update': datetime.now(),
        'info': {}
    }

    # Edge Case 1: Startdatum liegt nach allen Daten
    future_date = date(2023, 9, 10)
    result = filter_debug_data(mock_data, future_date, 0)
    assert result is None

    # Edge Case 2: Startdatum liegt vor allen Daten
    past_date = date(2023, 8, 25)
    result = filter_debug_data(mock_data, past_date, 0)
    assert result is not None
    assert len(result['data']) == 1  # Nur erste Kerze

    # Edge Case 3: Index größer als verfügbare Daten
    start_date = date(2023, 9, 3)  # Index 2
    result = filter_debug_data(mock_data, start_date, 10)  # Großer Index
    assert len(result['data']) == 5  # Alle verfügbaren Daten


if __name__ == "__main__":
    # Einfache Test-Ausführung ohne pytest
    test_filter_debug_data_with_start_date()
    test_filter_debug_data_progression()
    test_filter_debug_data_edge_cases()
    print("PASS: Alle Debug-Funktionalitaets-Tests bestanden!")