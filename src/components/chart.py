"""
Chart-Komponente für TradingView Lightweight Charts
Zentrale Logik für Chart-Erstellung und -Konfiguration
"""

import json
import time
from config.settings import CHART_CONFIG, CANDLESTICK_CONFIG

def create_trading_chart(data_dict, trades=None, show_volume=True, show_ma20=True, show_ma50=False, show_bollinger=False, selected_symbol="AAPL", selected_interval="1h", debug_start_timestamp=None, chart_update_data=None):
    """
    Erstellt den HTML-Code für TradingView Lightweight Charts

    Args:
        data_dict (dict): Daten-Dictionary mit OHLCV Daten
        trades (list): Liste der Trades (optional)
        show_volume (bool): Volume anzeigen
        show_ma20 (bool): 20-Period Moving Average anzeigen
        show_ma50 (bool): 50-Period Moving Average anzeigen
        show_bollinger (bool): Bollinger Bands anzeigen
        selected_symbol (str): Aktuelles Symbol
        selected_interval (str): Aktuelles Intervall

    Returns:
        str: HTML-Code für den Chart
    """
    if not data_dict or data_dict['data'].empty:
        return "<div style='padding: 20px; text-align: center; color: #ff6b6b;'>Keine Daten verfügbar</div>"

    df = data_dict['data']
    chart_data = _prepare_chart_data(df)
    # Verwende Session State für konsistente Chart-ID
    import streamlit as st
    if 'chart_id' not in st.session_state:
        st.session_state.chart_id = f'chart_{int(time.time() * 1000)}'
    chart_id = st.session_state.chart_id

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>RL Trading Chart - {selected_symbol}</title>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #1e1e1e;
                color: #fff;
            }}
            .toolbar {{
                background: #2d2d2d;
                padding: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
                border-bottom: 1px solid #404040;
            }}
            .tool-btn {{
                background: #007bff;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                transition: background-color 0.2s;
            }}
            .tool-btn:hover {{
                background: #0056b3;
            }}
            .tool-btn.active {{
                background: #28a745;
            }}
            .chart-info {{
                color: #999;
                margin-left: 20px;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="toolbar">
            <button id="positionBoxTool" class="tool-btn">📦 Position Box</button>
            <button id="clearAll" class="tool-btn">🗑️</button>
            <span class="chart-info">Click auf Chart um Position Box zu platzieren</span>
        </div>
        <div id="{chart_id}" style="width: {CHART_CONFIG['width']}px; height: {CHART_CONFIG['height']}px; background: #000; position: relative;"></div>

        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>

        <script>
            console.log('🚀 RL TRADING CHART: Starte für {selected_symbol}...');

            // Warte auf Library-Load
            setTimeout(() => {{
                console.log('📊 RL TRADING CHART: Erstelle Chart...');

                const chart = LightweightCharts.createChart(document.getElementById('{chart_id}'), {{
                    width: {CHART_CONFIG['width']},
                    height: {CHART_CONFIG['height']},
                    layout: {{
                        backgroundColor: '{CHART_CONFIG['layout']['backgroundColor']}',
                        textColor: '{CHART_CONFIG['layout']['textColor']}'
                    }},
                    timeScale: {{
                        timeVisible: {str(CHART_CONFIG['timeScale']['timeVisible']).lower()},
                        secondsVisible: {str(CHART_CONFIG['timeScale']['secondsVisible']).lower()},
                        borderColor: '{CHART_CONFIG['timeScale']['borderColor']}'
                    }},
                    grid: {{
                        vertLines: {{
                            visible: {str(CHART_CONFIG['grid']['vertLines']['visible']).lower()}
                        }},
                        horzLines: {{
                            visible: {str(CHART_CONFIG['grid']['horzLines']['visible']).lower()}
                        }}
                    }}
                }});

                console.log('✅ RL TRADING CHART: Chart erstellt');

                // Candlestick Series hinzufügen (global für Updates)
                window.candlestickSeries = chart.addCandlestickSeries({{
                    upColor: '{CANDLESTICK_CONFIG['upColor']}',
                    downColor: '{CANDLESTICK_CONFIG['downColor']}',
                    borderUpColor: '{CANDLESTICK_CONFIG['borderUpColor']}',
                    borderDownColor: '{CANDLESTICK_CONFIG['borderDownColor']}',
                    wickUpColor: '{CANDLESTICK_CONFIG['wickUpColor']}',
                    wickDownColor: '{CANDLESTICK_CONFIG['wickDownColor']}'
                }});

                console.log('✅ RL TRADING CHART: Candlestick Series hinzugefügt');

                // Daten setzen
                const data = {json.dumps(chart_data)};
                console.log('📊 RL TRADING CHART: Daten laden -', data.length, 'Kerzen');

                window.candlestickSeries.setData(data);
                console.log('✅ RL TRADING CHART: Daten gesetzt - Chart sollte sichtbar sein!');

                // Chart an Daten anpassen oder zum Debug-Startdatum positionieren
                {_generate_chart_positioning_js(debug_start_timestamp)}

                // Zusätzliche Indikatoren (falls aktiviert)
                {_add_indicators(show_volume, show_ma20, show_ma50, show_bollinger)}

                // Trade Markers hinzufügen (falls vorhanden)
                {_add_trade_markers(trades)}

                // Chart Update Mechanismus einrichten
                {_generate_chart_update_js(chart_update_data)}

                // Position Box Funktionalität hinzufügen
                {_generate_position_box_js()}

            }}, 1000);
        </script>
    </body>
    </html>
    """

    return html

def _prepare_chart_data(df):
    """
    Konvertiert DataFrame zu TradingView Lightweight Charts Format

    Args:
        df (DataFrame): OHLCV Daten

    Returns:
        list: Chart-Daten in TradingView Format
    """
    chart_data = []

    for idx, row in df.iterrows():
        chart_data.append({
            'time': int(idx.timestamp()),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close'])
        })

    return chart_data

def _add_indicators(show_volume, show_ma20, show_ma50, show_bollinger):
    """
    Generiert JavaScript-Code für zusätzliche Indikatoren

    Returns:
        str: JavaScript-Code für Indikatoren
    """
    indicators_js = ""

    if show_volume:
        indicators_js += """
        // Volume Series (falls implementiert)
        console.log('📊 Volume Indikator aktiviert');
        """

    if show_ma20:
        indicators_js += """
        // 20-Period Moving Average (falls implementiert)
        console.log('📊 MA20 Indikator aktiviert');
        """

    if show_ma50:
        indicators_js += """
        // 50-Period Moving Average (falls implementiert)
        console.log('📊 MA50 Indikator aktiviert');
        """

    if show_bollinger:
        indicators_js += """
        // Bollinger Bands (falls implementiert)
        console.log('📊 Bollinger Bands aktiviert');
        """

    return indicators_js

def _add_trade_markers(trades):
    """
    Generiert JavaScript-Code für Trade-Marker

    Args:
        trades (list): Liste der Trades

    Returns:
        str: JavaScript-Code für Trade-Marker
    """
    if not trades:
        return "// Keine Trades zum Anzeigen"

    return f"""
    // Trade Markers hinzufügen
    console.log('📊 Füge {len(trades)} Trade-Marker hinzu');
    // TODO: Trade-Marker Implementation
    """

def _generate_chart_positioning_js(debug_start_timestamp):
    """
    Generiert JavaScript für Chart-Positionierung

    Args:
        debug_start_timestamp: Timestamp für Debug-Start (None für normalen Modus)

    Returns:
        str: JavaScript-Code für Chart-Positionierung
    """
    if debug_start_timestamp:
        # Konvertiere zu Unix-Timestamp für TradingView
        start_time = int(debug_start_timestamp.timestamp())

        return f"""
        // Debug-Modus: Positioniere Chart zum Startdatum
        console.log('🎯 RL TRADING CHART: Positioniere zu Debug-Startzeit...');

        // Setze sichtbaren Bereich ab Startdatum mit etwas Kontext davor
        const startTime = {start_time};
        const contextTime = startTime - (24 * 60 * 60); // 1 Tag Kontext davor

        chart.timeScale().setVisibleRange({{
            from: contextTime,
            to: startTime + (7 * 24 * 60 * 60) // 7 Tage nach Startdatum sichtbar
        }});

        console.log('✅ Chart positioniert zu Debug-Startzeit');
        """
    else:
        # Normaler Modus: fitContent
        return """
        // Normaler Modus: Chart an alle Daten anpassen
        chart.timeScale().fitContent();
        console.log('✅ Chart an Daten angepasst');
        """

def _generate_chart_update_js(chart_update_data):
    """
    Generiert JavaScript für Chart-Updates ohne komplettes Neu-Laden
    Nutzt localStorage für persistente Kommunikation zwischen Streamlit Refreshs

    Args:
        chart_update_data: Dictionary mit Update-Informationen oder None

    Returns:
        str: JavaScript-Code für Chart-Updates
    """
    if not chart_update_data:
        return """
        // Chart Update Mechanismus - localStorage basiert
        console.log('🔄 Chart Update Mechanismus initialisiert (localStorage)');

        // Globale Update-Funktion für neue Kerzen
        window.updateChart = function(newCandleData) {
            if (window.candlestickSeries && newCandleData) {
                console.log('📊 Updating chart with new candle:', newCandleData);
                window.candlestickSeries.update(newCandleData);
                console.log('✅ Chart updated successfully');

                // Speichere letzten Update-Timestamp um Duplikate zu vermeiden
                localStorage.setItem('lastChartUpdate', Date.now().toString());
            } else {
                console.warn('⚠️ Cannot update chart - series or data missing');
            }
        };

        // localStorage Polling für Updates
        window.checkLocalStorageUpdates = function() {
            const pendingUpdate = localStorage.getItem('pendingChartUpdate');
            const lastProcessed = localStorage.getItem('lastChartUpdateProcessed') || '0';

            if (pendingUpdate) {
                try {
                    const updateData = JSON.parse(pendingUpdate);
                    const updateTimestamp = updateData.timestamp || '0';

                    // Nur verarbeiten wenn noch nicht processed
                    if (updateTimestamp > lastProcessed) {
                        console.log('📊 Processing localStorage update:', updateData.candle);
                        window.updateChart(updateData.candle);

                        // Markiere als verarbeitet
                        localStorage.setItem('lastChartUpdateProcessed', updateTimestamp);
                        localStorage.removeItem('pendingChartUpdate');
                    }
                } catch (e) {
                    console.error('❌ Error processing localStorage update:', e);
                    localStorage.removeItem('pendingChartUpdate');
                }
            }
        };

        // Check localStorage alle 200ms für schnelle Updates
        setInterval(window.checkLocalStorageUpdates, 200);

        // Cleanup beim Verlassen der Seite
        window.addEventListener('beforeunload', function() {
            localStorage.removeItem('pendingChartUpdate');
            localStorage.removeItem('lastChartUpdateProcessed');
        });
        """
    else:
        # Update-Daten vorhanden - speichere in localStorage
        update_js = f"""
        // Chart Update via localStorage
        console.log('🔄 Storing chart update in localStorage');

        const updateData = {{
            candle: {json.dumps(chart_update_data)},
            timestamp: Date.now().toString()
        }};

        localStorage.setItem('pendingChartUpdate', JSON.stringify(updateData));
        console.log('📊 Chart update stored in localStorage:', updateData);
        """
        return update_js

def _generate_position_box_js():
    """
    Generiert JavaScript für Position Box Tool Funktionalität

    Returns:
        str: JavaScript-Code für Position Box Tool
    """
    return """
        // Position Box Tool - Globale Variablen
        window.positionBoxMode = false;
        window.currentPositionBox = null;
        window.positionCanvas = null;
        window.positionCtx = null;
        window.boxCoordinates = null;
        window.resizeHandles = null;
        window.dragState = {
            isDragging: false,
            handleId: null,
            startX: 0,
            startY: 0
        };

        // Position Box Creation Function
        function createPositionBox(time, entryPrice) {
            // Entferne alte Position Box falls vorhanden
            if (window.currentPositionBox) {
                removeCurrentPositionBox();
            }

            // Standard SL/TP (1% Risk, 2% Reward)
            const riskPercent = 0.01; // 1%
            const rewardPercent = 0.02; // 2%

            const stopLoss = entryPrice * (1 - riskPercent);
            const takeProfit = entryPrice * (1 + rewardPercent);

            console.log('💰 Position Box Preise:', {entry: entryPrice, sl: stopLoss, tp: takeProfit});

            // Position Box Object erstellen
            window.currentPositionBox = {
                id: 'POS_' + Date.now(),
                entryPrice: entryPrice,
                stopLoss: stopLoss,
                takeProfit: takeProfit,
                time: time,
                isResizing: false,
                resizeHandle: null,
                x1Percent: 0.1,  // Startet bei 10% vom linken Rand
                x2Percent: 0.9   // Endet bei 90% der Breite
            };

            // Zeichne die Box mit Canvas Overlay
            createCanvasOverlay();
            drawPositionBox();

            console.log('📦 Neue Position Box erstellt:', window.currentPositionBox);
        }

        function createCanvasOverlay() {
            // Entferne alte Canvas falls vorhanden
            const oldCanvas = document.getElementById('position-canvas');
            if (oldCanvas) oldCanvas.remove();

            const chartContainer = document.getElementById('""" + """{chart_id}""" + """');
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
                // Chart Dimensionen
                const chartWidth = canvas.width;
                const chartHeight = canvas.height;

                // Sichere Koordinaten-Konvertierung mit Fallback
                let entryY, slY, tpY;

                try {
                    // Versuche echte Chart-API Koordinaten zu verwenden
                    if (chart && chart.priceToCoordinate) {
                        entryY = chart.priceToCoordinate(box.entryPrice);
                        slY = chart.priceToCoordinate(box.stopLoss);
                        tpY = chart.priceToCoordinate(box.takeProfit);
                    } else {
                        throw new Error('Chart API nicht verfügbar');
                    }
                } catch (apiError) {
                    // Fallback: Verwende manuelle Skalierung
                    console.warn('⚠️ Chart API nicht verfügbar, verwende Fallback Koordinaten');
                    const centerY = chartHeight / 2;
                    const priceRange = 50; // Angenommene Preisspanne
                    const pixelPerPrice = chartHeight / priceRange;

                    entryY = centerY;
                    slY = entryY + (box.entryPrice - box.stopLoss) * pixelPerPrice;
                    tpY = entryY - (box.takeProfit - box.entryPrice) * pixelPerPrice;
                }

                // X-Position: Dynamische Werte aus Box-Objekt
                const x1 = chartWidth * box.x1Percent;
                const x2 = chartWidth * box.x2Percent;

                // Berechne Box Dimensionen - KORREKTE RECHTECKE
                const slTop = Math.min(entryY, slY);
                const slHeight = Math.abs(entryY - slY);
                const tpTop = Math.min(entryY, tpY);
                const tpHeight = Math.abs(entryY - tpY);

                // Zeichne Stop Loss Box (rot)
                ctx.fillStyle = 'rgba(242, 54, 69, 0.2)';
                ctx.strokeStyle = '#f23645';
                ctx.lineWidth = 2;
                ctx.fillRect(x1, slTop, x2 - x1, slHeight);
                ctx.strokeRect(x1, slTop, x2 - x1, slHeight);

                // Zeichne Take Profit Box (grün)
                ctx.fillStyle = 'rgba(8, 153, 129, 0.2)';
                ctx.strokeStyle = '#089981';
                ctx.fillRect(x1, tpTop, x2 - x1, tpHeight);
                ctx.strokeRect(x1, tpTop, x2 - x1, tpHeight);

                // Zeichne Entry Line (weiß)
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.moveTo(x1, entryY);
                ctx.lineTo(x2, entryY);
                ctx.stroke();

                // Zeichne Resize Handles - NUR äußere Handles
                drawResizeHandles(x1, x2, slTop, tpTop, slHeight, tpHeight);

                console.log('✅ Position Box gezeichnet', {
                    entry: entryY,
                    sl: slY,
                    tp: tpY,
                    x1: x1,
                    x2: x2
                });

            } catch (error) {
                console.error('❌ Fehler beim Zeichnen der Position Box:', error);
            }
        }

        function drawResizeHandles(x1, x2, slTop, tpTop, slHeight, tpHeight) {
            // Nur äußere Handles - KEINE auf der Entry-Linie
            const slBottom = slTop + slHeight;

            // SL Box Handles (rot) - nur Bottom (weit unten)
            drawHandle(window.positionCtx, x1, slBottom, '#f23645', 'SL-BL'); // Bottom-Left
            drawHandle(window.positionCtx, x2, slBottom, '#f23645', 'SL-BR'); // Bottom-Right

            // TP Box Handles (grün) - nur Top (weit oben)
            drawHandle(window.positionCtx, x1, tpTop, '#089981', 'TP-TL'); // Top-Left
            drawHandle(window.positionCtx, x2, tpTop, '#089981', 'TP-TR'); // Top-Right

            // Speichere Handle-Positionen für Mouse Detection
            window.resizeHandles = [
                {id: 'SL-BL', x: x1, y: slBottom, color: '#f23645'},
                {id: 'SL-BR', x: x2, y: slBottom, color: '#f23645'},
                {id: 'TP-TL', x: x1, y: tpTop, color: '#089981'},
                {id: 'TP-TR', x: x2, y: tpTop, color: '#089981'}
            ];
        }

        function drawHandle(ctx, x, y, color, id) {
            const handleSize = 8;
            ctx.fillStyle = color;
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;

            ctx.fillRect(x - handleSize/2, y - handleSize/2, handleSize, handleSize);
            ctx.strokeRect(x - handleSize/2, y - handleSize/2, handleSize, handleSize);
        }

        // Mouse Event Handlers
        function onCanvasMouseDown(event) {
            const rect = window.positionCanvas.getBoundingClientRect();
            const mouseX = event.clientX - rect.left;
            const mouseY = event.clientY - rect.top;

            // Prüfe ob auf Handle geklickt wurde
            if (window.resizeHandles) {
                for (const handle of window.resizeHandles) {
                    const distance = Math.sqrt(
                        Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                    );

                    if (distance <= 10) { // 10px Toleranz
                        window.dragState = {
                            isDragging: true,
                            handleId: handle.id,
                            startX: mouseX,
                            startY: mouseY
                        };

                        console.log('🎯 Handle geklickt:', handle.id);
                        event.preventDefault();
                        return;
                    }
                }
            }
        }

        function onCanvasMouseMove(event) {
            if (!window.dragState.isDragging) {
                // Cursor ändern bei Hover über Handles
                const rect = window.positionCanvas.getBoundingClientRect();
                const mouseX = event.clientX - rect.left;
                const mouseY = event.clientY - rect.top;

                let overHandle = false;
                if (window.resizeHandles) {
                    for (const handle of window.resizeHandles) {
                        const distance = Math.sqrt(
                            Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                        );

                        if (distance <= 10) {
                            overHandle = true;
                            break;
                        }
                    }
                }

                window.positionCanvas.style.cursor = overHandle ? 'grab' : 'default';
                return;
            }

            // Handle Drag
            const rect = window.positionCanvas.getBoundingClientRect();
            const mouseX = event.clientX - rect.left;
            const mouseY = event.clientY - rect.top;

            performHandleResize(window.dragState.handleId, mouseX, mouseY);
        }

        function onCanvasMouseUp(event) {
            if (window.dragState.isDragging) {
                console.log('✅ Drag beendet für Handle:', window.dragState.handleId);
                window.dragState = {
                    isDragging: false,
                    handleId: null,
                    startX: 0,
                    startY: 0
                };
                window.positionCanvas.style.cursor = 'default';
            }
        }

        function performHandleResize(handleId, mouseX, mouseY) {
            const box = window.currentPositionBox;
            if (!box) return;

            const canvas = window.positionCanvas;

            // Konvertiere Maus-Koordinaten zurück zu Preisen (mit Fallback)
            let newPrice;
            try {
                if (chart && chart.coordinateToPrice) {
                    newPrice = chart.coordinateToPrice(mouseY);
                } else {
                    throw new Error('Chart API nicht verfügbar');
                }
            } catch (error) {
                // Fallback: Manuelle Preis-Berechnung
                const centerY = canvas.height / 2;
                const priceRange = 50;
                const pixelPerPrice = canvas.height / priceRange;
                newPrice = box.entryPrice + (centerY - mouseY) / pixelPerPrice;
            }

            // Berechne neue X-Position als Prozent
            const newXPercent = mouseX / canvas.width;

            // Update prices based on which handle was dragged
            if (handleId.includes('SL')) {
                // BEGRENZUNG: SL darf nicht über Entry-Preis gezogen werden
                if (newPrice >= box.entryPrice) {
                    console.warn('⚠️ SL darf nicht über Entry-Preis! Entry:', box.entryPrice, 'SL Versuch:', newPrice);
                    newPrice = box.entryPrice - 1; // 1 Punkt unter Entry
                }
                box.stopLoss = newPrice;
                console.log('📉 SL aktualisiert:', newPrice);
            } else if (handleId.includes('TP')) {
                // BEGRENZUNG: TP darf nicht unter Entry-Preis gezogen werden
                if (newPrice <= box.entryPrice) {
                    console.warn('⚠️ TP darf nicht unter Entry-Preis! Entry:', box.entryPrice, 'TP Versuch:', newPrice);
                    newPrice = box.entryPrice + 1; // 1 Punkt über Entry
                }
                box.takeProfit = newPrice;
                console.log('📈 TP aktualisiert:', newPrice);
            }

            // Horizontale Resize für Eckhandles
            const isLeftHandle = handleId.includes('-TL') || handleId.includes('-BL');
            const isRightHandle = handleId.includes('-TR') || handleId.includes('-BR');

            if (isLeftHandle) {
                box.x1Percent = newXPercent;
                console.log('↔️ Links Handle bewegt zu X:', mouseX);
            } else if (isRightHandle) {
                box.x2Percent = newXPercent;
                console.log('↔️ Rechts Handle bewegt zu X:', mouseX);
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

        function removeCurrentPositionBox() {
            if (window.currentPositionBox) {
                // Entferne Canvas Overlay
                const canvas = document.getElementById('position-canvas');
                if (canvas) {
                    canvas.remove();
                }

                // Lösche Box Object und globale Variablen
                window.currentPositionBox = null;
                window.positionCanvas = null;
                window.positionCtx = null;
                window.boxCoordinates = null;
                window.resizeHandles = null;

                console.log('🗑️ Position Box entfernt');
            }
        }

        // Toolbar Event Handlers
        document.getElementById('positionBoxTool').addEventListener('click', function() {
            window.positionBoxMode = !window.positionBoxMode;
            this.classList.toggle('active');

            if (window.positionBoxMode) {
                console.log('📦 Position Box Tool aktiviert');
            } else {
                console.log('📦 Position Box Tool deaktiviert');
            }
        });

        document.getElementById('clearAll').addEventListener('click', function() {
            console.log('🗑️ Clear All Button geklickt');
            removeCurrentPositionBox();

            // Deaktiviere Position Box Mode
            window.positionBoxMode = false;
            const toolBtn = document.getElementById('positionBoxTool');
            if (toolBtn) toolBtn.classList.remove('active');
            console.log('✅ Position Box entfernt und Tool deaktiviert');
        });

        // Chart Click Handler für Position Box Erstellung
        setTimeout(function() {
            const chartElement = document.getElementById('""" + """{chart_id}""" + """');
            if (chartElement) {
                chartElement.addEventListener('click', function(event) {
                    if (!window.positionBoxMode) return;

                    const rect = this.getBoundingClientRect();
                    const mouseX = event.clientX - rect.left;
                    const mouseY = event.clientY - rect.top;

                    // Konvertiere Y-Koordinate zu Preis
                    let clickPrice;
                    try {
                        if (chart && chart.coordinateToPrice) {
                            clickPrice = chart.coordinateToPrice(mouseY);
                        } else {
                            throw new Error('Chart API nicht verfügbar');
                        }
                    } catch (error) {
                        // Fallback Preis-Berechnung
                        const centerY = this.clientHeight / 2;
                        const priceRange = 50;
                        const pixelPerPrice = this.clientHeight / priceRange;
                        clickPrice = 19000 + (centerY - mouseY) / pixelPerPrice; // Beispiel-Basispreis
                    }

                    console.log('🎯 Chart geklickt - Position Box erstellen bei Preis:', clickPrice);
                    createPositionBox(Date.now(), clickPrice);

                    // Deaktiviere Position Box Mode nach Erstellung
                    window.positionBoxMode = false;
                    const toolBtn = document.getElementById('positionBoxTool');
                    if (toolBtn) toolBtn.classList.remove('active');
                });
            }
        }, 500);

        console.log('✅ Position Box Tool initialisiert');
    """

def create_minimal_chart():
    """
    Erstellt einen minimalen Chart für Tests

    Returns:
        str: HTML-Code für minimalen Test-Chart
    """
    chart_id = f'minimal_chart_{int(time.time() * 1000)}'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Minimal Test Chart</title>
    </head>
    <body>
        <div id="{chart_id}" style="width: 600px; height: 300px; background: #000;"></div>

        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>

        <script>
            console.log('🚀 MINIMAL CHART: Test gestartet...');

            setTimeout(() => {{
                const chart = LightweightCharts.createChart(document.getElementById('{chart_id}'), {{
                    width: 600,
                    height: 300,
                    layout: {{
                        backgroundColor: '#000000',
                        textColor: '#d9d9d9'
                    }}
                }});

                const candlestickSeries = chart.addCandlestickSeries();

                // Test-Daten
                const testData = [
                    {{ time: '2023-01-01', open: 100, high: 110, low: 95, close: 105 }},
                    {{ time: '2023-01-02', open: 105, high: 115, low: 100, close: 108 }},
                    {{ time: '2023-01-03', open: 108, high: 112, low: 103, close: 107 }}
                ];

                candlestickSeries.setData(testData);
                chart.timeScale().fitContent();

                console.log('✅ MINIMAL CHART: Test erfolgreich!');
            }}, 1000);
        </script>
    </body>
    </html>
    """

    return html