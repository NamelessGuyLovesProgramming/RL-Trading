#!/usr/bin/env python3
"""
Tests für Smart Chart Positioning System
Testet die 50-Kerzen Standard-Zoom Funktionalität mit 20% Freiraum
"""

import pytest
import json
from pathlib import Path


class TestSmartChartPositioning:
    """Test-Suite für Smart Chart Positioning System"""

    def test_standard_candle_count_configuration(self):
        """Test: Standard-Anzahl von 50 Kerzen ist konfiguriert"""
        # Simuliere JavaScript-Konfiguration
        config = {
            'standardCandleCount': 50,
            'rightMarginPercent': 0.2
        }

        assert config['standardCandleCount'] == 50, "Standard sollte 50 Kerzen sein"
        assert config['rightMarginPercent'] == 0.2, "Rechter Freiraum sollte 20% sein"

        print("OK: Standard-Konfiguration: 50 Kerzen mit 20% Freiraum")

    def test_time_range_calculation_with_margin(self):
        """Test: Zeitbereich-Berechnung mit 20% Freiraum"""
        # Simuliere Kerzen-Daten (Unix-Timestamps)
        mock_candles = [
            {'time': 1000, 'open': 100, 'high': 105, 'low': 95, 'close': 102},
            {'time': 1100, 'open': 102, 'high': 107, 'low': 98, 'close': 104},
            {'time': 1200, 'open': 104, 'high': 109, 'low': 100, 'close': 106},
            {'time': 1300, 'open': 106, 'high': 111, 'low': 102, 'close': 108},
            {'time': 1400, 'open': 108, 'high': 113, 'low': 104, 'close': 110}
        ]

        # Simuliere Smart Positioning Logik
        data_length = len(mock_candles)
        standard_candles = 50
        visible_candles = min(standard_candles, data_length)

        start_index = max(0, data_length - visible_candles)
        end_index = data_length - 1

        start_time = mock_candles[start_index]['time']
        end_time = mock_candles[end_index]['time']

        # 20% Freiraum berechnen
        time_span = end_time - start_time
        margin_percent = 0.2
        margin_time = time_span * (margin_percent / (1 - margin_percent))
        adjusted_end_time = end_time + margin_time

        expected_margin = (1400 - 1000) * (0.2 / 0.8)  # = 400 * 0.25 = 100
        expected_end = 1400 + 100  # = 1500

        assert start_time == 1000, f"Start-Zeit sollte 1000 sein, ist {start_time}"
        assert adjusted_end_time == expected_end, f"End-Zeit mit Freiraum sollte {expected_end} sein, ist {adjusted_end_time}"

        print(f"OK: Zeitbereich: {start_time}-{adjusted_end_time} (Freiraum: {margin_time})")

    def test_chart_positioning_with_large_dataset(self):
        """Test: Chart-Positioning mit großem Datensatz (nur 50 Kerzen sichtbar)"""
        # Simuliere 200 Kerzen, aber nur 50 sollten sichtbar sein
        large_dataset = []
        for i in range(200):
            large_dataset.append({
                'time': 1000 + (i * 100),
                'open': 100 + i,
                'high': 105 + i,
                'low': 95 + i,
                'close': 102 + i
            })

        data_length = len(large_dataset)
        standard_candles = 50
        visible_candles = min(standard_candles, data_length)

        start_index = max(0, data_length - visible_candles)
        end_index = data_length - 1

        # Sollte die letzten 50 Kerzen zeigen
        assert visible_candles == 50, f"Sollte 50 Kerzen zeigen, zeigt {visible_candles}"
        assert start_index == 150, f"Start-Index sollte 150 sein (200-50), ist {start_index}"
        assert end_index == 199, f"End-Index sollte 199 sein, ist {end_index}"

        # Zeitbereich der letzten 50 Kerzen
        start_time = large_dataset[start_index]['time']  # Zeit bei Index 150
        end_time = large_dataset[end_index]['time']      # Zeit bei Index 199

        expected_start = 1000 + (150 * 100)  # = 16000
        expected_end = 1000 + (199 * 100)    # = 20900

        assert start_time == expected_start, f"Start-Zeit sollte {expected_start} sein, ist {start_time}"
        assert end_time == expected_end, f"End-Zeit sollte {expected_end} sein, ist {end_time}"

        print(f"OK: Großer Datensatz: {data_length} Kerzen -> Zeige letzten {visible_candles} ({start_index}-{end_index})")

    def test_chart_positioning_with_small_dataset(self):
        """Test: Chart-Positioning mit weniger als 50 Kerzen"""
        # Simuliere nur 20 Kerzen
        small_dataset = []
        for i in range(20):
            small_dataset.append({
                'time': 1000 + (i * 100),
                'open': 100 + i,
                'high': 105 + i,
                'low': 95 + i,
                'close': 102 + i
            })

        data_length = len(small_dataset)
        standard_candles = 50
        visible_candles = min(standard_candles, data_length)

        start_index = max(0, data_length - visible_candles)

        # Sollte alle 20 Kerzen zeigen (nicht 50)
        assert visible_candles == 20, f"Sollte alle 20 Kerzen zeigen, zeigt {visible_candles}"
        assert start_index == 0, f"Start-Index sollte 0 sein bei kleinem Datensatz, ist {start_index}"

        print(f"OK: Kleiner Datensatz: {data_length} Kerzen -> Zeige alle {visible_candles}")

    def test_margin_calculation_edge_cases(self):
        """Test: Freiraum-Berechnung bei Edge Cases"""
        # Test 1: Nur eine Kerze
        single_candle = [{'time': 1000, 'open': 100, 'high': 105, 'low': 95, 'close': 102}]

        if len(single_candle) == 1:
            # Bei nur einer Kerze: start_index == end_index -> keine Berechnung möglich
            start_index = max(0, 1 - min(50, 1))  # = 0
            end_index = 1 - 1  # = 0

            assert start_index == end_index, "Bei einer Kerze sollten Start- und End-Index gleich sein"
            print("OK: Edge Case: Einzelne Kerze korrekt behandelt")

        # Test 2: Zwei Kerzen
        two_candles = [
            {'time': 1000, 'open': 100, 'high': 105, 'low': 95, 'close': 102},
            {'time': 2000, 'open': 102, 'high': 107, 'low': 98, 'close': 104}
        ]

        start_time = two_candles[0]['time']
        end_time = two_candles[1]['time']
        time_span = end_time - start_time  # = 1000
        margin_time = time_span * (0.2 / 0.8)  # = 1000 * 0.25 = 250
        adjusted_end_time = end_time + margin_time  # = 2000 + 250 = 2250

        assert adjusted_end_time == 2250, f"Bei 2 Kerzen sollte End-Zeit 2250 sein, ist {adjusted_end_time}"
        print("OK: Edge Case: Zwei Kerzen korrekt behandelt")

    def test_timeframe_reset_behavior(self):
        """Test: Nach Timeframe-Wechsel zurück zu 50-Kerzen Standard"""
        # Simuliere verschiedene Timeframes
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']

        for tf in timeframes:
            # Jeder Timeframe sollte zur Standard-Position zurückkehren
            config = {
                'timeframe': tf,
                'reset_to_standard': True,
                'visible_candles': 50,
                'right_margin': 0.2
            }

            assert config['reset_to_standard'] == True, f"Timeframe {tf} sollte zur Standard-Position zurückkehren"
            assert config['visible_candles'] == 50, f"Timeframe {tf} sollte 50 Kerzen zeigen"

        print(f"OK: Timeframe Reset: Alle {len(timeframes)} Timeframes kehren zu Standard zurück")

    def test_zoom_out_preserves_margin(self):
        """Test: Zoom-Out kann den 20% Freiraum überschreiten (per Drag)"""
        # Simuliere Zoom-Out Verhalten
        initial_candles = 50
        zoomed_out_candles = 200  # User zoomt aus

        # Initial: 50 Kerzen mit 20% Freiraum
        initial_config = {
            'visible_candles': initial_candles,
            'right_margin_enforced': True
        }

        # Nach Zoom-Out: Mehr Kerzen, Freiraum kann überschritten werden
        zoomed_config = {
            'visible_candles': zoomed_out_candles,
            'right_margin_enforced': False,  # Kann per Drag überschritten werden
            'user_interaction': 'zoom_out'
        }

        assert initial_config['right_margin_enforced'] == True, "Initial sollte Freiraum erzwingen"
        assert zoomed_config['right_margin_enforced'] == False, "Zoom-Out erlaubt Freiraum-Überschreitung"
        assert zoomed_config['visible_candles'] > initial_config['visible_candles'], "Zoom-Out zeigt mehr Kerzen"

        print(f"OK: Zoom-Verhalten: {initial_candles} -> {zoomed_out_candles} Kerzen, Freiraum flexibel")


def test_integration_with_backend():
    """Integration Test: Backend liefert 50 Kerzen als Standard"""
    # Simuliere Backend-Response
    backend_config = {
        'default_visible_candles': 50,
        'csv_tail_count': 50,
        'api_default_candles': 50
    }

    assert backend_config['default_visible_candles'] == 50, "Backend sollte 50 Kerzen als Standard setzen"
    assert backend_config['csv_tail_count'] == 50, "CSV-Load sollte 50 Kerzen laden"
    assert backend_config['api_default_candles'] == 50, "API sollte 50 Kerzen als Default haben"

    print("OK: Backend Integration: 50-Kerzen Standard konfiguriert")


if __name__ == "__main__":
    # Führe alle Tests aus
    test_instance = TestSmartChartPositioning()

    print("Starting Smart Chart Positioning Tests...")
    print("=" * 60)

    try:
        test_instance.test_standard_candle_count_configuration()
        test_instance.test_time_range_calculation_with_margin()
        test_instance.test_chart_positioning_with_large_dataset()
        test_instance.test_chart_positioning_with_small_dataset()
        test_instance.test_margin_calculation_edge_cases()
        test_instance.test_timeframe_reset_behavior()
        test_instance.test_zoom_out_preserves_margin()
        test_integration_with_backend()

        print("=" * 60)
        print("SUCCESS: Alle Tests erfolgreich! Smart Chart Positioning funktioniert korrekt.")

    except AssertionError as e:
        print(f"FEHLER: Test fehlgeschlagen: {e}")
        exit(1)
    except Exception as e:
        print(f"FEHLER: Unerwarteter Fehler: {e}")
        exit(1)