"""
Integration Tests für Template-Modularisierung
Tests prüfen ob CSS, JavaScript und HTML korrekt geladen werden
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Path setup
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, 'charts'))

from charts import chart_server
from charts.chart_server import app

# Global flag for initialization
_initialized = False


@pytest.fixture(scope="module", autouse=True)
def initialize_server():
    """Initialisiert Server-Komponenten einmalig"""
    global _initialized

    if not _initialized:
        chart_server.initialize_components()

        from charts.routes import debug as debug_routes
        from charts.routes import chart as chart_routes
        from charts.routes import static as static_routes

        debug_routes.setup_debug_routes(
            app=app,
            debug_service=chart_server.debug_service,
            navigation_service=chart_server.navigation_service,
            unified_time_manager=chart_server.unified_time_manager,
            manager=chart_server.manager,
            debug_controller=chart_server.debug_controller,
            global_skip_events=chart_server.global_skip_events,
            debug_control_timeframe=chart_server.debug_control_timeframe
        )

        chart_routes.setup_chart_routes(
            app=app,
            timeframe_service=chart_server.timeframe_service,
            manager=chart_server.manager,
            chart_lifecycle_manager=chart_server.chart_lifecycle_manager,
            unified_time_manager=chart_server.unified_time_manager,
            data_validator=chart_server.data_validator,
            timeframe_data_repository=chart_server.timeframe_data_repository,
            DataIntegrityGuard=chart_server.DataIntegrityGuard,
            global_skip_events=chart_server.global_skip_events,
            universal_renderer=chart_server.universal_renderer
        )

        static_routes.setup_static_routes(app=app)

        _initialized = True
        print("[TEST] Template-Modularisierung Tests - Server initialized ✅")

    yield


@pytest.fixture
def client():
    """Erstellt TestClient"""
    return TestClient(app)


class TestTemplateModularization:
    """
    Tests für Template-Modularisierung (Phase 9)

    Testet:
    - HTML-Template wird geladen
    - CSS-Dateien sind erreichbar
    - JavaScript-Dateien sind erreichbar
    - Modularisierte Struktur funktioniert
    """

    def test_html_template_loads(self, client):
        """Test: HTML-Template wird geladen"""
        response = client.get("/")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/html" in response.headers.get("content-type", ""), \
            "Content-Type sollte text/html sein"
        assert "RL Trading Chart" in response.text, \
            "HTML sollte 'RL Trading Chart' enthalten"

        # Prüfe ob Template externe CSS/JS referenziert
        assert '<link rel="stylesheet" href="/static/css/chart.css">' in response.text or \
               'href="/static/css/chart.css"' in response.text, \
            "HTML sollte externe CSS-Datei referenzieren"

        assert '<script src="/static/js/chart.js"></script>' in response.text or \
               'src="/static/js/chart.js"' in response.text, \
            "HTML sollte externe JavaScript-Datei referenzieren"

    def test_css_file_loads(self, client):
        """Test: CSS-Datei wird geladen"""
        response = client.get("/static/css/chart.css")

        assert response.status_code == 200, \
            f"CSS-Datei nicht gefunden: {response.status_code}"

        # Content-Type sollte CSS sein
        content_type = response.headers.get("content-type", "")
        assert "css" in content_type.lower() or "text/css" in content_type, \
            f"Content-Type sollte CSS sein, ist aber: {content_type}"

        # Prüfe ob CSS valide Inhalte hat
        css_content = response.text
        assert len(css_content) > 100, \
            "CSS-Datei sollte mindestens 100 Zeichen haben"

        # Prüfe CSS-Syntax (mindestens ein Selektor)
        assert "{" in css_content and "}" in css_content, \
            "CSS sollte valide Syntax haben (geschweifte Klammern)"

    def test_javascript_file_loads(self, client):
        """Test: JavaScript-Datei wird geladen"""
        response = client.get("/static/js/chart.js")

        assert response.status_code == 200, \
            f"JavaScript-Datei nicht gefunden: {response.status_code}"

        # Content-Type sollte JavaScript sein
        content_type = response.headers.get("content-type", "")
        assert "javascript" in content_type.lower() or "application/javascript" in content_type, \
            f"Content-Type sollte JavaScript sein, ist aber: {content_type}"

        # Prüfe ob JavaScript valide Inhalte hat
        js_content = response.text
        assert len(js_content) > 1000, \
            "JavaScript-Datei sollte mindestens 1000 Zeichen haben"

        # Prüfe JavaScript-Syntax (mindestens eine Funktion)
        assert "function" in js_content or "const" in js_content or "let" in js_content, \
            "JavaScript sollte valide Syntax haben"

    def test_template_size_reduction(self, client):
        """Test: Template ist kleiner als 1000 Zeilen (vorher 5752)"""
        response = client.get("/")

        assert response.status_code == 200

        # Zähle Zeilen
        html_lines = response.text.count('\n')

        # Template sollte DEUTLICH kleiner sein als vorher (5752 Zeilen)
        assert html_lines < 1000, \
            f"Template sollte <1000 Zeilen haben (ist {html_lines}). Modularisierung fehlgeschlagen!"

        print(f"[TEST] ✅ Template hat {html_lines} Zeilen (Reduktion von 5752 auf {html_lines})")

    def test_modularized_structure_complete(self, client):
        """Test: Modularisierte Struktur ist komplett"""

        # 1. HTML-Template
        html_response = client.get("/")
        assert html_response.status_code == 200

        # 2. CSS-Datei
        css_response = client.get("/static/css/chart.css")
        assert css_response.status_code == 200

        # 3. JavaScript-Datei
        js_response = client.get("/static/js/chart.js")
        assert js_response.status_code == 200

        # Alle 3 Komponenten geladen
        print("[TEST] ✅ Modularisierte Struktur komplett (HTML + CSS + JS)")

    def test_css_contains_chart_styles(self, client):
        """Test: CSS enthält Chart-spezifische Styles"""
        response = client.get("/static/css/chart.css")

        assert response.status_code == 200

        css_content = response.text

        # Prüfe ob wichtige Chart-Styles vorhanden sind
        assert ".chart-container" in css_content or "#chart" in css_content, \
            "CSS sollte Chart-Container Styles enthalten"

    def test_javascript_contains_chart_logic(self, client):
        """Test: JavaScript enthält Chart-Logik"""
        response = client.get("/static/js/chart.js")

        assert response.status_code == 200

        js_content = response.text

        # Prüfe ob wichtige Chart-Funktionen vorhanden sind
        assert "createChart" in js_content or "chart" in js_content.lower(), \
            "JavaScript sollte Chart-Logik enthalten"

        # Prüfe WebSocket-Logik
        assert "WebSocket" in js_content or "ws" in js_content, \
            "JavaScript sollte WebSocket-Logik enthalten"


if __name__ == "__main__":
    print("Running Template-Modularisierung Tests...")
    print("=" * 60)
    pytest.main([__file__, "-v", "--tb=short"])
