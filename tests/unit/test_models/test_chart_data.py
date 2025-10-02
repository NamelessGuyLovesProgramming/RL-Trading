"""
Unit Tests für Chart Data Models
"""

import pytest
from datetime import datetime
import pandas as pd
from charts.models.chart_data import Candle, ChartData, CandleFactory


class TestCandle:
    """Tests für Candle Model"""

    def test_candle_creation(self):
        """Test: Candle-Erstellung"""
        candle = Candle(
            time=1234567890,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5
        )

        assert candle.time == 1234567890
        assert candle.open == 100.0
        assert candle.high == 101.0
        assert candle.low == 99.0
        assert candle.close == 100.5
        assert candle.volume is None

    def test_candle_with_volume(self):
        """Test: Candle mit Volume"""
        candle = Candle(
            time=1234567890,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0
        )

        assert candle.volume == 1000.0

    def test_candle_to_dict(self):
        """Test: Candle zu Dictionary"""
        candle = Candle(
            time=1234567890,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5
        )

        data = candle.to_dict()

        assert data['time'] == 1234567890
        assert data['open'] == 100.0
        assert data['high'] == 101.0
        assert data['low'] == 99.0
        assert data['close'] == 100.5

    def test_candle_datetime_property(self):
        """Test: Candle datetime Property"""
        candle = Candle(
            time=1234567890,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5
        )

        dt = candle.datetime
        assert isinstance(dt, datetime)
        assert dt.timestamp() == 1234567890


class TestChartData:
    """Tests für ChartData Model"""

    def test_chart_data_creation(self):
        """Test: ChartData-Erstellung"""
        candles = [
            Candle(time=1234567890, open=100.0, high=101.0, low=99.0, close=100.5),
            Candle(time=1234567891, open=100.5, high=102.0, low=100.0, close=101.5),
        ]

        chart_data = ChartData(
            candles=candles,
            timeframe="5m",
            symbol="NQ=F"
        )

        assert len(chart_data.candles) == 2
        assert chart_data.timeframe == "5m"
        assert chart_data.symbol == "NQ=F"

    def test_chart_data_candle_count(self):
        """Test: ChartData candle_count Property"""
        candles = [
            Candle(time=1234567890, open=100.0, high=101.0, low=99.0, close=100.5),
            Candle(time=1234567891, open=100.5, high=102.0, low=100.0, close=101.5),
            Candle(time=1234567892, open=101.5, high=103.0, low=101.0, close=102.5),
        ]

        chart_data = ChartData(candles=candles, timeframe="5m", symbol="NQ=F")

        assert chart_data.candle_count == 3

    def test_chart_data_first_candle(self):
        """Test: ChartData first_candle Property"""
        candles = [
            Candle(time=1234567890, open=100.0, high=101.0, low=99.0, close=100.5),
            Candle(time=1234567891, open=100.5, high=102.0, low=100.0, close=101.5),
        ]

        chart_data = ChartData(candles=candles, timeframe="5m", symbol="NQ=F")

        assert chart_data.first_candle == candles[0]

    def test_chart_data_last_candle(self):
        """Test: ChartData last_candle Property"""
        candles = [
            Candle(time=1234567890, open=100.0, high=101.0, low=99.0, close=100.5),
            Candle(time=1234567891, open=100.5, high=102.0, low=100.0, close=101.5),
        ]

        chart_data = ChartData(candles=candles, timeframe="5m", symbol="NQ=F")

        assert chart_data.last_candle == candles[1]

    def test_chart_data_empty(self):
        """Test: ChartData mit leeren Candles"""
        chart_data = ChartData(candles=[], timeframe="5m", symbol="NQ=F")

        assert chart_data.candle_count == 0
        assert chart_data.first_candle is None
        assert chart_data.last_candle is None


class TestCandleFactory:
    """Tests für CandleFactory"""

    def test_factory_from_dict(self):
        """Test: CandleFactory.from_dict()"""
        data = {
            'time': 1234567890,
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000.0
        }

        candle = CandleFactory.from_dict(data)

        assert candle.time == 1234567890
        assert candle.open == 100.0
        assert candle.high == 101.0
        assert candle.low == 99.0
        assert candle.close == 100.5
        assert candle.volume == 1000.0

    def test_factory_from_dict_no_volume(self):
        """Test: CandleFactory.from_dict() ohne Volume"""
        data = {
            'time': 1234567890,
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5
        }

        candle = CandleFactory.from_dict(data)

        assert candle.volume is None

    def test_factory_from_list(self):
        """Test: CandleFactory.from_list()"""
        candles_data = [
            {'time': 1234567890, 'open': 100.0, 'high': 101.0, 'low': 99.0, 'close': 100.5},
            {'time': 1234567891, 'open': 100.5, 'high': 102.0, 'low': 100.0, 'close': 101.5},
        ]

        candles = CandleFactory.from_list(candles_data)

        assert len(candles) == 2
        assert candles[0].time == 1234567890
        assert candles[1].time == 1234567891

    def test_factory_to_lightweight_charts_format(self):
        """Test: CandleFactory.to_lightweight_charts_format()"""
        candles = [
            Candle(time=1234567890, open=100.0, high=101.0, low=99.0, close=100.5),
            Candle(time=1234567891, open=100.5, high=102.0, low=100.0, close=101.5),
        ]

        result = CandleFactory.to_lightweight_charts_format(candles)

        assert len(result) == 2
        assert result[0]['time'] == 1234567890
        assert result[1]['close'] == 101.5
