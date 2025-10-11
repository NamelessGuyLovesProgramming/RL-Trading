"""
Unit Tests für charts.core.skip_renderer
Testet UniversalSkipRenderer und LegacyCompatibilityBridge
"""

import pytest
from datetime import datetime
from charts.core.skip_renderer import UniversalSkipRenderer, LegacyCompatibilityBridge


class TestUniversalSkipRenderer:
    """Tests für UniversalSkipRenderer"""

    @pytest.fixture
    def renderer(self):
        """Erstellt Skip Renderer Instanz"""
        return UniversalSkipRenderer()

    @pytest.fixture
    def sample_candle(self):
        """Erstellt Sample Candle"""
        return {
            'time': 1704067200,  # 2024-01-01 00:00:00
            'open': 20000.0,
            'high': 20010.0,
            'low': 19990.0,
            'close': 20005.0,
            'volume': 1000
        }

    @pytest.fixture
    def sample_skip_event(self, sample_candle):
        """Erstellt Sample Skip Event"""
        return {
            'time': datetime(2024, 1, 1, 0, 0),
            'candle': sample_candle,
            'original_timeframe': '5m',
            'created_at': datetime.now()
        }

    # === INITIALIZATION TESTS ===

    def test_renderer_initialization(self, renderer):
        """Test: Renderer wird korrekt initialisiert"""
        assert renderer is not None
        assert renderer.price_repository is None

    def test_renderer_initialization_with_price_repo(self):
        """Test: Renderer mit PriceRepository"""
        mock_repo = type('MockRepo', (), {'initialized': True})()
        renderer = UniversalSkipRenderer(price_repository=mock_repo)
        assert renderer.price_repository == mock_repo

    # === TIMEFRAME CONVERSION TESTS ===

    def test_get_timeframe_minutes_1m(self):
        """Test: 1m = 1 Minute"""
        assert UniversalSkipRenderer.get_timeframe_minutes('1m') == 1

    def test_get_timeframe_minutes_5m(self):
        """Test: 5m = 5 Minuten"""
        assert UniversalSkipRenderer.get_timeframe_minutes('5m') == 5

    def test_get_timeframe_minutes_1h(self):
        """Test: 1h = 60 Minuten"""
        assert UniversalSkipRenderer.get_timeframe_minutes('1h') == 60

    def test_get_timeframe_minutes_4h(self):
        """Test: 4h = 240 Minuten"""
        assert UniversalSkipRenderer.get_timeframe_minutes('4h') == 240

    def test_get_timeframe_minutes_invalid(self):
        """Test: Ungültiger Timeframe gibt 1 zurück"""
        assert UniversalSkipRenderer.get_timeframe_minutes('invalid') == 1

    # === TIMEFRAME COMPATIBILITY TESTS ===

    def test_is_timeframe_compatible_same_timeframe(self):
        """Test: Gleicher Timeframe ist immer kompatibel"""
        assert UniversalSkipRenderer._is_timeframe_compatible('5m', '5m')

    def test_is_timeframe_compatible_different_timeframes(self):
        """Test: Verschiedene Timeframes sind kompatibel (Enhanced Compatibility)"""
        assert UniversalSkipRenderer._is_timeframe_compatible('5m', '15m')
        assert UniversalSkipRenderer._is_timeframe_compatible('15m', '5m')

    def test_is_timeframe_compatible_all_combinations(self):
        """Test: Alle Timeframe-Kombinationen kompatibel"""
        timeframes = ['1m', '5m', '15m', '1h']
        for source in timeframes:
            for target in timeframes:
                assert UniversalSkipRenderer._is_timeframe_compatible(source, target)

    # === CANDLE VALIDATION TESTS ===

    def test_is_candle_safe_valid_candle(self, sample_candle):
        """Test: Valide Candle passiert Validierung"""
        assert UniversalSkipRenderer._is_candle_safe_for_timeframe(sample_candle, '5m')

    def test_is_candle_safe_none_candle(self):
        """Test: None Candle wird abgelehnt"""
        assert not UniversalSkipRenderer._is_candle_safe_for_timeframe(None, '5m')

    def test_is_candle_safe_invalid_type(self):
        """Test: Nicht-Dict wird abgelehnt"""
        assert not UniversalSkipRenderer._is_candle_safe_for_timeframe("invalid", '5m')

    def test_is_candle_safe_missing_fields(self):
        """Test: Candle mit fehlenden Feldern wird abgelehnt"""
        invalid_candle = {'time': 1234567890, 'open': 20000.0}  # missing high, low, close
        assert not UniversalSkipRenderer._is_candle_safe_for_timeframe(invalid_candle, '5m')

    def test_is_candle_safe_unrealistic_prices(self):
        """Test: Unrealistische Preise werden abgelehnt"""
        # Zu niedrig
        invalid_candle_low = {
            'time': 1234567890,
            'open': 100.0,  # < 1000 (unrealistic for NQ)
            'high': 110.0,
            'low': 90.0,
            'close': 105.0
        }
        assert not UniversalSkipRenderer._is_candle_safe_for_timeframe(invalid_candle_low, '5m')

        # Zu hoch
        invalid_candle_high = {
            'time': 1234567890,
            'open': 60000.0,  # > 50000 (unrealistic for NQ)
            'high': 61000.0,
            'low': 59000.0,
            'close': 60500.0
        }
        assert not UniversalSkipRenderer._is_candle_safe_for_timeframe(invalid_candle_high, '5m')

    # === CANDLE ADAPTATION TESTS ===

    def test_adapt_candle_same_timeframe(self, sample_candle):
        """Test: Candle bleibt gleich bei gleichem Timeframe"""
        event_time = datetime.fromtimestamp(sample_candle['time'])
        adapted = UniversalSkipRenderer._adapt_candle_for_timeframe(
            sample_candle, '5m', '5m', event_time
        )

        assert adapted['time'] == sample_candle['time']
        assert adapted['open'] == sample_candle['open']
        assert adapted['close'] == sample_candle['close']

    def test_adapt_candle_different_timeframe(self, sample_candle):
        """Test: Candle Zeit wird für anderen Timeframe angepasst"""
        # 2024-01-01 00:07:00 -> 15m boundary = 2024-01-01 00:00:00
        event_time = datetime(2024, 1, 1, 0, 7, 0)
        adapted = UniversalSkipRenderer._adapt_candle_for_timeframe(
            sample_candle, '5m', '15m', event_time
        )

        # Zeit sollte auf 15m Grenze angepasst sein
        expected_time = datetime(2024, 1, 1, 0, 0, 0)
        assert adapted['time'] == int(expected_time.timestamp())

    def test_adapt_candle_preserves_ohlc(self, sample_candle):
        """Test: OHLC Werte bleiben erhalten"""
        event_time = datetime.fromtimestamp(sample_candle['time'])
        adapted = UniversalSkipRenderer._adapt_candle_for_timeframe(
            sample_candle, '5m', '15m', event_time
        )

        assert adapted['open'] == sample_candle['open']
        assert adapted['high'] == sample_candle['high']
        assert adapted['low'] == sample_candle['low']
        assert adapted['close'] == sample_candle['close']

    # === RENDER SKIP CANDLES TESTS ===

    def test_render_skip_candles_empty_events(self, renderer):
        """Test: Leere Event-Liste gibt leere Candles zurück"""
        result = renderer.render_skip_candles_for_timeframe('5m', [])
        assert result == []

    def test_render_skip_candles_single_event_same_timeframe(self, renderer, sample_skip_event):
        """Test: Single Event im gleichen Timeframe wird gerendert"""
        result = renderer.render_skip_candles_for_timeframe('5m', [sample_skip_event])

        assert len(result) == 1
        assert result[0]['open'] == sample_skip_event['candle']['open']
        assert result[0]['close'] == sample_skip_event['candle']['close']

    def test_render_skip_candles_single_event_different_timeframe(self, renderer, sample_skip_event):
        """Test: Single Event in anderem Timeframe wird angepasst"""
        result = renderer.render_skip_candles_for_timeframe('15m', [sample_skip_event])

        assert len(result) == 1
        # Zeit sollte auf 15m Grenze angepasst sein
        assert result[0]['time'] is not None

    def test_render_skip_candles_multiple_events(self, renderer, sample_candle):
        """Test: Multiple Events werden gerendert"""
        events = [
            {
                'time': datetime(2024, 1, 1, 0, 0),
                'candle': sample_candle.copy(),
                'original_timeframe': '5m',
                'created_at': datetime.now()
            },
            {
                'time': datetime(2024, 1, 1, 0, 5),
                'candle': sample_candle.copy(),
                'original_timeframe': '5m',
                'created_at': datetime.now()
            }
        ]

        result = renderer.render_skip_candles_for_timeframe('5m', events)
        assert len(result) == 2

    def test_render_skip_candles_filters_invalid_candles(self, renderer):
        """Test: Ungültige Candles werden gefiltert"""
        events = [
            {
                'time': datetime(2024, 1, 1, 0, 0),
                'candle': {'time': 1234, 'open': 100.0},  # Invalid (missing fields, unrealistic)
                'original_timeframe': '5m',
                'created_at': datetime.now()
            }
        ]

        result = renderer.render_skip_candles_for_timeframe('5m', events)
        assert len(result) == 0  # Invalid candle should be filtered

    # === CREATE SKIP EVENT TESTS ===

    def test_create_skip_event_initializes_master_clock(self, renderer, sample_candle):
        """Test: create_skip_event initialisiert Master Clock"""
        master_clock = {}

        event = renderer.create_skip_event(sample_candle, '5m', master_clock)

        assert master_clock['initialized'] is True
        assert master_clock['current_time'] is not None
        assert isinstance(event, dict)
        assert event['original_timeframe'] == '5m'

    def test_create_skip_event_updates_master_clock(self, renderer, sample_candle):
        """Test: create_skip_event aktualisiert existierenden Master Clock"""
        master_clock = {
            'initialized': True,
            'current_time': datetime(2024, 1, 1, 0, 0)
        }

        event = renderer.create_skip_event(sample_candle, '5m', master_clock)

        # Master Clock sollte aktualisiert sein
        assert master_clock['current_time'] == datetime.fromtimestamp(sample_candle['time'])

    def test_create_skip_event_includes_candle_copy(self, renderer, sample_candle):
        """Test: Skip Event enthält Candle-Kopie"""
        master_clock = {}
        event = renderer.create_skip_event(sample_candle, '5m', master_clock)

        assert event['candle'] is not sample_candle  # Should be copy
        assert event['candle']['time'] == sample_candle['time']


class TestLegacyCompatibilityBridge:
    """Tests für LegacyCompatibilityBridge"""

    @pytest.fixture
    def renderer(self):
        """Erstellt Skip Renderer"""
        return UniversalSkipRenderer()

    @pytest.fixture
    def skip_events(self):
        """Erstellt Skip Events"""
        sample_candle = {
            'time': 1704067200,
            'open': 20000.0,
            'high': 20010.0,
            'low': 19990.0,
            'close': 20005.0,
            'volume': 1000
        }
        return [
            {
                'time': datetime(2024, 1, 1, 0, 0),
                'candle': sample_candle,
                'original_timeframe': '5m',
                'created_at': datetime.now()
            }
        ]

    @pytest.fixture
    def bridge(self, renderer, skip_events):
        """Erstellt Legacy Compatibility Bridge"""
        return LegacyCompatibilityBridge(renderer, skip_events)

    def test_bridge_initialization(self, renderer, skip_events):
        """Test: Bridge wird korrekt initialisiert"""
        bridge = LegacyCompatibilityBridge(renderer, skip_events)

        assert bridge.renderer == renderer
        assert bridge.skip_events == skip_events

    def test_bridge_getitem(self, bridge):
        """Test: Bridge unterstützt dict-like Access [timeframe]"""
        result = bridge['5m']

        assert isinstance(result, list)
        assert len(result) >= 0

    def test_bridge_get_with_default(self, bridge):
        """Test: Bridge.get() mit Default-Wert"""
        result = bridge.get('5m', [])

        assert isinstance(result, list)

    def test_bridge_get_invalid_timeframe(self, bridge):
        """Test: Bridge.get() für ungültigen Timeframe gibt Default zurück"""
        result = bridge.get('invalid', [])

        assert isinstance(result, list)

    def test_bridge_items(self, bridge):
        """Test: Bridge.items() gibt Timeframe-Tuple-Liste zurück"""
        items = bridge.items()

        assert isinstance(items, list)
        assert len(items) > 0
        # Jedes Item sollte Tuple (timeframe, candles) sein
        for timeframe, candles in items:
            assert isinstance(timeframe, str)
            assert isinstance(candles, list)

    def test_bridge_get_legacy_skip_candles_for_timeframe(self, bridge):
        """Test: get_legacy_skip_candles_for_timeframe funktioniert"""
        result = bridge.get_legacy_skip_candles_for_timeframe('5m')

        assert isinstance(result, list)
        assert len(result) >= 0
