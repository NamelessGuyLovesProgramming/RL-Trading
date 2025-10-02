@echo off
echo ============================================================
echo TEST COVERAGE - Mit Coverage Report
echo ============================================================
echo.

py -m pytest tests/ -v --cov=charts --cov-report=html --cov-report=term

echo.
echo ============================================================
echo Coverage Report generiert: htmlcov/index.html
echo ============================================================
echo Oeffne Coverage Report im Browser...
start htmlcov/index.html

pause
