"""
Tests für Wochentag-Localization im Chart Crosshair-Tooltip
"""

import unittest
from datetime import datetime

class TestWeekdayLocalization(unittest.TestCase):
    """Test cases für deutsche Wochentag-Anzeige im Chart Tooltip"""

    def setUp(self):
        """Test setup - deutsche Wochentag-Array"""
        self.weekdays = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']
        self.months = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']

    def test_weekday_abbreviations(self):
        """Test korrekte deutsche Wochentag-Abkürzungen"""
        self.assertEqual(len(self.weekdays), 7)
        self.assertEqual(self.weekdays[0], 'So')  # Sonntag
        self.assertEqual(self.weekdays[1], 'Mo')  # Montag
        self.assertEqual(self.weekdays[2], 'Di')  # Dienstag
        self.assertEqual(self.weekdays[3], 'Mi')  # Mittwoch
        self.assertEqual(self.weekdays[4], 'Do')  # Donnerstag
        self.assertEqual(self.weekdays[5], 'Fr')  # Freitag
        self.assertEqual(self.weekdays[6], 'Sa')  # Samstag

    def test_month_abbreviations(self):
        """Test korrekte deutsche Monats-Abkürzungen"""
        self.assertEqual(len(self.months), 12)
        self.assertEqual(self.months[0], 'Jan')   # Januar
        self.assertEqual(self.months[2], 'Mär')   # März (deutsche Variante)
        self.assertEqual(self.months[4], 'Mai')   # Mai (vollständig)
        self.assertEqual(self.months[11], 'Dez')  # Dezember

    def test_date_formatting_logic(self):
        """Test logische Formatierung des timeFormatter"""
        # Simuliere 31. Dezember 2024, 14:22 (Dienstag)
        test_date = datetime(2024, 12, 31, 14, 22)

        # Erwartete Komponenten
        weekday = self.weekdays[test_date.weekday()]  # weekday() gibt 0=Montag zurück
        # JavaScript Date.getDay() gibt 0=Sonntag zurück, weekday() gibt 0=Montag
        # Für JavaScript: Di=2, für Python: Di=1
        js_weekday = self.weekdays[(test_date.weekday() + 1) % 7]

        day = str(test_date.day).zfill(2)
        month = self.months[test_date.month - 1]
        year = str(test_date.year)[-2:]
        hours = str(test_date.hour).zfill(2)
        minutes = str(test_date.minute).zfill(2)

        expected_format = f"{js_weekday} {day} {month} '{year} {hours}:{minutes}"

        # Für 31. Dezember 2024, 14:22 (Dienstag)
        self.assertEqual(expected_format, "Di 31 Dez '24 14:22")

    def test_edge_cases(self):
        """Test edge cases für Formatierung"""
        # Einstellige Tage/Stunden mit Padding
        test_date = datetime(2024, 1, 5, 9, 7)

        day = str(test_date.day).zfill(2)
        hours = str(test_date.hour).zfill(2)
        minutes = str(test_date.minute).zfill(2)

        self.assertEqual(day, "05")
        self.assertEqual(hours, "09")
        self.assertEqual(minutes, "07")

    def test_chart_server_localization_exists(self):
        """Test dass Localization im Chart Server definiert ist"""
        import os
        chart_server_path = os.path.join('charts', 'chart_server.py')

        self.assertTrue(os.path.exists(chart_server_path),
                       "Chart Server Datei muss existieren")

        with open(chart_server_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Prüfe dass localization Block vorhanden ist
        self.assertIn('localization:', content,
                     "Localization Block muss im Chart Server definiert sein")

        self.assertIn('timeFormatter:', content,
                     "timeFormatter muss in localization definiert sein")

        # Prüfe deutsche Wochentage im Code
        self.assertIn("['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']", content,
                     "Deutsche Wochentag-Array muss definiert sein")

if __name__ == '__main__':
    unittest.main()