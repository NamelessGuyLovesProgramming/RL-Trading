@echo off
REM ============================================================
REM RL-Trading Test Suite - Konsolidierter Test Runner
REM ============================================================

if "%1"=="" goto menu

REM Parameter-basierte Ausführung
if "%1"=="all" goto run_all
if "%1"=="unit" goto run_unit
if "%1"=="integration" goto run_integration
if "%1"=="core" goto run_core
if "%1"=="repositories" goto run_repositories
if "%1"=="coverage" goto run_coverage
goto invalid_param

:menu
cls
echo ============================================================
echo       RL-TRADING TEST SUITE - INTERACTIVE MENU
echo ============================================================
echo.
echo [1] Alle Tests                    (pytest tests/ -v)
echo [2] Unit Tests                    (pytest tests/unit/ -v)
echo [3] Integration Tests             (pytest tests/integration/ -v)
echo [4] Core Tests (Phase 3)          (pytest tests/unit/test_core/ -v)
echo [5] Repository Tests (Phase 2)    (pytest tests/unit/test_repositories/ -v)
echo [6] Coverage Report               (pytest --cov=charts --cov-report=html)
echo [7] Template Modularization       (pytest tests/integration/test_template_modularization.py -v)
echo.
echo [0] Exit
echo ============================================================
echo.
set /p choice=Wähle Option [0-7]:

if "%choice%"=="0" exit /b 0
if "%choice%"=="1" goto run_all
if "%choice%"=="2" goto run_unit
if "%choice%"=="3" goto run_integration
if "%choice%"=="4" goto run_core
if "%choice%"=="5" goto run_repositories
if "%choice%"=="6" goto run_coverage
if "%choice%"=="7" goto run_template
goto invalid_choice

:run_all
echo.
echo [RUN] Alle Tests...
echo ============================================================
py -m pytest tests/ -v --tb=short
goto end

:run_unit
echo.
echo [RUN] Unit Tests...
echo ============================================================
py -m pytest tests/unit/ -v --tb=short
goto end

:run_integration
echo.
echo [RUN] Integration Tests...
echo ============================================================
py -m pytest tests/integration/ -v --tb=short
goto end

:run_core
echo.
echo [RUN] Core Tests (Phase 3)...
echo ============================================================
py -m pytest tests/unit/test_core/ -v --tb=short
goto end

:run_repositories
echo.
echo [RUN] Repository Tests (Phase 2)...
echo ============================================================
py -m pytest tests/unit/test_repositories/ -v --tb=short
goto end

:run_coverage
echo.
echo [RUN] Coverage Report (wird in Browser geöffnet)...
echo ============================================================
py -m pytest tests/ -v --cov=charts --cov-report=html
if exist htmlcov\index.html (
    echo.
    echo [INFO] Coverage Report wurde erstellt!
    echo [INFO] Öffne htmlcov\index.html...
    start htmlcov\index.html
)
goto end

:run_template
echo.
echo [RUN] Template Modularization Tests...
echo ============================================================
py -m pytest tests/integration/test_template_modularization.py -v --tb=short
goto end

:invalid_param
echo [ERROR] Ungültiger Parameter: %1
echo.
echo Verwendung:
echo   run_tests.bat [option]
echo.
echo Optionen:
echo   all           - Alle Tests
echo   unit          - Unit Tests
echo   integration   - Integration Tests
echo   core          - Core Tests (Phase 3)
echo   repositories  - Repository Tests (Phase 2)
echo   coverage      - Coverage Report
echo.
echo Ohne Parameter: Interaktives Menü
exit /b 1

:invalid_choice
echo [ERROR] Ungültige Auswahl!
timeout /t 2 >nul
goto menu

:end
echo.
echo ============================================================
echo [DONE] Tests abgeschlossen!
echo ============================================================
if "%1"=="" (
    echo.
    pause
)
exit /b 0
