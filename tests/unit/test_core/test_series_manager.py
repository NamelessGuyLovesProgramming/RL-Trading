"""Unit Tests für charts.core.series_manager - Testet ChartSeriesLifecycleManager"""
import pytest
from charts.core.series_manager import ChartSeriesLifecycleManager


class TestChartSeriesLifecycleManager:
    """Tests für ChartSeriesLifecycleManager - Chart State Machine & Factory Pattern"""

    @pytest.fixture
    def manager(self):
        return ChartSeriesLifecycleManager()

    # === INITIALIZATION TESTS ===

    def test_manager_initialization(self, manager):
        """Test: Manager wird korrekt initialisiert mit CLEAN State"""
        assert manager.current_state == manager.STATES['CLEAN']
        assert manager.skip_operations_count == 0
        assert manager.chart_series_version == 1
        assert manager.last_timeframe is None

    def test_manager_has_all_states(self, manager):
        """Test: Manager hat alle benötigten States"""
        assert 'CLEAN' in manager.STATES
        assert 'DATA_LOADED' in manager.STATES
        assert 'SKIP_MODIFIED' in manager.STATES
        assert 'CORRUPTED' in manager.STATES
        assert 'TRANSITIONING' in manager.STATES

    # === SKIP OPERATION TRACKING ===

    def test_track_skip_operation_changes_state(self, manager):
        """Test: Skip Operation ändert State von CLEAN zu SKIP_MODIFIED"""
        assert manager.current_state == manager.STATES['CLEAN']

        manager.track_skip_operation('5m')

        assert manager.current_state == manager.STATES['SKIP_MODIFIED']
        assert manager.skip_operations_count == 1
        assert manager.last_timeframe == '5m'

    def test_track_multiple_skip_operations(self, manager):
        """Test: Multiple Skip Operations werden gezählt"""
        manager.track_skip_operation('5m')
        manager.track_skip_operation('5m')
        manager.track_skip_operation('15m')

        assert manager.skip_operations_count == 3
        assert manager.last_timeframe == '15m'

    # === TIMEFRAME TRANSITION TESTS ===

    def test_prepare_timeframe_transition_clean_state(self, manager):
        """Test: Transition ohne Skip Operations braucht keine Recreation"""
        plan = manager.prepare_timeframe_transition('5m', '15m')

        assert plan['needs_recreation'] is False
        assert plan['from_timeframe'] == '5m'
        assert plan['to_timeframe'] == '15m'
        assert manager.current_state == manager.STATES['TRANSITIONING']

    def test_prepare_timeframe_transition_with_skips(self, manager):
        """Test: Transition nach Skip Operations braucht Recreation"""
        manager.track_skip_operation('5m')

        plan = manager.prepare_timeframe_transition('5m', '15m')

        assert plan['needs_recreation'] is True
        assert plan['skip_count'] == 1
        assert plan['reason'] == 'skip_contamination'

    def test_prepare_timeframe_transition_corrupted_state(self, manager):
        """Test: Transition bei CORRUPTED State braucht Recreation"""
        manager.mark_chart_corrupted("test")

        plan = manager.prepare_timeframe_transition('5m', '15m')

        assert plan['needs_recreation'] is True

    def test_complete_timeframe_transition_success(self, manager):
        """Test: Erfolgreicher Transition-Abschluss setzt DATA_LOADED State"""
        manager.track_skip_operation('5m')
        manager.prepare_timeframe_transition('5m', '15m')

        manager.complete_timeframe_transition(success=True)

        assert manager.current_state == manager.STATES['DATA_LOADED']
        assert manager.skip_operations_count == 0  # Reset nach Erfolg

    def test_complete_timeframe_transition_failure(self, manager):
        """Test: Fehlgeschlagener Transition setzt CORRUPTED State"""
        manager.prepare_timeframe_transition('5m', '15m')

        manager.complete_timeframe_transition(success=False)

        assert manager.current_state == manager.STATES['CORRUPTED']

    # === CHART RECREATION TESTS ===

    def test_get_chart_recreation_command_increments_version(self, manager):
        """Test: Recreation Command erhöht Chart Version"""
        initial_version = manager.chart_series_version

        command = manager.get_chart_recreation_command()

        assert manager.chart_series_version == initial_version + 1
        assert command['action'] == 'recreate_chart_series'
        assert command['version'] == initial_version + 1
        assert command['clear_strategy'] == 'complete_destruction'

    def test_mark_chart_corrupted(self, manager):
        """Test: Chart kann als korrupt markiert werden"""
        manager.mark_chart_corrupted("test corruption")

        assert manager.current_state == manager.STATES['CORRUPTED']

    def test_force_chart_recreation_on_next_transition(self, manager):
        """Test: EMERGENCY Recreation kann forciert werden"""
        manager.force_chart_recreation_on_next_transition()

        assert manager.current_state == manager.STATES['CORRUPTED']

    # === CLEAN RESET TESTS ===

    def test_reset_to_clean_state(self, manager):
        """Test: Reset zu CLEAN State funktioniert"""
        # Setup: Erzeuge Skip-modifizierten State
        manager.track_skip_operation('5m')
        manager.track_skip_operation('5m')
        assert manager.skip_operations_count == 2

        # Reset
        manager.reset_to_clean_state()

        assert manager.current_state == manager.STATES['CLEAN']
        assert manager.skip_operations_count == 0
        assert manager.chart_series_version == 2  # Inkrementiert bei Reset

    # === STATE INFO TESTS ===

    def test_get_state_info(self, manager):
        """Test: get_state_info gibt vollständige Info zurück"""
        manager.track_skip_operation('5m')

        info = manager.get_state_info()

        assert 'state' in info
        assert 'skip_count' in info
        assert 'version' in info
        assert 'last_timeframe' in info
        assert info['skip_count'] == 1
        assert info['last_timeframe'] == '5m'
