"""
Integration Tests für Market/Limit Order Type System
Tests prüfen ob HTML, CSS und JavaScript korrekt implementiert sind
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os
import re

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
            global_skip_events=chart_server.global_skip_events,
            chart_data_service=chart_server.chart_data_service
        )

        static_routes.setup_static_routes(app=app)

        _initialized = True

    yield


@pytest.fixture(scope="module")
def client():
    """TestClient für FastAPI"""
    return TestClient(app)


class TestOrderTypeSystemHTML:
    """Tests für HTML Template Order Type Dropdown"""

    def test_chart_html_contains_order_type_dropdown(self, client):
        """Test: chart.html enthält Order Type Dropdown"""
        response = client.get("/")
        assert response.status_code == 200

        html_content = response.text

        # Check für Order Type Label
        assert 'Order:' in html_content or 'Order Type' in html_content, \
            "HTML sollte Order Type Label enthalten"

        # Check für orderType select element
        assert 'id="orderType"' in html_content, \
            "HTML sollte orderType select element enthalten"

        # Check für onchange handler
        assert 'onchange="onOrderTypeChange()"' in html_content, \
            "HTML sollte onOrderTypeChange() Handler enthalten"

    def test_chart_html_contains_market_option(self, client):
        """Test: chart.html enthält Market Order Option"""
        response = client.get("/")
        html_content = response.text

        # Check für Market Order Option
        assert 'value="market"' in html_content, \
            "HTML sollte Market Order Option enthalten"
        assert 'Market Order' in html_content, \
            "HTML sollte 'Market Order' Text enthalten"

    def test_chart_html_contains_limit_option(self, client):
        """Test: chart.html enthält Limit Order Option"""
        response = client.get("/")
        html_content = response.text

        # Check für Limit Order Option
        assert 'value="limit"' in html_content, \
            "HTML sollte Limit Order Option enthalten"
        assert 'Limit Order' in html_content, \
            "HTML sollte 'Limit Order' Text enthalten"

    def test_order_type_dropdown_in_trade_modal(self, client):
        """Test: Order Type Dropdown ist im Trade Modal platziert"""
        response = client.get("/")
        html_content = response.text

        # Check dass orderType zwischen tradeType und tradeEntry ist
        trade_type_pos = html_content.find('id="tradeType"')
        order_type_pos = html_content.find('id="orderType"')
        trade_entry_pos = html_content.find('id="tradeEntry"')

        assert trade_type_pos > 0, "tradeType sollte existieren"
        assert order_type_pos > 0, "orderType sollte existieren"
        assert trade_entry_pos > 0, "tradeEntry sollte existieren"

        # Order Type sollte zwischen Trade Type und Entry sein
        assert trade_type_pos < order_type_pos < trade_entry_pos, \
            "Order Type sollte zwischen Trade Type und Entry platziert sein"


class TestOrderTypeSystemCSS:
    """Tests für CSS Styling"""

    def test_css_file_accessible(self, client):
        """Test: CSS Datei ist zugänglich"""
        response = client.get("/static/css/chart.css")
        assert response.status_code == 200, "CSS Datei sollte zugänglich sein"

    def test_css_contains_order_type_select_styling(self, client):
        """Test: CSS enthält .order-type-select Styling"""
        response = client.get("/static/css/chart.css")
        css_content = response.text

        assert '.order-type-select' in css_content, \
            "CSS sollte .order-type-select Klasse enthalten"

        # Check für wichtige CSS Properties
        # Suche nach .order-type-select Block
        select_block_match = re.search(
            r'\.order-type-select\s*\{([^}]+)\}',
            css_content,
            re.DOTALL
        )

        assert select_block_match, "CSS sollte .order-type-select Block enthalten"

        select_block = select_block_match.group(1)

        # Check für wichtige Properties
        assert 'background' in select_block.lower(), \
            "order-type-select sollte background Property haben"
        assert 'border' in select_block.lower(), \
            "order-type-select sollte border Property haben"
        assert 'color' in select_block.lower(), \
            "order-type-select sollte color Property haben"


class TestOrderTypeSystemJavaScript:
    """Tests für JavaScript Funktionalität"""

    def test_js_file_accessible(self, client):
        """Test: JavaScript Datei ist zugänglich"""
        response = client.get("/static/js/chart.js")
        assert response.status_code == 200, "JavaScript Datei sollte zugänglich sein"

    def test_js_contains_last_candle_close_variable(self, client):
        """Test: JavaScript enthält window.lastCandleClose Variable"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        assert 'window.lastCandleClose' in js_content, \
            "JavaScript sollte window.lastCandleClose Variable enthalten"

    def test_js_contains_active_limit_orders_variable(self, client):
        """Test: JavaScript enthält window.activeLimitOrders Array"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        assert 'window.activeLimitOrders' in js_content, \
            "JavaScript sollte window.activeLimitOrders Array enthalten"

    def test_js_contains_get_current_market_price_function(self, client):
        """Test: JavaScript enthält getCurrentMarketPrice() Funktion"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        assert 'function getCurrentMarketPrice()' in js_content, \
            "JavaScript sollte getCurrentMarketPrice() Funktion enthalten"

    def test_js_contains_on_order_type_change_function(self, client):
        """Test: JavaScript enthält onOrderTypeChange() Funktion"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        assert 'function onOrderTypeChange()' in js_content, \
            "JavaScript sollte onOrderTypeChange() Funktion enthalten"

    def test_js_contains_place_limit_order_function(self, client):
        """Test: JavaScript enthält placeLimitOrder() Funktion"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        assert 'function placeLimitOrder()' in js_content, \
            "JavaScript sollte placeLimitOrder() Funktion enthalten"

    def test_js_contains_check_limit_orders_function(self, client):
        """Test: JavaScript enthält checkLimitOrders() Funktion"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        assert 'function checkLimitOrders(' in js_content, \
            "JavaScript sollte checkLimitOrders() Funktion enthalten"

    def test_js_execute_trade_checks_order_type(self, client):
        """Test: executeTrade() prüft Order Type"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        # Suche nach executeTrade Funktion
        assert 'function executeTrade()' in js_content, \
            "executeTrade() Funktion sollte existieren"

        # Suche nach Order Type Check in executeTrade
        execute_trade_match = re.search(
            r'function executeTrade\(\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)',
            js_content,
            re.DOTALL
        )

        assert execute_trade_match, "executeTrade() Funktion sollte gefunden werden"

        execute_trade_content = execute_trade_match.group(1)

        assert 'orderType' in execute_trade_content, \
            "executeTrade() sollte orderType Variable verwenden"

        assert 'placeLimitOrder' in execute_trade_content, \
            "executeTrade() sollte placeLimitOrder() aufrufen"

    def test_js_updates_last_candle_close_in_websocket_handlers(self, client):
        """Test: WebSocket Handler aktualisieren window.lastCandleClose"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        # Check dass lastCandleClose in verschiedenen Event Handlern gesetzt wird
        # Initial Data Handler
        initial_data_section = js_content[js_content.find("case 'initial_data':"):]
        if 'break' in initial_data_section:
            initial_data_section = initial_data_section[:initial_data_section.find('break')]

        assert 'window.lastCandleClose' in initial_data_section, \
            "initial_data Handler sollte window.lastCandleClose setzen"

        # Revolutionary Skip Handler
        if 'revolutionary_skip_event' in js_content:
            rev_skip_section = js_content[js_content.find("case 'revolutionary_skip_event':"):]
            if 'break' in rev_skip_section:
                rev_skip_section = rev_skip_section[:rev_skip_section.find('break')]

            assert 'window.lastCandleClose' in rev_skip_section, \
                "revolutionary_skip_event Handler sollte window.lastCandleClose setzen"

        # Unified Skip Handler
        if 'unified_skip_event' in js_content:
            unified_skip_section = js_content[js_content.find("case 'unified_skip_event':"):]
            if 'break' in unified_skip_section:
                unified_skip_section = unified_skip_section[:unified_skip_section.find('break')]

            assert 'window.lastCandleClose' in unified_skip_section, \
                "unified_skip_event Handler sollte window.lastCandleClose setzen"

    def test_js_contains_limit_order_monitoring_interval(self, client):
        """Test: JavaScript enthält setInterval für Limit Order Monitoring"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        # Check für setInterval mit checkLimitOrders
        assert 'setInterval' in js_content, \
            "JavaScript sollte setInterval enthalten"

        assert 'checkLimitOrders' in js_content, \
            "setInterval sollte checkLimitOrders aufrufen"

    def test_js_open_trade_modal_handles_order_types(self, client):
        """Test: openTradeModal() verarbeitet Order Types korrekt"""
        response = client.get("/static/js/chart.js")
        js_content = response.text

        # Suche nach openTradeModal Funktion
        open_modal_match = re.search(
            r'function openTradeModal\([^)]*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)',
            js_content,
            re.DOTALL
        )

        assert open_modal_match, "openTradeModal() Funktion sollte existieren"

        open_modal_content = open_modal_match.group(1)

        # Check für savedOrderType
        assert 'savedOrderType' in open_modal_content, \
            "openTradeModal() sollte savedOrderType verwenden"

        # Check für getCurrentMarketPrice
        assert 'getCurrentMarketPrice' in open_modal_content, \
            "openTradeModal() sollte getCurrentMarketPrice() aufrufen"

        # Check für localStorage
        assert 'localStorage' in open_modal_content, \
            "openTradeModal() sollte localStorage verwenden"


class TestOrderTypeSystemIntegration:
    """Integration Tests für vollständiges System"""

    def test_complete_market_order_flow_components_present(self, client):
        """Test: Alle Komponenten für Market Order Flow sind vorhanden"""
        # HTML Check
        html_response = client.get("/")
        assert html_response.status_code == 200
        assert 'id="orderType"' in html_response.text

        # CSS Check
        css_response = client.get("/static/css/chart.css")
        assert css_response.status_code == 200
        assert '.order-type-select' in css_response.text

        # JavaScript Check
        js_response = client.get("/static/js/chart.js")
        assert js_response.status_code == 200
        js_content = js_response.text

        # Alle wichtigen Funktionen vorhanden
        required_functions = [
            'getCurrentMarketPrice',
            'onOrderTypeChange',
            'placeLimitOrder',
            'checkLimitOrders'
        ]

        for func in required_functions:
            assert func in js_content, \
                f"JavaScript sollte {func} Funktion enthalten"

    def test_complete_limit_order_flow_components_present(self, client):
        """Test: Alle Komponenten für Limit Order Flow sind vorhanden"""
        js_response = client.get("/static/js/chart.js")
        js_content = js_response.text

        # Limit Order spezifische Checks
        assert 'window.activeLimitOrders' in js_content, \
            "activeLimitOrders Array sollte vorhanden sein"

        assert 'placeLimitOrder' in js_content, \
            "placeLimitOrder Funktion sollte vorhanden sein"

        assert 'checkLimitOrders' in js_content, \
            "checkLimitOrders Funktion sollte vorhanden sein"

        # Check für Price Line Creation in placeLimitOrder
        assert 'createPriceLine' in js_content, \
            "placeLimitOrder sollte Price Line erstellen"
