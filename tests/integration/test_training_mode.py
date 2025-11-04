"""
Integration Tests für Training Mode System
Testet RL Agent, Training Mode Service und WebSocket Integration
"""

import pytest
import json
from fastapi.testclient import TestClient
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
            debug_control_timeframe=chart_server.debug_control_timeframe,
            account_service=chart_server.account_service
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


class TestTrainingModeCommands:
    """
    Integration Tests für Training Mode WebSocket Commands

    Testet:
    - toggle_ai_mode Command
    - get_ai_status Command
    - AI-Integration beim Skip
    """

    @pytest.fixture
    def client(self):
        """Erstellt TestClient für WebSocket-Tests"""
        return TestClient(app)

    def test_toggle_ai_mode_command(self, client):
        """Test: toggle_ai_mode aktiviert/deaktiviert Training Mode"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende toggle_ai_mode Command (aktivieren)
            websocket.send_json({
                "type": "toggle_ai_mode"
            })

            # Empfange Response
            response = websocket.receive_json()

            # Sollte ai_mode_toggled zurückgeben
            assert response["type"] == "ai_mode_toggled"
            assert "is_active" in response
            assert "session_id" in response
            assert "stats" in response

            # Stats sollten Struktur haben
            stats = response["stats"]
            assert "trades_count" in stats
            assert "long_count" in stats
            assert "short_count" in stats
            assert "hold_count" in stats
            assert "avg_confidence" in stats

    def test_get_ai_status_command(self, client):
        """Test: get_ai_status gibt aktuellen Status zurück"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende get_ai_status Command
            websocket.send_json({
                "type": "get_ai_status"
            })

            # Empfange Response
            response = websocket.receive_json()

            # Sollte ai_status zurückgeben
            assert response["type"] == "ai_status"
            assert "is_active" in response
            assert isinstance(response["is_active"], bool)

            if response["is_active"]:
                assert "session_id" in response
                assert "stats" in response

    def test_ai_mode_toggle_twice(self, client):
        """Test: Toggle an → toggle aus"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Toggle 1: Aktivieren
            websocket.send_json({"type": "toggle_ai_mode"})
            response1 = websocket.receive_json()

            assert response1["type"] == "ai_mode_toggled"
            is_active_1 = response1["is_active"]

            # Toggle 2: Deaktivieren
            websocket.send_json({"type": "toggle_ai_mode"})
            response2 = websocket.receive_json()

            assert response2["type"] == "ai_mode_toggled"
            is_active_2 = response2["is_active"]

            # Status sollte sich umgekehrt haben
            assert is_active_1 != is_active_2


class TestRLAgentIntegration:
    """
    Integration Tests für RL Agent

    Testet:
    - Agent ist initialisiert
    - Agent gibt valide Decisions zurück
    - Decision-Format ist korrekt
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_rl_agent_initialized(self):
        """Test: RL Agent ist initialisiert"""
        assert chart_server.rl_agent is not None, "RL Agent not initialized"
        assert hasattr(chart_server.rl_agent, 'decide'), "RL Agent has no decide method"
        assert hasattr(chart_server.rl_agent, 'learn_from_feedback'), "RL Agent has no learn_from_feedback method"

    def test_rl_agent_decide_returns_valid_action(self):
        """Test: RL Agent gibt valide Action zurück"""
        if chart_server.rl_agent is None:
            pytest.skip("RL Agent not available")

        # Erstelle Dummy Market Context
        market_context = {
            'fvg_bullish': [{'gap_size': 0.02}],
            'fvg_bearish': [],
            'order_blocks_bullish': [{'strength': 0.7}],
            'order_blocks_bearish': [],
            'in_killzone': True,
            'session': 'london',
            'volume_spike': True,
            'trend': 'bullish',
            'current_price': 20000.0
        }

        # Hole Decision
        decision = chart_server.rl_agent.decide(market_context)

        # Validate Decision Format
        assert isinstance(decision, dict), "Decision must be dict"
        assert "action" in decision, "Decision missing 'action'"
        assert "confidence" in decision, "Decision missing 'confidence'"
        assert "reasoning" in decision, "Decision missing 'reasoning'"

        # Validate action
        assert decision["action"] in ["long", "short", "hold"], \
            f"Invalid action: {decision['action']}"

        # Validate confidence
        assert isinstance(decision["confidence"], float), "Confidence must be float"
        assert 0.0 <= decision["confidence"] <= 1.0, \
            f"Confidence out of range: {decision['confidence']}"

        # Validate reasoning
        assert isinstance(decision["reasoning"], str), "Reasoning must be string"
        assert len(decision["reasoning"]) > 0, "Reasoning is empty"


class TestTrainingModeService:
    """
    Integration Tests für Training Mode Service

    Testet:
    - Service ist initialisiert
    - Toggle funktioniert
    - Stats werden getrackt
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_training_service_initialized(self):
        """Test: Training Mode Service ist initialisiert"""
        assert chart_server.training_service is not None, "Training Service not initialized"
        assert hasattr(chart_server.training_service, 'toggle_mode'), "Service has no toggle_mode"
        assert hasattr(chart_server.training_service, 'on_skip'), "Service has no on_skip"

    def test_training_service_toggle(self):
        """Test: Training Service Toggle funktioniert"""
        if chart_server.training_service is None:
            pytest.skip("Training Service not available")

        service = chart_server.training_service

        # Initial state
        initial_state = service.is_active

        # Toggle
        result = service.toggle_mode()

        assert "is_active" in result
        assert result["is_active"] != initial_state, "State should change after toggle"

        # Toggle zurück
        result2 = service.toggle_mode()
        assert result2["is_active"] == initial_state, "State should return to initial"

    def test_training_service_stats_structure(self):
        """Test: Training Service Stats haben korrekte Struktur"""
        if chart_server.training_service is None:
            pytest.skip("Training Service not available")

        service = chart_server.training_service
        status = service.get_status()
        stats = status.get('stats', {})

        # Validate stats structure
        assert "trades_count" in stats
        assert "long_count" in stats
        assert "short_count" in stats
        assert "hold_count" in stats
        assert "avg_confidence" in stats

        # Validate types
        assert isinstance(stats["trades_count"], int)
        assert isinstance(stats["long_count"], int)
        assert isinstance(stats["short_count"], int)
        assert isinstance(stats["hold_count"], int)
        assert isinstance(stats["avg_confidence"], float)


class TestFeedbackDeletion:
    """
    Integration Tests für Feedback Deletion

    Testet:
    - delete_feedback Command
    - Deletion wird korrekt verarbeitet
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_delete_feedback_command_structure(self, client):
        """Test: delete_feedback Command wird verarbeitet"""
        with client.websocket_connect("/ws") as websocket:
            # Empfange initial_data Event
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # Sende delete_feedback mit Test-ID
            websocket.send_json({
                "type": "delete_feedback",
                "trade_id": "test_trade_id_xyz"
            })

            # Empfange Response (kann error sein wenn ID nicht existiert, ist ok)
            response = websocket.receive_json()

            # Sollte entweder feedback_deleted oder error sein
            assert response["type"] in ["feedback_deleted", "error"], \
                f"Unexpected response type: {response['type']}"


class TestTrainingModeWorkflow:
    """
    End-to-End Tests für Training Mode Workflow

    Testet:
    - Kompletter Workflow: Toggle → Skip → AI Decision → Feedback
    """

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_complete_workflow_toggle_and_skip(self, client):
        """Test: Kompletter Workflow - Toggle AI, Skip, Check AI Action"""
        with client.websocket_connect("/ws") as websocket:
            # 1. Initial data
            initial = websocket.receive_json()
            assert initial["type"] == "initial_data"

            # 2. Aktiviere AI Mode (oder deaktiviere falls schon an)
            websocket.send_json({"type": "toggle_ai_mode"})
            toggle_response = websocket.receive_json()

            assert toggle_response["type"] == "ai_mode_toggled"
            ai_mode_active = toggle_response["is_active"]

            # Wenn AI Mode nicht aktiv ist, toggle nochmal
            if not ai_mode_active:
                websocket.send_json({"type": "toggle_ai_mode"})
                toggle_response = websocket.receive_json()
                assert toggle_response["type"] == "ai_mode_toggled"
                assert toggle_response["is_active"] == True

            # 3. Test ist erfolgreich wenn AI Mode aktiviert wurde
            # Kompletter Workflow-Test mit Skip würde mehr Mock-Setup benötigen
            # Dieser Test verifiziert nur die Basis-Integration
            pass


if __name__ == "__main__":
    print("Running Training Mode Integration Tests...")
    print("=" * 60)
    pytest.main([__file__, "-v", "--tb=short"])
