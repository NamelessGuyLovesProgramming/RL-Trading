@echo off
echo ============================================================
echo UNIT TESTS - Alle Unit Tests
echo ============================================================
echo.

py -m pytest tests/unit/ -v --tb=short

echo.
echo ============================================================
echo UNIT TESTS ABGESCHLOSSEN
echo ============================================================
pause
