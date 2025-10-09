"""
Feature Tests für main_v2.py Server
Testet Timeframe-Switch, Go To Date und Skip-Funktionalität
"""

import sys
import os
import io
import requests
import json
from datetime import datetime
import time

# Windows UTF-8 encoding fix
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8003"

def get_chart_status():
    """Holt aktuellen Chart-Status"""
    response = requests.get(f"{BASE_URL}/api/chart/status")
    return response.json()

def get_chart_data():
    """Holt Chart-Daten"""
    response = requests.get(f"{BASE_URL}/api/chart/data")
    return response.json()

def change_timeframe(timeframe):
    """Wechselt Timeframe"""
    response = requests.post(
        f"{BASE_URL}/api/chart/change_timeframe",
        json={"timeframe": timeframe, "visible_candles": 200}
    )
    time.sleep(0.5)  # Kurz warten für Processing
    return response.json()

def go_to_date(date_str):
    """Springt zu einem Datum"""
    response = requests.post(
        f"{BASE_URL}/api/debug/go_to_date",
        json={"date": date_str}
    )
    time.sleep(0.5)
    return response.json()

def skip_forward():
    """Führt Skip aus"""
    response = requests.post(f"{BASE_URL}/api/debug/skip")
    time.sleep(0.5)
    return response.json()


def test_timeframe_consistency():
    """
    Test 1: Timeframe-Switch Konsistenz
    Prüft ob alle Timeframes die gleiche/ähnliche Endzeit haben
    """
    print("\n" + "="*70)
    print("TEST 1: Timeframe-Switch Konsistenz")
    print("="*70)

    timeframes = ['1m', '5m', '15m', '1h']  # Reduziert für schnellere Tests
    results = {}

    # Starte mit 5m
    print("\n[INIT] Starte mit 5m Timeframe...")
    change_timeframe('5m')
    time.sleep(1)

    for tf in timeframes:
        print(f"\n--- Teste Timeframe: {tf} ---")

        # Switch zu TF
        switch_result = change_timeframe(tf)
        if switch_result.get('status') != 'success':
            print(f"❌ FEHLER: Timeframe-Switch fehlgeschlagen")
            results[tf] = {'status': 'failed', 'error': 'switch_failed'}
            continue

        # Hole Chart-Daten
        data = get_chart_data()
        candles = data.get('data', [])

        if not candles:
            print(f"❌ FEHLER: Keine Kerzen geladen")
            results[tf] = {'status': 'failed', 'error': 'no_candles'}
            continue

        count = len(candles)
        last_candle = candles[-1]
        last_time = datetime.fromtimestamp(last_candle['time'])

        print(f"✅ Anzahl: {count} Kerzen")
        print(f"✅ Letzte Kerze: {last_time.strftime('%Y-%m-%d %H:%M')} (Close: {last_candle['close']})")

        results[tf] = {
            'status': 'success',
            'count': count,
            'last_time': last_time,
            'last_timestamp': last_candle['time'],
            'last_close': last_candle['close']
        }

    # Validierung: Alle sollten ähnliche Endzeit haben
    print("\n" + "="*70)
    print("VALIDIERUNG: Endzeit-Konsistenz")
    print("="*70)

    # Sammle alle letzten Timestamps
    timestamps = {tf: r['last_timestamp'] for tf, r in results.items() if r['status'] == 'success'}

    if not timestamps:
        print("❌ FEHLER: Keine erfolgreichen Timeframe-Switches")
        return False

    # Referenz: 5m Timestamp
    ref_timestamp = timestamps.get('5m')
    if not ref_timestamp:
        print("❌ FEHLER: 5m Timeframe fehlt als Referenz")
        return False

    print(f"\n🔹 Referenz (5m): {datetime.fromtimestamp(ref_timestamp).strftime('%Y-%m-%d %H:%M')}")

    all_consistent = True
    max_diff_minutes = 60  # Max 60 Minuten Unterschied erlaubt

    for tf, ts in timestamps.items():
        if tf == '5m':
            continue

        diff_seconds = abs(ts - ref_timestamp)
        diff_minutes = diff_seconds / 60

        time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')

        if diff_minutes <= max_diff_minutes:
            print(f"✅ {tf}: {time_str} (Diff: {diff_minutes:.1f} min)")
        else:
            print(f"❌ {tf}: {time_str} (Diff: {diff_minutes:.1f} min) - ZU GROSS!")
            all_consistent = False

    if all_consistent:
        print("\n✅ TEST 1 ERFOLGREICH: Alle Timeframes haben konsistente Endzeiten")
        return True
    else:
        print("\n❌ TEST 1 FEHLGESCHLAGEN: Endzeiten inkonsistent")
        return False


def test_go_to_date():
    """
    Test 2: Go To Date
    Springt zu 17.12.2024, dann zu 13.12.2024
    """
    print("\n" + "="*70)
    print("TEST 2: Go To Date")
    print("="*70)

    dates = ["2024-12-17", "2024-12-13"]

    for target_date in dates:
        print(f"\n--- Go To Date: {target_date} ---")

        # Go To Date
        result = go_to_date(target_date)

        if result.get('status') != 'success':
            print(f"❌ FEHLER: Go To Date fehlgeschlagen")
            print(f"   Error: {result.get('message', 'Unknown')}")
            return False

        # Prüfe Chart-Daten
        data = get_chart_data()
        candles = data.get('data', [])

        if not candles:
            print(f"❌ FEHLER: Keine Kerzen nach Go To Date")
            return False

        count = len(candles)
        last_candle = candles[-1]
        last_time = datetime.fromtimestamp(last_candle['time'])

        print(f"✅ Anzahl: {count} Kerzen")
        print(f"✅ Letzte Kerze: {last_time.strftime('%Y-%m-%d %H:%M')} (Close: {last_candle['close']})")

        # Prüfe ob Datum in der Nähe ist
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        if last_time.date() != target_dt.date():
            # Toleranz: +/- 1 Tag
            diff_days = abs((last_time.date() - target_dt.date()).days)
            if diff_days <= 1:
                print(f"⚠️  Datum weicht ab: {diff_days} Tag(e) Unterschied (toleriert)")
            else:
                print(f"❌ FEHLER: Datum zu weit entfernt: {last_time.date()} vs {target_dt.date()}")
                return False

    print("\n✅ TEST 2 ERFOLGREICH: Go To Date funktioniert korrekt")
    return True


def test_skip_forward():
    """
    Test 3: Skip Test
    Skip +5min im 5m Timeframe
    """
    print("\n" + "="*70)
    print("TEST 3: Skip Forward (+5min)")
    print("="*70)

    # Wechsle zu 5m
    print("\n[INIT] Wechsle zu 5m Timeframe...")
    change_timeframe('5m')
    time.sleep(1)

    # Hole initiale Daten
    data_before = get_chart_data()
    candles_before = data_before.get('data', [])

    if not candles_before:
        print("❌ FEHLER: Keine Kerzen vor Skip")
        return False

    count_before = len(candles_before)
    last_candle_before = candles_before[-1]
    last_time_before = datetime.fromtimestamp(last_candle_before['time'])

    print(f"📊 VOR SKIP:")
    print(f"   Anzahl: {count_before} Kerzen")
    print(f"   Letzte Kerze: {last_time_before.strftime('%Y-%m-%d %H:%M')} (Close: {last_candle_before['close']})")

    # Führe Skip aus
    print("\n⏭️  Führe Skip +5min aus...")
    skip_result = skip_forward()

    if skip_result.get('status') != 'success':
        print(f"❌ FEHLER: Skip fehlgeschlagen")
        print(f"   Error: {skip_result.get('message', 'Unknown')}")
        return False

    # Hole neue Daten
    data_after = get_chart_data()
    candles_after = data_after.get('data', [])

    if not candles_after:
        print("❌ FEHLER: Keine Kerzen nach Skip")
        return False

    count_after = len(candles_after)
    last_candle_after = candles_after[-1]
    last_time_after = datetime.fromtimestamp(last_candle_after['time'])

    print(f"\n📊 NACH SKIP:")
    print(f"   Anzahl: {count_after} Kerzen")
    print(f"   Letzte Kerze: {last_time_after.strftime('%Y-%m-%d %H:%M')} (Close: {last_candle_after['close']})")

    # Validierung
    count_increased = count_after > count_before
    time_increased = last_time_after > last_time_before
    time_diff_minutes = (last_time_after - last_time_before).total_seconds() / 60

    print(f"\n🔍 VALIDIERUNG:")
    print(f"   Kerzenanzahl erhöht: {count_before} -> {count_after} {'✅' if count_increased else '❌'}")
    print(f"   Zeit vorgerückt: {time_diff_minutes:.0f} Minuten {'✅' if time_increased else '❌'}")

    if not (count_increased and time_increased):
        print(f"\n❌ FEHLER: Skip hat keine neue Kerze erstellt")
        return False

    print("\n✅ TEST 3 ERFOLGREICH: Skip funktioniert korrekt")
    return True


def run_all_feature_tests():
    """Führt alle Feature-Tests aus"""
    print("\n" + "="*70)
    print("🧪 FEATURE TESTS für main_v2.py Server")
    print("="*70)

    # Check Server
    try:
        response = requests.get(f"{BASE_URL}/api/chart/status", timeout=5)
        if response.status_code != 200:
            print("❌ FEHLER: Server nicht erreichbar oder nicht bereit")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ FEHLER: Server nicht erreichbar: {e}")
        print(f"   Stelle sicher dass main_v2.py auf {BASE_URL} läuft")
        return False

    print(f"✅ Server erreichbar: {BASE_URL}")

    tests = [
        ("Timeframe-Switch Konsistenz", test_timeframe_consistency),
        ("Go To Date", test_go_to_date),
        ("Skip Forward", test_skip_forward),
        ("Final Timeframe-Switch Konsistenz", test_timeframe_consistency),  # Finale Konsistenzprüfung
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
        if not result:
            all_passed = False

    print("="*70)

    if all_passed:
        print("✅ ALLE FEATURE-TESTS ERFOLGREICH!")
        print("="*70)
        return True
    else:
        print("❌ EINIGE TESTS FEHLGESCHLAGEN!")
        print("="*70)
        return False


if __name__ == "__main__":
    success = run_all_feature_tests()
    sys.exit(0 if success else 1)
