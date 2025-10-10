"""
Input Validators - Validation Logic for API Inputs
REFACTOR PHASE 6: Zentralisierte Validierung
"""

from datetime import datetime, date
from typing import Optional, Union
from charts.config.constants import (
    TIMEFRAMES,
    MIN_VISIBLE_CANDLES,
    MAX_VISIBLE_CANDLES,
    MIN_PRICE_VALUE,
    MAX_PRICE_VALUE,
    MIN_TIMESTAMP,
    MAX_TIMESTAMP,
    DEBUG_MIN_SPEED,
    DEBUG_MAX_SPEED
)


# ============================================================
# VALIDATION RESULTS
# ============================================================

class ValidationResult:
    """
    Validation Result mit Success/Error Info

    Attributes:
        valid: True wenn Validierung erfolgreich
        error: Fehlermeldung (None wenn valid=True)
        value: Validierter Wert (konvertiert falls nötig)
    """

    def __init__(self, valid: bool, error: Optional[str] = None, value: any = None):
        self.valid = valid
        self.error = error
        self.value = value

    def __bool__(self):
        return self.valid

    def __repr__(self):
        if self.valid:
            return f"ValidationResult(valid=True, value={self.value})"
        return f"ValidationResult(valid=False, error={self.error})"


# ============================================================
# VALIDATOR CLASS
# ============================================================

class InputValidator:
    """
    Input Validator für API-Eingaben

    Validiert:
    - Timeframes
    - Datumsangaben
    - Kerzen-Anzahl
    - Preise
    - Timestamps
    - Debug-Speed
    """

    @staticmethod
    def validate_timeframe(timeframe: str) -> ValidationResult:
        """
        Validiert Timeframe

        Args:
            timeframe: Zu validierender Timeframe

        Returns:
            ValidationResult mit valid/error/value

        Example:
            >>> InputValidator.validate_timeframe("5m")
            ValidationResult(valid=True, value="5m")
            >>> InputValidator.validate_timeframe("10m")
            ValidationResult(valid=False, error="...")
        """
        if not timeframe:
            return ValidationResult(False, "Timeframe darf nicht leer sein")

        if not isinstance(timeframe, str):
            return ValidationResult(False, f"Timeframe muss String sein, nicht {type(timeframe).__name__}")

        if timeframe not in TIMEFRAMES:
            valid_tfs = ", ".join(TIMEFRAMES)
            return ValidationResult(False, f"Ungültiger Timeframe '{timeframe}'. Erlaubt: {valid_tfs}")

        return ValidationResult(True, value=timeframe)

    @staticmethod
    def validate_date(date_value: Union[str, datetime, date]) -> ValidationResult:
        """
        Validiert und parst Datum

        Args:
            date_value: Datum als String, datetime oder date

        Returns:
            ValidationResult mit datetime-Objekt

        Example:
            >>> InputValidator.validate_date("2024-01-01")
            ValidationResult(valid=True, value=datetime(2024, 1, 1))
        """
        if not date_value:
            return ValidationResult(False, "Datum darf nicht leer sein")

        # Bereits datetime
        if isinstance(date_value, datetime):
            return ValidationResult(True, value=date_value)

        # date → datetime
        if isinstance(date_value, date):
            dt = datetime.combine(date_value, datetime.min.time())
            return ValidationResult(True, value=dt)

        # String parsen
        if isinstance(date_value, str):
            try:
                # ISO-Format: YYYY-MM-DD oder YYYY-MM-DD HH:MM:SS
                if "T" in date_value:
                    dt = datetime.fromisoformat(date_value)
                elif " " in date_value:
                    dt = datetime.strptime(date_value, "%Y-%m-%d %H:%M:%S")
                else:
                    dt = datetime.strptime(date_value, "%Y-%m-%d")
                return ValidationResult(True, value=dt)
            except ValueError as e:
                return ValidationResult(False, f"Ungültiges Datum-Format: {e}")

        return ValidationResult(False, f"Ungültiger Datum-Typ: {type(date_value).__name__}")

    @staticmethod
    def validate_candle_count(count: Union[int, str]) -> ValidationResult:
        """
        Validiert Kerzen-Anzahl

        Args:
            count: Anzahl Kerzen (int oder String)

        Returns:
            ValidationResult mit int-Wert

        Example:
            >>> InputValidator.validate_candle_count(300)
            ValidationResult(valid=True, value=300)
        """
        # String → int konvertieren
        if isinstance(count, str):
            try:
                count = int(count)
            except ValueError:
                return ValidationResult(False, f"Ungültige Zahl: '{count}'")

        if not isinstance(count, int):
            return ValidationResult(False, f"Count muss int sein, nicht {type(count).__name__}")

        if count < MIN_VISIBLE_CANDLES:
            return ValidationResult(False, f"Mindestens {MIN_VISIBLE_CANDLES} Kerzen erforderlich")

        if count > MAX_VISIBLE_CANDLES:
            return ValidationResult(False, f"Maximal {MAX_VISIBLE_CANDLES} Kerzen erlaubt")

        return ValidationResult(True, value=count)

    @staticmethod
    def validate_price(price: Union[float, int, str]) -> ValidationResult:
        """
        Validiert Preis-Wert

        Args:
            price: Preis (float, int oder String)

        Returns:
            ValidationResult mit float-Wert

        Example:
            >>> InputValidator.validate_price(100.5)
            ValidationResult(valid=True, value=100.5)
        """
        # String → float konvertieren
        if isinstance(price, str):
            try:
                price = float(price)
            except ValueError:
                return ValidationResult(False, f"Ungültiger Preis: '{price}'")

        # int → float
        if isinstance(price, int):
            price = float(price)

        if not isinstance(price, float):
            return ValidationResult(False, f"Preis muss Zahl sein, nicht {type(price).__name__}")

        if price < MIN_PRICE_VALUE:
            return ValidationResult(False, f"Preis darf nicht negativ sein")

        if price > MAX_PRICE_VALUE:
            return ValidationResult(False, f"Preis zu hoch (max: {MAX_PRICE_VALUE})")

        return ValidationResult(True, value=price)

    @staticmethod
    def validate_timestamp(timestamp: Union[int, float]) -> ValidationResult:
        """
        Validiert Unix-Timestamp

        Args:
            timestamp: Unix-Timestamp (int oder float)

        Returns:
            ValidationResult mit int-Timestamp

        Example:
            >>> InputValidator.validate_timestamp(1704067200)
            ValidationResult(valid=True, value=1704067200)
        """
        if not isinstance(timestamp, (int, float)):
            return ValidationResult(False, f"Timestamp muss Zahl sein, nicht {type(timestamp).__name__}")

        timestamp = int(timestamp)

        if timestamp < MIN_TIMESTAMP:
            return ValidationResult(False, f"Timestamp zu alt (vor 2000-01-01)")

        if timestamp > MAX_TIMESTAMP:
            return ValidationResult(False, f"Timestamp zu weit in Zukunft (Y2038 Problem)")

        return ValidationResult(True, value=timestamp)

    @staticmethod
    def validate_debug_speed(speed: Union[float, int, str]) -> ValidationResult:
        """
        Validiert Debug-Speed

        Args:
            speed: Speed-Wert (float, int oder String)

        Returns:
            ValidationResult mit float-Wert

        Example:
            >>> InputValidator.validate_debug_speed(2.0)
            ValidationResult(valid=True, value=2.0)
        """
        # String → float konvertieren
        if isinstance(speed, str):
            try:
                speed = float(speed)
            except ValueError:
                return ValidationResult(False, f"Ungültige Speed: '{speed}'")

        # int → float
        if isinstance(speed, int):
            speed = float(speed)

        if not isinstance(speed, float):
            return ValidationResult(False, f"Speed muss Zahl sein, nicht {type(speed).__name__}")

        if speed < DEBUG_MIN_SPEED:
            return ValidationResult(False, f"Speed zu langsam (min: {DEBUG_MIN_SPEED}x)")

        if speed > DEBUG_MAX_SPEED:
            return ValidationResult(False, f"Speed zu schnell (max: {DEBUG_MAX_SPEED}x)")

        return ValidationResult(True, value=speed)


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def validate_timeframe(timeframe: str) -> bool:
    """
    Einfache Timeframe-Validierung (nur bool)

    Args:
        timeframe: Zu validierender Timeframe

    Returns:
        True wenn gültig, False sonst

    Example:
        >>> validate_timeframe("5m")
        True
    """
    return InputValidator.validate_timeframe(timeframe).valid


def validate_date(date_value: Union[str, datetime, date]) -> Optional[datetime]:
    """
    Einfache Datum-Validierung mit Rückgabe

    Args:
        date_value: Zu validierendes Datum

    Returns:
        datetime-Objekt oder None bei Fehler

    Example:
        >>> validate_date("2024-01-01")
        datetime(2024, 1, 1, 0, 0)
    """
    result = InputValidator.validate_date(date_value)
    return result.value if result.valid else None


def validate_candle_count(count: Union[int, str]) -> Optional[int]:
    """
    Einfache Candle-Count-Validierung mit Rückgabe

    Args:
        count: Zu validierende Anzahl

    Returns:
        int-Wert oder None bei Fehler

    Example:
        >>> validate_candle_count(300)
        300
    """
    result = InputValidator.validate_candle_count(count)
    return result.value if result.valid else None


def validate_price(price: Union[float, int, str]) -> Optional[float]:
    """
    Einfache Preis-Validierung mit Rückgabe

    Args:
        price: Zu validierender Preis

    Returns:
        float-Wert oder None bei Fehler

    Example:
        >>> validate_price(100.5)
        100.5
    """
    result = InputValidator.validate_price(price)
    return result.value if result.valid else None


# ============================================================
# DEVELOPMENT HELPERS
# ============================================================

if __name__ == "__main__":
    # Quick Validator Test
    print("=" * 60)
    print("✅ Input Validator Test")
    print("=" * 60)

    # Test Timeframe
    print("\n📊 Timeframe Validation:")
    for tf in ["1m", "5m", "10m", "invalid"]:
        result = InputValidator.validate_timeframe(tf)
        print(f"  {tf}: {result}")

    # Test Date
    print("\n📅 Date Validation:")
    for d in ["2024-01-01", "2024-01-01T12:00:00", "invalid", datetime.now()]:
        result = InputValidator.validate_date(d)
        print(f"  {d}: {result}")

    # Test Candle Count
    print("\n🕯️  Candle Count Validation:")
    for count in [1, 300, 3000, "100", "invalid"]:
        result = InputValidator.validate_candle_count(count)
        print(f"  {count}: {result}")

    # Test Price
    print("\n💰 Price Validation:")
    for price in [100.5, -10, 1000000000, "123.45", "invalid"]:
        result = InputValidator.validate_price(price)
        print(f"  {price}: {result}")

    # Test Debug Speed
    print("\n⚡ Debug Speed Validation:")
    for speed in [0.1, 1.0, 10.0, 200, "2.5", "invalid"]:
        result = InputValidator.validate_debug_speed(speed)
        print(f"  {speed}: {result}")
