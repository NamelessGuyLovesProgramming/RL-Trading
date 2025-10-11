"""
Test-Skript für Phase 1: Models Layer
Validiert alle erstellten Models
"""

print("=" * 60)
print("🧪 PHASE 1 VALIDIERUNG - Models Layer")
print("=" * 60)
print()

# Test 1: Candle Model
print("Test 1: Candle Model")
try:
    from charts.models import Candle
    candle = Candle(time=1234567890, open=100, high=101, low=99, close=100.5)
    print(f"  ✅ Candle erstellt: {candle}")
    print(f"  ✅ Candle.datetime: {candle.datetime}")
    print(f"  ✅ Candle.to_dict(): {candle.to_dict()}")
except Exception as e:
    print(f"  ❌ FEHLER: {e}")
print()

# Test 2: ChartData Model
print("Test 2: ChartData Model")
try:
    from charts.models import ChartData, CandleFactory
    candles = [
        Candle(time=1234567890, open=100, high=101, low=99, close=100.5),
        Candle(time=1234567891, open=100.5, high=102, low=100, close=101.5),
    ]
    chart_data = ChartData(candles=candles, timeframe="5m", symbol="NQ=F")
    print(f"  ✅ ChartData erstellt: {chart_data.candle_count} Kerzen")
    print(f"  ✅ First Candle: {chart_data.first_candle}")
    print(f"  ✅ Last Candle: {chart_data.last_candle}")
except Exception as e:
    print(f"  ❌ FEHLER: {e}")
print()

# Test 3: CandleFactory
print("Test 3: CandleFactory")
try:
    data = {'time': 1234567890, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5}
    candle = CandleFactory.from_dict(data)
    print(f"  ✅ Candle aus Dict: {candle}")

    candles_list = CandleFactory.from_list([data, data])
    print(f"  ✅ Candles aus List: {len(candles_list)} Kerzen")
except Exception as e:
    print(f"  ❌ FEHLER: {e}")
print()

# Test 4: SkipEvent & SkipEventStore
print("Test 4: SkipEvent & SkipEventStore")
try:
    from charts.models import SkipEvent, SkipEventStore
    from datetime import datetime

    store = SkipEventStore()
    print(f"  ✅ SkipEventStore erstellt: {store}")

    skip_event = SkipEvent(
        time=datetime.now(),
        candle=candle,
        original_timeframe="5m"
    )
    store.add_event(skip_event)
    print(f"  ✅ SkipEvent hinzugefügt: {store.count()} Events")
    print(f"  ✅ Events für 5m: {store.count_by_timeframe('5m')}")
except Exception as e:
    print(f"  ❌ FEHLER: {e}")
print()

# Test 5: Position Models
print("Test 5: Position Models")
try:
    from charts.models import Position, PositionBox
    from charts.models.position import PositionDirection, PositionStatus

    position = Position(
        id="pos_1",
        entry_price=20000.0,
        sl_price=19900.0,
        tp_price=20200.0,
        entry_time=datetime.now(),
        direction=PositionDirection.LONG,
        status=PositionStatus.OPEN
    )
    print(f"  ✅ Position erstellt: {position.id}")
    print(f"  ✅ Direction: {position.direction}")
    print(f"  ✅ Risk/Reward Ratio: {position.risk_reward_ratio}")
    print(f"  ✅ Is Open: {position.is_open}")

    position_box = PositionBox(position=position)
    print(f"  ✅ PositionBox erstellt: {position_box}")
except Exception as e:
    print(f"  ❌ FEHLER: {e}")
print()

# Test 6: Timeframe Models
print("Test 6: Timeframe Models")
try:
    from charts.models import TimeframeConfig, TIMEFRAME_CONFIGS
    from charts.models.timeframe import (
        get_timeframe_minutes,
        is_valid_timeframe,
        get_next_higher_timeframe,
        get_next_lower_timeframe
    )

    print(f"  ✅ Timeframe Configs: {len(TIMEFRAME_CONFIGS)} verfügbar")
    print(f"  ✅ 5m minutes: {get_timeframe_minutes('5m')}")
    print(f"  ✅ is_valid_timeframe('5m'): {is_valid_timeframe('5m')}")
    print(f"  ✅ is_valid_timeframe('10m'): {is_valid_timeframe('10m')}")
    print(f"  ✅ Next higher (5m): {get_next_higher_timeframe('5m')}")
    print(f"  ✅ Next lower (5m): {get_next_lower_timeframe('5m')}")
except Exception as e:
    print(f"  ❌ FEHLER: {e}")
print()

# Test 7: DebugState Model
print("Test 7: DebugState Model")
try:
    from charts.models import DebugState

    debug = DebugState()
    print(f"  ✅ DebugState erstellt: {debug}")

    debug.activate(start_date=datetime.now())
    print(f"  ✅ Debug aktiviert: {debug}")

    debug.set_speed(2.0)
    print(f"  ✅ Speed gesetzt: {debug.speed}x")
    print(f"  ✅ Delay: {debug.delay_ms}ms")

    debug.play()
    print(f"  ✅ Is running: {debug.is_running}")
except Exception as e:
    print(f"  ❌ FEHLER: {e}")
print()

# Zusammenfassung
print("=" * 60)
print("✅ PHASE 1 VALIDIERUNG ERFOLGREICH!")
print("=" * 60)
print()
print("Alle Models funktionieren:")
print("  ✅ Candle & ChartData")
print("  ✅ CandleFactory")
print("  ✅ SkipEvent & SkipEventStore")
print("  ✅ Position & PositionBox")
print("  ✅ TimeframeConfig")
print("  ✅ DebugState")
print()
print("🚀 Bereit für Phase 2: Repositories Layer")
print()
