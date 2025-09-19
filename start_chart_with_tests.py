#!/usr/bin/env python3
"""
Chart Server Startup Script with Pre-Start Tests
Führt umfassende Tests aus bevor der Server gestartet wird
"""

import subprocess
import sys
import time
import os
from threading import Thread
import signal

def run_pre_start_tests():
    """Führe Tests vor Server-Start aus"""
    print("🔧 Führe Pre-Start Tests aus...")
    print("=" * 50)

    # Test 1: NQ Data Files
    print("📁 Teste NQ Data Files...")
    data_path = "src/data/nq-1m"
    if not os.path.exists(data_path):
        print(f"❌ FEHLER: {data_path} existiert nicht!")
        return False

    csv_files = [f for f in os.listdir(data_path) if f.endswith('.csv') and 'nq-1m' in f]
    if not csv_files:
        print(f"❌ FEHLER: Keine NQ CSV-Dateien in {data_path}!")
        return False

    print(f"✅ Gefunden: {len(csv_files)} NQ CSV-Dateien")

    # Test 2: NQDataLoader
    print("🔄 Teste NQDataLoader...")
    try:
        sys.path.insert(0, 'src/data')
        from nq_data_loader import NQDataLoader

        loader = NQDataLoader()
        info = loader.get_info()

        if not info['available_years']:
            print("❌ FEHLER: Keine verfügbaren Jahre!")
            return False

        print(f"✅ NQDataLoader bereit mit Jahren: {info['available_years']}")

        # Test sample data loading
        recent_data = loader.load_latest_days(1)
        if recent_data.empty:
            print("❌ FEHLER: Kann keine aktuellen Daten laden!")
            return False

        print(f"✅ Beispiel-Daten geladen: {len(recent_data)} Kerzen")

    except Exception as e:
        print(f"❌ FEHLER: NQDataLoader Test fehlgeschlagen: {e}")
        return False

    # Test 3: Chart Server Module Import
    print("📊 Teste Chart Server Module...")
    try:
        # Just test if we can import without errors
        import chart_server
        print("✅ Chart Server Module importiert")
    except Exception as e:
        print(f"❌ FEHLER: Chart Server Import fehlgeschlagen: {e}")
        return False

    print("\n🎉 Alle Pre-Start Tests erfolgreich!")
    return True

def start_server_background():
    """Starte Server im Hintergrund"""
    print("🚀 Starte Chart Server...")
    try:
        # Start chart server
        server_process = subprocess.Popen(
            [sys.executable, "chart_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return server_process
    except Exception as e:
        print(f"❌ FEHLER: Server-Start fehlgeschlagen: {e}")
        return None

def run_post_start_tests():
    """Führe Tests nach Server-Start aus"""
    print("\n🧪 Führe Post-Start Tests aus...")

    # Wait for server to be ready
    print("⏳ Warte auf Server-Bereitschaft...")
    time.sleep(5)

    try:
        # Run comprehensive tests
        result = subprocess.run(
            [sys.executable, "test_chart_data_loading.py"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print("✅ Post-Start Tests erfolgreich!")
            print("🌟 Chart Server ist bereit und funktionsfähig!")
            return True
        else:
            print("❌ Post-Start Tests fehlgeschlagen!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("❌ Post-Start Tests Timeout!")
        return False
    except Exception as e:
        print(f"❌ Post-Start Tests Fehler: {e}")
        return False

def main():
    """Main startup routine"""
    print("🎯 RL Trading Chart Server - Startup mit Tests")
    print("=" * 60)

    # Step 1: Pre-Start Tests
    if not run_pre_start_tests():
        print("\n💥 Pre-Start Tests fehlgeschlagen - Server wird nicht gestartet!")
        sys.exit(1)

    # Step 2: Start Server
    server_process = start_server_background()
    if not server_process:
        print("\n💥 Server-Start fehlgeschlagen!")
        sys.exit(1)

    try:
        # Step 3: Post-Start Tests
        tests_passed = run_post_start_tests()

        if tests_passed:
            print("\n🎉 ERFOLG: Server läuft und alle Tests bestanden!")
            print("🔗 Chart verfügbar unter: http://localhost:8001")
            print("🔧 Debug verfügbar unter: http://localhost:8001/debug")
            print("\n🔄 Server läuft weiter... (Ctrl+C zum Beenden)")

            # Keep server running
            try:
                server_process.wait()
            except KeyboardInterrupt:
                print("\n⏹️  Server wird beendet...")
                server_process.terminate()
                server_process.wait()
                print("✅ Server beendet")

        else:
            print("\n⚠️  WARNUNG: Tests fehlgeschlagen, aber Server läuft")
            print("🔧 Verwende Debug-Seite: http://localhost:8001/debug")
            print("📊 Chart-Seite: http://localhost:8001")

            # Keep server running despite test failures
            try:
                server_process.wait()
            except KeyboardInterrupt:
                print("\n⏹️  Server wird beendet...")
                server_process.terminate()
                server_process.wait()
                print("✅ Server beendet")

    except KeyboardInterrupt:
        print("\n⏹️  Beende Server...")
        server_process.terminate()
        server_process.wait()
        print("✅ Server beendet")

if __name__ == "__main__":
    main()