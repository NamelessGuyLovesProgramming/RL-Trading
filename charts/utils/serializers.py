"""
JSON Serializers - Datetime & Complex Object Handling
REFACTOR PHASE 6: Zentralisierte Serialisierung
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List
import json


# ============================================================
# MAIN SERIALIZER
# ============================================================

def json_serializer(obj: Any) -> Any:
    """
    Custom JSON Serializer für datetime und komplexe Objekte

    Unterstützt:
    - datetime → ISO-Format
    - date → ISO-Format
    - Decimal → float
    - Custom Objects → dict (via __dict__)

    Args:
        obj: Zu serialisierendes Objekt

    Returns:
        Serialisierbares Objekt

    Raises:
        TypeError: Wenn Objekt nicht serialisierbar

    Example:
        >>> import json
        >>> data = {"time": datetime.now()}
        >>> json.dumps(data, default=json_serializer)
        '{"time": "2024-12-31T16:55:00.000000"}'
    """
    # datetime → ISO-String
    if isinstance(obj, datetime):
        return obj.isoformat()

    # date → ISO-String
    if isinstance(obj, date):
        return obj.isoformat()

    # Decimal → float
    if isinstance(obj, Decimal):
        return float(obj)

    # Custom Objects mit __dict__
    if hasattr(obj, '__dict__'):
        try:
            result = {}
            for key, value in obj.__dict__.items():
                # Private Attribute überspringen
                if key.startswith('_'):
                    continue

                # Callable überspringen
                if callable(value):
                    continue

                # Rekursiv serialisieren
                if isinstance(value, (datetime, date, Decimal)):
                    result[key] = json_serializer(value)
                elif isinstance(value, (list, tuple)):
                    result[key] = [json_serializer(item) for item in value]
                elif isinstance(value, dict):
                    result[key] = {k: json_serializer(v) for k, v in value.items()}
                else:
                    result[key] = value

            return result
        except Exception:
            return str(obj)

    # Fallback
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ============================================================
# SPECIFIC SERIALIZERS
# ============================================================

def serialize_candle(candle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialisiert Candle-Daten für JSON-Output

    Args:
        candle: Candle-Dict mit time, open, high, low, close

    Returns:
        Serialisiertes Candle-Dict

    Example:
        >>> candle = {"time": datetime(2024, 1, 1), "open": 100.5}
        >>> serialize_candle(candle)
        {"time": "2024-01-01T00:00:00", "open": 100.5}
    """
    result = {}

    for key, value in candle.items():
        if isinstance(value, datetime):
            # Datetime → Unix Timestamp (für TradingView Chart)
            result[key] = int(value.timestamp())
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value

    return result


def serialize_chart_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Serialisiert Chart-Daten (Liste von Candles)

    Args:
        data: Liste von Candle-Dicts

    Returns:
        Serialisierte Chart-Daten

    Example:
        >>> data = [{"time": datetime(2024, 1, 1), "open": 100.5}]
        >>> serialize_chart_data(data)
        [{"time": 1704067200, "open": 100.5}]
    """
    return [serialize_candle(candle) for candle in data]


def serialize_debug_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialisiert Debug-State für JSON-Output

    Args:
        state: Debug-State Dict

    Returns:
        Serialisierter Debug-State

    Example:
        >>> state = {"active": True, "current_date": datetime(2024, 1, 1)}
        >>> serialize_debug_state(state)
        {"active": True, "current_date": "2024-01-01T00:00:00"}
    """
    result = {}

    for key, value in state.items():
        if isinstance(value, datetime):
            # Datetime → ISO-String (für Debug-UI)
            result[key] = value.isoformat()
        elif isinstance(value, date):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, (list, tuple)):
            result[key] = [json_serializer(item) for item in value]
        elif isinstance(value, dict):
            result[key] = {k: json_serializer(v) for k, v in value.items()}
        else:
            result[key] = value

    return result


# ============================================================
# SAFE SERIALIZATION
# ============================================================

def safe_serialize(obj: Any, fallback: Any = None) -> Any:
    """
    Sichere Serialisierung mit Fallback

    Args:
        obj: Zu serialisierendes Objekt
        fallback: Fallback-Wert bei Fehler

    Returns:
        Serialisiertes Objekt oder Fallback

    Example:
        >>> safe_serialize(datetime.now())
        "2024-12-31T16:55:00.000000"
        >>> safe_serialize(object(), fallback="error")
        "error"
    """
    try:
        return json_serializer(obj)
    except (TypeError, ValueError):
        return fallback if fallback is not None else str(obj)


def to_json_string(obj: Any, pretty: bool = False) -> str:
    """
    Konvertiert Objekt zu JSON-String

    Args:
        obj: Zu serialisierendes Objekt
        pretty: Pretty-Print mit Einrückung

    Returns:
        JSON-String

    Example:
        >>> to_json_string({"time": datetime.now()}, pretty=True)
        '{\\n  "time": "2024-12-31T16:55:00.000000"\\n}'
    """
    indent = 2 if pretty else None
    return json.dumps(obj, default=json_serializer, indent=indent)


# ============================================================
# DESERIALIZATION HELPERS
# ============================================================

def parse_datetime(value: Any) -> datetime:
    """
    Parst Datetime aus verschiedenen Formaten

    Args:
        value: Datetime-String, Unix-Timestamp oder datetime

    Returns:
        datetime-Objekt

    Raises:
        ValueError: Wenn Parsing fehlschlägt

    Example:
        >>> parse_datetime("2024-01-01T00:00:00")
        datetime(2024, 1, 1, 0, 0, 0)
        >>> parse_datetime(1704067200)
        datetime(2024, 1, 1, 0, 0, 0)
    """
    # Bereits datetime
    if isinstance(value, datetime):
        return value

    # Unix-Timestamp (int oder float)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)

    # ISO-String
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            # Fallback: Weitere Formate
            from datetime import datetime as dt
            formats = [
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%d.%m.%Y",
                "%d.%m.%Y %H:%M:%S"
            ]
            for fmt in formats:
                try:
                    return dt.strptime(value, fmt)
                except ValueError:
                    continue

    raise ValueError(f"Cannot parse datetime from: {value}")


def parse_date(value: Any) -> date:
    """
    Parst Date aus verschiedenen Formaten

    Args:
        value: Date-String oder date

    Returns:
        date-Objekt

    Raises:
        ValueError: Wenn Parsing fehlschlägt
    """
    # Bereits date
    if isinstance(value, date):
        return value

    # datetime → date
    if isinstance(value, datetime):
        return value.date()

    # String
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            # Fallback
            dt = parse_datetime(value)
            return dt.date()

    raise ValueError(f"Cannot parse date from: {value}")


# ============================================================
# DEVELOPMENT HELPERS
# ============================================================

if __name__ == "__main__":
    # Quick Serializer Test
    print("=" * 60)
    print("🔄 JSON Serializer Test")
    print("=" * 60)

    # Test datetime
    now = datetime.now()
    print(f"datetime: {now}")
    print(f"  → {json_serializer(now)}")

    # Test Candle
    candle = {
        "time": now,
        "open": 100.5,
        "high": 101.0,
        "low": 100.0,
        "close": 100.8
    }
    print(f"\nCandle: {candle}")
    print(f"  → {serialize_candle(candle)}")

    # Test Chart Data
    data = [candle, candle]
    print(f"\nChart Data ({len(data)} candles)")
    print(f"  → {serialize_chart_data(data)}")

    # Test to_json_string
    print(f"\nJSON String (pretty):")
    print(to_json_string({"time": now, "value": 123.45}, pretty=True))
