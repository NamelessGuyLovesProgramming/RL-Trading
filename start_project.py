#!/usr/bin/env python3
"""
RL Trading - Project Startup Script
Zentrale Stelle zum Starten des Projekts nach .claude-preferences.md Standards
"""

import subprocess
import sys
import webbrowser
import time
import os
from pathlib import Path

def kill_existing_processes():
    """Beendet alle laufenden Chart-Server Prozesse für sauberen Neustart"""
    try:
        # Windows: Alle Python Chart-Server Prozesse beenden
        subprocess.run(['taskkill', '/F', '/IM', 'python.exe'],
                      capture_output=True, text=True)
        print("Alte Chart-Server Prozesse beendet")
        time.sleep(1)
    except Exception as e:
        print(f"⚠️  Warnung beim Beenden alter Prozesse: {e}")

def start_chart_server():
    """Startet den Haupt-Chart-Server mit Short Position Tool"""
    chart_path = Path("charts/chart_server.py")
    if not chart_path.exists():
        print(f"❌ Chart-Server nicht gefunden: {chart_path}")
        return False

    print("🚀 Starte Chart-Server mit Short Position Tool...")

    # Setze PYTHONPATH für korrekte Module-Importe
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path.cwd() / "src")

    # Chart-Server im Hintergrund starten
    process = subprocess.Popen([sys.executable, str(chart_path)],
                             cwd=Path.cwd(), env=env)

    # Kurz warten bis Server läuft
    time.sleep(3)

    # Browser öffnen
    webbrowser.open('http://localhost:8003')

    print("✅ Chart-Server läuft auf http://localhost:8003")
    print("📈 Long Position Tool verfügbar")
    print("📉 Short Position Tool verfügbar")

    return True

def start_streamlit_app():
    """Startet optional die vollständige Streamlit App"""
    print("\n🤖 Möchtest du auch die vollständige Streamlit App starten? (y/n): ", end="")
    choice = input().lower().strip()

    if choice in ['y', 'yes', 'ja', 'j']:
        print("🚀 Starte Streamlit App...")

        # Setze PYTHONPATH und starte Streamlit
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{Path.cwd()}/src"

        subprocess.Popen([
            sys.executable, '-m', 'streamlit', 'run',
            'src/app.py', '--server.port', '8504',
            '--server.headless', 'true'
        ], env=env)

        time.sleep(2)
        print("✅ Streamlit App läuft auf http://localhost:8504")

def main():
    """Hauptfunktion - Projektstart nach .claude-preferences.md Standards"""
    print("RL Trading - Projekt Start")
    print("=" * 50)

    # Schritt 1: Alte Prozesse beenden
    kill_existing_processes()

    # Schritt 2: Chart-Server starten (Hauptfenster)
    if not start_chart_server():
        print("❌ Fehler beim Starten des Chart-Servers")
        return 1

    # Schritt 3: Optional Streamlit App
    start_streamlit_app()

    print("\n🎉 Projekt erfolgreich gestartet!")
    print("\n📋 Verfügbare Services:")
    print("   📊 Chart-Only (Hauptfenster): http://localhost:8003")
    print("   🖥️  Vollständige App:        http://localhost:8504 (falls gestartet)")

    print("\n⌨️  Drücke Ctrl+C zum Beenden")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Projekt beendet!")
        return 0

if __name__ == "__main__":
    sys.exit(main())