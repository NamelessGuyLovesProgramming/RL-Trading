"""Unit Tests für charts.core.debug_controller - Testet DebugController"""
import pytest
from datetime import datetime, timedelta
from charts.core.debug_controller import DebugController


class TestDebugController:
    """Tests für DebugController - Debug-Funktionalität mit Multi-Timeframe Sync"""

    @pytest.fixture
    def sample_chart_data(self):
        """Erstellt Sample Chart-Daten"""
        return [
            {
                'time': 1735574400,  # 2024-12-30 16:00:00
                'open': 20000.0,
                'high': 20050.0,
                'low': 19980.0,
                'close': 20020.0,
                'volume': 1000
            },
            {
                'time': 1735574700,  # 2024-12-30 16:05:00
                'open': 20020.0,
                'high': 20060.0,
                'low': 20010.0,
                'close': 20040.0,
                'volume': 1200
            }
        ]

    @pytest.fixture
    def controller(self, sample_chart_data):
        # Mock dependencies
        mock_time_mgr = type('MockTimeManager', (), {
            'initialize_time': lambda s, t: None,
            'initialized': False
        })()
        mock_csv_loader = type('MockCSVLoader', (), {})()
        mock_state = type('MockState', (), {
            'update_skip_position': lambda s, t, source: None
        })()

        return DebugController(
            unified_time_manager=mock_time_mgr,
            csv_loader=mock_csv_loader,
            initial_chart_data=sample_chart_data,
            unified_state=mock_state
        )

    # === INITIALIZATION TESTS ===

    def test_controller_initialization(self, controller):
        """Test: Controller wird korrekt initialisiert"""
        assert controller is not None
        assert hasattr(controller, 'unified_time')
        assert hasattr(controller, 'csv_loader')
        assert hasattr(controller, 'unified_state')
        assert hasattr(controller, 'initial_chart_data')

    def test_controller_has_aggregator(self, controller):
        """Test: Controller hat TimeframeAggregator"""
        assert hasattr(controller, 'aggregator')
        assert controller.aggregator is not None

    def test_controller_has_sync_manager(self, controller):
        """Test: Controller hat TimeframeSyncManager"""
        assert hasattr(controller, 'sync_manager')
        # sync_manager kann None sein wenn csv_loader None ist

    def test_controller_initial_state(self, controller):
        """Test: Controller hat korrekten Initial State"""
        assert controller.timeframe == "5m"
        assert controller.play_mode is False
        assert controller.speed == 2
        assert controller.current_time is not None  # Gesetzt aus initial_chart_data

    def test_controller_initializes_with_chart_data(self, controller, sample_chart_data):
        """Test: Controller initialisiert Zeit aus Chart-Daten"""
        # Zeit sollte auf 30. Dezember 2024, 16:55 gesetzt sein (1 Tag vor CSV-Daten)
        assert controller.current_time == datetime(2024, 12, 30, 16, 55, 0)

    # === TIMEFRAME TESTS ===

    def test_set_timeframe(self, controller):
        """Test: Timeframe kann geändert werden"""
        controller.set_timeframe('15m')
        assert controller.timeframe == '15m'
        assert controller.current_timeframe == '15m'

    def test_current_timeframe_property(self, controller):
        """Test: current_timeframe Property funktioniert"""
        controller.timeframe = '1h'
        assert controller.current_timeframe == '1h'

    # === SPEED TESTS ===

    def test_set_speed_valid_range(self, controller):
        """Test: Speed kann auf 1-15 gesetzt werden"""
        controller.set_speed(10)
        assert controller.speed == 10

    def test_set_speed_clamps_to_max(self, controller):
        """Test: Speed wird auf max 15 begrenzt"""
        controller.set_speed(20)
        assert controller.speed == 15

    def test_set_speed_clamps_to_min(self, controller):
        """Test: Speed wird auf min 1 begrenzt"""
        controller.set_speed(0)
        assert controller.speed == 1

    # === PLAY MODE TESTS ===

    def test_toggle_play_mode(self, controller):
        """Test: Play Mode kann umgeschaltet werden"""
        initial_mode = controller.play_mode
        result = controller.toggle_play_mode()

        assert controller.play_mode == (not initial_mode)
        assert result == controller.play_mode

    def test_toggle_play_mode_twice(self, controller):
        """Test: Play Mode Toggle zurück zu Original"""
        initial_mode = controller.play_mode
        controller.toggle_play_mode()
        controller.toggle_play_mode()

        assert controller.play_mode == initial_mode

    # === CURRENT INDEX PROPERTY TESTS ===

    def test_current_index_property_get(self, controller):
        """Test: current_index Property Getter"""
        index = controller.current_index
        assert index == 0  # Default value

    def test_current_index_property_set(self, controller):
        """Test: current_index Property Setter"""
        controller.current_index = 42
        assert controller.current_index == 42

    # === GET STATE TESTS ===

    def test_get_state_returns_complete_info(self, controller):
        """Test: get_state gibt vollständige Info zurück"""
        state = controller.get_state()

        assert 'current_time' in state
        assert 'timeframe' in state
        assert 'play_mode' in state
        assert 'speed' in state
        assert 'incomplete_candles' in state
        assert 'aggregator_state' in state

    def test_get_state_values(self, controller):
        """Test: get_state Werte korrekt"""
        controller.set_timeframe('15m')
        controller.set_speed(5)

        state = controller.get_state()

        assert state['timeframe'] == '15m'
        assert state['speed'] == 5
        assert state['play_mode'] is False

    # Note: skip_minute(), skip_minutes(), skip_hours(), skip_with_real_data()
    # benötigen echte CSV-Daten und werden in Integration Tests getestet
