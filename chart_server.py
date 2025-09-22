"""
FastAPI Chart Server für RL Trading
Realtime Chart-Updates ohne Streamlit-Limitations
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
from typing import Dict, List, Any
import uvicorn
from datetime import datetime
import logging
import sys
import os

# Füge src Verzeichnis zum Pfad hinzu
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Importiere NQ Data Loader und Performance Aggregator
from data.nq_data_loader import NQDataLoader
from data.performance_aggregator import get_performance_aggregator

# FastAPI App
app = FastAPI(title="RL Trading Chart Server", version="1.0.0")

# Globaler NQ Data Loader und Performance Aggregator
nq_loader = NQDataLoader()
performance_aggregator = get_performance_aggregator()

# Lade initiale Chart-Daten aus CSV (schneller Startup)
print("Lade initiale 5m Chart-Daten aus CSV...")
try:
    import pandas as pd
    from pathlib import Path

    csv_path = Path("src/data/aggregated/5m/nq-2024.csv")
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        result_df = df.tail(200)  # Letzte 200 Kerzen als Puffer

        initial_chart_data = []
        for _, row in result_df.iterrows():
            initial_chart_data.append({
                'time': int(row['time']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume'])
            })
        print(f"ERFOLG: Geladen: {len(initial_chart_data)} 5m Kerzen aus CSV")
    else:
        initial_chart_data = []
        print("FEHLER: CSV nicht gefunden - verwende leere Daten")
except Exception as e:
    print(f"FEHLER beim CSV-Laden: {e}")
    initial_chart_data = []

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

# Global Connection Manager
manager = ConnectionManager()

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
        #chart_container { width: calc(100% - 35px); height: calc(100vh - 120px); margin-left: 35px; } /* Angepasst für vier Toolbars */
        .status { position: fixed; top: 10px; right: 10px; color: #fff; background: rgba(0,0,0,0.7); padding: 5px 10px; border-radius: 5px; font-size: 12px; }
        .status.connected { color: #089981; }
        .status.disconnected { color: #f23645; }
        /* Erste Chart-Toolbar (leer, oberhalb) */
        .chart-toolbar-1 { position: fixed; top: 0; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Zweite Chart-Toolbar (Timeframes, darunter) */
        .chart-toolbar-2 { position: fixed; top: 40px; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Legacy toolbar class für Kompatibilität */
        .toolbar { position: fixed; top: 40px; left: 0; right: 0; height: 40px; background: #1e1e1e; border-bottom: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Bottom Chart-Toolbar (unten) */
        .chart-toolbar-bottom { position: fixed; bottom: 0; left: 35px; right: 0; height: 40px; background: #1e1e1e; border-top: 1px solid #333; display: flex; align-items: center; padding: 0; margin: 0; gap: 12px; z-index: 1000; }

        /* Left Chart-Sidebar (links) */
        .chart-sidebar-left { position: fixed; top: 80px; bottom: 40px; left: 0; width: 35px; background: #1e1e1e; border-right: 1px solid #333; display: flex; flex-direction: column; align-items: center; padding: 0; margin: 0; gap: 10px; z-index: 1000; }
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
    </style>
</head>
<body>
    <!-- Erste Chart-Toolbar (leer) -->
    <div class="chart-toolbar-1">
        <!-- Leer - für zukünftige Funktionen -->
    </div>

    <!-- Zweite Chart-Toolbar (Timeframes) -->
    <div class="chart-toolbar-2">
        <button id="positionBoxTool" class="tool-btn">📦 Position Box</button>
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
        <!-- Leer - für zukünftige Funktionen -->
    </div>

    <!-- Bottom Chart-Toolbar (unten) -->
    <div class="chart-toolbar-bottom">
        <!-- Leer - für zukünftige Funktionen -->
    </div>

    <div id="status" class="status disconnected">Disconnected</div>
    <div id="chart_container"></div>

    <script>
        console.log('🚀 RL Trading Chart - FastAPI Edition');

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
                width: window.innerWidth,
                height: window.innerHeight,
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
                    width: window.innerWidth,
                    height: window.innerHeight
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

                if (window.positionBoxMode && param.point) {
                    const price = candlestickSeries.coordinateToPrice(param.point.y);
                    const clickX = param.point.x; // ⭐ Click-X-Koordinate erfassen
                    const clickY = param.point.y; // ⭐ Click-Y-Koordinate erfassen

                    // Verwende param.time falls vorhanden (Kerzen-Klick), sonst aktuelle Zeit (freier Bereich)
                    const timeForBox = param.time || Math.floor(Date.now() / 1000);

                    console.log('📦 Erstelle Position Box bei Preis:', price, 'an X-Position:', clickX, 'Y-Position:', clickY, 'Zeit:', timeForBox);
                    createPositionBox(timeForBox, price, clickX, clickY);
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
        function createPositionBox(time, entryPrice, clickX, clickY) {
            // Entferne alte Position Box falls vorhanden
            if (window.currentPositionBox) {
                removeCurrentPositionBox();
            }

            // Kleinere SL/TP für bessere Sichtbarkeit (0.25% Risk, 0.5% Reward)
            const riskPercent = 0.0025; // 0.25%
            const rewardPercent = 0.005; // 0.5%

            const stopLoss = entryPrice * (1 - riskPercent);
            const takeProfit = entryPrice * (1 + rewardPercent);

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

        function clearAllPositions() {
            console.log('🗑️ Clear All Button geklickt via onclick - FORCE DEAKTIVIERE TOOL');

            try {
                // Deaktiviere Position Box Tool komplett
                window.positionBoxMode = false;
                const positionTool = document.getElementById('positionBoxTool');
                if (positionTool) {
                    positionTool.classList.remove('active');
                    positionTool.style.background = '#333';
                    positionTool.style.color = '#fff';
                    console.log('✅ Position Tool deaktiviert via onclick');
                } else {
                    console.error('❌ positionBoxTool Element nicht gefunden beim Clear!');
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

        // Warte bis DOM und Script geladen sind
        document.addEventListener('DOMContentLoaded', function() {
            console.log('🔧 DOM loaded - Registriere Button Event Handlers...');

            // Registriere Button Event Handlers
            const positionBoxTool = document.getElementById('positionBoxTool');
            const clearAllBtn = document.getElementById('clearAll');

            if (positionBoxTool) {
                positionBoxTool.addEventListener('click', togglePositionTool);
                console.log('✅ Position Box Tool Event Handler registriert');
            } else {
                console.error('❌ positionBoxTool Button nicht gefunden');
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
                initChart();
                connectWebSocket();
            } else {
                console.error('❌ LightweightCharts library not loaded');
                // Fallback: Versuche nochmal nach kurzer Wartezeit
                setTimeout(() => {
                    if (typeof LightweightCharts !== 'undefined') {
                        console.log('✅ LightweightCharts library loaded (delayed)');
                        initChart();
                        connectWebSocket();
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
    """Aktuelle Chart-Daten zurückgeben"""
    return {
        "data": manager.chart_state['data'],
        "symbol": manager.chart_state['symbol'],
        "interval": manager.chart_state['interval'],
        "count": len(manager.chart_state['data'])
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
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
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

                const chart = LightweightCharts.createChart(document.getElementById('chart'), {
                    width: document.getElementById('chart').clientWidth,
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
                        time: Math.floor(new Date(item.time).getTime() / 1000),
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

        document.addEventListener('DOMContentLoaded', loadChart);
    </script>
</body>
</html>
"""
        return HTMLResponse(content=html_content)

    print("Starting RL Trading Chart Server...")
    print("Chart: http://localhost:8003")
    print("Debug: http://localhost:8003/debug")
    print("WebSocket: ws://localhost:8003/ws")
    print("API: http://localhost:8003/docs")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        log_level="info",
        reload=False  # Disable reload for production
    )