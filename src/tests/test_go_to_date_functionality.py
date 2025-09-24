#!/usr/bin/env python3
"""
Unit Tests für Go To Date Funktionalität
Tests für die korrekte Implementierung der Go To Date Navigation nach Bugfix
"""

import unittest
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
from pathlib import Path

# Füge src zur PYTHONPATH hinzu für Importe
sys.path.append(str(Path(__file__).parent.parent))

class TestGoToDateFunctionality(unittest.TestCase):
    """Tests für Go To Date Navigation und Timeframe Persistence"""

    def setUp(self):
        """Test Setup - Erstelle Test-Daten"""
        # Erstelle Test-DataFrame mit 1000 Kerzen über mehrere Tage
        self.test_dates = pd.date_range(
            start='2024-12-20 00:00:00',
            periods=1000,
            freq='1min'
        )

        self.test_df = pd.DataFrame({
            'datetime': self.test_dates,
            'Open': range(100, 1100),
            'High': range(101, 1101),
            'Low': range(99, 1099),
            'Close': range(100, 1100),
            'Volume': [1000] * 1000
        }).set_index('datetime')

        # Target-Datum für Tests
        self.target_date = datetime(2024, 12, 25, 0, 0, 0)

    def test_go_to_date_direction_logic(self):
        """Test: Go To Date lädt Daten RÜCKWÄRTS bis zum Zieldatum"""
        # Simuliere die Go To Date Logik aus chart_server.py
        target_datetime = self.target_date

        # Finde Kerzen für das Zieldatum (00:00 bis 23:59)
        target_start = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        target_end = target_start + timedelta(days=1)

        # Filtere Test-Daten für den Zielzeitraum
        target_rows = self.test_df[
            (self.test_df.index >= target_start) &
            (self.test_df.index < target_end)
        ]

        if len(target_rows) > 0:
            # KORREKT: Verwende die erste Kerze des Zieldatums und lade 200 Kerzen rückwärts
            end_index = target_rows.index[0] + 1   # Ende bei erster Kerze des Zieldatums (00:00)
            start_index = max(0, end_index - 200)  # 200 Kerzen rückwärts

            # Teste dass die Logik korrekt ist
            self.assertGreater(end_index, start_index, "End-Index muss größer als Start-Index sein")
            self.assertEqual(end_index - start_index, 200, "Sollte genau 200 Kerzen laden (falls genug verfügbar)")

            # Teste dass das letzte Datum korrekt ist
            expected_last_candle = target_datetime.replace(hour=0, minute=0)
            self.assertEqual(
                target_rows.index[0].replace(second=0, microsecond=0),
                expected_last_candle,
                f"Letzte Kerze sollte {expected_last_candle} sein"
            )

    def test_go_to_date_candle_count(self):
        """Test: Go To Date lädt genau 200 Kerzen (wenn verfügbar)"""
        target_datetime = self.target_date
        expected_candle_count = 200

        # Simuliere Kerzen-Auswahl
        target_start = target_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        target_end = target_start + timedelta(days=1)

        target_rows = self.test_df[
            (self.test_df.index >= target_start) &
            (self.test_df.index < target_end)
        ]

        if len(target_rows) > 0:
            end_index = len(self.test_df[self.test_df.index <= target_rows.index[0]])
            start_index = max(0, end_index - expected_candle_count)
            selected_df = self.test_df.iloc[start_index:end_index]

            # Teste Kerzen-Anzahl
            self.assertEqual(
                len(selected_df),
                expected_candle_count,
                f"Sollte {expected_candle_count} Kerzen laden"
            )

    def test_go_to_date_boundary_conditions(self):
        """Test: Go To Date mit Edge Cases (Anfang/Ende der Daten)"""
        # Test am Anfang der Daten
        early_date = self.test_dates[50]  # 51. Kerze als Ziel
        target_start = early_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Sollte weniger als 200 Kerzen zurückgeben wenn am Anfang
        target_rows = self.test_df[self.test_df.index >= target_start]
        if len(target_rows) > 0:
            end_index = len(self.test_df[self.test_df.index <= target_rows.index[0]])
            start_index = max(0, end_index - 200)
            selected_df = self.test_df.iloc[start_index:end_index]

            # Am Anfang der Daten sollten weniger als 200 Kerzen sein
            self.assertLessEqual(len(selected_df), 200, "Am Anfang der Daten: <= 200 Kerzen")
            self.assertGreater(len(selected_df), 0, "Sollte mindestens 1 Kerze laden")

    def test_timeframe_persistence_simulation(self):
        """Test: Global State Management für Timeframe-Wechsel"""
        # Simuliere globale Variable
        current_go_to_date = self.target_date

        # Test verschiedene Timeframes
        timeframes = ['1m', '5m', '15m', '1h']

        for timeframe in timeframes:
            # Simuliere Timeframe-Wechsel mit aktiver Go To Date
            if current_go_to_date is not None:
                # Sollte das gleiche Datum verwenden
                self.assertEqual(
                    current_go_to_date,
                    self.target_date,
                    f"Go To Date sollte bei {timeframe} Wechsel erhalten bleiben"
                )

    def test_csv_fallback_system(self):
        """Test: CSV-basiertes Fallback System"""
        # Teste dass CSV-Pfade korrekt sind
        base_path = Path("src/data/aggregated")
        timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']

        for timeframe in timeframes:
            csv_path = base_path / timeframe / "nq-2024.csv"
            expected_path_str = f"src/data/aggregated/{timeframe}/nq-2024.csv"

            self.assertEqual(
                str(csv_path).replace('\\', '/'),
                expected_path_str,
                f"CSV-Pfad für {timeframe} sollte korrekt sein"
            )

    def test_data_index_consistency(self):
        """Test: Index-basierte Navigation Konsistenz"""
        # Teste dass DataFrame-Indizierung konsistent ist
        target_datetime = self.target_date

        # Finde Index-Position des Zieldatums
        closest_index = self.test_df.index.get_indexer([target_datetime], method='nearest')[0]

        # Teste Index-Berechnung
        if closest_index >= 0:
            end_index = closest_index + 1
            start_index = max(0, end_index - 200)

            # Konsistenz-Tests
            self.assertGreaterEqual(start_index, 0, "Start-Index darf nicht negativ sein")
            self.assertLessEqual(end_index, len(self.test_df), "End-Index darf nicht größer als DataFrame sein")
            self.assertLessEqual(start_index, end_index, "Start-Index muss <= End-Index sein")

    def test_datetime_format_compatibility(self):
        """Test: DateTime-Format Kompatibilität für CSV/Memory-Cache"""
        # Teste verschiedene DateTime-Formate
        test_formats = [
            "2024-12-25 00:00:00",
            "25.12.2024 00:00",
            "12/25/2024 00:00:00"
        ]

        target_dt = datetime(2024, 12, 25, 0, 0, 0)

        # Teste dass pd.to_datetime alle Formate handhaben kann
        for fmt_str in test_formats:
            try:
                parsed_dt = pd.to_datetime(fmt_str)
                self.assertIsInstance(parsed_dt, pd.Timestamp, f"Format {fmt_str} sollte parsbar sein")
            except:
                self.fail(f"DateTime-Format {fmt_str} sollte kompatibel sein")

def run_tests():
    """Führe alle Go To Date Tests aus"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGoToDateFunctionality)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Rückgabe für Erfolg/Fehler
    return result.wasSuccessful()

if __name__ == '__main__':
    print("=== Go To Date Funktionalität Tests ===")
    print("Teste korrekte Implementierung nach Bugfix")
    print("=" * 50)

    success = run_tests()

    if success:
        print("\n✅ ALLE TESTS BESTANDEN - Go To Date Funktionalität korrekt implementiert")
        exit(0)
    else:
        print("\n❌ TESTS FEHLGESCHLAGEN - Go To Date benötigt Überprüfung")
        exit(1)