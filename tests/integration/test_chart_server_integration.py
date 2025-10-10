"""
Integration Tests für Chart Server - Phase 5 Verification
Tests WebSocket Commands, API Endpoints und Service-Integration
"""

import pytest
import asyncio
import json
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
import sys
import os

# Path setup
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, 'charts'))
sys.path.insert(0, os.path.join(parent_dir, 'src'))

from charts import chart_server
from charts.chart_server import app

# Global flag to track if components are initialized
_components_initialized = False


@pytest.fixture(scope="session", autouse=True)
def initialize_server():
    """Initialisiert Server-Komponenten für alle Tests (nur einmal)"""
    global _components_initialized

    if not _components_initialized:
        # Initialize components
        chart_server.initialize_components()

        # Setup routers
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

        _components_initialized = True
        print("[TEST-SETUP] Server components initialized ✅")

    yield


class TestChartServerIntegration:
    """
    Integration Tests für den kompletten Chart Server

    Testet:
    - Server startet erfolgreich
    - Alle Routers sind registriert
    - Services sind initialisiert
    - Endpoints sind erreichbar
    """

    @pytest.fixture
    def client(self):
        """Erstellt TestClient für HTTP-Requests"""
        return TestClient(app)

    def test_server_startup(self, client):
        """Test: Server startet und ist erreichbar"""
        response = client.get("/")

        # Sollte HTML-Template zurückgeben
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "RL Trading Chart" in response.text

    def test_api_docs_available(self, client):
        """Test: FastAPI Docs sind verfügbar"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_debug_state_endpoint(self, client):
        """Test: Debug State Endpoint funktioniert"""
        response = client.get("/api/debug/state")

        assert response.status_code == 200
        data = response.json()

        # Response ist FLACH (nicht verschachtelt)
        assert "play_mode" in data
        assert "speed" in data
        assert isinstance(data["play_mode"], bool)
        assert isinstance(data["speed"], (int, float))

    def test_chart_status_endpoint(self, client):
        """Test: Chart Status Endpoint funktioniert"""
        response = client.get("/api/chart/status")

        assert response.status_code == 200
        data = response.json()

        # Sollte Status-Info zurückgeben
        assert "status" in data or "message" in data


class TestWebSocketCommands:
    """
    Integration Tests für WebSocket Command Handling

    Testet alle WebSocket-Commands:
    - timeframe_change
    - skip
    - go_to_date
    - set_speed
    - toggle_play
    - add_position
    - remove_position
    - get_debug_state
    - get_chart_data
    """

    @pytest.fixture
    def client(self):
        """Erstellt TestClient für WebSocket-Tests"""
        return TestClient(app)

    def test_websocket_connection(self, client):
        """Test: WebSocket-Verbindung kann hergestellt werden"""
        with client.websocket_connect("/ws") as websocket:
            # Connection sollte erfolgreich sein
            assert websocket is not None

    def test_get_chart_data_command(self, client):
        """Test: get_chart_data Command"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event (wird beim Connect automatisch gesendet)
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende get_chart_data Command
            websocket.send_json({
                "type": "get_chart_data"
            })

            # Empfange Response
            response = websocket.receive_json()

            assert response["type"] == "chart_data"
            assert "data" in response
            assert "interval" in response
            assert isinstance(response["data"], list)

    def test_get_debug_state_command(self, client):
        """Test: get_debug_state Command"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende get_debug_state Command
            websocket.send_json({
                "type": "get_debug_state"
            })

            # Empfange Response
            response = websocket.receive_json()

            assert response["type"] == "debug_state"
            assert "state" in response
            assert "play_mode" in response["state"]
            assert "speed" in response["state"]

    def test_set_speed_command(self, client):
        """Test: set_speed Command"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende set_speed Command
            websocket.send_json({
                "type": "set_speed",
                "speed": 5
            })

            # Empfange Broadcast
            response = websocket.receive_json()

            assert response["type"] == "debug_speed_changed"
            assert response["speed"] == 5

    def test_toggle_play_command(self, client):
        """Test: toggle_play Command"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende toggle_play Command
            websocket.send_json({
                "type": "toggle_play"
            })

            # Empfange Broadcast
            response = websocket.receive_json()

            assert response["type"] == "debug_play_toggled"
            assert "play_mode" in response
            assert isinstance(response["play_mode"], bool)

    def test_timeframe_change_command(self, client):
        """Test: timeframe_change Command"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende timeframe_change Command
            websocket.send_json({
                "type": "timeframe_change",
                "timeframe": "1h",
                "visible_candles": 200
            })

            # Empfange Response (kann chart_series_recreation sein, dann bulletproof_timeframe_changed)
            response = websocket.receive_json()

            # Falls Chart Recreation, empfange nächstes Event
            if response.get("type") == "chart_series_recreation":
                response = websocket.receive_json()

            # Sollte bulletproof_timeframe_changed zurückgeben
            assert response["type"] == "bulletproof_timeframe_changed"
            assert response["timeframe"] == "1h"
            assert "data" in response
            assert isinstance(response["data"], list)

    def test_add_position_command(self, client):
        """Test: add_position Command"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            test_position = {
                "id": "test_pos_1",
                "type": "long",
                "price": 20000.0,
                "time": int(datetime.now().timestamp())
            }

            # Sende add_position Command
            websocket.send_json({
                "type": "add_position",
                "position": test_position
            })

            # Empfange Broadcast
            response = websocket.receive_json()

            assert response["type"] == "add_position"
            assert response["position"]["id"] == "test_pos_1"

    def test_remove_position_command(self, client):
        """Test: remove_position Command"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende remove_position Command
            websocket.send_json({
                "type": "remove_position",
                "position_id": "test_pos_1"
            })

            # Empfange Broadcast
            response = websocket.receive_json()

            assert response["type"] == "remove_position"
            assert response["position_id"] == "test_pos_1"

    def test_unknown_command_error(self, client):
        """Test: Unbekannte Commands werden abgelehnt"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende unbekanntes Command
            websocket.send_json({
                "type": "invalid_command_xyz"
            })

            # Sollte Error zurückgeben
            response = websocket.receive_json()

            assert response["type"] == "error"
            assert "Unknown command" in response["message"]


class TestServiceIntegration:
    """
    Integration Tests für Service Layer

    Testet:
    - Services sind korrekt initialisiert
    - Services kommunizieren korrekt untereinander
    - Dependency Injection funktioniert
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_chart_service_integration(self, client):
        """Test: ChartService ist integriert und funktioniert"""
        # Test über WebSocket get_chart_data (nutzt indirekt manager.chart_state)
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            websocket.send_json({"type": "get_chart_data"})
            response = websocket.receive_json()

            # Sollte Chart-Daten liefern
            assert response["type"] == "chart_data"
            assert len(response["data"]) > 0  # Initial chart data sollte geladen sein

    def test_debug_service_integration(self, client):
        """Test: DebugService ist integriert und funktioniert"""
        # Test über API Endpoint
        response = client.get("/api/debug/state")

        assert response.status_code == 200
        data = response.json()

        # Response ist FLACH (nicht verschachtelt)
        assert "play_mode" in data
        assert "speed" in data

    def test_timeframe_service_integration(self, client):
        """Test: TimeframeService ist integriert und funktioniert"""
        # Test über WebSocket timeframe_change (nutzt TimeframeService.switch_timeframe)
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            websocket.send_json({
                "type": "timeframe_change",
                "timeframe": "15m",
                "visible_candles": 100
            })

            response = websocket.receive_json()

            # Falls Chart Recreation, empfange nächstes Event
            if response.get("type") == "chart_series_recreation":
                response = websocket.receive_json()

            # TimeframeService sollte Timeframe wechseln können
            assert response["type"] == "bulletproof_timeframe_changed"
            assert response["timeframe"] == "15m"

    def test_navigation_service_integration(self, client):
        """Test: NavigationService ist integriert und funktioniert"""
        # Test über WebSocket go_to_date (nutzt NavigationService.go_to_date)
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            websocket.send_json({
                "type": "go_to_date",
                "date": "2024-12-01"
            })

            # Kann mehrere Events geben (debug_control_timeframe_changed, go_to_date_complete)
            response = websocket.receive_json()

            # Skip intermediate events
            while response.get("type") != "go_to_date_complete":
                response = websocket.receive_json()

            # NavigationService sollte zu Datum navigieren können
            assert response["type"] == "go_to_date_complete"
            assert "2024-12-01" in response["date"]


class TestErrorHandling:
    """
    Integration Tests für Error Handling

    Testet:
    - Ungültige Requests werden korrekt abgelehnt
    - Fehler werden sauber behandelt
    - Error-Messages sind aussagekräftig
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_invalid_endpoint_404(self, client):
        """Test: Ungültige Endpoints geben 404"""
        response = client.get("/api/invalid/endpoint/xyz")
        assert response.status_code == 404

    def test_websocket_invalid_command(self, client):
        """Test: Ungültige WebSocket-Commands geben Error"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            websocket.send_json({
                "type": "completely_invalid_command"
            })

            response = websocket.receive_json()

            assert response["type"] == "error"
            assert "Unknown command" in response["message"]

    def test_websocket_missing_parameters(self, client):
        """Test: Fehlende Parameter werden erkannt"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # go_to_date ohne date Parameter
            websocket.send_json({
                "type": "go_to_date"
                # date fehlt!
            })

            response = websocket.receive_json()

            assert response["type"] == "error"
            assert "Kein Datum" in response["message"] or "No" in response["message"]


class TestChartFunctionality:
    """
    Integration Tests für Chart-Funktionalität

    Testet:
    - Timeframe-Wechsel zwischen verschiedenen TFs (1m, 5m, 15m, 1h, 4h)
    - Kerzen-Konsistenz (sortiert, keine Duplikate, keine Lücken)
    - OHLC-Validierung (High ≥ Open/Close, Low ≤ Open/Close)
    - Chart-State-Konsistenz nach TF-Wechsel
    - Candle-Count und Zeitfenster-Konsistenz
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_timeframe_switching_multiple_timeframes(self, client):
        """Test: Wechsel zwischen mehreren Timeframes (1m → 5m → 1h → 4h)"""
        with client.websocket_connect("/ws") as websocket:
            # Initial data
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            timeframes = ["1m", "5m", "15m", "1h", "4h"]

            for tf in timeframes:
                websocket.send_json({
                    "type": "timeframe_change",
                    "timeframe": tf,
                    "visible_candles": 200
                })

                response = websocket.receive_json()

                # Skip chart recreation event if present
                if response.get("type") == "chart_series_recreation":
                    response = websocket.receive_json()

                # Verify response
                assert response["type"] == "bulletproof_timeframe_changed", f"TF {tf} failed"
                assert response["timeframe"] == tf, f"Expected {tf}, got {response['timeframe']}"
                assert len(response["data"]) > 0, f"No data for {tf}"

                # Verify all candles have required fields
                for candle in response["data"]:
                    assert "time" in candle
                    assert "open" in candle
                    assert "high" in candle
                    assert "low" in candle
                    assert "close" in candle

    def test_candle_time_consistency_no_duplicates(self, client):
        """Test: Kerzen sind zeitlich sortiert und haben keine Duplikate"""
        with client.websocket_connect("/ws") as websocket:
            initial = websocket.receive_json()

            websocket.send_json({"type": "get_chart_data"})
            response = websocket.receive_json()

            data = response["data"]
            assert len(data) > 0, "No chart data"

            # Extrahiere alle Timestamps
            timestamps = [candle["time"] for candle in data]

            # Test 1: Keine Duplikate
            unique_timestamps = set(timestamps)
            assert len(timestamps) == len(unique_timestamps), \
                f"Duplikate gefunden: {len(timestamps)} total, {len(unique_timestamps)} unique"

            # Test 2: Zeitlich aufsteigend sortiert
            sorted_timestamps = sorted(timestamps)

            if timestamps != sorted_timestamps:
                # Finde die erste unsortierte Stelle
                for i in range(len(timestamps) - 1):
                    if timestamps[i] > timestamps[i+1]:
                        from datetime import datetime
                        t1 = datetime.fromtimestamp(timestamps[i])
                        t2 = datetime.fromtimestamp(timestamps[i+1])
                        error_msg = (
                            f"Unsortiert bei Index {i}: "
                            f"time[{i}]={timestamps[i]} ({t1}) > "
                            f"time[{i+1}]={timestamps[i+1]} ({t2})"
                        )
                        assert False, error_msg

            # Test 3: Keine negativen oder null Timestamps
            assert all(t > 0 for t in timestamps), \
                "Ungültige Timestamps gefunden (≤ 0)"

    def test_ohlc_price_consistency(self, client):
        """Test: OHLC-Preise sind konsistent (High ≥ Open/Close, Low ≤ Open/Close)"""
        with client.websocket_connect("/ws") as websocket:
            initial = websocket.receive_json()

            websocket.send_json({"type": "get_chart_data"})
            response = websocket.receive_json()

            data = response["data"]
            assert len(data) > 0

            for i, candle in enumerate(data):
                open_price = candle["open"]
                high_price = candle["high"]
                low_price = candle["low"]
                close_price = candle["close"]

                # Test 1: High ist höchster Wert
                assert high_price >= open_price, \
                    f"Candle {i}: High ({high_price}) < Open ({open_price})"
                assert high_price >= close_price, \
                    f"Candle {i}: High ({high_price}) < Close ({close_price})"
                assert high_price >= low_price, \
                    f"Candle {i}: High ({high_price}) < Low ({low_price})"

                # Test 2: Low ist niedrigster Wert
                assert low_price <= open_price, \
                    f"Candle {i}: Low ({low_price}) > Open ({open_price})"
                assert low_price <= close_price, \
                    f"Candle {i}: Low ({low_price}) > Close ({close_price})"
                assert low_price <= high_price, \
                    f"Candle {i}: Low ({low_price}) > High ({high_price})"

                # Test 3: Alle Preise sind positiv
                assert open_price > 0, f"Candle {i}: Open ≤ 0"
                assert high_price > 0, f"Candle {i}: High ≤ 0"
                assert low_price > 0, f"Candle {i}: Low ≤ 0"
                assert close_price > 0, f"Candle {i}: Close ≤ 0"

    def test_chart_state_after_timeframe_change(self, client):
        """Test: Chart-State ist konsistent nach Timeframe-Wechsel"""
        with client.websocket_connect("/ws") as websocket:
            initial = websocket.receive_json()

            # Wechsel zu 1h
            websocket.send_json({
                "type": "timeframe_change",
                "timeframe": "1h",
                "visible_candles": 150
            })

            response = websocket.receive_json()
            if response.get("type") == "chart_series_recreation":
                response = websocket.receive_json()

            # Speichere Chart-Daten
            chart_data_1h = response["data"]

            # Hole Chart-State über get_chart_data
            websocket.send_json({"type": "get_chart_data"})
            state_response = websocket.receive_json()

            # Verify: State sollte 1h Timeframe reflektieren
            assert state_response["interval"] == "1h", \
                f"Interval mismatch: expected 1h, got {state_response['interval']}"

            # Verify: Data count sollte übereinstimmen
            assert len(state_response["data"]) == len(chart_data_1h), \
                f"Data count mismatch: {len(state_response['data'])} vs {len(chart_data_1h)}"

    def test_timeframe_data_validation_and_skip_contamination(self, client):
        """Test: Timeframe-Daten sind validiert & frei von Skip-Kontamination"""
        with client.websocket_connect("/ws") as websocket:
            initial = websocket.receive_json()

            # Teste mehrere Timeframes
            timeframes_to_test = ["5m", "15m", "30m"]

            for tf in timeframes_to_test:
                websocket.send_json({
                    "type": "timeframe_change",
                    "timeframe": tf,
                    "visible_candles": 100
                })

                response = websocket.receive_json()
                if response.get("type") == "chart_series_recreation":
                    response = websocket.receive_json()

                # Test 1: Validation Summary vorhanden
                assert "validation_summary" in response, \
                    f"TF {tf}: Keine validation_summary"

                validation = response["validation_summary"]

                # Test 2: Skip Contamination ist CLEAN
                assert validation["skip_contamination"] == "CLEAN", \
                    f"TF {tf}: Skip contamination nicht CLEAN: {validation['skip_contamination']}"

                # Test 3: Validated count > 0
                assert validation["validated_count"] > 0, \
                    f"TF {tf}: Keine validierten Candles"

                # Test 4: Data source ist bekannt
                assert "data_source" in validation, \
                    f"TF {tf}: Keine data_source in validation"


class TestDataIntegrity:
    """
    Integration Tests für Data Integrity

    Testet:
    - DataIntegrityGuard funktioniert
    - Keine null/undefined Werte in Responses
    - Chart-Daten sind valide
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_chart_data_has_no_null_values(self, client):
        """Test: Chart-Daten enthalten keine null-Werte"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            websocket.send_json({"type": "get_chart_data"})
            response = websocket.receive_json()

            # Prüfe alle Candles
            for candle in response["data"]:
                assert candle["time"] is not None
                assert candle["open"] is not None
                assert candle["high"] is not None
                assert candle["low"] is not None
                assert candle["close"] is not None

                # Werte müssen sinnvoll sein
                assert candle["time"] > 0
                assert candle["open"] > 0
                assert candle["high"] > 0
                assert candle["low"] > 0
                assert candle["close"] > 0

                # OHLC-Logik
                assert candle["high"] >= candle["open"]
                assert candle["high"] >= candle["close"]
                assert candle["low"] <= candle["open"]
                assert candle["low"] <= candle["close"]

    def test_timeframe_change_validates_data(self, client):
        """Test: Timeframe-Wechsel validiert Daten"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            websocket.send_json({
                "type": "timeframe_change",
                "timeframe": "30m",
                "visible_candles": 150
            })

            response = websocket.receive_json()

            # Falls Chart Recreation, empfange nächstes Event
            if response.get("type") == "chart_series_recreation":
                response = websocket.receive_json()

            # Validierung Summary sollte vorhanden sein
            assert "validation_summary" in response
            assert response["validation_summary"]["skip_contamination"] == "CLEAN"


if __name__ == "__main__":
    print("Running Integration Tests for Chart Server Phase 5...")
    print("=" * 60)
    pytest.main([__file__, "-v", "--tb=short"])
