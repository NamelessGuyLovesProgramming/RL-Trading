@echo off
chcp 65001 >nul
echo ================================================
echo   RL Trading - Test Runner & Project Starter
echo ================================================
echo.

REM **********************************************************
REM  Schritt 1: Server Cleanup (Claude-Preferences Standard)
REM **********************************************************
echo [1/4] 🧹 Server Cleanup - Alte Prozesse beenden...
echo.

REM Kill alle Python-Prozesse die chart_server verwenden
echo Beende Chart Server Prozesse...
wmic process where "CommandLine like '%%chart_server%%'" delete >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Chart Server Prozesse beendet
) else (
    echo ℹ️  Keine Chart Server Prozesse gefunden
)

REM Kill alle Python-Prozesse die streamlit verwenden
echo Beende Streamlit Prozesse...
wmic process where "CommandLine like '%%streamlit%%'" delete >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Streamlit Prozesse beendet
) else (
    echo ℹ️  Keine Streamlit Prozesse gefunden
)

REM Zusätzliche Python-Prozesse auf Port 8003 und 8504 suchen
echo Prüfe Prozesse auf Ports 8003 und 8504...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8003"') do (
    if not "%%p"=="0" (
        taskkill /PID %%p /F >nul 2>&1
        echo ✅ Prozess auf Port 8003 beendet (PID: %%p)
    )
)

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8504"') do (
    if not "%%p"=="0" (
        taskkill /PID %%p /F >nul 2>&1
        echo ✅ Prozess auf Port 8504 beendet (PID: %%p)
    )
)

echo.
echo ✅ Server Cleanup abgeschlossen
echo.
timeout /t 2 >nul

REM **********************************************************
REM  Schritt 2: Python Environment Setup
REM **********************************************************
echo [2/4] 🐍 Python Environment Setup...
echo.

REM PYTHONPATH setzen (Claude-Preferences Standard)
set PYTHONPATH=%cd%\src
echo PYTHONPATH gesetzt: %PYTHONPATH%

REM Python Installation prüfen
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python ist nicht installiert oder nicht im PATH verfügbar
    echo Bitte Python installieren und zu PATH hinzufügen
    pause
    exit /b 1
)

REM pytest Installation prüfen
python -m pytest --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  pytest nicht gefunden - installiere pytest...
    pip install pytest
    if %errorlevel% neq 0 (
        echo ❌ pytest Installation fehlgeschlagen
        pause
        exit /b 1
    )
)

echo ✅ Python Environment bereit
echo.

REM **********************************************************
REM  Schritt 3: Unit Tests ausführen (Claude-Preferences Standard)
REM **********************************************************
echo [3/4] 🧪 Unit Tests ausführen...
echo.

REM Test-Ordner prüfen
if not exist "src\tests\" (
    echo ❌ Test-Ordner 'src\tests\' nicht gefunden
    echo Tests werden übersprungen
    goto :skip_tests
)

REM Anzahl Test-Dateien ermitteln
set test_count=0
for %%f in (src\tests\test_*.py) do set /a test_count+=1

if %test_count% equ 0 (
    echo ⚠️  Keine Test-Dateien gefunden in src\tests\
    echo Tests werden übersprungen
    goto :skip_tests
)

echo Gefundene Test-Dateien: %test_count%
echo.

REM Alle Tests ausführen mit ausführlichem Output
echo 🔍 Führe alle Unit Tests aus...
echo ================================================
python -m pytest src\tests\ -v --tb=short --no-header
set test_result=%errorlevel%

echo ================================================
echo.

if %test_result% equ 0 (
    echo ✅ Alle Tests erfolgreich bestanden!
    echo.
) else (
    echo ❌ Einige Tests sind fehlgeschlagen!
    echo.
    echo Möchten Sie trotzdem fortfahren? (j/N)
    set /p continue_choice="Eingabe: "
    if /i not "%continue_choice%"=="j" (
        echo Abbruch durch Benutzer - Behebe erst die Test-Fehler
        pause
        exit /b %test_result%
    )
    echo Fortfahren trotz Test-Fehlern...
    echo.
)

goto :after_tests

:skip_tests
echo ⚠️  Tests übersprungen
echo.

:after_tests

REM **********************************************************
REM  Schritt 4: Projekt starten (Claude-Preferences Standard)
REM **********************************************************
echo [4/4] 🚀 Projekt starten...
echo.

REM Port 8003 Verfügbarkeit prüfen
netstat -an | findstr ":8003" >nul
if %errorlevel% equ 0 (
    echo ⚠️  Port 8003 ist bereits belegt - versuche trotzdem zu starten
)

echo Chart Server wird gestartet...
echo URL: http://localhost:8003
echo.

REM Chart Server im Hintergrund starten
echo Starting Chart Server mit NQ=F Standard-Asset...
start /min "RL-Trading Chart Server" cmd /c "python charts\chart_server.py"

echo.
echo ⏳ Warte 3 Sekunden auf Server-Start...
timeout /t 3 >nul

REM Server-Status prüfen
netstat -an | findstr ":8003" >nul
if %errorlevel% equ 0 (
    echo ✅ Chart Server erfolgreich gestartet!
    echo.
    echo 🌐 Öffne Browser mit http://localhost:8003
    start http://localhost:8003
    echo.
    echo ================================================
    echo   RL Trading Projekt erfolgreich gestartet!
    echo ================================================
    echo.
    echo 📊 Chart Server: http://localhost:8003
    echo 🎯 Features: NQ=F Trading, Timeframes, Go To Date
    echo 🔧 Adaptive Timeout System aktiv
    echo 🛡️  Race Condition Fixes implementiert
    echo.
    echo Zum Beenden: Fenster schließen oder Strg+C
    echo.
) else (
    echo ❌ Chart Server konnte nicht gestartet werden!
    echo.
    echo Mögliche Ursachen:
    echo - Port 8003 bereits belegt
    echo - Python-Abhängigkeiten fehlen
    echo - chart_server.py nicht gefunden
    echo.
    echo Prüfe die Konsole für Fehlermeldungen...
)

REM **********************************************************
REM  Monitoring und Cleanup Optionen
REM **********************************************************
echo.
echo 🔧 Verfügbare Optionen:
echo   [1] Browser neu öffnen
echo   [2] Server-Status prüfen
echo   [3] Server neu starten
echo   [4] Alle Prozesse beenden
echo   [5] Tests erneut ausführen
echo   [Q] Beenden
echo.

:menu
set /p choice="Wähle eine Option (1-5/Q): "

if /i "%choice%"=="1" (
    start http://localhost:8003
    goto :menu
)

if /i "%choice%"=="2" (
    echo.
    echo 📊 Server-Status:
    netstat -an | findstr ":8003"
    if %errorlevel% equ 0 (
        echo ✅ Server läuft auf Port 8003
    ) else (
        echo ❌ Kein Server auf Port 8003 gefunden
    )
    echo.
    goto :menu
)

if /i "%choice%"=="3" (
    echo.
    echo 🔄 Server neu starten...
    wmic process where "CommandLine like '%%chart_server%%'" delete >nul 2>&1
    timeout /t 2 >nul
    start /min "RL-Trading Chart Server" cmd /c "python charts\chart_server.py"
    timeout /t 3 >nul
    echo ✅ Server neu gestartet
    start http://localhost:8003
    echo.
    goto :menu
)

if /i "%choice%"=="4" (
    echo.
    echo 🛑 Beende alle Prozesse...
    wmic process where "CommandLine like '%%chart_server%%'" delete >nul 2>&1
    wmic process where "CommandLine like '%%streamlit%%'" delete >nul 2>&1
    echo ✅ Alle Prozesse beendet
    echo.
    goto :end
)

if /i "%choice%"=="5" (
    echo.
    echo 🧪 Führe Tests erneut aus...
    python -m pytest src\tests\ -v --tb=short --no-header
    echo.
    goto :menu
)

if /i "%choice%"=="q" (
    goto :end
)

echo ⚠️  Ungültige Eingabe. Versuche erneut.
goto :menu

:end
echo.
echo 👋 RL Trading Session beendet
echo.
pause