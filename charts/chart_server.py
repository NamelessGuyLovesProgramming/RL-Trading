"""
FastAPI Chart Server für RL Trading
Realtime Chart-Updates ohne Streamlit-Limitations
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
from typing import Dict, List, Any
import uvicorn
from datetime import datetime, timedelta
import random
import logging
import sys
import os

# Füge src Verzeichnis zum Pfad hinzu (ein Verzeichnis höher)
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.append(os.path.join(parent_dir, 'src'))

# FastAPI App (Importiere Module später um Startup-Deadlock zu vermeiden)
app = FastAPI(title="RL Trading Chart Server", version="1.0.0")

# Globale Variablen (werden nach Startup initialisiert)
nq_loader = None
performance_aggregator = None
account_service = None

# Lade initiale Chart-Daten aus CSV (schneller Startup)
print("Lade initiale 5m Chart-Daten aus CSV...")
initial_chart_data = []

try:
    import pandas as pd
    from pathlib import Path

    csv_path = Path("src/data/aggregated/5m/nq-2024.csv")
    if csv_path.exists():
        print(f"CSV gefunden: {csv_path}")

        # Direkt die letzten 200 Zeilen lesen (ohne komplexe Filter)
        df = pd.read_csv(csv_path).tail(200)
        print(f"CSV gelesen: {len(df)} Zeilen")

        # Konvertiere zu Chart-Format
        for _, row in df.iterrows():
            initial_chart_data.append({
                'time': int(row['time']),  # Unix Timestamp für TradingView
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume'])
            })
        print(f"ERFOLG: {len(initial_chart_data)} NQ-Kerzen geladen!")
    else:
        print(f"FEHLER: CSV nicht gefunden: {csv_path}")
except Exception as e:
    print(f"FEHLER beim CSV-Laden: {e}")
    import traceback
    traceback.print_exc()

# WebSocket Connection Manager
class ConnectionManager:
    """Verwaltet WebSocket-Verbindungen für Realtime-Updates"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.chart_state: Dict[str, Any] = {
            'data': initial_chart_data,  # Verwende echte NQ-Daten
            'symbol': 'NQ=F',
            'interval': '5m',  # 5-Minuten Standard
            'last_update': datetime.now().isoformat(),
            'positions': [],
            'raw_1m_data': None  # CSV-basiert, kein raw data needed
        }

    async def connect(self, websocket: WebSocket):
        """Neue WebSocket-Verbindung hinzufügen"""
        await websocket.accept()
        self.active_connections.append(websocket)

        # Sende aktuellen Chart-State an neuen Client
        await self.send_personal_message({
            'type': 'initial_data',
            'data': self.chart_state
        }, websocket)

    def disconnect(self, websocket: WebSocket):
        """WebSocket-Verbindung entfernen"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Nachricht an spezifischen Client senden"""
        try:
            # Erstelle eine serialisierbare Kopie der Daten ohne DataFrame
            if 'data' in message and isinstance(message['data'], dict):
                serializable_data = message['data'].copy()
                # Entferne nicht-serialisierbare DataFrame-Objekte
                if 'raw_1m_data' in serializable_data:
                    del serializable_data['raw_1m_data']
                message = message.copy()
                message['data'] = serializable_data

            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logging.error(f"Error sending message: {e}")

    async def broadcast(self, message: dict):
        """Nachricht an alle verbundenen Clients senden"""
        print(f"Broadcast: {len(self.active_connections)} aktive Verbindungen, Nachricht: {message.get('type', 'unknown')}")

        if not self.active_connections:
            print("WARNUNG: Keine aktiven WebSocket-Verbindungen für Broadcast!")
            return

        # Sende parallel an alle Clients
        tasks = []
        for connection in self.active_connections.copy():
            tasks.append(self.send_personal_message(message, connection))

        # Warte auf alle Sends (mit Error-Handling)
        await asyncio.gather(*tasks, return_exceptions=True)
        print(f"Broadcast abgeschlossen an {len(self.active_connections)} Clients")

    def update_chart_state(self, update_data: dict):
        """Chart-State aktualisieren"""
        if update_data.get('type') == 'set_data':
            self.chart_state['data'] = update_data.get('data', [])
            self.chart_state['symbol'] = update_data.get('symbol', 'NQ=F')
            self.chart_state['interval'] = update_data.get('interval', '5m')
        elif update_data.get('type') == 'add_candle':
            # Neue Kerze hinzufügen
            candle = update_data.get('candle')
            if candle:
                self.chart_state['data'].append(candle)
        elif update_data.get('type') == 'add_position':
            # Position Overlay hinzufügen
            if 'positions' not in self.chart_state:
                self.chart_state['positions'] = []
            position = update_data.get('position')
            if position:
                self.chart_state['positions'].append(position)
        elif update_data.get('type') == 'remove_position':
            # Position entfernen
            position_id = update_data.get('position_id')
            if position_id and 'positions' in self.chart_state:
                self.chart_state['positions'] = [
                    p for p in self.chart_state['positions']
                    if p.get('id') != position_id
                ]

        self.chart_state['last_update'] = datetime.now().isoformat()

# Timeframe Aggregator für intelligente Kerzen-Logik
class TimeframeAggregator:
    """Intelligente Kerzen-Logik für verschiedene Timeframes"""

    def __init__(self):
        # Timeframe-Definitionen in Minuten
        self.timeframes = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60
        }

        # Aktuelle unvollständige Kerzen pro Timeframe
        self.incomplete_candles = {}

        # Letzte vollständige Kerze für jeden Timeframe
        self.last_complete_candles = {}

    def add_minute_to_timeframe(self, current_time: datetime, timeframe: str, last_candle: dict) -> tuple:
        """
        Fügt eine Minute zu einem Timeframe hinzu und gibt zurück:
        - neue_kerze: dict mit neuer Kerze oder None
        - incomplete_data: dict mit unvollständiger Kerze oder None
        - is_complete: bool ob Kerze vollständig ist
        """
        tf_minutes = self.timeframes.get(timeframe, 1)
        new_time = current_time + timedelta(minutes=1)

        # Berechne Start-Zeit für aktuelle Timeframe-Periode
        if timeframe == '1m':
            period_start = new_time.replace(second=0, microsecond=0)
        elif timeframe == '5m':
            period_start = new_time.replace(minute=(new_time.minute // 5) * 5, second=0, microsecond=0)
        elif timeframe == '15m':
            period_start = new_time.replace(minute=(new_time.minute // 15) * 15, second=0, microsecond=0)
        elif timeframe == '30m':
            period_start = new_time.replace(minute=(new_time.minute // 30) * 30, second=0, microsecond=0)
        elif timeframe == '1h':
            period_start = new_time.replace(minute=0, second=0, microsecond=0)
        else:
            period_start = new_time.replace(second=0, microsecond=0)

        # Generiere Mock-Preis-Bewegung basierend auf letzter Kerze
        last_close = last_candle.get('close', 18500)
        price_change = random.uniform(-20, 20)  # ±20 Punkte Bewegung
        new_price = last_close + price_change

        # Prüfe ob wir eine neue Periode beginnen
        key = f"{timeframe}_{period_start.isoformat()}"

        if key not in self.incomplete_candles:
            # Neue Periode beginnt
            self.incomplete_candles[key] = {
                'time': int(period_start.timestamp()),
                'open': new_price,
                'high': new_price,
                'low': new_price,
                'close': new_price,
                'period_start': period_start,
                'minutes_elapsed': 1,
                'timeframe': timeframe,
                'is_complete': False
            }
        else:
            # Bestehende Periode fortsetzen
            candle = self.incomplete_candles[key]
            candle['high'] = max(candle['high'], new_price)
            candle['low'] = min(candle['low'], new_price)
            candle['close'] = new_price
            candle['minutes_elapsed'] += 1

        current_candle = self.incomplete_candles[key]

        # Prüfe ob Periode vollständig ist
        if current_candle['minutes_elapsed'] >= tf_minutes:
            # Kerze ist vollständig
            complete_candle = current_candle.copy()
            complete_candle['is_complete'] = True

            # Entferne aus incomplete und speichere als last_complete
            del self.incomplete_candles[key]
            self.last_complete_candles[timeframe] = complete_candle

            return complete_candle, None, True
        else:
            # Kerze ist noch unvollständig
            return None, current_candle, False

    def get_incomplete_candle(self, timeframe: str) -> dict:
        """Gibt die aktuelle unvollständige Kerze für einen Timeframe zurück"""
        for key, candle in self.incomplete_candles.items():
            if candle['timeframe'] == timeframe:
                return candle
        return None

    def get_all_incomplete_candles(self) -> dict:
        """Gibt alle unvollständigen Kerzen zurück, gruppiert nach Timeframe"""
        result = {}
        for key, candle in self.incomplete_candles.items():
            tf = candle['timeframe']
            if tf not in result:
                result[tf] = []
            result[tf].append(candle)
        return result

# Debug Controller für Debug-Funktionalität
class DebugController:
    """Verwaltet Debug-Funktionalität mit intelligenter Timeframe-Aggregation"""

    def __init__(self):
        self.current_time = None  # Wird beim ersten Skip gesetzt
        self.timeframe = "5m"
        self.play_mode = False
        self.speed = 2  # Linear 1-15

        # TimeframeAggregator für intelligente Kerzen-Logik
        self.aggregator = TimeframeAggregator()

        # Initialisiere mit aktuellstem Zeitpunkt aus CSV-Daten
        if initial_chart_data:
            # Hole letzten Zeitpunkt aus den initialen Daten
            last_candle = initial_chart_data[-1]
            # Setze Debug-Zeit auf 30. Dezember 2024, 16:55 (1 Tag vor den CSV-Daten)
            self.current_time = datetime(2024, 12, 30, 16, 55, 0)
            print(f"DEBUG INIT: Startzeit gesetzt auf {self.current_time} (30. Dezember)")

    def skip_minute(self):
        """Skip +1 Minute mit intelligenter Timeframe-Aggregation"""
        if not self.current_time:
            # Fallback: Verwende aktuellste Zeit aus Chart-Daten
            if initial_chart_data:
                last_candle = initial_chart_data[-1]
                self.current_time = datetime.fromtimestamp(last_candle['time'])
            else:
                self.current_time = datetime.now()

        # +1 Minute
        self.current_time += timedelta(minutes=1)

        print(f"DEBUG SKIP: Neue Zeit: {self.current_time} (Timeframe: {self.timeframe})")

        # Verwende TimeframeAggregator für intelligente Kerzen-Logik
        if initial_chart_data:
            last_candle = initial_chart_data[-1]
        else:
            last_candle = {'close': 18500}  # Fallback

        # Nutze Aggregator für +1 Minute Skip
        complete_candle, incomplete_candle, is_complete = self.aggregator.add_minute_to_timeframe(
            self.current_time - timedelta(minutes=1),  # Aktuelle Zeit vor dem Skip
            self.timeframe,
            last_candle
        )

        if is_complete:
            # Vollständige Kerze - zum Chart hinzufügen
            print(f"DEBUG: Vollständige {self.timeframe} Kerze generiert: {complete_candle['time']}")
            return {
                'type': 'complete_candle',
                'candle': complete_candle,
                'timeframe': self.timeframe
            }
        else:
            # Unvollständige Kerze - mit weißem Rand markieren
            print(f"DEBUG: Unvollständige {self.timeframe} Kerze: {incomplete_candle['minutes_elapsed']}/{self.aggregator.timeframes[self.timeframe]} min")
            return {
                'type': 'incomplete_candle',
                'candle': incomplete_candle,
                'timeframe': self.timeframe
            }

    def set_timeframe(self, timeframe):
        """Ändert den Timeframe und behält Zeitpunkt bei"""
        self.timeframe = timeframe
        print(f"DEBUG TIMEFRAME: Gewechselt zu {timeframe}")

    def set_speed(self, speed):
        """Setzt die Play-Geschwindigkeit (1-15)"""
        self.speed = max(1, min(15, speed))
        print(f"DEBUG SPEED: Geschwindigkeit auf {self.speed}x gesetzt")

    def toggle_play_mode(self):
        """Toggle Play/Pause Modus"""
        self.play_mode = not self.play_mode
        print(f"DEBUG PLAY: Play-Modus {'aktiviert' if self.play_mode else 'deaktiviert'}")
        return self.play_mode

    def _generate_next_candle(self):
        """Generiert nächste Kerze basierend auf aktuellem Timeframe"""
        # Einfache Mock-Kerze für jetzt - wird später durch echte Aggregations-Logik ersetzt
        timestamp = int(self.current_time.timestamp())

        # Basis-Preis aus letzter Kerze wenn verfügbar
        base_price = 18000  # NQ Standard-Preis
        if initial_chart_data:
            base_price = initial_chart_data[-1]['close']

        # Simuliere leichte Preisbewegung (+/- 0.1%)
        import random
        price_change = random.uniform(-0.001, 0.001)
        new_price = base_price * (1 + price_change)

        return {
            'time': timestamp,
            'open': base_price,
            'high': max(base_price, new_price) + random.uniform(0, base_price * 0.0005),
            'low': min(base_price, new_price) - random.uniform(0, base_price * 0.0005),
            'close': new_price,
            'volume': random.randint(1000, 5000)
        }

    def get_state(self):
        """Gibt aktuellen Debug-Status zurück"""
        return {
            'current_time': self.current_time.isoformat() if self.current_time else None,
            'timeframe': self.timeframe,
            'play_mode': self.play_mode,
            'speed': self.speed,
            'incomplete_candles': len(self.aggregator.incomplete_candles),
            'aggregator_state': self.aggregator.get_all_incomplete_candles()
        }

# Global Connection Manager und Debug Controller
manager = ConnectionManager()
debug_controller = DebugController()

# Background Task für Auto-Play Modus
async def auto_play_loop():
    """Background-Task für kontinuierliches Skip im Play-Modus"""
    while True:
        if debug_controller.play_mode:
            try:
                # Berechne Delay basierend auf Speed (1x-15x)
                # Speed 1 = 1000ms, Speed 15 = 67ms (linear)
                delay = max(1000 / debug_controller.speed, 67)  # Minimum 67ms

                # Skip +1 Minute
                result = debug_controller.skip_minute()

                # Extrahiere Kerze aus dem Ergebnis
                if result.get('type') == 'complete_candle':
                    new_candle = result['candle']
                    # Neue vollständige Kerze zu Chart-Daten hinzufügen
                    manager.chart_state['data'].append(new_candle)
                else:
                    # Incomplete Kerze - markiere als solche
                    new_candle = result['candle']
                    new_candle['incomplete'] = True

                # WebSocket-Update an alle Clients
                await manager.broadcast({
                    'type': 'auto_play_skip',
                    'candle': new_candle,
                    'debug_state': debug_controller.get_state()
                })

                print(f"AUTO-PLAY: Skip +1min (Speed {debug_controller.speed}x, Delay {delay:.0f}ms)")

                # Warte basierend auf Speed
                await asyncio.sleep(delay / 1000.0)

            except Exception as e:
                print(f"AUTO-PLAY FEHLER: {e}")
                await asyncio.sleep(1)  # Fehler-Fallback
        else:
            # Wenn Play-Mode aus ist, warte kurz und prüfe erneut
            await asyncio.sleep(0.1)

# Startup Event - Auto-Play Background Task starten
@app.on_event("startup")
async def startup_event():
    """App Startup - Starte Auto-Play Background Task"""
    print("Chart Server startet - Initialisiere Auto-Play Task")
    asyncio.create_task(auto_play_loop())

@app.get("/")
async def get_chart():
    """Haupt-Chart-Seite"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>RL Trading Chart - Realtime</title>
    <meta charset="utf-8">
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body { margin: 0; padding: 0; background: #000; font-family: Arial, sans-serif; }
        #chart_container { width: calc(100% - 35px); margin-left: 35px; position: fixed; top: 80px; bottom: 40px; } /* Angepasst für linke Sidebar */
        .status { position: fixed; top: 10px; right: 10px; color: #fff; background: rgba(0,0,0,0.7); padding: 5px 10px; border-radius: 5px; font-size: 12px; }
        .status.connected { color: #089981; }
        .status.disconnected { color: #f23645; }
        /* Erste Chart-Toolbar (Debug-Controls, oberhalb) */
        .chart-toolbar-1 { position: fixed; top: 0; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; justify-content: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Zweite Chart-Toolbar (Timeframes, darunter) */
        .chart-toolbar-2 { position: fixed; top: 40px; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Legacy toolbar class für Kompatibilität */
        .toolbar { position: fixed; top: 40px; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Bottom Chart-Toolbar (unten) - Split Design */
        .chart-toolbar-bottom { position: fixed; bottom: 0; left: 35px; right: 0; height: 40px; background: #1e1e1e; border-top: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; z-index: 1000; }

        /* Account Split Container */
        .account-split-container { display: flex; width: 100%; height: 100%; }

        /* RL-KI Account (Links) */
        .account-section-ai { flex: 1; display: flex; align-items: center; padding: 0 15px; background: rgba(8, 153, 129, 0.1); border-right: 2px solid #089981; }
        .account-section-ai .account-label { color: #089981; font-weight: bold; margin-right: 15px; font-size: 11px; }
        .account-section-ai .account-values { display: flex; gap: 20px; font-size: 11px; color: #ccc; }

        /* Nutzer Account (Rechts) */
        .account-section-user { flex: 1; display: flex; align-items: center; padding: 0 15px; background: rgba(242, 54, 69, 0.1); }
        .account-section-user .account-label { color: #f23645; font-weight: bold; margin-right: 15px; font-size: 11px; }
        .account-section-user .account-values { display: flex; gap: 20px; font-size: 11px; color: #ccc; }

        /* Account Value Styling */
        .account-value { display: flex; flex-direction: column; align-items: center; }
        .account-value-label { font-size: 9px; color: #666; margin-bottom: 1px; }
        .account-value-amount { font-size: 11px; font-weight: bold; }
        .positive { color: #089981; }
        .negative { color: #f23645; }
        .neutral { color: #ccc; }

        /* Left Chart-Sidebar (links) */
        .chart-sidebar-left { position: fixed; top: 80px; bottom: 40px; left: 0; width: 35px; background: #1e1e1e; border-right: 1px solid #333; display: flex; flex-direction: column; align-items: center; padding: 8px 0; margin: 0; gap: 10px; z-index: 1000; }
        .chart-sidebar-left .tool-btn {
            width: 28px;
            height: 28px;
            padding: 0;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
        }
        .tool-btn { background: #333; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px; transition: all 0.2s; }
        .tool-btn:hover { background: #444; }
        .tool-btn.active { background: #089981; }
        .tool-btn:disabled { background: #222; color: #666; cursor: not-allowed; }

        /* Timeframe Styles */
        .timeframe-group { display: flex; gap: 5px; margin-left: 20px; border-left: 1px solid #444; padding-left: 20px; }
        .timeframe-btn { background: #2a2a2a; color: #ccc; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; font-size: 11px; transition: all 0.2s; min-width: 35px; }
        .timeframe-btn:hover { background: #3a3a3a; color: #fff; }
        .timeframe-btn.active { background: #089981; color: #fff; font-weight: bold; }
        .timeframe-btn:disabled { background: #1a1a1a; color: #555; cursor: not-allowed; }

        /* Intelligent Zoom Toast Animations */
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }

        /* Debug-Controls Styling */
        .debug-controls {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 0 12px;
            justify-content: center;
        }

        .debug-btn {
            background: #2a2a2a;
            border: 1px solid #404040;
            color: #ffffff;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
        }

        .debug-btn:hover {
            background: #3a3a3a;
            border-color: #505050;
        }

        .debug-btn:active {
            background: #1a1a1a;
            transform: scale(0.95);
        }

        .debug-slider {
            width: 80px;
            height: 20px;
            -webkit-appearance: none;
            background: #404040;
            border-radius: 10px;
            outline: none;
        }

        .debug-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 16px;
            height: 16px;
            background: #089981;
            border-radius: 50%;
            cursor: pointer;
        }

        .debug-slider::-moz-range-thumb {
            width: 16px;
            height: 16px;
            background: #089981;
            border-radius: 50%;
            cursor: pointer;
            border: none;
        }

        .debug-speed {
            color: #089981;
            font-weight: bold;
            font-size: 12px;
            min-width: 24px;
            text-align: center;
        }

        .debug-timeframe {
            background: #2a2a2a;
            border: 1px solid #404040;
            color: #ffffff;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }

        .debug-timeframe:focus {
            outline: none;
            border-color: #089981;
        }
    </style>
</head>
<body>
    <!-- Erste Chart-Toolbar (Debug-Controls) -->
    <div class="chart-toolbar-1">
        <!-- Debug-Controls -->
        <div class="debug-controls">
            <button id="skipBtn" class="debug-btn" title="Skip +1min">⏭️</button>
            <button id="playPauseBtn" class="debug-btn" title="Play/Pause">▶️</button>
            <input type="range" id="speedSlider" class="debug-slider" min="1" max="15" value="2" title="Speed Control">
            <span id="speedDisplay" class="debug-speed">2x</span>
            <select id="timeframeSelector" class="debug-timeframe" title="Timeframe">
                <option value="1m">1m</option>
                <option value="5m" selected>5m</option>
                <option value="15m">15m</option>
                <option value="30m">30m</option>
                <option value="1h">1h</option>
            </select>
        </div>
    </div>

    <!-- Zweite Chart-Toolbar (Timeframes) -->
    <div class="chart-toolbar-2">
        <button id="clearAll" class="tool-btn">🗑️</button>

        <!-- Timeframe Buttons -->
        <div class="timeframe-group">
            <button id="tf-1m" class="timeframe-btn" data-timeframe="1m">1m</button>
            <button id="tf-2m" class="timeframe-btn" data-timeframe="2m">2m</button>
            <button id="tf-3m" class="timeframe-btn" data-timeframe="3m">3m</button>
            <button id="tf-5m" class="timeframe-btn active" data-timeframe="5m">5m</button>
            <button id="tf-15m" class="timeframe-btn" data-timeframe="15m">15m</button>
            <button id="tf-30m" class="timeframe-btn" data-timeframe="30m">30m</button>
            <button id="tf-1h" class="timeframe-btn" data-timeframe="1h">1h</button>
            <button id="tf-4h" class="timeframe-btn" data-timeframe="4h">4h</button>
        </div>
    </div>

    <!-- Left Chart-Sidebar (links) -->
    <div class="chart-sidebar-left">
        <button id="positionBoxTool" class="tool-btn" title="Long Position">📈</button>
        <button id="shortPositionTool" class="tool-btn" title="Short Position">📉</button>
    </div>

    <!-- Bottom Chart-Toolbar (unten) - Split Account Display -->
    <div class="chart-toolbar-bottom">
        <div class="account-split-container">
            <!-- RL-KI Account (Links) -->
            <div class="account-section-ai">
                <div class="account-label">🤖 RL-KI</div>
                <div class="account-values">
                    <div class="account-value">
                        <div class="account-value-label">Account Balance</div>
                        <div class="account-value-amount neutral" id="ai-balance">500.000€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Realized PnL</div>
                        <div class="account-value-amount neutral" id="ai-realized">0€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Unrealized PnL</div>
                        <div class="account-value-amount neutral" id="ai-unrealized">0€</div>
                    </div>
                </div>
            </div>

            <!-- Nutzer Account (Rechts) -->
            <div class="account-section-user">
                <div class="account-label">👤 Nutzer</div>
                <div class="account-values">
                    <div class="account-value">
                        <div class="account-value-label">Account Balance</div>
                        <div class="account-value-amount neutral" id="user-balance">500.000€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Realized PnL</div>
                        <div class="account-value-amount neutral" id="user-realized">0€</div>
                    </div>
                    <div class="account-value">
                        <div class="account-value-label">Unrealized PnL</div>
                        <div class="account-value-amount neutral" id="user-unrealized">0€</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="status" class="status disconnected">Disconnected</div>
    <div id="chart_container"></div>

    <script>
        console.log('🚀 RL Trading Chart - FastAPI Edition');

        // Server-side Logging Function für Debug-Ausgaben
        function serverLog(message, data = null) {
            const logData = {
                message: message,
                timestamp: new Date().toISOString(),
                data: data
            };

            // Console ausgeben für Browser
            console.log('📤 SERVER LOG:', message, data);

            // An Server senden für Terminal-Ausgabe
            fetch('/api/debug/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(logData)
            }).catch(e => console.warn('Server log failed:', e));
        }

        // Erster Test-Log
        serverLog('🚀 JavaScript-Execution gestartet');

        let chart;
        let candlestickSeries;
        let ws;
        let isInitialized = false;

        // Chart initialisieren
        // EINFACHE CHART POSITIONING FUNKTION
        function setChartWith20PercentMargin(chartData) {
            console.log('MARGIN: Setze 20% Freiraum für', chartData.length, 'Kerzen');

            if (!chartData || chartData.length < 2) {
                console.log('MARGIN: Fallback zu fitContent (zu wenig Daten)');
                chart.timeScale().fitContent();
                return;
            }

            // Hole erste und letzte Zeit
            const firstTime = chartData[0].time;
            const lastTime = chartData[chartData.length - 1].time;

            // Berechne 20% Freiraum rechts
            const dataTimeSpan = lastTime - firstTime;
            const marginTime = dataTimeSpan * 0.25; // 25% der Daten = 20% der Gesamt-Chart

            console.log('MARGIN: Daten-Zeitspanne:', dataTimeSpan, 'Freiraum:', marginTime);
            console.log('MARGIN: Chart von', firstTime, 'bis', lastTime + marginTime);

            // Setze sichtbaren Bereich
            chart.timeScale().setVisibleRange({
                from: firstTime,
                to: lastTime + marginTime
            });

            console.log('MARGIN: 20% Freiraum gesetzt');
        }

        // Smart Chart Positioning System - 50 Kerzen Standard mit 20% Freiraum
        class SmartChartPositioning {
            constructor(chart, candlestickSeries) {
                this.chart = chart;
                this.candlestickSeries = candlestickSeries;
                this.standardCandleCount = 50; // Standard: 50 Kerzen sichtbar
                this.rightMarginPercent = 0.2; // 20% rechter Freiraum

                console.log(`📊 Smart Positioning: ${this.standardCandleCount} Kerzen Standard mit ${this.rightMarginPercent * 100}% Freiraum`);
            }

            // Setze Chart auf Standard-Position: 50 Kerzen + 20% Freiraum
            setStandardPosition(data) {
                if (!data || data.length === 0) {
                    console.warn('🚫 Keine Daten für Standard Position');
                    return;
                }

                const dataLength = data.length;
                const visibleCandles = Math.min(this.standardCandleCount, dataLength);

                // Berechne Zeitbereich für sichtbare Kerzen
                const startIndex = Math.max(0, dataLength - visibleCandles);
                const endIndex = dataLength - 1;

                if (startIndex === endIndex) {
                    console.warn('🚫 Nicht genug Daten für Standard Position');
                    this.chart.timeScale().fitContent();
                    return;
                }

                // Zeitstempel der ersten und letzten sichtbaren Kerze
                const startTime = data[startIndex].time;
                const endTime = data[endIndex].time;

                // RICHTIGE FREIRAUM-BERECHNUNG:
                // 50 Kerzen sollen 4/5 (80%) der Chart-Breite links einnehmen
                // 1/5 (20%) rechts soll frei bleiben für neue Kerzen

                const dataTimeSpan = endTime - startTime;

                // Wenn Daten 80% der Chart einnehmen sollen, dann:
                // Gesamt-Chart-Breite = Daten-Breite / 0.8
                const totalChartTimeSpan = dataTimeSpan / 0.8;

                // Rechter Freiraum = 20% der Gesamt-Chart-Breite
                const rightMarginTime = totalChartTimeSpan * 0.2;

                // Chart beginnt bei den Daten, endet mit Freiraum
                const chartStartTime = startTime;
                const chartEndTime = endTime + rightMarginTime;

                console.log(`📍 Smart Position: ${visibleCandles} Kerzen (${startIndex}-${endIndex})`);
                console.log(`📍 Daten nehmen 80% ein: ${startTime} bis ${endTime}`);
                console.log(`📍 Chart-Bereich: ${chartStartTime} bis ${chartEndTime} (20% Freiraum: ${rightMarginTime})`);

                // Setze sichtbaren Bereich: Daten links 80%, Freiraum rechts 20%
                this.chart.timeScale().setVisibleRange({
                    from: chartStartTime,
                    to: chartEndTime
                });
            }

            // Nach Timeframe-Wechsel: Immer zurück zur Standard-Position
            resetToStandardPosition(newData) {
                console.log(`🔄 Reset zu Standard-Position nach Timeframe-Wechsel`);
                this.setStandardPosition(newData);
            }
        }

        // Intelligent Zoom System Class
        class IntelligentZoomSystem {
            constructor(chart, candlestickSeries, currentTimeframe = '5m') {
                this.chart = chart;
                this.candlestickSeries = candlestickSeries;
                this.currentTimeframe = currentTimeframe;
                this.currentCandles = 200; // Aktuelle Anzahl geladener Kerzen
                this.minVisibleCandles = 50; // Minimum sichtbare Kerzen
                this.maxVisibleCandles = 2000; // Maximum für Performance
                this.isLoading = false;
                this.lastVisibleRange = null;

                this.setupZoomMonitoring();
            }

            setupZoomMonitoring() {
                // Überwache Änderungen der sichtbaren Zeitspanne
                this.chart.timeScale().subscribeVisibleLogicalRangeChange((newVisibleLogicalRange) => {
                    if (newVisibleLogicalRange === null) return;
                    this.handleVisibleRangeChange(newVisibleLogicalRange);
                });

                console.log('🔍 Intelligent Zoom System aktiviert');
            }

            handleVisibleRangeChange(visibleLogicalRange) {
                const { from, to } = visibleLogicalRange;
                const visibleCandleCount = Math.ceil(to - from);

                console.log(`📊 Sichtbare Kerzen: ${visibleCandleCount}, Geladen: ${this.currentCandles}`);

                // Check if we need more candles (user zoomed out)
                if (this.shouldLoadMoreCandles(visibleCandleCount)) {
                    this.loadMoreCandles(visibleCandleCount);
                }

                this.lastVisibleRange = visibleLogicalRange;
            }

            shouldLoadMoreCandles(visibleCandleCount) {
                // TEMPORÄR DEAKTIVIERT - Testing Timeframe Fix
                console.log('🚫 Zoom System temporär deaktiviert für Timeframe-Fix');
                return false;

                // Original code (auskommentiert):
                // const visibilityRatio = visibleCandleCount / this.currentCandles;
                // return visibilityRatio > 0.7 &&
                //        this.currentCandles < this.maxVisibleCandles &&
                //        !this.isLoading;
            }

            async loadMoreCandles(visibleCandleCount) {
                if (this.isLoading) return;

                this.isLoading = true;
                console.log('📈 Lade mehr Kerzen für bessere Zoom-Erfahrung...');

                try {
                    // Berechne wie viele Kerzen wir brauchen
                    const targetCandles = Math.min(
                        Math.max(visibleCandleCount * 2.5, this.currentCandles * 1.5),
                        this.maxVisibleCandles
                    );

                    // API-Call für mehr Daten
                    const response = await fetch('/api/chart/change_timeframe', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            timeframe: this.currentTimeframe,
                            visible_candles: Math.ceil(targetCandles)
                        })
                    });

                    const result = await response.json();

                    if (result.status === 'success') {
                        // Update Chart mit mehr Daten
                        this.candlestickSeries.setData(result.data);
                        this.currentCandles = result.data.length;

                        console.log(`✅ Mehr Kerzen geladen: ${this.currentCandles}`);

                        // Toast-Benachrichtigung
                        this.showZoomNotification(`🔍 Zoom erweitert: ${this.currentCandles} Kerzen verfügbar`);
                    }
                } catch (error) {
                    console.error('❌ Fehler beim Laden zusätzlicher Kerzen:', error);
                } finally {
                    this.isLoading = false;
                }
            }

            updateTimeframe(newTimeframe, newCandleCount) {
                this.currentTimeframe = newTimeframe;
                this.currentCandles = newCandleCount || this.currentCandles;
                console.log(`🔄 Timeframe geändert zu: ${newTimeframe} (${this.currentCandles} Kerzen)`);
            }

            showZoomNotification(message) {
                // Erstelle Toast-Benachrichtigung
                const toast = document.createElement('div');
                toast.textContent = message;
                toast.style.cssText = `
                    position: fixed;
                    top: 80px;
                    right: 20px;
                    background: rgba(8, 153, 129, 0.9);
                    color: white;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 11px;
                    z-index: 10000;
                    animation: slideIn 0.3s ease-out;
                `;

                document.body.appendChild(toast);

                // Auto-remove nach 2 Sekunden
                setTimeout(() => {
                    toast.style.animation = 'slideOut 0.3s ease-in';
                    setTimeout(() => toast.remove(), 300);
                }, 2000);
            }
        }

        function initChart() {
            console.log('🔧 initChart() aufgerufen');

            const chartContainer = document.getElementById('chart_container');
            console.log('🔧 Chart Container:', chartContainer);

            if (!chartContainer) {
                console.error('❌ Chart Container nicht gefunden!');
                return;
            }

            console.log('🔧 LightweightCharts verfügbar:', typeof LightweightCharts);

            chart = LightweightCharts.createChart(chartContainer, {
                width: chartContainer.clientWidth,
                height: chartContainer.clientHeight,
                layout: {
                    backgroundColor: '#000000',
                    textColor: '#d9d9d9'
                },
                timeScale: {
                    timeVisible: true,
                    secondsVisible: false,
                    borderColor: '#485c7b'
                },
                grid: {
                    vertLines: { visible: false },
                    horzLines: { visible: false }
                }
            });

            candlestickSeries = chart.addCandlestickSeries({
                upColor: '#089981',
                downColor: '#f23645',
                borderUpColor: '#089981',
                borderDownColor: '#f23645',
                wickUpColor: '#089981',
                wickDownColor: '#f23645'
            });

            // Smart Positioning System initialisieren
            try {
                window.smartPositioning = new SmartChartPositioning(chart, candlestickSeries);
                console.log('INIT: Smart Positioning System initialisiert');

                // Chart-Daten sofort laden
                loadInitialData();

                // SOFORTIGER TEST der Smart Positioning
                window.testSmartPositioning = function() {
                    console.log('DIRECT TEST: Smart Positioning wird getestet...');
                    if (window.smartPositioning) {
                        // Erstelle Test-Daten
                        const testData = [];
                        const baseTime = Math.floor(Date.now() / 1000);
                        for (let i = 0; i < 50; i++) {
                            testData.push({
                                time: baseTime + (i * 300), // 5-Minuten Intervall
                                open: 100 + i,
                                high: 105 + i,
                                low: 95 + i,
                                close: 102 + i
                            });
                        }
                        console.log('DIRECT TEST: Test-Daten erstellt, rufe setStandardPosition auf...');
                        window.smartPositioning.setStandardPosition(testData);
                        console.log('DIRECT TEST: setStandardPosition aufgerufen');
                    } else {
                        console.error('DIRECT TEST: Smart Positioning nicht verfügbar');
                    }
                };

            } catch (error) {
                console.error('INIT ERROR: Fehler bei Smart Positioning Initialisierung:', error);
                window.smartPositioning = null;
            }

            console.log('🔧 CandlestickSeries und Smart Positioning erstellt:', candlestickSeries);

            // Position Lines Container
            window.positionLines = {};
            window.activeSeries = {};
            window.positionBoxMode = false;
            window.shortPositionMode = false;
            window.currentPositionBox = null;

            // Timeframe State mit Performance-Optimierung
            window.currentTimeframe = '5m';
            window.timeframeCache = new Map();  // Browser-side caching
            window.isTimeframeChanging = false;  // Prevent double-requests

            // Smart Chart Positioning System - 50 Kerzen + 20% Freiraum
            window.smartPositioning = null;  // Wird nach Chart-Init initialisiert

            // Intelligent Zoom System - Garantiert sichtbare Kerzen beim Auszoomen
            window.intelligentZoom = null;  // Wird nach Daten-Load initialisiert

            // Responsive Resize
            window.addEventListener('resize', () => {
                chart.applyOptions({
                    width: chartContainer.clientWidth,
                    height: chartContainer.clientHeight
                });
            });

            // LADE ECHTE NQ-DATEN über WebSocket
            console.log('🔄 Lade echte NQ-Daten...');

            // Initialer Request für Chart-Daten
            setTimeout(() => {
                loadInitialData();
            }, 1000);

            // Chart Click Handler für Position Box Tool
            chart.subscribeClick((param) => {
                console.log('🖱️ Chart geklickt:', param);
                console.log('📦 Position Box Mode:', window.positionBoxMode);

                if ((window.positionBoxMode || window.shortPositionMode) && param.point) {
                    const price = candlestickSeries.coordinateToPrice(param.point.y);
                    const clickX = param.point.x; // ⭐ Click-X-Koordinate erfassen
                    const clickY = param.point.y; // ⭐ Click-Y-Koordinate erfassen

                    // Verwende param.time falls vorhanden (Kerzen-Klick), sonst aktuelle Zeit (freier Bereich)
                    const timeForBox = param.time || Math.floor(Date.now() / 1000);

                    const isShort = window.shortPositionMode;
                    console.log('📦 Erstelle', isShort ? 'Short' : 'Long', 'Position Box bei Preis:', price, 'an X-Position:', clickX, 'Y-Position:', clickY, 'Zeit:', timeForBox);
                    createPositionBox(timeForBox, price, clickX, clickY, isShort);
                } else {
                    console.log('❌ Position Box Mode nicht aktiv oder ungültiger Klick');
                }
            });

            isInitialized = true;
            console.log('✅ Chart initialisiert, lade NQ-Daten...');
        }

        // Lade initiale Chart-Daten vom Server
        function loadInitialData() {
            console.log('📊 Lade initiale NQ-Daten...');

            // Prüfe ob Chart und Series verfügbar sind
            if (!chart || !candlestickSeries) {
                console.error('❌ Chart oder CandlestickSeries nicht initialisiert!');
                console.log('Chart:', chart);
                console.log('CandlestickSeries:', candlestickSeries);
                return;
            }

            fetch('/api/chart/status')
                .then(response => response.json())
                .then(data => {
                    console.log('📊 Status:', data);
                    // Lade Chart-Daten
                    return fetch('/api/chart/data');
                })
                .then(response => response.json())
                .then(chartData => {
                    console.log('📊 Chart-Daten erhalten:', chartData.data?.length || 0, 'Kerzen');
                    console.log('DRASTIC: SOFORT nach Chart-Daten Log - 20% Freiraum wird ERZWUNGEN!');
                    if (chartData.data && chartData.data.length > 0) {
                        // Daten sind bereits im korrekten LightweightCharts Format (Unix-Timestamps)
                        const formattedData = chartData.data.map(item => ({
                            time: item.time,  // Bereits Unix-Timestamp, keine Konvertierung nötig
                            open: parseFloat(item.open),
                            high: parseFloat(item.high),
                            low: parseFloat(item.low),
                            close: parseFloat(item.close)
                        }));

                        candlestickSeries.setData(formattedData);

                        // DRASTISCHE SOFORT-LÖSUNG: 20% Freiraum GARANTIERT
                        console.log('DRASTIC-EXEC: Setze 20% Freiraum SOFORT nach setData()');
                        const firstTime = formattedData[0].time;
                        const lastTime = formattedData[formattedData.length - 1].time;
                        const span = lastTime - firstTime;
                        const margin = span * 0.25;
                        chart.timeScale().setVisibleRange({
                            from: firstTime,
                            to: lastTime + margin
                        });
                        console.log('DRASTIC-EXEC: Freiraum gesetzt von', firstTime, 'bis', lastTime + margin);

                        // FINALE DIREKTE LÖSUNG: 20% Freiraum OHNE Bedingungen
                        console.log('FINAL: Setze GARANTIERT 20% Freiraum für', formattedData.length, 'Kerzen');

                        if (formattedData.length >= 2) {
                            const firstTime = formattedData[0].time;
                            const lastTime = formattedData[formattedData.length - 1].time;
                            const dataSpan = lastTime - firstTime;
                            const margin = dataSpan * 0.25; // 25% = 20% der Gesamt-Chart

                            console.log('FINAL: Zeitspanne:', dataSpan, 'Margin:', margin);
                            console.log('FINAL: Von', firstTime, 'bis', lastTime + margin);

                            chart.timeScale().setVisibleRange({
                                from: firstTime,
                                to: lastTime + margin
                            });

                            console.log('FINAL: Chart-Position GESETZT');
                        } else {
                            console.log('FINAL: Zu wenig Daten - verwende fitContent');
                            chart.timeScale().fitContent();
                        }

                        // ZUSÄTZLICHER SCHUTZ: Nochmal nach 100ms setzen
                        setTimeout(() => {
                            if (formattedData.length >= 2) {
                                const firstTime = formattedData[0].time;
                                const lastTime = formattedData[formattedData.length - 1].time;
                                const dataSpan = lastTime - firstTime;
                                const margin = dataSpan * 0.25;

                                chart.timeScale().setVisibleRange({
                                    from: firstTime,
                                    to: lastTime + margin
                                });

                                console.log('DELAYED: 20% Freiraum nochmal gesetzt nach 100ms');
                            }
                        }, 100);

                        console.log('✅ NQ-Daten geladen:', formattedData.length, 'Kerzen, Smart Positioning angewandt');

                        // ZOOM SYSTEM KOMPLETT DEAKTIVIERT für Timeframe-Fix
                        console.log('🚫 Zoom System komplett deaktiviert');
                        window.intelligentZoom = null;
                    } else {
                        console.warn('⚠️ Keine Chart-Daten empfangen');
                    }
                })
                .catch(error => {
                    console.error('❌ Fehler beim Laden der Chart-Daten:', error);
                });
        }

        // WebSocket Connection
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            ws = new WebSocket(wsUrl);

            // TEST: Direkter Smart Positioning Test nach 3 Sekunden
            setTimeout(() => {
                console.log('AUTO TEST: Smart Positioning nach 3 Sekunden...');
                if (window.testSmartPositioning) {
                    window.testSmartPositioning();
                } else {
                    console.error('AUTO TEST: testSmartPositioning Funktion nicht verfügbar');
                }
            }, 3000);

            // TEST: API-basierter Test nach 6 Sekunden
            setTimeout(() => {
                console.log('API TEST: Smart Positioning mit echten Daten...');
                if (window.smartPositioning && candlestickSeries) {
                    try {
                        // Hole aktuelle Daten von der Chart API
                        fetch('/api/chart/data')
                            .then(response => response.json())
                            .then(data => {
                                if (data.data && data.data.length > 0) {
                                    console.log('API TEST: Gefunden', data.data.length, 'Kerzen, wende Smart Positioning an');
                                    window.smartPositioning.setStandardPosition(data.data);
                                } else {
                                    console.error('API TEST: Keine Daten erhalten');
                                }
                            })
                            .catch(error => console.error('API TEST Fehler:', error));
                    } catch (error) {
                        console.error('API TEST Smart Positioning Fehler:', error);
                    }
                } else {
                    console.warn('API TEST: Smart Positioning oder CandlestickSeries nicht verfügbar');
                    console.log('API TEST window.smartPositioning:', window.smartPositioning);
                    console.log('API TEST candlestickSeries:', candlestickSeries);
                }
            }, 6000);

            ws.onopen = function(event) {
                console.log('🔗 WebSocket verbunden');
                document.getElementById('status').textContent = 'Connected';
                document.getElementById('status').className = 'status connected';
            };

            ws.onmessage = function(event) {
                const message = JSON.parse(event.data);
                handleMessage(message);
            };

            ws.onclose = function(event) {
                console.log('❌ WebSocket getrennt');
                document.getElementById('status').textContent = 'Disconnected';
                document.getElementById('status').className = 'status disconnected';

                // Reconnect nach 2 Sekunden
                setTimeout(connectWebSocket, 2000);
            };

            ws.onerror = function(error) {
                console.error('❌ WebSocket Error:', error);
            };
        }

        // Account Update Functions
        async function loadAccountData() {
            // Lädt Account-Daten für beide Accounts und aktualisiert die UI
            try {
                const response = await fetch('/api/account/status');
                const data = await response.json();

                if (data.status === 'success') {
                    updateAccountDisplay('ai', data.ai_account);
                    updateAccountDisplay('user', data.user_account);
                }
            } catch (error) {
                console.error('❌ Fehler beim Laden der Account-Daten:', error);
            }
        }

        function updateAccountDisplay(accountType, accountData) {
            // Aktualisiert die Account-Anzeige in der UI
            const prefix = accountType === 'ai' ? 'ai' : 'user';

            // Update Balance
            const balanceEl = document.getElementById(`${prefix}-balance`);
            if (balanceEl) {
                balanceEl.textContent = accountData.balance;
                balanceEl.className = 'account-value-amount neutral';
            }

            // Update Realized PnL
            const realizedEl = document.getElementById(`${prefix}-realized`);
            if (realizedEl) {
                realizedEl.textContent = accountData.realized_pnl;
                realizedEl.className = `account-value-amount ${getPnLClass(accountData.realized_pnl)}`;
            }

            // Update Unrealized PnL
            const unrealizedEl = document.getElementById(`${prefix}-unrealized`);
            if (unrealizedEl) {
                unrealizedEl.textContent = accountData.unrealized_pnl;
                unrealizedEl.className = `account-value-amount ${getPnLClass(accountData.unrealized_pnl)}`;
            }
        }

        function getPnLClass(pnlString) {
            // Bestimmt CSS-Klasse basierend auf PnL-Wert
            if (pnlString.includes('+')) return 'positive';
            if (pnlString.includes('-')) return 'negative';
            return 'neutral';
        }

        // Account Data alle 5 Sekunden laden
        setInterval(loadAccountData, 5000);

        // Message Handler
        function handleMessage(message) {
            console.log('📨 Message received:', message.type);

            switch(message.type) {
                case 'initial_data':
                    if (!isInitialized) initChart();

                    const data = message.data.data;
                    if (data && data.length > 0) {
                        candlestickSeries.setData(data);

                        // NEUE LOGIK: Zeige nur letzten 50 Kerzen mit 80/20 Aufteilung
                        console.log(`📊 Initial: ${data.length} Kerzen geladen, zeige letzten 50 mit 80/20 Aufteilung`);
                        document.title = `Chart: ${data.length} Kerzen verfügbar, 50 sichtbar (${message.data.interval})`;

                        // Berechne die letzten 50 Kerzen
                        const totalCandles = data.length;
                        const visibleCandles = Math.min(50, totalCandles);
                        const startIndex = Math.max(0, totalCandles - visibleCandles);

                        const firstVisibleTime = data[startIndex].time;
                        const lastVisibleTime = data[totalCandles - 1].time;
                        const visibleSpan = lastVisibleTime - firstVisibleTime;

                        // 20% Freiraum rechts hinzufügen: 50 Kerzen sind 80%, also 20% zusätzlich
                        const margin = visibleSpan / 4; // visibleSpan / 4 = 20% von den 80%

                        chart.timeScale().setVisibleRange({
                            from: firstVisibleTime,
                            to: lastVisibleTime + margin
                        });

                        console.log(`✅ Standard-Zoom: Kerzen ${startIndex}-${totalCandles-1} sichtbar (${visibleCandles} Kerzen mit 20% Freiraum)`);
                    }
                    break;

                case 'set_data':
                    if (!isInitialized) initChart();

                    candlestickSeries.setData(message.data);

                    // Smart Positioning: 50 Kerzen Standard mit 20% Freiraum
                    if (window.smartPositioning) {
                        window.smartPositioning.setStandardPosition(message.data);
                    }

                    console.log('📊 Data updated:', message.data.length, 'candles mit Smart Positioning');
                    break;

                case 'add_candle':
                    if (isInitialized && message.candle) {
                        candlestickSeries.update(message.candle);
                        console.log('➡️ Candle added:', message.candle);
                    }
                    break;

                case 'debug_skip':
                    // Debug Skip: Direkte Chart-Update ohne Smart Positioning System
                    if (isInitialized && message.candle) {
                        candlestickSeries.update(message.candle);
                        console.log('⏭️ Debug Skip: Neue Kerze hinzugefügt:', message.candle);
                        console.log('📊 Result Type:', message.result_type);
                    } else {
                        console.log('❌ Debug Skip fehlgeschlagen: Chart nicht initialisiert oder fehlende Kerze');
                    }
                    break;

                case 'add_position':
                    if (isInitialized && message.position) {
                        addPositionOverlay(message.position);
                        console.log('🎯 Position added:', message.position);
                    }
                    break;

                case 'remove_position':
                    if (isInitialized && message.position_id) {
                        removePositionOverlay(message.position_id);
                        console.log('❌ Position removed:', message.position_id);
                    }
                    break;

                case 'positions_sync':
                    if (isInitialized && message.positions) {
                        syncPositions(message.positions);
                        console.log('🔄 Positions synced:', message.positions.length);
                    }
                    break;

                case 'timeframe_changed':
                    console.log('DEBUG: timeframe_changed message received:', message);

                    if (isInitialized && message.data) {
                        // Chart-Daten für neuen Timeframe setzen
                        const formattedData = message.data.map(item => ({
                            time: item.time,
                            open: parseFloat(item.open),
                            high: parseFloat(item.high),
                            low: parseFloat(item.low),
                            close: parseFloat(item.close)
                        }));

                        candlestickSeries.setData(formattedData);

                        // NEUE LOGIK: Zeige nur letzten 50 Kerzen mit 80/20 Aufteilung bei TF-Wechsel
                        console.log(`📊 Timeframe ${message.timeframe}: ${formattedData.length} Kerzen geladen, zeige letzten 50 mit 80/20 Aufteilung`);
                        document.title = `Chart: ${formattedData.length} Kerzen verfügbar, 50 sichtbar (${message.timeframe})`;

                        // Berechne die letzten 50 Kerzen
                        const totalCandles = formattedData.length;
                        const visibleCandles = Math.min(50, totalCandles);
                        const startIndex = Math.max(0, totalCandles - visibleCandles);

                        const firstVisibleTime = formattedData[startIndex].time;
                        const lastVisibleTime = formattedData[totalCandles - 1].time;
                        const visibleSpan = lastVisibleTime - firstVisibleTime;

                        // 20% Freiraum rechts hinzufügen: 50 Kerzen sind 80%, also 20% zusätzlich
                        const margin = visibleSpan / 4; // visibleSpan / 4 = 20% von den 80%

                        chart.timeScale().setVisibleRange({
                            from: firstVisibleTime,
                            to: lastVisibleTime + margin
                        });

                        // Update current timeframe
                        window.currentTimeframe = message.timeframe;

                        console.log(`✅ TF-Wechsel: Kerzen ${startIndex}-${totalCandles-1} sichtbar (${visibleCandles} Kerzen mit 20% Freiraum)`);
                    }
                    break;

                default:
                    console.log('❓ Unknown message type:', message.type);
            }
        }

        // Position Overlay Functions
        function addPositionOverlay(position) {
            const positionId = position.id;

            // Entry Line (grün für Long, rot für Short)
            const entryColor = position.type === 'LONG' ? '#089981' : '#f23645';
            const entrySeries = chart.addLineSeries({
                color: entryColor,
                lineWidth: 2,
                lineStyle: 0, // Solid
                title: `Entry ${positionId}`
            });
            entrySeries.setData([{time: 0, value: position.entry_price}]);

            // Stop Loss Line (rot)
            let stopLossSeries = null;
            if (position.stop_loss) {
                stopLossSeries = chart.addLineSeries({
                    color: '#ff4444',
                    lineWidth: 1,
                    lineStyle: 1, // Dashed
                    title: `SL ${positionId}`
                });
                stopLossSeries.setData([{time: 0, value: position.stop_loss}]);
            }

            // Take Profit Line (grün)
            let takeProfitSeries = null;
            if (position.take_profit) {
                takeProfitSeries = chart.addLineSeries({
                    color: '#44ff44',
                    lineWidth: 1,
                    lineStyle: 1, // Dashed
                    title: `TP ${positionId}`
                });
                takeProfitSeries.setData([{time: 0, value: position.take_profit}]);
            }

            // Position Box (transparente Box zwischen Entry und TP/SL)
            const boxSeries = chart.addAreaSeries({
                topColor: position.type === 'LONG' ? 'rgba(8, 153, 129, 0.1)' : 'rgba(242, 54, 69, 0.1)',
                bottomColor: position.type === 'LONG' ? 'rgba(8, 153, 129, 0.05)' : 'rgba(242, 54, 69, 0.05)',
                lineColor: 'transparent'
            });

            // Box-Daten basierend auf Position-Typ
            const boxTop = position.type === 'LONG' ?
                (position.take_profit || position.entry_price * 1.02) :
                position.entry_price;
            const boxBottom = position.type === 'LONG' ?
                position.entry_price :
                (position.take_profit || position.entry_price * 0.98);

            boxSeries.setData([{time: 0, value: boxTop}]);

            // Speichere alle Series für diese Position
            window.positionLines[positionId] = {
                entry: entrySeries,
                stopLoss: stopLossSeries,
                takeProfit: takeProfitSeries,
                box: boxSeries,
                position: position
            };

            console.log(`✅ Position overlay added: ${positionId} ${position.type}`);
        }

        function removePositionOverlay(positionId) {
            const positionData = window.positionLines[positionId];
            if (positionData) {
                // Entferne alle Series
                chart.removeSeries(positionData.entry);
                if (positionData.stopLoss) chart.removeSeries(positionData.stopLoss);
                if (positionData.takeProfit) chart.removeSeries(positionData.takeProfit);
                chart.removeSeries(positionData.box);

                // Lösche aus Container
                delete window.positionLines[positionId];
                console.log(`❌ Position overlay removed: ${positionId}`);
            }
        }

        function syncPositions(positions) {
            // Lösche alle existierenden Overlays
            for (const positionId in window.positionLines) {
                removePositionOverlay(positionId);
            }

            // Füge alle aktiven Positionen hinzu
            positions.forEach(position => {
                if (position.status === 'OPEN') {
                    addPositionOverlay(position);
                }
            });
        }

        // Position Box Functions - NEUE IMPLEMENTIERUNG MIT ECHTEN RECHTECKEN
        function createPositionBox(time, entryPrice, clickX, clickY, isShort = false) {
            // Entferne alte Position Box falls vorhanden
            if (window.currentPositionBox) {
                removeCurrentPositionBox();
            }

            // Kleinere SL/TP für bessere Sichtbarkeit (0.25% Risk, 0.5% Reward)
            const riskPercent = 0.0025; // 0.25%
            const rewardPercent = 0.005; // 0.5%

            // Für Short Positionen sind TP/SL umgekehrt
            let stopLoss, takeProfit;
            if (isShort) {
                stopLoss = entryPrice * (1 + riskPercent);   // SL oben (höher als Entry)
                takeProfit = entryPrice * (1 - rewardPercent); // TP unten (niedriger als Entry)
            } else {
                stopLoss = entryPrice * (1 - riskPercent);   // SL unten (niedriger als Entry)
                takeProfit = entryPrice * (1 + rewardPercent); // TP oben (höher als Entry)
            }

            console.log('💰 Preise:', {entry: entryPrice, sl: stopLoss, tp: takeProfit});
            console.log('📍 Click-Position:', clickX, clickY, 'Container Breite:', document.getElementById('chart_container')?.clientWidth);

            // Box Dimensionen
            const currentTime = Math.floor(Date.now() / 1000);
            const boxWidth = 7200; // 2 Stunden für bessere Sichtbarkeit
            const timeEnd = currentTime + boxWidth;

            // Position Box Object erstellen
            window.currentPositionBox = {
                id: 'POS_' + Date.now(),
                entryPrice: entryPrice,
                stopLoss: stopLoss,
                takeProfit: takeProfit,
                time: currentTime,
                timeEnd: timeEnd,
                width: boxWidth,
                isResizing: false,
                resizeHandle: null,
                isShort: isShort,
                // NEUE X-Koordinaten basierend auf Click-Position
                clickX: clickX || null,  // Echte Click-X-Koordinate
                clickY: clickY || null,  // Echte Click-Y-Koordinate
                x1Percent: clickX ? Math.max(0, (clickX - 60) / document.getElementById('chart_container').clientWidth) : 0.45,  // 60px links vom Klick
                x2Percent: clickX ? Math.min(1, (clickX + 60) / document.getElementById('chart_container').clientWidth) : 0.55,  // 60px rechts vom Klick
                // DIREKTE Y-KOORDINATEN FÜR SOFORTIGE UPDATES - Entry Level an exakter Click-Position
                entryY: clickY || null,  // ⭐ Verwende Click-Y für Entry Level
                slY: null,
                tpY: null
            };

            // Zeichne die Box mit Canvas Overlay (echte Rechtecke)
            createCanvasOverlay();
            drawPositionBox();

            // Erstelle Price Lines auf der Y-Achse (DEAKTIVIERT für Positionseröffnungstool)
            // createPriceLines(entryPrice, stopLoss, takeProfit);

            console.log('📦 Neue Position Box erstellt:', window.currentPositionBox);
        }

        function createCanvasOverlay() {
            // Entferne alte Canvas falls vorhanden
            const oldCanvas = document.getElementById('position-canvas');
            if (oldCanvas) oldCanvas.remove();

            const chartContainer = document.getElementById('chart_container');
            const canvas = document.createElement('canvas');
            canvas.id = 'position-canvas';
            canvas.style.position = 'absolute';
            canvas.style.top = '0';
            canvas.style.left = '0';
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.pointerEvents = 'auto';
            canvas.style.zIndex = '1000';
            canvas.width = chartContainer.clientWidth;
            canvas.height = chartContainer.clientHeight;

            chartContainer.style.position = 'relative';
            chartContainer.appendChild(canvas);

            const ctx = canvas.getContext('2d');
            window.positionCanvas = canvas;
            window.positionCtx = ctx;

            // Mouse Events für Resize
            canvas.addEventListener('mousedown', onCanvasMouseDown);
            canvas.addEventListener('mousemove', onCanvasMouseMove);
            canvas.addEventListener('mouseup', onCanvasMouseUp);
        }

        function drawPositionBox() {
            const box = window.currentPositionBox;
            const ctx = window.positionCtx;
            const canvas = window.positionCanvas;

            if (!box || !ctx || !canvas) {
                console.warn('❌ drawPositionBox: Missing box, context, or canvas');
                return;
            }

            // Clear canvas
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            try {
                // SICHERE API AUFRUFE - Prüfe ob Chart bereit ist
                if (!chart || !candlestickSeries) {
                    console.warn('❌ Chart or series not ready');
                    return;
                }

                // Verwende dynamische oder Fallback Koordinaten
                const chartWidth = canvas.width;
                const chartHeight = canvas.height;

                // X-Position: Dynamische Werte aus Box-Objektt, sonst Fallback
                const x1 = chartWidth * (box.x1Percent || 0.1);
                const x2 = chartWidth * (box.x2Percent || 0.9);

                // Y-Koordinaten: VERWENDE GESPEICHERTE ODER BERECHNE NEU
                let entryY, slY, tpY;

                // EINZELNE KOORDINATEN-CACHE-PRÜFUNG
                // Verwende gecachte Koordinate wenn vorhanden, sonst berechne neu
                try {
                    entryY = (box.entryY !== null) ? box.entryY : candlestickSeries.priceToCoordinate(box.entryPrice);
                    slY = (box.slY !== null) ? box.slY : candlestickSeries.priceToCoordinate(box.stopLoss);
                    tpY = (box.tpY !== null) ? box.tpY : candlestickSeries.priceToCoordinate(box.takeProfit);

                    // Validiere Koordinaten
                    if (isNaN(entryY) || isNaN(slY) || isNaN(tpY) ||
                        entryY < 0 || slY < 0 || tpY < 0 ||
                        entryY > chartHeight || slY > chartHeight || tpY > chartHeight) {
                        throw new Error('Invalid coordinates from API');
                    }

                    // Aktualisiere Cache nur für neu berechnete Werte
                    if (box.entryY === null) box.entryY = entryY;
                    if (box.slY === null) box.slY = slY;
                    if (box.tpY === null) box.tpY = tpY;

                    console.log('📍 Using mixed cached/calculated coordinates:', {
                        entryY: box.entryY === entryY ? 'cached' : 'calculated',
                        slY: box.slY === slY ? 'cached' : 'calculated',
                        tpY: box.tpY === tpY ? 'cached' : 'calculated'
                    });

                } catch (apiError) {
                        console.warn('❌ API Error, using fallback coordinates:', apiError);
                        // Fallback: Verwende prozentuale Positionen
                        entryY = chartHeight * 0.5;  // Mitte
                        slY = chartHeight * 0.7;     // 70% (unten)
                        tpY = chartHeight * 0.3;     // 30% (oben)

                        // Speichere auch Fallback-Koordinaten
                        box.entryY = entryY;
                        box.slY = slY;
                        box.tpY = tpY;
                    }

                console.log('📊 Drawing at coordinates:', {entryY, slY, tpY, x1, x2});

                // Zeichne Stop Loss Box (rot)
                ctx.fillStyle = 'rgba(242, 54, 69, 0.2)';
                ctx.strokeStyle = '#f23645';
                ctx.lineWidth = 2;
                const slHeight = Math.abs(entryY - slY);
                const slTop = Math.min(entryY, slY);

                if (slHeight > 0) {
                    ctx.fillRect(x1, slTop, x2 - x1, slHeight);
                    ctx.strokeRect(x1, slTop, x2 - x1, slHeight);
                }

                // Zeichne Take Profit Box (grün)
                ctx.fillStyle = 'rgba(8, 153, 129, 0.2)';
                ctx.strokeStyle = '#089981';
                ctx.lineWidth = 2;
                const tpHeight = Math.abs(entryY - tpY);
                const tpTop = Math.min(entryY, tpY);

                if (tpHeight > 0) {
                    ctx.fillRect(x1, tpTop, x2 - x1, tpHeight);
                    ctx.strokeRect(x1, tpTop, x2 - x1, tpHeight);
                }

                // Zeichne Entry Line (weiß)
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.moveTo(x1, entryY);
                ctx.lineTo(x2, entryY);
                ctx.stroke();

                // Zeichne Resize Handles in den Ecken
                drawResizeHandles(x1, x2, slTop, tpTop, slHeight, tpHeight);

                // Zeichne Mülleimer-Symbol (Delete Button)
                drawDeleteButton(x2, Math.min(slTop, tpTop));

                // Speichere Koordinaten für Interaktion
                window.boxCoordinates = {
                    x1, x2, entryY, slY, tpY,
                    slTop, tpTop, slHeight, tpHeight,
                    // Delete Button Koordinaten
                    deleteButtonX: x2,
                    deleteButtonY: Math.min(slTop, tpTop),
                    deleteButtonSize: 20
                };

                console.log('✅ Position Box gezeichnet erfolgreich');

            } catch (error) {
                console.error('❌ Kritischer Fehler beim Zeichnen der Position Box:', error);
                console.error('Error Stack:', error.stack);
            }
        }

        function drawResizeHandles(x1, x2, slTop, tpTop, slHeight, tpHeight) {
            const ctx = window.positionCtx;
            const handleSize = 8;

            // Nur äußere Handles - KEINE auf der Entry-Linie
            const slBottom = slTop + slHeight;
            // SL Box Handles (rot) - nur Bottom (weit unten)
            drawHandle(ctx, x1, slBottom, '#f23645', 'SL-BL'); // Bottom-Left
            drawHandle(ctx, x2, slBottom, '#f23645', 'SL-BR'); // Bottom-Right

            // TP Box Handles (grün) - nur Top (weit oben)
            drawHandle(ctx, x1, tpTop, '#089981', 'TP-TL'); // Top-Left
            drawHandle(ctx, x2, tpTop, '#089981', 'TP-TR'); // Top-Right

            // DEAKTIVIERT: Mittlere Handles für Box-Breite
            // const middleY = (slTop + tpBottom) / 2;
            // drawHandle(ctx, x1, middleY, '#007bff', 'WIDTH-L');
            // drawHandle(ctx, x2, middleY, '#007bff', 'WIDTH-R');

            // Speichere Handle-Positionen - nur äußere Handles
            window.resizeHandles = {
                'SL-BL': {x: x1, y: slBottom, type: 'sl'},
                'SL-BR': {x: x2, y: slBottom, type: 'sl'},
                'TP-TL': {x: x1, y: tpTop, type: 'tp'},
                'TP-TR': {x: x2, y: tpTop, type: 'tp'}
            };
        }

        function drawHandle(ctx, x, y, color, id) {
            const size = 8;
            ctx.fillStyle = color;
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 1;

            ctx.fillRect(x - size/2, y - size/2, size, size);
            ctx.strokeRect(x - size/2, y - size/2, size, size);
        }

        function drawDeleteButton(x, y) {
            const ctx = window.positionCtx;
            const size = 20;
            const iconSize = 12;

            // Button Position: rechts oben an der Box
            const buttonX = x + 5;
            const buttonY = y - 25;

            // Zeichne Button Hintergrund (rot mit Transparenz)
            ctx.fillStyle = 'rgba(242, 54, 69, 0.8)';
            ctx.strokeStyle = '#f23645';
            ctx.lineWidth = 2;
            ctx.fillRect(buttonX - size/2, buttonY - size/2, size, size);
            ctx.strokeRect(buttonX - size/2, buttonY - size/2, size, size);

            // Zeichne Mülleimer-Symbol (vereinfacht als "X")
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.beginPath();
            // X-Symbol
            ctx.moveTo(buttonX - iconSize/2, buttonY - iconSize/2);
            ctx.lineTo(buttonX + iconSize/2, buttonY + iconSize/2);
            ctx.moveTo(buttonX + iconSize/2, buttonY - iconSize/2);
            ctx.lineTo(buttonX - iconSize/2, buttonY + iconSize/2);
            ctx.stroke();

            // Speichere Button Koordinaten für Click-Detection
            if (!window.deleteButtonCoords) window.deleteButtonCoords = {};
            window.deleteButtonCoords = {
                x: buttonX,
                y: buttonY,
                size: size
            };
        }

        // NEUE MOUSE EVENT HANDLERS FÜR BOX-INTERNE RESIZE
        let isDragging = false;
        let dragHandle = null;

        function onCanvasMouseDown(e) {
            const rect = e.target.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            // Check if mouse is over delete button
            if (window.deleteButtonCoords && window.currentPositionBox) {
                const btn = window.deleteButtonCoords;
                const distance = Math.sqrt(
                    Math.pow(mouseX - btn.x, 2) + Math.pow(mouseY - btn.y, 2)
                );

                if (distance <= btn.size/2) {
                    console.log('🗑️ Delete Button geklickt - lösche Position Box');
                    removeCurrentPositionBox();
                    e.preventDefault();
                    return;
                }
            }

            // Check if mouse is over any resize handle
            for (const [id, handle] of Object.entries(window.resizeHandles || {})) {
                const distance = Math.sqrt(
                    Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                );

                if (distance <= 12) { // 12px click tolerance
                    isDragging = true;
                    dragHandle = id;
                    // Cursor für Eckhandles
                    e.target.style.cursor = 'nw-resize'; // Diagonal resize für Eckhandles
                    console.log('🎯 Resize gestartet:', id);
                    return;
                }
            }

            // Check if mouse is over Entry-Linie (weiße Linie)
            if (window.boxCoordinates && window.currentPositionBox) {
                const coords = window.boxCoordinates;
                const entryY = coords.entryY;
                const x1 = coords.x1;
                const x2 = coords.x2;

                // Prüfe ob Klick auf Entry-Linie (Y-Koordinate ±10px, X zwischen x1 und x2)
                if (Math.abs(mouseY - entryY) <= 10 && mouseX >= x1 && mouseX <= x2) {
                    isDragging = true;
                    dragHandle = 'ENTRY-LINE';
                    e.target.style.cursor = 'ns-resize';
                    console.log('🎯 Entry-Linie Drag gestartet');
                }
            }
        }

        function onCanvasMouseMove(e) {
            const rect = e.target.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            if (!isDragging) {
                // Update cursor based on hover over handles
                let cursorType = 'default';
                for (const [id, handle] of Object.entries(window.resizeHandles || {})) {
                    const distance = Math.sqrt(
                        Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                    );
                    if (distance <= 12) {
                        cursorType = 'nw-resize'; // Diagonal für Eckhandles
                        break;
                    }
                }

                // Check hover over Entry-Linie
                if (cursorType === 'default' && window.boxCoordinates && window.currentPositionBox) {
                    const coords = window.boxCoordinates;
                    const entryY = coords.entryY;
                    const x1 = coords.x1;
                    const x2 = coords.x2;

                    if (Math.abs(mouseY - entryY) <= 10 && mouseX >= x1 && mouseX <= x2) {
                        cursorType = 'ns-resize'; // Vertikal für Entry-Linie
                    }
                }

                e.target.style.cursor = cursorType;
                return;
            }

            // Dragging logic - resize the box (HORIZONTAL + VERTIKAL)
            try {
                // SICHERE API AUFRUFE für Coordinate Conversion
                if (!chart || !candlestickSeries) {
                    console.warn('❌ Chart not ready for coordinate conversion');
                    return;
                }

                // Vertical Price änderung
                const newPrice = candlestickSeries.coordinateToPrice(mouseY);

                // Horizontal Time/Width änderung
                const canvas = window.positionCanvas;
                const chartWidth = canvas.width;

                // Berechne neue X-Position als Prozent der Chart-Breite
                const newXPercent = mouseX / chartWidth;

                if (!isNaN(newPrice) && newPrice > 0 && newXPercent >= 0 && newXPercent <= 1) {
                    updateBoxFromHandle(dragHandle, newPrice, newXPercent, mouseX);
                } else {
                    console.warn('❌ Invalid values:', {price: newPrice, xPercent: newXPercent});
                }
            } catch (error) {
                console.error('❌ Fehler beim Box Resize:', error);
                // Fallback: Stoppe Dragging bei Fehler
                isDragging = false;
                dragHandle = null;
                e.target.style.cursor = 'default';
            }
        }

        function onCanvasMouseUp(e) {
            if (isDragging) {
                console.log('🎯 Box Resize beendet:', dragHandle);
                isDragging = false;
                dragHandle = null;
                e.target.style.cursor = 'default';
            }
        }

        function updateBoxFromHandle(handleId, newPrice, newXPercent, mouseX) {
            const box = window.currentPositionBox;
            if (!box) return;

            // ENTRY-LINIE: Verschieben nur Entry-Preis vertikal
            if (handleId === 'ENTRY-LINE') {
                box.entryPrice = newPrice;

                // SOFORTIGE KOORDINATEN-CACHE AKTUALISIERUNG
                box.entryY = candlestickSeries.priceToCoordinate(newPrice);
                console.log('🎯 ENTRY-Koordinate sofort cached:', box.entryY);

                // Update Price Lines mit neuem Entry-Preis
                if (window.positionPriceLines && window.positionPriceLines.entry) {
                    candlestickSeries.removePriceLine(window.positionPriceLines.entry);
                    window.positionPriceLines.entry = candlestickSeries.createPriceLine({
                        price: newPrice,
                        color: '#ffffff',
                        lineWidth: 2,
                        lineStyle: LightweightCharts.LineStyle.Solid,
                        axisLabelVisible: true,
                        title: 'Entry'
                    });
                }

                console.log('📊 ENTRY-LINIE VERSCHOBEN:', {
                    newEntry: newPrice,
                    SL: box.stopLoss,
                    TP: box.takeProfit
                });
            } else {
                // ECKHANDLES: Sowohl Preise als auch Breite ändern

                // Update prices based on which handle was dragged
                if (handleId.includes('SL')) {
                    // BEGRENZUNG: SL darf nicht über Entry-Preis gezogen werden
                    if (newPrice >= box.entryPrice) {
                        console.warn('⚠️ SL darf nicht über Entry-Preis! Entry:', box.entryPrice, 'SL Versuch:', newPrice);
                        newPrice = box.entryPrice - 1; // 1 Punkt unter Entry
                    }
                    box.stopLoss = newPrice;

                    // SOFORTIGE KOORDINATEN-CACHE AKTUALISIERUNG
                    box.slY = candlestickSeries.priceToCoordinate(newPrice);
                    console.log('🎯 SL-Koordinate sofort cached:', box.slY);

                    // Update SL Price Line
                    if (window.positionPriceLines && window.positionPriceLines.stopLoss) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.stopLoss);
                        window.positionPriceLines.stopLoss = candlestickSeries.createPriceLine({
                            price: newPrice,
                            color: '#f23645',
                            lineWidth: 2,
                            lineStyle: LightweightCharts.LineStyle.Solid,
                            axisLabelVisible: true,
                            title: 'SL'
                        });
                    }

                    console.log('📉 SL aktualisiert:', newPrice);
                } else if (handleId.includes('TP')) {
                    // BEGRENZUNG: TP darf nicht unter Entry-Preis gezogen werden
                    if (newPrice <= box.entryPrice) {
                        console.warn('⚠️ TP darf nicht unter Entry-Preis! Entry:', box.entryPrice, 'TP Versuch:', newPrice);
                        newPrice = box.entryPrice + 1; // 1 Punkt über Entry
                    }
                    box.takeProfit = newPrice;

                    // SOFORTIGE KOORDINATEN-CACHE AKTUALISIERUNG
                    box.tpY = candlestickSeries.priceToCoordinate(newPrice);
                    console.log('🎯 TP-Koordinate sofort cached:', box.tpY);

                    // Update TP Price Line
                    if (window.positionPriceLines && window.positionPriceLines.takeProfit) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.takeProfit);
                        window.positionPriceLines.takeProfit = candlestickSeries.createPriceLine({
                            price: newPrice,
                            color: '#089981',
                            lineWidth: 2,
                            lineStyle: LightweightCharts.LineStyle.Solid,
                            axisLabelVisible: true,
                            title: 'TP'
                        });
                    }

                    console.log('📈 TP aktualisiert:', newPrice);
                }

                // Horizontale Resize für Eckhandles
                const isLeftHandle = handleId.includes('-TL') || handleId.includes('-BL');
                const isRightHandle = handleId.includes('-TR') || handleId.includes('-BR');

                if (isLeftHandle) {
                    box.x1Percent = newXPercent;
                    console.log('↔️ ECK: Links Handle bewegt zu X:', mouseX);
                } else if (isRightHandle) {
                    box.x2Percent = newXPercent;
                    console.log('↔️ ECK: Rechts Handle bewegt zu X:', mouseX);
                }
            }

            // Stelle sicher dass x1 < x2
            if (box.x1Percent && box.x2Percent && box.x1Percent > box.x2Percent) {
                const temp = box.x1Percent;
                box.x1Percent = box.x2Percent;
                box.x2Percent = temp;
                console.log('🔄 Box-Seiten getauscht');
            }

            // Redraw the entire position box
            drawPositionBox();
        }

        // VERALTETE FUNKTIONEN ENTFERNT - NUR NOCH CANVAS-BASIERT

        function createPriceLines(entryPrice, stopLoss, takeProfit) {
            // Entferne alte Price Lines falls vorhanden
            removePriceLines();

            // Speichere Price Lines in globaler Variable für späteres Entfernen
            window.positionPriceLines = {};

            try {
                // Entry Price Line (weiß)
                window.positionPriceLines.entry = candlestickSeries.createPriceLine({
                    price: entryPrice,
                    color: '#ffffff',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'Entry'
                });

                // Stop Loss Price Line (rot)
                window.positionPriceLines.stopLoss = candlestickSeries.createPriceLine({
                    price: stopLoss,
                    color: '#f23645',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'SL'
                });

                // Take Profit Price Line (grün)
                window.positionPriceLines.takeProfit = candlestickSeries.createPriceLine({
                    price: takeProfit,
                    color: '#089981',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: 'TP'
                });

                console.log('📊 Price Lines erstellt:', {entry: entryPrice, sl: stopLoss, tp: takeProfit});
            } catch (error) {
                console.error('❌ Fehler beim Erstellen der Price Lines:', error);
            }
        }

        function removePriceLines() {
            // Entferne alle vorhandenen Price Lines
            if (window.positionPriceLines) {
                try {
                    if (window.positionPriceLines.entry) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.entry);
                    }
                    if (window.positionPriceLines.stopLoss) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.stopLoss);
                    }
                    if (window.positionPriceLines.takeProfit) {
                        candlestickSeries.removePriceLine(window.positionPriceLines.takeProfit);
                    }
                } catch (error) {
                    console.warn('⚠️ Fehler beim Entfernen der Price Lines:', error);
                }
                window.positionPriceLines = null;
            }
        }

        function removeCurrentPositionBox() {
            if (window.currentPositionBox) {
                // Entferne Canvas Overlay
                const canvas = document.getElementById('position-canvas');
                if (canvas) {
                    canvas.remove();
                }

                // Entferne Price Lines (DEAKTIVIERT da Price Lines deaktiviert)
                // removePriceLines();

                // Lösche Box Object und globale Variablen
                window.currentPositionBox = null;
                window.positionCanvas = null;
                window.positionCtx = null;
                window.boxCoordinates = null;
                window.resizeHandles = null;

                console.log('🗑️ Position Box entfernt');
            }
        }

        // ===== GLOBAL FUNCTIONS FOR ONCLICK HANDLERS =====
        // Test global scope
        console.log('🌍 Global functions being defined...');

        function togglePositionTool() {
            console.log('📦 Position Box Tool Button geklickt via onclick');
            window.positionBoxMode = !window.positionBoxMode;

            const positionTool = document.getElementById('positionBoxTool');
            if (!positionTool) {
                console.error('❌ positionBoxTool Element nicht gefunden!');
                return;
            }

            if (window.positionBoxMode) {
                // Deaktiviere Short Position Mode wenn Long aktiviert wird
                if (window.shortPositionMode) {
                    window.shortPositionMode = false;
                    const shortTool = document.getElementById('shortPositionTool');
                    if (shortTool) {
                        shortTool.classList.remove('active');
                        shortTool.style.background = '#333';
                        shortTool.style.color = '#fff';
                    }
                }
                // Aktiviere Tool
                positionTool.classList.add('active');
                console.log('📦 Position Box Tool AKTIVIERT');
            } else {
                // Deaktiviere Tool
                positionTool.classList.remove('active');
                positionTool.style.background = '#333';
                positionTool.style.color = '#fff';
                console.log('📦 Position Box Tool DEAKTIVIERT');
            }
        }

        function toggleShortPositionTool() {
            console.log('📉 Short Position Tool Button geklickt via onclick');
            window.shortPositionMode = !window.shortPositionMode;

            const shortTool = document.getElementById('shortPositionTool');
            if (!shortTool) {
                console.error('❌ shortPositionTool Element nicht gefunden!');
                return;
            }

            if (window.shortPositionMode) {
                // Deaktiviere Long Position Mode wenn Short aktiviert wird
                if (window.positionBoxMode) {
                    window.positionBoxMode = false;
                    const positionTool = document.getElementById('positionBoxTool');
                    if (positionTool) {
                        positionTool.classList.remove('active');
                        positionTool.style.background = '#333';
                        positionTool.style.color = '#fff';
                    }
                }
                // Aktiviere Tool
                shortTool.classList.add('active');
                console.log('📉 Short Position Tool AKTIVIERT');
            } else {
                // Deaktiviere Tool
                shortTool.classList.remove('active');
                shortTool.style.background = '#333';
                shortTool.style.color = '#fff';
                console.log('📉 Short Position Tool DEAKTIVIERT');
            }
        }

        function clearAllPositions() {
            console.log('🗑️ Clear All Button geklickt via onclick - FORCE DEAKTIVIERE TOOL');

            try {
                // Deaktiviere beide Position Tools komplett
                window.positionBoxMode = false;
                window.shortPositionMode = false;

                const positionTool = document.getElementById('positionBoxTool');
                if (positionTool) {
                    positionTool.classList.remove('active');
                    positionTool.style.background = '#333';
                    positionTool.style.color = '#fff';
                    console.log('✅ Long Position Tool deaktiviert via onclick');
                } else {
                    console.error('❌ positionBoxTool Element nicht gefunden beim Clear!');
                }

                const shortTool = document.getElementById('shortPositionTool');
                if (shortTool) {
                    shortTool.classList.remove('active');
                    shortTool.style.background = '#333';
                    shortTool.style.color = '#fff';
                    console.log('✅ Short Position Tool deaktiviert via onclick');
                } else {
                    console.error('❌ shortPositionTool Element nicht gefunden beim Clear!');
                }

                // Versuche Position Box zu entfernen (falls vorhanden)
                if (typeof removeCurrentPositionBox === 'function') {
                    removeCurrentPositionBox();
                    console.log('✅ Position Box entfernt');
                } else {
                    console.log('⚠️ removeCurrentPositionBox function not available yet');
                }
            } catch (error) {
                console.error('❌ Fehler in clearAllPositions:', error);
            }
        }

        // ===== TIMEFRAME FUNCTIONS =====
        // High-Performance Timeframe Change Function
        async function changeTimeframe(timeframe) {
            // Prevent double-requests
            if (window.isTimeframeChanging || timeframe === window.currentTimeframe) {
                return;
            }

            console.log(`Wechsle zu Timeframe: ${timeframe}`);
            window.isTimeframeChanging = true;

            try {
                // Check browser cache first
                const cacheKey = `tf_${timeframe}`;
                if (window.timeframeCache.has(cacheKey)) {
                    console.log(`Browser Cache Hit für ${timeframe}`);
                    const cachedData = window.timeframeCache.get(cacheKey);

                    // Instant UI update from cache mit Smart Positioning
                    updateTimeframeButtons(timeframe);
                    candlestickSeries.setData(cachedData);

                    // Smart Positioning: Nach Cache-Hit zurück zu 50-Kerzen Standard
                    if (window.smartPositioning) {
                        window.smartPositioning.resetToStandardPosition(cachedData);
                    }

                    window.currentTimeframe = timeframe;
                    window.isTimeframeChanging = false;
                    return;
                }

                // Optimistic UI update
                updateTimeframeButtons(timeframe);

                // Performance-optimized API call
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout

                const response = await fetch('/api/chart/change_timeframe', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ timeframe: timeframe }),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);
                const result = await response.json();

                if (result.status === 'success' && result.data && result.data.length > 0) {
                    console.log(`Timeframe gewechselt zu ${timeframe}: ${result.count} Kerzen`);

                    // Optimized data formatting - no unnecessary parsing
                    const formattedData = result.data.map(item => ({
                        time: item.time,  // Already correct format
                        open: item.open,  // Already float
                        high: item.high,
                        low: item.low,
                        close: item.close
                    }));

                    // Cache for instant future access
                    window.timeframeCache.set(cacheKey, formattedData);

                    // Limit cache size to prevent memory issues
                    if (window.timeframeCache.size > 8) {
                        const firstKey = window.timeframeCache.keys().next().value;
                        window.timeframeCache.delete(firstKey);
                    }

                    // Fast chart update mit Smart Positioning
                    candlestickSeries.setData(formattedData);

                    // Smart Positioning: Nach Timeframe-Wechsel zurück zu 50-Kerzen Standard
                    if (window.smartPositioning) {
                        window.smartPositioning.resetToStandardPosition(formattedData);
                    }

                    window.currentTimeframe = timeframe;
                } else {
                    console.error('Timeframe-Wechsel fehlgeschlagen:', result.message);
                    updateTimeframeButtons(window.currentTimeframe);
                }

            } catch (error) {
                if (error.name === 'AbortError') {
                    console.warn('Timeframe request timeout');
                } else {
                    console.error('Fehler beim Timeframe-Wechsel:', error);
                }
                updateTimeframeButtons(window.currentTimeframe);
            } finally {
                window.isTimeframeChanging = false;
            }
        }

        // Update Timeframe Button States
        function updateTimeframeButtons(activeTimeframe) {
            const timeframeButtons = document.querySelectorAll('.timeframe-btn');
            timeframeButtons.forEach(btn => {
                const btnTimeframe = btn.getAttribute('data-timeframe');
                if (btnTimeframe === activeTimeframe) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }

        // ============ DEBUG CONTROLS EVENT HANDLERS ============
        // WICHTIG: Funktionen MÜSSEN vor DOMContentLoaded definiert werden!

        // Debug Skip Button Handler
        function handleDebugSkip() {
            console.log('🚀 DEBUG SKIP: +1 Minute - Button clicked!');
            serverLog('🔧 handleDebugSkip called');

            fetch('/api/debug/skip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Debug Skip Response:', data);
                serverLog('✅ Debug Skip successful', data);
            })
            .catch(error => {
                console.error('❌ Debug Skip Error:', error);
                serverLog('❌ Debug Skip failed', error);
            });
        }

        // Debug Play/Pause Button Handler
        function handleDebugPlayPause() {
            console.log('🚀 DEBUG PLAY/PAUSE: Toggle - Button clicked!');
            serverLog('🔧 handleDebugPlayPause called');

            fetch('/api/debug/toggle_play', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Debug PlayPause Response:', data);
                serverLog('✅ Debug PlayPause successful', data);

                // Update button text
                const playPauseBtn = document.getElementById('playPauseBtn');
                if (playPauseBtn) {
                    playPauseBtn.textContent = data.play_mode ? '⏸️' : '▶️';
                }
            })
            .catch(error => {
                console.error('❌ Debug PlayPause Error:', error);
                serverLog('❌ Debug PlayPause failed', error);
            });
        }

        // Warte bis DOM und Script geladen sind
        document.addEventListener('DOMContentLoaded', function() {
            serverLog('🔧 DOM loaded - Initialisiere Chart und Event Handlers...');

            // WICHTIG: Chart zuerst initialisieren
            console.log('🔧 Initialisiere Chart beim DOMContentLoaded...');
            initChart();

            // Registriere Button Event Handlers
            const positionBoxTool = document.getElementById('positionBoxTool');
            const shortPositionTool = document.getElementById('shortPositionTool');
            const clearAllBtn = document.getElementById('clearAll');

            // Debug Button Event Handlers - konsolidiert hier
            // Skip Button
            const skipBtn = document.getElementById('skipBtn');
            console.log('🔧 Debug setup - Skip Button element:', skipBtn);
            if (skipBtn) {
                skipBtn.addEventListener('click', handleDebugSkip);
                console.log('✅ Skip Button event listener attached');
            } else {
                console.error('❌ Skip Button not found!');
            }

            // Play/Pause Button
            const playPauseBtn = document.getElementById('playPauseBtn');
            console.log('🔧 Debug setup - PlayPause Button element:', playPauseBtn);
            if (playPauseBtn) {
                playPauseBtn.addEventListener('click', handleDebugPlayPause);
                console.log('✅ PlayPause Button event listener attached');
            } else {
                console.error('❌ PlayPause Button not found!');
            }

            // Speed Slider
            const speedSlider = document.getElementById('speedSlider');
            const speedDisplay = document.getElementById('speedDisplay');
            if (speedSlider && speedDisplay) {
                speedSlider.addEventListener('input', function() {
                    speedDisplay.textContent = `${this.value}x`;
                });

                speedSlider.addEventListener('change', function() {
                    handleDebugSpeed(this.value);
                });
            }

            // Timeframe Selector
            const timeframeSelector = document.getElementById('timeframeSelector');
            if (timeframeSelector) {
                timeframeSelector.addEventListener('change', function() {
                    handleDebugTimeframe(this.value);
                });
            }

            console.log('🛠️ Debug Controls Event Handlers konsolidiert und initialized');

            if (positionBoxTool) {
                positionBoxTool.addEventListener('click', togglePositionTool);
                console.log('✅ Position Box Tool Event Handler registriert');
            } else {
                console.error('❌ positionBoxTool Button nicht gefunden');
            }

            if (shortPositionTool) {
                shortPositionTool.addEventListener('click', toggleShortPositionTool);
                console.log('✅ Short Position Tool Event Handler registriert');
            } else {
                console.error('❌ shortPositionTool Button nicht gefunden');
            }

            if (clearAllBtn) {
                clearAllBtn.addEventListener('click', clearAllPositions);
                console.log('✅ Clear All Button Event Handler registriert');
            } else {
                console.error('❌ clearAll Button nicht gefunden');
            }

            // Registriere Timeframe Button Event Handlers
            const timeframeButtons = document.querySelectorAll('.timeframe-btn');
            timeframeButtons.forEach(btn => {
                const timeframe = btn.getAttribute('data-timeframe');
                btn.addEventListener('click', () => changeTimeframe(timeframe));
                console.log(`✅ Timeframe Button ${timeframe} Event Handler registriert`);
            });

            if (timeframeButtons.length > 0) {
                console.log(`✅ ${timeframeButtons.length} Timeframe Buttons Event Handler registriert`);
            } else {
                console.error('❌ Keine Timeframe Buttons gefunden');
            }

            // Zusätzliche Sicherheit: Prüfe ob LightweightCharts verfügbar ist
            if (typeof LightweightCharts !== 'undefined') {
                console.log('✅ LightweightCharts library loaded');
                // DIREKT TESTEN: Chart erstellen ohne loadChart()
                try {
                    serverLog('🔧 DIRECT CHART TEST - Starting detailed debug...');

                    // 1. Container Debug
                    const container = document.getElementById('chart_container');
                    serverLog('🔍 Container Debug:', {
                        gefunden: !!container,
                        clientWidth: container?.clientWidth,
                        clientHeight: container?.clientHeight,
                        offsetWidth: container?.offsetWidth,
                        offsetHeight: container?.offsetHeight,
                        rect: container?.getBoundingClientRect()
                    });

                    if (!container) {
                        console.error('❌ Chart container nicht gefunden! ID: chart_container');
                        return;
                    }

                    // 2. LightweightCharts Debug
                    console.log('🔍 LightweightCharts Debug:');
                    console.log('  - LightweightCharts verfügbar:', typeof LightweightCharts);
                    console.log('  - createChart function:', typeof LightweightCharts.createChart);

                    // 3. Chart Creation Debug
                    console.log('🔧 Creating chart with options...');
                    const chartOptions = {
                        width: 800,
                        height: 600,
                        timeScale: { timeVisible: true },
                        grid: { vertLines: { visible: false }, horzLines: { visible: false } },
                        layout: {
                            background: { type: 'solid', color: '#FFFFFF' },
                            textColor: '#333'
                        }
                    };
                    console.log('  - Chart Options:', chartOptions);

                    const chart = LightweightCharts.createChart(container, chartOptions);
                    console.log('✅ Chart object created:', chart);

                    // 4. Series Debug
                    console.log('🔧 Adding candlestick series...');
                    const candlestickSeries = chart.addCandlestickSeries({
                        upColor: '#089981',
                        downColor: '#f23645',
                        borderVisible: false,
                        wickUpColor: '#089981',
                        wickDownColor: '#f23645'
                    });
                    console.log('✅ Candlestick series created:', candlestickSeries);

                    // 5. API Call Debug
                    console.log('🔧 Fetching chart data...');
                    fetch('/api/chart/data')
                        .then(response => {
                            console.log('📡 API Response Status:', response.status);
                            console.log('📡 API Response OK:', response.ok);
                            return response.json();
                        })
                        .then(data => {
                            console.log('📊 DETAILED DATA DEBUG:');
                            console.log('  - Data object:', data);
                            console.log('  - Data.data exists:', !!data.data);
                            console.log('  - Data.data length:', data.data?.length);
                            console.log('  - First 3 candles:', data.data?.slice(0, 3));
                            console.log('  - Last 3 candles:', data.data?.slice(-3));

                            if (data.data && data.data.length > 0) {
                                console.log('🔧 Setting data on candlestick series...');
                                candlestickSeries.setData(data.data);
                                console.log('✅ Data set successfully!');

                                // 6. Chart Rendering Debug
                                console.log('🔍 POST-RENDER DEBUG:');
                                setTimeout(() => {
                                    console.log('  - Container nach Render clientWidth:', container.clientWidth);
                                    console.log('  - Container nach Render clientHeight:', container.clientHeight);
                                    const canvasElements = container.querySelectorAll('canvas');
                                    console.log('  - Anzahl Canvas Elemente:', canvasElements.length);
                                    canvasElements.forEach((canvas, i) => {
                                        console.log(`  - Canvas ${i}: ${canvas.width}x${canvas.height}`);
                                    });
                                }, 1000);

                                console.log('✅ CHART ERFOLGREICH GELADEN!');
                            } else {
                                console.error('❌ Keine Daten erhalten oder leeres Array');
                            }
                        })
                        .catch(error => {
                            console.error('❌ Chart API Error Details:');
                            console.error('  - Error object:', error);
                            console.error('  - Error message:', error.message);
                            console.error('  - Error stack:', error.stack);
                        });

                } catch (error) {
                    console.error('❌ DIRECT CHART ERROR:', error);
                }
                connectWebSocket();
                loadAccountData(); // Lade initiale Account-Daten
            } else {
                console.error('❌ LightweightCharts library not loaded');
                // Fallback: Versuche nochmal nach kurzer Wartezeit
                setTimeout(() => {
                    if (typeof LightweightCharts !== 'undefined') {
                        console.log('✅ LightweightCharts library loaded (delayed)');
                        // DIREKT TESTEN: Chart erstellen (2. Fallback)
                        try {
                            console.log('🔧 FALLBACK CHART TEST - Creating chart...');
                            const chart = LightweightCharts.createChart(document.getElementById('chart_container'), {
                                width: 800,
                                height: 600,
                                timeScale: { timeVisible: true },
                                grid: { vertLines: { visible: false }, horzLines: { visible: false } }
                            });

                            const candlestickSeries = chart.addCandlestickSeries();

                            fetch('/api/chart/data')
                                .then(response => response.json())
                                .then(data => {
                                    console.log('🔧 FALLBACK - Daten empfangen:', data);
                                    if (data.data && data.data.length > 0) {
                                        candlestickSeries.setData(data.data);
                                        console.log('✅ FALLBACK CHART ERFOLGREICH!');
                                    }
                                })
                                .catch(error => console.error('❌ Fallback Chart Error:', error));

                        } catch (error) {
                            console.error('❌ FALLBACK CHART ERROR:', error);
                        }
                        connectWebSocket();
                        loadAccountData(); // Lade initiale Account-Daten
                    } else {
                        console.error('❌ LightweightCharts library failed to load');
                    }
                }, 1000);
            }
        });
    </script>
</body>
</html>
    """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket Endpoint für Realtime-Communication"""
    await manager.connect(websocket)

    try:
        while True:
            # Warte auf Nachrichten vom Client (falls nötig)
            data = await websocket.receive_text()
            # Hier könnten Client-Nachrichten verarbeitet werden

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")

@app.post("/api/chart/set_data")
async def set_chart_data(data: dict):
    """API Endpoint um Chart-Daten zu setzen"""

    # Update Chart State
    manager.update_chart_state({
        'type': 'set_data',
        'data': data.get('data', []),
        'symbol': data.get('symbol', 'NQ=F'),
        'interval': data.get('interval', '5m')
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'set_data',
        'data': data.get('data', []),
        'symbol': data.get('symbol', 'NQ=F'),
        'interval': data.get('interval', '5m')
    })

    return {"status": "success", "message": "Chart data updated"}

@app.post("/api/chart/add_candle")
async def add_candle(candle_data: dict):
    """API Endpoint um neue Kerze hinzuzufügen"""

    candle = candle_data.get('candle')
    if not candle:
        return {"status": "error", "message": "No candle data provided"}

    # Update Chart State
    manager.update_chart_state({
        'type': 'add_candle',
        'candle': candle
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'add_candle',
        'candle': candle
    })

    return {"status": "success", "message": "Candle added"}

@app.post("/api/chart/add_position")
async def add_position(position_data: dict):
    """API Endpoint um Position Overlay hinzuzufügen"""

    position = position_data.get('position')
    if not position:
        return {"status": "error", "message": "No position data provided"}

    # Update Chart State
    manager.update_chart_state({
        'type': 'add_position',
        'position': position
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'add_position',
        'position': position
    })

    return {"status": "success", "message": "Position overlay added"}

@app.post("/api/chart/remove_position")
async def remove_position(position_data: dict):
    """API Endpoint um Position Overlay zu entfernen"""

    position_id = position_data.get('position_id')
    if not position_id:
        return {"status": "error", "message": "No position_id provided"}

    # Update Chart State
    manager.update_chart_state({
        'type': 'remove_position',
        'position_id': position_id
    })

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'remove_position',
        'position_id': position_id
    })

    return {"status": "success", "message": "Position overlay removed"}

@app.post("/api/chart/sync_positions")
async def sync_positions(positions_data: dict):
    """API Endpoint um alle Positionen zu synchronisieren"""

    positions = positions_data.get('positions', [])

    # Update Chart State
    manager.chart_state['positions'] = positions

    # Broadcast an alle Clients
    await manager.broadcast({
        'type': 'positions_sync',
        'positions': positions
    })

    return {"status": "success", "message": f"Synchronized {len(positions)} positions"}

@app.get("/api/chart/status")
async def get_chart_status():
    """Chart Status und Verbindungsinfo"""
    return {
        "status": "running",
        "connections": len(manager.active_connections),
        "chart_state": {
            "symbol": manager.chart_state['symbol'],
            "interval": manager.chart_state['interval'],
            "candles_count": len(manager.chart_state['data']),
            "last_update": manager.chart_state['last_update']
        }
    }

@app.get("/api/chart/data")
async def get_chart_data():
    """Aktuelle Chart-Daten zurückgeben - Korrekt formatiert für TradingView"""
    chart_data = manager.chart_state['data']

    # Debug-Ausgabe für Datenvalidierung
    print(f"API /chart/data: Sende {len(chart_data)} Kerzen")
    if chart_data:
        first_candle = chart_data[0]
        print(f"Erste Kerze: time={first_candle.get('time')}, open={first_candle.get('open')}")

    return {
        "data": chart_data,  # Unix Timestamps direkt verwenden
        "symbol": manager.chart_state['symbol'],
        "interval": manager.chart_state['interval'],
        "count": len(chart_data),
        "format": "unix_timestamp"  # Frontend-Hinweis für Zeitformat
    }

@app.post("/api/chart/change_timeframe")
async def change_timeframe(request: dict):
    """Ändert den Timeframe und gibt aggregierte Daten zurück - DIREKT AUS CSV"""
    timeframe = request.get('timeframe', '5m')
    visible_candles = request.get('visible_candles', 50)  # Default 50 für Standard-Zoom

    print(f"=== API CALL DEBUG ===")
    print(f"Timeframe-Wechsel zu: {timeframe} mit {visible_candles} sichtbaren Kerzen")
    print(f"Vollständiger Request: {request}")
    print(f"Aktive Connections: {len(manager.active_connections)}")
    print(f"=== END DEBUG ===")

    try:
        import pandas as pd
        from pathlib import Path

        # Direkter CSV-Load (Option 2 Struktur)
        csv_path = Path(f"src/data/aggregated/{timeframe}/nq-2024.csv")

        if not csv_path.exists():
            return {"status": "error", "message": f"CSV-Datei für {timeframe} nicht gefunden: {csv_path}"}

        # CSV laden
        df = pd.read_csv(csv_path)

        # Lade 200 Kerzen als Puffer (nicht visible_candles)
        buffer_candles = 200
        if len(df) > buffer_candles:
            result_df = df.tail(buffer_candles)
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

@app.post("/api/chart/load_historical")
async def load_historical_data(request: dict):
    """Lädt historische Daten für Lazy Loading mit dynamischen visible_candles"""
    timeframe = request.get('timeframe', '1m')
    before_timestamp = request.get('before_timestamp')
    chunk_size = request.get('chunk_size')
    visible_candles = request.get('visible_candles')  # Vom Frontend

    if before_timestamp is None:
        return {"status": "error", "message": "before_timestamp ist erforderlich"}

    print(f"Lade historische Daten für {timeframe} vor Timestamp {before_timestamp}")

    try:
        # Prüfe ob Roh-1m-Daten verfügbar sind
        if manager.chart_state['raw_1m_data'] is None:
            # Lade komplettes Jahr 2024 für historische Daten
            data_2024 = nq_loader.load_year(2024)
            if data_2024 is not None:
                manager.chart_state['raw_1m_data'] = data_2024
            else:
                return {"status": "error", "message": "Keine 1m-Daten verfügbar"}

        # Lazy Loading: Lade historischen Datenblock
        historical_data = performance_aggregator.get_historical_data_lazy(
            manager.chart_state['raw_1m_data'],
            timeframe,
            before_timestamp,
            chunk_size
        )

        # Berechne Info für Logs mit dynamischen visible_candles
        if visible_candles:
            initial_candles = performance_aggregator.calculate_initial_candles(visible_candles)
            chunk_info = performance_aggregator.calculate_chunk_size(visible_candles)
        else:
            initial_candles = performance_aggregator.calculate_initial_candles(timeframe=timeframe)
            chunk_info = performance_aggregator.calculate_chunk_size(timeframe=timeframe)

        # Broadcast an alle verbundenen Clients
        await manager.broadcast({
            'type': 'historical_data_loaded',
            'data': historical_data,
            'timeframe': timeframe,
            'count': len(historical_data),
            'before_timestamp': before_timestamp,
            'lazy_loading_info': {
                'initial_candles': initial_candles,
                'chunk_size': chunk_info
            }
        })

        print(f"Historische Daten geladen für {timeframe}: {len(historical_data)} Kerzen vor {before_timestamp}")

        return {
            "status": "success",
            "timeframe": timeframe,
            "data": historical_data,
            "count": len(historical_data),
            "before_timestamp": before_timestamp,
            "lazy_loading_info": {
                'initial_candles': initial_candles,
                'chunk_size': chunk_info
            }
        }

    except Exception as e:
        print(f"Fehler beim Laden historischer Daten: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/chart/lazy_loading_info")
async def get_lazy_loading_info():
    """Gibt Lazy Loading Konfiguration zurück"""
    try:
        timeframes_info = {}
        for timeframe in ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']:
            initial_candles = performance_aggregator.calculate_initial_candles(timeframe)
            chunk_size = performance_aggregator.calculate_chunk_size(timeframe)
            timeframes_info[timeframe] = {
                'initial_candles': initial_candles,
                'chunk_size': chunk_size,
                'visible_candles': performance_aggregator.timeframe_config[timeframe]['visible_candles']
            }

        return {
            "status": "success",
            "lazy_loading_multiplier": performance_aggregator.lazy_loading_multiplier,
            "chunk_size_multiplier": performance_aggregator.chunk_size_multiplier,
            "timeframes": timeframes_info
        }

    except Exception as e:
        print(f"Fehler beim Abrufen der Lazy Loading Info: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/account/status")
async def get_account_status():
    """API Endpunkt für Account Status beider Accounts"""
    try:
        ai_summary = account_service.get_ai_account_summary()
        user_summary = account_service.get_user_account_summary()

        return {
            "status": "success",
            "ai_account": ai_summary,
            "user_account": user_summary
        }
    except Exception as e:
        print(f"Fehler beim Abrufen des Account Status: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/account/update_ai_pnl")
async def update_ai_pnl(pnl_data: dict):
    """API Endpunkt für KI PnL Updates"""
    try:
        unrealized_pnl = pnl_data.get("unrealized_pnl", 0.0)
        account_service.update_ai_position(unrealized_pnl)

        return {
            "status": "success",
            "message": "KI PnL aktualisiert",
            "ai_account": account_service.get_ai_account_summary()
        }
    except Exception as e:
        print(f"Fehler beim Aktualisieren der KI PnL: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/account/update_user_pnl")
async def update_user_pnl(pnl_data: dict):
    """API Endpunkt für Nutzer PnL Updates"""
    try:
        unrealized_pnl = pnl_data.get("unrealized_pnl", 0.0)
        account_service.update_user_position(unrealized_pnl)

        return {
            "status": "success",
            "message": "Nutzer PnL aktualisiert",
            "user_account": account_service.get_user_account_summary()
        }
    except Exception as e:
        print(f"Fehler beim Aktualisieren der Nutzer PnL: {e}")
        return {"status": "error", "message": str(e)}

# ===== DEBUG API ENDPOINTS =====

@app.post("/api/debug/skip")
async def debug_skip():
    """API Endpoint für Debug Skip (+1 Minute)"""
    try:
        result = debug_controller.skip_minute()

        # Extrahiere Kerze aus dem Ergebnis
        if result.get('type') == 'complete_candle':
            new_candle = result['candle']
            # Neue vollständige Kerze zu Chart-Daten hinzufügen
            manager.chart_state['data'].append(new_candle)
        else:
            # Incomplete Kerze - markiere als solche
            new_candle = result['candle']
            new_candle['incomplete'] = True

        # WebSocket-Update an alle Clients (konvertiere datetime für JSON-Serialisierung)
        candle_for_ws = new_candle.copy()
        if 'period_start' in candle_for_ws and hasattr(candle_for_ws['period_start'], 'isoformat'):
            candle_for_ws['period_start'] = candle_for_ws['period_start'].isoformat()

        await manager.broadcast({
            'type': 'debug_skip',
            'candle': candle_for_ws,
            'result_type': result.get('type')
        })

        return {
            "status": "success",
            "message": f"Skip +1min erfolgreich ({result.get('type')})",
            "candle": new_candle,
            "result_type": result.get('type'),
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Debug Skip: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/set_timeframe/{timeframe}")
async def debug_set_timeframe(timeframe: str):
    """API Endpoint um Debug Timeframe zu ändern"""
    try:
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h"]
        if timeframe not in valid_timeframes:
            return {"status": "error", "message": f"Ungültiger Timeframe. Erlaubt: {valid_timeframes}"}

        debug_controller.set_timeframe(timeframe)

        # WebSocket-Update an alle Clients
        await manager.broadcast({
            'type': 'debug_timeframe_changed',
            'timeframe': timeframe,
            'debug_state': debug_controller.get_state()
        })

        return {
            "status": "success",
            "message": f"Timeframe auf {timeframe} gesetzt",
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Setzen des Timeframes: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/set_speed")
async def debug_set_speed(speed_data: dict):
    """API Endpoint um Debug Speed zu ändern"""
    try:
        speed = speed_data.get("speed", 2)
        debug_controller.set_speed(speed)

        # WebSocket-Update an alle Clients
        await manager.broadcast({
            'type': 'debug_speed_changed',
            'speed': speed,
            'debug_state': debug_controller.get_state()
        })

        return {
            "status": "success",
            "message": f"Geschwindigkeit auf {speed}x gesetzt",
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Setzen der Geschwindigkeit: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/toggle_play")
async def debug_toggle_play():
    """API Endpoint um Play/Pause zu togglen"""
    try:
        play_mode = debug_controller.toggle_play_mode()

        # WebSocket-Update an alle Clients (ohne debug_state wegen JSON-Serialisierung)
        await manager.broadcast({
            'type': 'debug_play_toggled',
            'play_mode': play_mode
        })

        return {
            "status": "success",
            "message": f"Play-Modus {'aktiviert' if play_mode else 'deaktiviert'}",
            "play_mode": play_mode,
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Toggle Play/Pause: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/debug/state")
async def debug_get_state():
    """API Endpoint um aktuellen Debug-Status zu holen"""
    try:
        return {
            "status": "success",
            "debug_state": debug_controller.get_state()
        }

    except Exception as e:
        print(f"Fehler beim Holen des Debug-Status: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/debug/log")
async def debug_log_from_client(request: Request):
    """API Endpoint für JavaScript Debug-Logs im Terminal"""
    try:
        data = await request.json()
        message = data.get('message', 'No message')
        timestamp = data.get('timestamp', '')
        log_data = data.get('data', None)

        # Im Terminal ausgeben mit Prefix für JavaScript-Logs
        print(f"[JS-DEBUG] [{timestamp}]: {message}")
        if log_data:
            print(f"    ↳ Data: {log_data}")

        return {"status": "success"}
    except Exception as e:
        print(f"Fehler beim JavaScript Debug-Log: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Debug Route
    @app.get("/debug")
    async def debug_chart():
        """Debug Chart Page"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Debug Chart</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        #chart { width: 100%; height: 600px; }
        .status { margin: 10px; padding: 10px; background: #f0f0f0; }
    </style>
</head>
<body>
    <h1>🔧 Debug Chart - Teste NQ Daten</h1>
    <div class="status" id="status">Status: Initialisiere...</div>
    <div id="chart"></div>

    <script>
        const statusDiv = document.getElementById('status');

        function updateStatus(message) {
            statusDiv.innerHTML = `Status: ${message}`;
            console.log(message);
        }

        async function loadChart() {
            try {
                updateStatus('Erstelle Chart...');

                const chart = LightweightCharts.createChart(document.getElementById('chart_container'), {
                    width: document.getElementById('chart_container').clientWidth,
                    height: 600,
                    timeScale: { timeVisible: true },
                    grid: { vertLines: { color: '#e1e1e1' }, horzLines: { color: '#e1e1e1' } }
                });

                const candlestickSeries = chart.addCandlestickSeries();

                updateStatus('Lade Daten von Server...');

                const response = await fetch('/api/chart/data');
                const chartData = await response.json();

                updateStatus(`Daten erhalten: ${chartData.data?.length || 0} Kerzen`);

                if (chartData.data && chartData.data.length > 0) {
                    const formattedData = chartData.data.map(item => ({
                        time: item.time,  // Unix Timestamp direkt verwenden (keine Konvertierung!)
                        open: parseFloat(item.open),
                        high: parseFloat(item.high),
                        low: parseFloat(item.low),
                        close: parseFloat(item.close)
                    }));

                    candlestickSeries.setData(formattedData);

                    // Smart Positioning: 50 Kerzen Standard mit 20% Freiraum
                    if (window.smartPositioning) {
                        window.smartPositioning.setStandardPosition(formattedData);
                    }

                    updateStatus(`✅ SUCCESS: ${formattedData.length} NQ-Kerzen geladen!`);
                } else {
                    updateStatus('❌ FEHLER: Keine Daten empfangen');
                }

            } catch (error) {
                updateStatus(`❌ FEHLER: ${error.message}`);
                console.error('Chart Error:', error);
            }
        }

    </script>
</body>
</html>
        """

        return HTMLResponse(content=html_content)

    @app.get("/debug")
    async def debug_chart():
        """Debug Chart Page"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>NQ Debug Chart</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body { margin: 0; padding: 20px; background: #f0f0f0; font-family: Arial, sans-serif; }
        h1 { text-align: center; }
        .status { text-align: center; font-weight: bold; margin: 10px 0; }
        #chart { margin: 0 auto; border: 1px solid #ccc; }
    </style>
</head>
<body>
    <h1>🔧 Debug Chart - Teste NQ Daten</h1>
    <div class="status" id="status">Status: Initialisiere...</div>
    <div id="chart"></div>

    <script>
        function updateStatus(message) {
            document.getElementById('status').textContent = message;
            console.log(message);
        }

        async function loadChart() {
            try {
                updateStatus('Erstelle Chart...');

                const chart = LightweightCharts.createChart(document.getElementById('chart'), {
                    width: document.getElementById('chart_container').clientWidth,
                    height: 600,
                    timeScale: { timeVisible: true },
                    grid: { vertLines: { color: '#e1e1e1' }, horzLines: { color: '#e1e1e1' } }
                });

                const candlestickSeries = chart.addCandlestickSeries();

                updateStatus('Lade Daten von Server...');

                const response = await fetch('/api/chart/data');
                const chartData = await response.json();

                console.log('Chart Data received:', chartData);

                if (chartData.data && chartData.data.length > 0) {
                    candlestickSeries.setData(chartData.data);
                    updateStatus(`✅ ${chartData.data.length} Kerzen geladen`);
                } else {
                    updateStatus('❌ Keine Daten empfangen');
                }

            } catch (error) {
                updateStatus(`❌ FEHLER: ${error.message}`);
                console.error('Chart Error:', error);
            }
        }

        // Starte Chart-Loading nach DOM-Load
        document.addEventListener('DOMContentLoaded', loadChart);
    </script>
</body>
</html>
        """

        return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        access_log=False
    )
