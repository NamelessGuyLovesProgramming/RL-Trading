@echo off
echo ============================================================
echo ALLE TESTS - Komplette Test-Suite
echo ============================================================
echo.

echo [1/4] Phase 1 - Models Layer
echo ------------------------------------------------------------
py test_phase1_models.py
echo.

echo [2/4] Phase 2 - Repositories Layer (pytest)
echo ------------------------------------------------------------
py -m pytest tests/unit/test_repositories/ -v --tb=short
echo.

echo [3/4] Integration Tests
echo ------------------------------------------------------------
py -m pytest tests/integration/ -v --tb=short
echo.

echo [4/4] Komplette pytest Suite
echo ------------------------------------------------------------
py -m pytest tests/ -v --tb=short
echo.

echo ============================================================
echo ALLE TESTS ABGESCHLOSSEN
echo ============================================================
pause
