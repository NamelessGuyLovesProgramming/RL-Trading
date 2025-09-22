"""
Patch für chart_server.py - Timeframe Endpoint Fix
"""

def get_new_change_timeframe_endpoint():
    return '''
@app.post("/api/chart/change_timeframe")
async def change_timeframe(request: dict):
    """Ändert den Timeframe und gibt aggregierte Daten zurück - DIREKT AUS CSV"""
    timeframe = request.get('timeframe', '5m')
    visible_candles = request.get('visible_candles', 200)  # Default 200

    print(f"Timeframe-Wechsel zu: {timeframe} mit {visible_candles} sichtbaren Kerzen")

    try:
        import pandas as pd
        from pathlib import Path

        # Direkter CSV-Load (Option 2 Struktur)
        csv_path = Path(f"src/data/aggregated/{timeframe}/nq-2024.csv")

        if not csv_path.exists():
            return {"status": "error", "message": f"CSV-Datei für {timeframe} nicht gefunden: {csv_path}"}

        # CSV laden
        df = pd.read_csv(csv_path)

        # Neueste N Kerzen nehmen
        if len(df) > visible_candles:
            result_df = df.tail(visible_candles)
        else:
            result_df = df

        # In API-Format konvertieren
        aggregated_data = []
        for _, row in result_df.iterrows():
            aggregated_data.append({
                'time': int(row['time']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume'])
            })

        print(f"CSV geladen: {len(aggregated_data)} {timeframe} Kerzen")

        # Update Chart State
        manager.chart_state['data'] = aggregated_data
        manager.chart_state['interval'] = timeframe
        manager.chart_state['last_update'] = datetime.now().isoformat()

        # Broadcast an alle Clients
        await manager.broadcast({
            'type': 'timeframe_changed',
            'timeframe': timeframe,
            'data': aggregated_data,
            'count': len(aggregated_data)
        })

        print(f"Timeframe geändert zu {timeframe} - {len(aggregated_data)} Kerzen")

        return {
            "status": "success",
            "data": aggregated_data,
            "count": len(aggregated_data),
            "timeframe": timeframe,
            "message": f"Timeframe zu {timeframe} gewechselt"
        }

    except Exception as e:
        print(f"Fehler beim Timeframe-Wechsel: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Fehler beim Laden der {timeframe} Daten: {str(e)}"
        }
'''

if __name__ == "__main__":
    print("Diese Datei enthält den Fix für den change_timeframe Endpunkt")
    print("Der neue Endpunkt lädt DIREKT aus CSV statt über PerformanceAggregator")