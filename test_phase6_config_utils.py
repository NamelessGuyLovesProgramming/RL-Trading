"""
Phase 6 Validation Test - Config & Utils
Tests Settings, Constants, Serializers und Validators
"""

import sys
from datetime import datetime, date


def test_config_imports():
    """Test 1: Config Module Import"""
    print("\n" + "=" * 60)
    print("TEST 1: Config Module Import")
    print("=" * 60)

    try:
        from charts.config import settings, TIMEFRAMES, TIMEFRAME_MINUTES
        print(f"[OK] settings imported: {type(settings).__name__}")
        print(f"[OK] TIMEFRAMES imported: {len(TIMEFRAMES)} timeframes")
        print(f"[OK] TIMEFRAME_MINUTES imported: {len(TIMEFRAME_MINUTES)} entries")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        return False


def test_settings_values():
    """Test 2: Settings Values"""
    print("\n" + "=" * 60)
    print("TEST 2: Settings Values")
    print("=" * 60)

    try:
        from charts.config import settings

        print(f"Host: {settings.host}")
        print(f"Port: {settings.port}")
        print(f"Data Path: {settings.data_path}")
        print(f"Default Symbol: {settings.default_symbol}")
        print(f"Default Timeframe: {settings.default_timeframe}")
        print(f"Cache Enabled: {settings.enable_cache}")
        print(f"Debug Mode: {settings.debug_mode}")

        assert settings.host == "0.0.0.0"
        assert settings.port == 8003
        assert settings.default_timeframe in ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]

        print("[OK] All settings valid")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        return False


def test_constants():
    """Test 3: Constants"""
    print("\n" + "=" * 60)
    print("TEST 3: Constants")
    print("=" * 60)

    try:
        from charts.config.constants import (
            TIMEFRAMES,
            TIMEFRAME_MINUTES,
            DEFAULT_CANDLE_COUNT,
            get_adjacent_timeframes,
            get_timeframe_display_name
        )

        print(f"Timeframes: {TIMEFRAMES}")
        print(f"Default Candle Count: {DEFAULT_CANDLE_COUNT}")

        # Test adjacent timeframes
        adjacent = get_adjacent_timeframes("5m")
        print(f"Adjacent to 5m: {adjacent}")
        assert "3m" in adjacent
        assert "15m" in adjacent

        # Test display name
        display = get_timeframe_display_name("5m")
        print(f"Display name for 5m: {display}")
        assert display == "5 Minutes"

        print("[OK] All constants valid")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        return False


def test_serializers():
    """Test 4: Serializers"""
    print("\n" + "=" * 60)
    print("TEST 4: Serializers")
    print("=" * 60)

    try:
        from charts.utils.serializers import (
            json_serializer,
            serialize_candle,
            serialize_chart_data,
            to_json_string
        )

        # Test datetime serialization
        now = datetime.now()
        serialized = json_serializer(now)
        print(f"datetime serialized: {serialized}")
        assert isinstance(serialized, str)

        # Test candle serialization
        candle = {
            "time": datetime(2024, 1, 1, 10, 0, 0),
            "open": 100.5,
            "high": 101.0,
            "low": 100.0,
            "close": 100.8
        }
        serialized_candle = serialize_candle(candle)
        print(f"Candle serialized: {serialized_candle}")
        assert isinstance(serialized_candle["time"], int)
        assert serialized_candle["open"] == 100.5

        # Test chart data serialization
        data = [candle, candle]
        serialized_data = serialize_chart_data(data)
        print(f"Chart data serialized: {len(serialized_data)} candles")
        assert len(serialized_data) == 2

        # Test to_json_string
        json_str = to_json_string({"time": now}, pretty=False)
        print(f"JSON string: {json_str[:50]}...")
        assert isinstance(json_str, str)

        print("[OK] All serializers working")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validators():
    """Test 5: Validators"""
    print("\n" + "=" * 60)
    print("TEST 5: Validators")
    print("=" * 60)

    try:
        from charts.utils.validators import (
            InputValidator,
            validate_timeframe,
            validate_date,
            validate_candle_count,
            validate_price
        )

        # Test timeframe validation
        result = InputValidator.validate_timeframe("5m")
        print(f"Timeframe '5m' valid: {result.valid}")
        assert result.valid

        result_invalid = InputValidator.validate_timeframe("10m")
        print(f"Timeframe '10m' valid: {result_invalid.valid} (should be False)")
        assert not result_invalid.valid

        # Test date validation
        result_date = InputValidator.validate_date("2024-01-01")
        print(f"Date '2024-01-01' valid: {result_date.valid}, value: {result_date.value}")
        assert result_date.valid
        assert isinstance(result_date.value, datetime)

        # Test candle count validation
        result_count = InputValidator.validate_candle_count(300)
        print(f"Candle count 300 valid: {result_count.valid}")
        assert result_count.valid

        result_count_invalid = InputValidator.validate_candle_count(5000)
        print(f"Candle count 5000 valid: {result_count_invalid.valid} (should be False)")
        assert not result_count_invalid.valid

        # Test price validation
        result_price = InputValidator.validate_price(100.5)
        print(f"Price 100.5 valid: {result_price.valid}")
        assert result_price.valid

        result_price_invalid = InputValidator.validate_price(-10)
        print(f"Price -10 valid: {result_price_invalid.valid} (should be False)")
        assert not result_price_invalid.valid

        # Test convenience functions
        is_valid = validate_timeframe("5m")
        print(f"Convenience validate_timeframe('5m'): {is_valid}")
        assert is_valid

        parsed_date = validate_date("2024-01-01")
        print(f"Convenience validate_date('2024-01-01'): {parsed_date}")
        assert parsed_date is not None

        print("[OK] All validators working")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test 6: Integration Test"""
    print("\n" + "=" * 60)
    print("TEST 6: Integration Test")
    print("=" * 60)

    try:
        from charts.config import settings, TIMEFRAMES
        from charts.utils import InputValidator, serialize_candle

        # Workflow: Validate → Process → Serialize
        timeframe = "5m"

        # 1. Validate Timeframe
        tf_result = InputValidator.validate_timeframe(timeframe)
        assert tf_result.valid
        print(f"[OK] Step 1: Timeframe '{timeframe}' validated")

        # 2. Validate Date
        date_result = InputValidator.validate_date("2024-01-01")
        assert date_result.valid
        print(f"[OK] Step 2: Date validated: {date_result.value}")

        # 3. Validate Candle Count
        count_result = InputValidator.validate_candle_count(settings.default_candle_count)
        assert count_result.valid
        print(f"[OK] Step 3: Candle count validated: {count_result.value}")

        # 4. Create & Serialize Candle
        candle = {
            "time": date_result.value,
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5
        }
        serialized = serialize_candle(candle)
        assert isinstance(serialized["time"], int)
        print(f"[OK] Step 4: Candle serialized: time={serialized['time']}, close={serialized['close']}")

        print("[OK] Integration test passed")
        return True
    except Exception as e:
        print(f"[FAIL] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("PHASE 6 VALIDATION - CONFIG & UTILS")
    print("=" * 60)

    tests = [
        ("Config Imports", test_config_imports),
        ("Settings Values", test_settings_values),
        ("Constants", test_constants),
        ("Serializers", test_serializers),
        ("Validators", test_validators),
        ("Integration", test_integration)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[FAIL] Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"{status}: {name}")

    print("=" * 60)
    print(f"TOTAL: {passed}/{total} tests passed ({passed * 100 // total}%)")
    print("=" * 60)

    if passed == total:
        print("\n[OK] Phase 6: Config & Utils - ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n[FAIL] Phase 6: Config & Utils - {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
