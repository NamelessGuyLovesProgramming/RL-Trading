#!/usr/bin/env python3
"""
Debug Script für Smart Chart Positioning
Testet die Mathematik und identifiziert Fehler
"""

def test_smart_positioning_math():
    """Test der Smart Positioning Mathematik"""
    print("=== SMART POSITIONING DEBUG TESTS ===")
    print()

    # Simuliere 50 Kerzen mit 5m Intervall
    candles = []
    base_time = 1700000000  # Unix timestamp
    interval_minutes = 5
    interval_seconds = interval_minutes * 60

    for i in range(50):
        timestamp = base_time + (i * interval_seconds)
        candles.append({
            'time': timestamp,
            'open': 100 + i,
            'high': 105 + i,
            'low': 95 + i,
            'close': 102 + i
        })

    print(f"INFO: Test-Daten: {len(candles)} Kerzen")
    print(f"INFO: Erste Kerze Zeit: {candles[0]['time']}")
    print(f"INFO: Letzte Kerze Zeit: {candles[-1]['time']}")
    print()

    # Teste die Smart Positioning Logik
    def test_positioning_logic(data, visible_candles=50):
        """Testet die aktuelle Smart Positioning Logik"""
        print(f"TEST: TEST: Smart Positioning für {visible_candles} Kerzen")

        data_length = len(data)
        vis_candles = min(visible_candles, data_length)

        # Berechne Zeitbereich für sichtbare Kerzen (letzte N Kerzen)
        start_index = max(0, data_length - vis_candles)
        end_index = data_length - 1

        start_time = data[start_index]['time']
        end_time = data[end_index]['time']

        print(f"   Sichtbare Kerzen: {vis_candles} (Index {start_index}-{end_index})")
        print(f"   Start-Zeit: {start_time}")
        print(f"   End-Zeit: {end_time}")

        # AKTUELLE LOGIK (aus chart_server.py)
        data_time_span = end_time - start_time
        total_chart_time_span = data_time_span / 0.8  # Daten = 80% der Chart
        right_margin_time = total_chart_time_span * 0.2  # 20% Freiraum rechts

        chart_start_time = start_time  # Chart beginnt bei ersten Daten
        chart_end_time = end_time + right_margin_time  # Chart endet mit Freiraum

        print(f"   Daten-Zeitspanne: {data_time_span} sekunden")
        print(f"   Gesamt-Chart-Zeitspanne: {total_chart_time_span} sekunden")
        print(f"   Rechter Freiraum: {right_margin_time} sekunden")
        print(f"   Chart-Bereich: {chart_start_time} bis {chart_end_time}")

        # Berechne Verhältnisse
        total_chart_span = chart_end_time - chart_start_time
        data_percentage = (data_time_span / total_chart_span) * 100
        margin_percentage = (right_margin_time / total_chart_span) * 100

        print(f"   CALC: Daten nehmen {data_percentage:.1f}% der Chart ein")
        print(f"   CALC: Freiraum nimmt {margin_percentage:.1f}% der Chart ein")

        # Prüfe ob das korrekt ist
        if abs(data_percentage - 80.0) < 1.0 and abs(margin_percentage - 20.0) < 1.0:
            print("   OK: Mathematik ist KORREKT")
        else:
            print("   FEHLER: Mathematik ist FALSCH")

        return {
            'chart_start': chart_start_time,
            'chart_end': chart_end_time,
            'data_start': start_time,
            'data_end': end_time,
            'data_percentage': data_percentage,
            'margin_percentage': margin_percentage
        }

    # Test mit 50 Kerzen
    result = test_positioning_logic(candles, 50)
    print()

    # Test mit weniger Kerzen
    print("TEST: TEST: Smart Positioning für 20 Kerzen")
    result_small = test_positioning_logic(candles[:20], 50)  # Nur 20 Kerzen verfügbar
    print()

    # Test der TradingView setVisibleRange Simulation
    print("TEST: TEST: TradingView setVisibleRange Simulation")
    print("   Was passiert wenn setVisibleRange() aufgerufen wird:")
    print(f"   setVisibleRange(from: {result['chart_start']}, to: {result['chart_end']})")

    # Simuliere was der Chart zeigen sollte
    chart_time_span = result['chart_end'] - result['chart_start']
    data_time_span = result['data_end'] - result['data_start']

    print(f"   Chart zeigt Zeitbereich von {chart_time_span} sekunden")
    print(f"   Davon sind {data_time_span} sekunden Daten ({(data_time_span/chart_time_span)*100:.1f}%)")
    print(f"   Und {chart_time_span - data_time_span} sekunden Freiraum ({((chart_time_span - data_time_span)/chart_time_span)*100:.1f}%)")

    # Identifiziere mögliche Probleme
    print()
    print("DEBUG: MÖGLICHE PROBLEME:")

    if result['data_percentage'] != 80.0:
        print(f"   FEHLER: Daten-Anteil ist {result['data_percentage']:.1f}%, nicht 80%")

    if result['margin_percentage'] != 20.0:
        print(f"   FEHLER: Freiraum-Anteil ist {result['margin_percentage']:.1f}%, nicht 20%")

    # Check ob Smart Positioning überhaupt aufgerufen wird
    print()
    print("DEBUG: DEBUGGING CHECKLIST:")
    print("   1. Wird SmartChartPositioning korrekt initialisiert?")
    print("   2. Wird setStandardPosition() aufgerufen?")
    print("   3. Funktioniert chart.timeScale().setVisibleRange()?")
    print("   4. Überschreibt ein anderer Code die Positionierung?")

    return result


def test_alternative_approach():
    """Teste alternative Ansätze für die Positionierung"""
    print()
    print("=== ALTERNATIVE ANSÄTZE ===")

    # Alternative 1: Direkte Kerzen-basierte Berechnung
    print("ALT: Alternative 1: Kerzen-basierte Berechnung")

    # 50 Kerzen sollen 80% einnehmen
    # Das bedeutet: Gesamt-Chart = 50 / 0.8 = 62.5 Kerzen-Breiten
    # Freiraum = 62.5 - 50 = 12.5 Kerzen-Breiten

    visible_candles = 50
    total_chart_candles = visible_candles / 0.8  # 62.5
    margin_candles = total_chart_candles - visible_candles  # 12.5

    print(f"   Sichtbare Kerzen: {visible_candles}")
    print(f"   Gesamt-Chart (Kerzen): {total_chart_candles}")
    print(f"   Freiraum (Kerzen): {margin_candles}")

    # Simuliere 5-Minuten Kerzen
    candle_interval = 5 * 60  # 5 Minuten in Sekunden
    margin_time = margin_candles * candle_interval

    print(f"   Freiraum (Zeit): {margin_time} sekunden = {margin_time/60:.1f} minuten")

    # Alternative 2: Fixed Margin
    print()
    print("ALT: Alternative 2: Fixed Margin (einfacher)")
    fixed_margin_candles = 10  # Feste 10 Kerzen Freiraum
    fixed_margin_time = fixed_margin_candles * candle_interval

    print(f"   Fester Freiraum: {fixed_margin_candles} Kerzen = {fixed_margin_time} sekunden")
    print(f"   Das sind {(fixed_margin_candles / (visible_candles + fixed_margin_candles)) * 100:.1f}% der Chart")


if __name__ == "__main__":
    # Führe alle Tests aus
    try:
        result = test_smart_positioning_math()
        test_alternative_approach()

        print()
        print("=== ZUSAMMENFASSUNG ===")
        print("OK: Debug-Tests abgeschlossen")
        print("INFO: Mathematik-Validierung durchgeführt")
        print("DEBUG: Mögliche Fehlerquellen identifiziert")

    except Exception as e:
        print(f"FEHLER: Debug-Test Fehler: {e}")
        import traceback
        traceback.print_exc()