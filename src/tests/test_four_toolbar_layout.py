#!/usr/bin/env python3
"""
Tests für das Four-Toolbar-Layout System
Testet die CSS-Dimensionen und Layout-Logik der vier Chart-Toolbars
"""

import unittest
import re
from pathlib import Path

class TestFourToolbarLayout(unittest.TestCase):
    """Tests für das Four-Toolbar-Layout System"""

    def setUp(self):
        """Setup für Tests"""
        self.chart_server_path = Path("chart_server.py")
        self.assertTrue(self.chart_server_path.exists(), "chart_server.py nicht gefunden")

        with open(self.chart_server_path, 'r', encoding='utf-8') as f:
            self.chart_server_content = f.read()

    def test_chart_toolbar_1_exists(self):
        """Test: Chart-Toolbar 1 (top, leer) existiert"""
        pattern = r'\.chart-toolbar-1\s*\{[^}]*\}'
        match = re.search(pattern, self.chart_server_content)
        self.assertIsNotNone(match, "Chart-Toolbar 1 CSS-Klasse nicht gefunden")

        # Teste spezifische Eigenschaften
        toolbar_css = match.group(0)
        self.assertIn('position: fixed', toolbar_css)
        self.assertIn('top: 0', toolbar_css)
        self.assertIn('height: 40px', toolbar_css)

    def test_chart_toolbar_2_exists(self):
        """Test: Chart-Toolbar 2 (timeframes) existiert"""
        pattern = r'\.chart-toolbar-2\s*\{[^}]*\}'
        match = re.search(pattern, self.chart_server_content)
        self.assertIsNotNone(match, "Chart-Toolbar 2 CSS-Klasse nicht gefunden")

        toolbar_css = match.group(0)
        self.assertIn('position: fixed', toolbar_css)
        self.assertIn('top: 40px', toolbar_css)
        self.assertIn('height: 40px', toolbar_css)

    def test_chart_sidebar_left_exists(self):
        """Test: Left Chart-Sidebar existiert"""
        pattern = r'\.chart-sidebar-left\s*\{[^}]*\}'
        match = re.search(pattern, self.chart_server_content)
        self.assertIsNotNone(match, "Chart-Sidebar Left CSS-Klasse nicht gefunden")

        sidebar_css = match.group(0)
        self.assertIn('position: fixed', sidebar_css)
        self.assertIn('width: 35px', sidebar_css)
        self.assertIn('top: 80px', sidebar_css)

    def test_chart_toolbar_bottom_exists(self):
        """Test: Bottom Chart-Toolbar existiert"""
        pattern = r'\.chart-toolbar-bottom\s*\{[^}]*\}'
        match = re.search(pattern, self.chart_server_content)
        self.assertIsNotNone(match, "Chart-Toolbar Bottom CSS-Klasse nicht gefunden")

        toolbar_css = match.group(0)
        self.assertIn('position: fixed', toolbar_css)
        self.assertIn('bottom: 0', toolbar_css)
        self.assertIn('height: 40px', toolbar_css)
        self.assertIn('left: 35px', toolbar_css)

    def test_chart_container_dimensions(self):
        """Test: Chart-Container hat korrekte Dimensionen"""
        pattern = r'#chart_container\s*\{[^}]*\}'
        match = re.search(pattern, self.chart_server_content)
        self.assertIsNotNone(match, "Chart-Container CSS nicht gefunden")

        container_css = match.group(0)
        self.assertIn('width: calc(100% - 35px)', container_css)
        self.assertIn('height: calc(100vh - 120px)', container_css)
        self.assertIn('margin-left: 35px', container_css)

    def test_html_toolbar_elements_exist(self):
        """Test: HTML-Elemente für alle Toolbars existieren"""
        # Chart-Toolbar 1 (leer)
        self.assertIn('class="chart-toolbar-1"', self.chart_server_content)

        # Chart-Toolbar 2 (timeframes)
        self.assertIn('class="chart-toolbar-2"', self.chart_server_content)

        # Left Sidebar
        self.assertIn('class="chart-sidebar-left"', self.chart_server_content)

        # Bottom Toolbar
        self.assertIn('class="chart-toolbar-bottom"', self.chart_server_content)

    def test_toolbar_positioning_hierarchy(self):
        """Test: Toolbar-Positionierung ist hierarchisch korrekt"""
        # Top Toolbars
        toolbar1_pattern = r'\.chart-toolbar-1[^}]*top:\s*0[^}]*'
        toolbar2_pattern = r'\.chart-toolbar-2[^}]*top:\s*40px[^}]*'

        self.assertTrue(re.search(toolbar1_pattern, self.chart_server_content),
                       "Chart-Toolbar 1 nicht bei top: 0")
        self.assertTrue(re.search(toolbar2_pattern, self.chart_server_content),
                       "Chart-Toolbar 2 nicht bei top: 40px")

        # Left Sidebar startet nach beiden Top-Toolbars
        sidebar_pattern = r'\.chart-sidebar-left[^}]*top:\s*80px[^}]*'
        self.assertTrue(re.search(sidebar_pattern, self.chart_server_content),
                       "Left Sidebar nicht bei top: 80px")

    def test_consistent_toolbar_heights(self):
        """Test: Alle horizontalen Toolbars haben gleiche Höhe"""
        # Alle horizontalen Toolbars sollten 40px hoch sein
        height_patterns = [
            r'\.chart-toolbar-1[^}]*height:\s*40px[^}]*',
            r'\.chart-toolbar-2[^}]*height:\s*40px[^}]*',
            r'\.chart-toolbar-bottom[^}]*height:\s*40px[^}]*'
        ]

        for pattern in height_patterns:
            self.assertTrue(re.search(pattern, self.chart_server_content),
                           f"Toolbar-Höhe 40px nicht gefunden für Pattern: {pattern}")

    def test_sidebar_width_optimization(self):
        """Test: Left-Sidebar hat optimierte Breite (35px)"""
        sidebar_pattern = r'\.chart-sidebar-left[^}]*width:\s*35px[^}]*'
        self.assertTrue(re.search(sidebar_pattern, self.chart_server_content),
                       "Left Sidebar nicht 35px breit")

        # Bottom Toolbar sollte entsprechend positioniert sein
        bottom_pattern = r'\.chart-toolbar-bottom[^}]*left:\s*35px[^}]*'
        self.assertTrue(re.search(bottom_pattern, self.chart_server_content),
                       "Bottom Toolbar nicht bei left: 35px")

    def test_no_padding_margins(self):
        """Test: Toolbars haben kein Padding/Margin"""
        toolbar_classes = [
            'chart-toolbar-1', 'chart-toolbar-2',
            'chart-sidebar-left', 'chart-toolbar-bottom'
        ]

        for toolbar_class in toolbar_classes:
            pattern = rf'\.{toolbar_class}[^}}]*padding:\s*0[^}}]*'
            self.assertTrue(re.search(pattern, self.chart_server_content),
                           f"{toolbar_class} hat Padding != 0")

            pattern = rf'\.{toolbar_class}[^}}]*margin:\s*0[^}}]*'
            self.assertTrue(re.search(pattern, self.chart_server_content),
                           f"{toolbar_class} hat Margin != 0")

    def test_z_index_layering(self):
        """Test: Alle Toolbars haben korrekten z-index"""
        toolbar_classes = [
            'chart-toolbar-1', 'chart-toolbar-2',
            'chart-sidebar-left', 'chart-toolbar-bottom'
        ]

        for toolbar_class in toolbar_classes:
            pattern = rf'\.{toolbar_class}[^}}]*z-index:\s*1000[^}}]*'
            self.assertTrue(re.search(pattern, self.chart_server_content),
                           f"{toolbar_class} hat z-index != 1000")

    def test_background_styling_consistency(self):
        """Test: Alle Toolbars haben konsistentes Styling"""
        toolbar_classes = [
            'chart-toolbar-1', 'chart-toolbar-2',
            'chart-sidebar-left', 'chart-toolbar-bottom'
        ]

        for toolbar_class in toolbar_classes:
            # Background color
            pattern = rf'\.{toolbar_class}[^}}]*background:\s*#1e1e1e[^}}]*'
            self.assertTrue(re.search(pattern, self.chart_server_content),
                           f"{toolbar_class} hat background != #1e1e1e")

    def test_layout_mathematical_correctness(self):
        """Test: Layout-Mathematik ist korrekt"""
        # Chart-Container sollte exakt passen
        # Top: 80px (2x 40px Toolbars)
        # Bottom: 40px (1x 40px Toolbar)
        # Left: 35px (Sidebar)
        # Total: 100vh - 120px height, 100% - 35px width

        container_pattern = r'#chart_container[^}]*height:\s*calc\(100vh\s*-\s*120px\)[^}]*'
        self.assertTrue(re.search(container_pattern, self.chart_server_content),
                       "Chart-Container height calc incorrect")

        container_pattern = r'#chart_container[^}]*width:\s*calc\(100%\s*-\s*35px\)[^}]*'
        self.assertTrue(re.search(container_pattern, self.chart_server_content),
                       "Chart-Container width calc incorrect")


class TestToolbarLayoutIntegration(unittest.TestCase):
    """Integration Tests für Toolbar-Layout"""

    def setUp(self):
        """Setup für Integration Tests"""
        self.chart_server_path = Path("chart_server.py")
        with open(self.chart_server_path, 'r', encoding='utf-8') as f:
            self.content = f.read()

    def test_timeframe_buttons_in_correct_toolbar(self):
        """Test: Timeframe-Buttons sind in Chart-Toolbar 2"""
        # Finde Chart-Toolbar 2 HTML-Block
        toolbar2_pattern = r'<div class="chart-toolbar-2">(.*?)</div>'
        match = re.search(toolbar2_pattern, self.content, re.DOTALL)
        self.assertIsNotNone(match, "Chart-Toolbar 2 HTML-Block nicht gefunden")

        toolbar2_content = match.group(1)

        # Timeframe-Buttons sollten in diesem Block sein
        timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']
        for tf in timeframes:
            self.assertIn(f'data-timeframe="{tf}"', toolbar2_content)

    def test_empty_toolbars_are_empty(self):
        """Test: Leere Toolbars sind tatsächlich leer"""
        # Chart-Toolbar 1 sollte nur Kommentar enthalten
        toolbar1_pattern = r'<div class="chart-toolbar-1">(.*?)</div>'
        match = re.search(toolbar1_pattern, self.content, re.DOTALL)
        self.assertIsNotNone(match)

        toolbar1_content = match.group(1).strip()
        # Sollte nur HTML-Kommentar enthalten
        self.assertTrue('<!-- Leer' in toolbar1_content or toolbar1_content == '')

    def test_layout_completeness(self):
        """Test: Layout ist vollständig implementiert"""
        required_elements = [
            'chart-toolbar-1',  # Top 1
            'chart-toolbar-2',  # Top 2
            'chart-sidebar-left',  # Left
            'chart-toolbar-bottom',  # Bottom
            'chart_container'  # Chart
        ]

        for element in required_elements:
            self.assertTrue(element in self.content,
                           f"Required element {element} missing")


if __name__ == '__main__':
    print("=== Four-Toolbar-Layout Tests ===")
    unittest.main(verbosity=2)