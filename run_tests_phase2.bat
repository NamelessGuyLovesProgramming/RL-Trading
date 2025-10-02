@echo off
echo ============================================================
echo PHASE 2 TESTS - Repositories Layer
echo ============================================================
echo.

echo [1/2] Running pytest for Repository Unit Tests...
py -m pytest tests/unit/test_repositories/ -v --tb=short

echo.
echo [2/2] Running Phase 2 Validation Script...
py test_phase2_repositories.py 2>nul

echo.
echo ============================================================
echo PHASE 2 TESTS ABGESCHLOSSEN
echo ============================================================
pause
