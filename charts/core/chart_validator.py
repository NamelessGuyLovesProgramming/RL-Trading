"""
Chart Data Validator
Prevents "Value is null" errors in LightweightCharts
Data validation and sanitization für LightweightCharts compatibility
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class ChartDataValidator:
    """Data validation and sanitization für LightweightCharts compatibility"""

    def __init__(self):
        self.validation_stats: Dict[str, int] = {
            'total_validations': 0,
            'null_fixes': 0,
            'type_fixes': 0
        }

    def validate_chart_data(self, data: List[Dict[str, Any]],
                           timeframe: Optional[str] = None,
                           source: str = "unknown") -> List[Dict[str, Any]]:
        """Validates and sanitizes chart data before sending to LightweightCharts"""
        self.validation_stats['total_validations'] += 1

        if not data:
            print(f"[DATA-VALIDATOR] WARNING: Empty data from {source}")
            return []

        validated_data: List[Dict[str, Any]] = []
        fixed_count = 0

        for i, candle in enumerate(data):
            # Copy candle to prevent mutation
            validated_candle = candle.copy()
            candle_fixed = False

            # CRITICAL: Fix null/undefined values that cause LightweightCharts crashes
            required_fields = ['time', 'open', 'high', 'low', 'close']
            for field in required_fields:
                if field not in validated_candle or validated_candle[field] is None:
                    print(f"[DATA-VALIDATOR] CRITICAL: {field} is null in {timeframe} candle {i} from {source}")

                    if field == 'time':
                        # Use previous candle time + timeframe minutes if available
                        if i > 0 and validated_data:
                            prev_time = validated_data[-1]['time']
                            timeframe_minutes = self._get_timeframe_minutes(timeframe)
                            validated_candle[field] = prev_time + (timeframe_minutes * 60)
                        else:
                            # Fallback: Use current timestamp
                            validated_candle[field] = int(datetime.now().timestamp())
                        candle_fixed = True
                    else:
                        # For OHLC: Use previous candle's close or 20000 as fallback
                        fallback_price = 20000  # NQ realistic fallback
                        if i > 0 and validated_data:
                            fallback_price = validated_data[-1]['close']
                        validated_candle[field] = fallback_price
                        candle_fixed = True

                    self.validation_stats['null_fixes'] += 1

            # Type validation and conversion
            for field in required_fields:
                if field == 'time':
                    if not isinstance(validated_candle[field], (int, float)):
                        validated_candle[field] = int(float(validated_candle[field]))
                        candle_fixed = True
                        self.validation_stats['type_fixes'] += 1
                else:
                    if not isinstance(validated_candle[field], (int, float)):
                        try:
                            validated_candle[field] = float(validated_candle[field])
                            candle_fixed = True
                            self.validation_stats['type_fixes'] += 1
                        except (ValueError, TypeError):
                            validated_candle[field] = 20000  # Safe fallback
                            candle_fixed = True
                            self.validation_stats['null_fixes'] += 1

            # SPECIAL: 4h timeframe specific validation
            if timeframe == '4h' and candle_fixed:
                print(f"[DATA-VALIDATOR] 4h-FIX: Candle {i} sanitized - time:{validated_candle['time']}, "
                      f"OHLC:[{validated_candle['open']:.2f}, {validated_candle['high']:.2f}, "
                      f"{validated_candle['low']:.2f}, {validated_candle['close']:.2f}]")
                fixed_count += 1

            validated_data.append(validated_candle)

        if fixed_count > 0:
            print(f"[DATA-VALIDATOR] {timeframe} from {source}: {fixed_count}/{len(data)} candles fixed")

        return validated_data

    def _get_timeframe_minutes(self, timeframe: Optional[str]) -> int:
        """Helper: Convert timeframe to minutes"""
        if not timeframe:
            return 5

        timeframe_map = {
            '1m': 1, '2m': 2, '3m': 3, '5m': 5,
            '15m': 15, '30m': 30, '1h': 60, '4h': 240
        }
        return timeframe_map.get(timeframe, 5)

    def get_validation_stats(self) -> Dict[str, int]:
        """Returns validation statistics for debugging"""
        return self.validation_stats.copy()

    def reset_stats(self) -> None:
        """Reset validation statistics"""
        self.validation_stats = {'total_validations': 0, 'null_fixes': 0, 'type_fixes': 0}
