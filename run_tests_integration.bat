@echo off
echo ============================================================
echo INTEGRATION TESTS - Data Loading Workflows
echo ============================================================
echo.

py -m pytest tests/integration/ -v --tb=short

echo.
echo ============================================================
echo INTEGRATION TESTS ABGESCHLOSSEN
echo ============================================================
pause
