"""
Unit Tests für Timeframe Models
"""

import pytest
from charts.models.timeframe import (
    TimeframeConfig,
    TIMEFRAME_CONFIGS,
    get_timeframe_config,
    get_timeframe_minutes,
    is_valid_timeframe,
    get_next_higher_timeframe,
    get_next_lower_timeframe
)


class TestTimeframeConfig:
    """Tests für TimeframeConfig"""

    def test_timeframe_config_creation(self):
        """Test: TimeframeConfig-Erstellung"""
        config = TimeframeConfig(timeframe="5m", minutes=5, display_name="5 Minutes")

        assert config.timeframe == "5m"
        assert config.minutes == 5
        assert config.display_name == "5 Minutes"

    def test_timeframe_config_seconds(self):
        """Test: TimeframeConfig.seconds Property"""
        config = TimeframeConfig(timeframe="5m", minutes=5, display_name="5 Minutes")

        assert config.seconds == 300  # 5 * 60

    def test_timeframe_config_is_intraday(self):
        """Test: TimeframeConfig.is_intraday Property"""
        config_5m = TimeframeConfig(timeframe="5m", minutes=5, display_name="5 Minutes")
        config_1h = TimeframeConfig(timeframe="1h", minutes=60, display_name="1 Hour")

        assert config_5m.is_intraday is True
        assert config_1h.is_intraday is True


class TestTimeframeConfigs:
    """Tests für TIMEFRAME_CONFIGS"""

    def test_all_timeframes_exist(self):
        """Test: Alle Timeframes vorhanden"""
        expected = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]

        for tf in expected:
            assert tf in TIMEFRAME_CONFIGS

    def test_5m_config(self):
        """Test: 5m Config korrekt"""
        config = TIMEFRAME_CONFIGS["5m"]

        assert config.timeframe == "5m"
        assert config.minutes == 5
        assert config.display_name == "5 Minutes"


class TestTimeframeFunctions:
    """Tests für Timeframe-Hilfsfunktionen"""

    def test_get_timeframe_config(self):
        """Test: get_timeframe_config()"""
        config = get_timeframe_config("5m")

        assert config.timeframe == "5m"
        assert config.minutes == 5

    def test_get_timeframe_config_invalid(self):
        """Test: get_timeframe_config() mit ungültigem Timeframe"""
        with pytest.raises(ValueError):
            get_timeframe_config("10m")

    def test_get_timeframe_minutes(self):
        """Test: get_timeframe_minutes()"""
        assert get_timeframe_minutes("1m") == 1
        assert get_timeframe_minutes("5m") == 5
        assert get_timeframe_minutes("1h") == 60
        assert get_timeframe_minutes("4h") == 240

    def test_is_valid_timeframe(self):
        """Test: is_valid_timeframe()"""
        assert is_valid_timeframe("5m") is True
        assert is_valid_timeframe("1h") is True
        assert is_valid_timeframe("10m") is False
        assert is_valid_timeframe("invalid") is False

    def test_get_next_higher_timeframe(self):
        """Test: get_next_higher_timeframe()"""
        assert get_next_higher_timeframe("1m") == "2m"
        assert get_next_higher_timeframe("5m") == "15m"
        assert get_next_higher_timeframe("1h") == "4h"
        assert get_next_higher_timeframe("4h") == "4h"  # Bereits höchster

    def test_get_next_lower_timeframe(self):
        """Test: get_next_lower_timeframe()"""
        assert get_next_lower_timeframe("5m") == "3m"
        assert get_next_lower_timeframe("1h") == "30m"
        assert get_next_lower_timeframe("1m") == "1m"  # Bereits niedrigster
