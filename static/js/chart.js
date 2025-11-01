        console.log('🚀 RL Trading Chart - FastAPI Edition');

        // Server-side Logging Function für Debug-Ausgaben
        function serverLog(message, data = null) {
            // Bereinige data für JSON-Serialisierung
            let cleanData = null;
            if (data !== null && data !== undefined) {
                try {
                    // Teste ob data JSON-serialisierbar ist
                    JSON.stringify(data);
                    cleanData = data;
                } catch (e) {
                    // Falls nicht serialisierbar, konvertiere zu String
                    cleanData = String(data);
                }
            }

            const logData = {
                message: message || 'No message',
                timestamp: new Date().toISOString(),
                data: cleanData
            };

            // Console ausgeben für Browser
            console.log('[SERVER LOG]', message, cleanData);

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

        // Make chart and candlestickSeries globally available for PnL rendering
        window.chart = null;
        window.candlestickSeries = null;

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
            window.isProgrammaticRangeChange = true;  // Flag: Programmatische Navigation (Chart Init)
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
                window.isProgrammaticRangeChange = true;  // Flag: Programmatische Navigation (Chart Init)
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

        // Position-Based Lazy Loading System
        class IntelligentZoomSystem {
            constructor(chart, candlestickSeries, currentTimeframe = '5m') {
                this.chart = chart;
                this.candlestickSeries = candlestickSeries;
                this.currentTimeframe = currentTimeframe;
                this.isLoading = false;
                this.lastVisibleRange = null;
                this.oldestLoadedTime = null; // Timestamp der ältesten geladenen Kerze

                // Timeframe-spezifische Konfiguration
                this.config = this.getConfig(currentTimeframe);
                this.currentCandles = 300; // Backend lädt initial 300

                console.log(`📊 Lazy Load Config: Initial=${this.config.initial}, Chunk=${this.config.chunk}, Max=${this.config.max}, Trigger@${this.config.trigger}`);

                this.setupZoomMonitoring();

                // Initial Load auf gewünschte Menge wenn nötig
                this.ensureInitialLoad();
            }

            getConfig(timeframe) {
                const LAZY_LOAD_CONFIG = {
                    // trigger = Anzahl verbleibender Kerzen LINKS (barsBefore < trigger)
                    '1m':  { initial: 1000, chunk: 500,  max: 5000,  trigger: 100 },
                    '5m':  { initial: 500,  chunk: 250,  max: 5000,  trigger: 50 },
                    '15m': { initial: 400,  chunk: 200,  max: 4000,  trigger: 50 },
                    '30m': { initial: 300,  chunk: 150,  max: 3500,  trigger: 50 },
                    '1h':  { initial: 300,  chunk: 150,  max: 3000,  trigger: 50 },
                    '4h':  { initial: 200,  chunk: 100,  max: 1500,  trigger: 30 }
                };
                return LAZY_LOAD_CONFIG[timeframe] || LAZY_LOAD_CONFIG['5m'];
            }

            async ensureInitialLoad() {
                // Backend lädt 300, wir brauchen aber evtl. mehr (z.B. 500 für 5m)
                if (this.currentCandles < this.config.initial) {
                    console.log(`🔄 Initial Load: Erhöhe von ${this.currentCandles} auf ${this.config.initial} Kerzen`);
                    await this.loadMoreCandles(0); // Force initial load
                }
            }

            setupZoomMonitoring() {
                // Überwache Änderungen der sichtbaren Zeitspanne
                this.chart.timeScale().subscribeVisibleLogicalRangeChange((newVisibleLogicalRange) => {
                    if (newVisibleLogicalRange === null) return;
                    this.handleVisibleRangeChange(newVisibleLogicalRange);
                });

                console.log('🔍 Position-Based Lazy Load aktiviert');
            }

            handleVisibleRangeChange(visibleLogicalRange) {
                const { from, to } = visibleLogicalRange;
                const visibleCandleCount = Math.ceil(to - from);

                // Nutze barsInLogicalRange() für robustere Trigger-Logik
                const barsInfo = this.candlestickSeries.barsInLogicalRange(visibleLogicalRange);

                if (barsInfo) {
                    console.log(`📊 Sichtbar: Kerzen ${Math.floor(from)}-${Math.floor(to)} (${visibleCandleCount} sichtbar, ${barsInfo.barsBefore} links, ${barsInfo.barsAfter} rechts)`);
                } else {
                    console.log(`📊 Sichtbar: Kerzen ${Math.floor(from)}-${Math.floor(to)} (${visibleCandleCount} von ${this.currentCandles})`);
                }

                // Trigger Lazy Loading wenn nah am linken Rand
                if (this.shouldLoadMoreCandles(barsInfo)) {
                    this.loadMoreCandles(visibleCandleCount);
                }

                this.lastVisibleRange = visibleLogicalRange;
            }

            shouldLoadMoreCandles(barsInfo) {
                // Wenn barsInfo nicht verfügbar, kein Loading
                if (!barsInfo) return false;

                // Trigger: Weniger als X Kerzen ÜBRIG am linken Rand
                // (X kommt aus config.trigger, z.B. 50 für robusteres Verhalten)
                const nearLeftEdge = barsInfo.barsBefore < this.config.trigger;

                // Noch nicht am Maximum?
                const belowMaxLimit = this.currentCandles < this.config.max;

                // Nicht bereits am Laden?
                const notLoading = !this.isLoading;

                // Logging für Debugging
                if (nearLeftEdge && !belowMaxLimit) {
                    console.log(`⚠️ Lazy Load Limit erreicht: ${this.currentCandles} / ${this.config.max}`);
                }

                if (nearLeftEdge && barsInfo.barsBefore === 0) {
                    console.log(`⚠️ Chart-Anfang erreicht: Keine älteren Daten verfügbar`);
                }

                return nearLeftEdge && belowMaxLimit && notLoading;
            }

            async loadMoreCandles(visibleCandleCount) {
                if (this.isLoading) return;

                // Prüfe ob oldestLoadedTime bekannt ist
                if (!this.oldestLoadedTime) {
                    // Initial: Hole älteste Kerze aus aktuellen Chart-Daten
                    const currentData = this.candlestickSeries.data();
                    if (currentData && currentData.length > 0) {
                        this.oldestLoadedTime = currentData[0].time;
                        console.log(`📌 Älteste Kerze: ${this.oldestLoadedTime} (${new Date(this.oldestLoadedTime * 1000).toLocaleString()})`);
                    } else {
                        console.warn('⚠️ Keine Chart-Daten verfügbar für Lazy Load');
                        return;
                    }
                }

                this.isLoading = true;

                const chunkSize = this.config.chunk;
                console.log(`📈 Lade ${chunkSize} historische Kerzen VOR ${new Date(this.oldestLoadedTime * 1000).toLocaleString()}`);

                try {
                    // Neuer API-Call: /load-more
                    const response = await fetch('/api/chart/load-more', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            timeframe: this.currentTimeframe,
                            before_time: this.oldestLoadedTime,
                            count: chunkSize
                        })
                    });

                    const result = await response.json();

                    if (result.status === 'success' && result.chart_data && result.chart_data.length > 0) {
                        const newHistoricalData = validateCandleData(result.chart_data);
                        const currentData = this.candlestickSeries.data();

                        // Kombiniere: neue historische Daten + bestehende Daten
                        // WICHTIG: Deduplizierung nach Zeit um Überschneidungen zu vermeiden
                        const timeSet = new Set();
                        const combinedData = [];

                        // Zuerst neue historische Daten (ältere)
                        for (const candle of newHistoricalData) {
                            if (!timeSet.has(candle.time)) {
                                timeSet.add(candle.time);
                                combinedData.push(candle);
                            }
                        }

                        // Dann bestehende Daten (neuere)
                        for (const candle of currentData) {
                            if (!timeSet.has(candle.time)) {
                                timeSet.add(candle.time);
                                combinedData.push(candle);
                            }
                        }

                        console.log(`🔄 Deduplication: ${newHistoricalData.length + currentData.length} → ${combinedData.length} candles (removed ${newHistoricalData.length + currentData.length - combinedData.length} duplicates)`);

                        // Update Chart
                        this.candlestickSeries.setData(combinedData);
                        this.currentCandles = combinedData.length;

                        // Update oldestLoadedTime
                        if (newHistoricalData.length > 0) {
                            this.oldestLoadedTime = newHistoricalData[0].time;
                        }

                        console.log(`✅ +${newHistoricalData.length} Kerzen geladen: Total ${this.currentCandles} (${this.currentCandles}/${this.config.max})`);

                        // Toast-Benachrichtigung
                        if (this.currentCandles >= this.config.max * 0.9) {
                            this.showZoomNotification(
                                `⚠️ ${this.currentCandles} / ${this.config.max} Kerzen geladen`
                            );
                        }
                    } else {
                        console.log(`⚠️ Keine älteren Daten verfügbar - CSV-Anfang erreicht`);
                        this.config.max = this.currentCandles; // Setze Max auf aktuelle Anzahl
                    }
                } catch (error) {
                    console.error('❌ Lazy Load Fehler:', error);
                } finally {
                    this.isLoading = false;
                }
            }

            updateTimeframe(newTimeframe, newCandleCount) {
                this.currentTimeframe = newTimeframe;
                this.config = this.getConfig(newTimeframe);
                this.currentCandles = newCandleCount || this.currentCandles;

                // WICHTIG: Reset History-State bei Timeframe-Wechsel!
                // Historische Kerzen sollen NICHT über TF-Wechsel hinweg gespeichert bleiben
                this.oldestLoadedTime = null;

                console.log(`🔄 Timeframe: ${newTimeframe}, Config: ${this.config.initial}/${this.config.max}, Geladen: ${this.currentCandles}`);
                console.log(`🔄 History-State RESET: oldestLoadedTime=null`);
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

        // ============================================================
        // UNBEGRENZTE ZEIT-EXTRAPOLATION - "Magische Wand" Fix
        // ============================================================

        // Konvertiert Timeframe-String zu Sekunden
        function getTimeframeSeconds(timeframe) {
            const map = {
                '1m': 60,
                '5m': 300,
                '15m': 900,
                '1h': 3600,
                '4h': 14400,
                '1d': 86400
            };
            return map[timeframe] || 300; // Fallback: 5min
        }

        // DEACTIVATED: Phantom-Kerzen komplett deaktiviert
        // function extendDataWithFuture(data, futureCandles = 100) {
        //     // Funktion deaktiviert - keine Phantom-Kerzen
        //     return data;
        // }

        //         // 🔮 Helper: Update Candle UND regeneriere Phantom-Kerzen
        // // → Löst "Phantom bleiben nach Next" Problem
        // function candlestickSeries.update(candle) {
        //     // 1. Hole alle aktuellen Chart-Daten
        //     const currentData = candlestickSeries.data();

        //     // 2. Finde letzte ECHTE Kerze (nicht Phantom)
        //     // Phantom-Kerzen haben alle denselben OHLC-Wert
        //     let realData = [];
        //     for (let i = 0; i < currentData.length; i++) {
        //         const c = currentData[i];
        //         // Kerze ist echt wenn OHLC unterschiedlich ODER wenn es eine neue Kerze ist
        //         if (c.open !== c.close || c.high !== c.low || i === 0) {
        //             realData.push(c);
        //         } else {
        //             // Phantom-Kerze gefunden → Rest sind auch Phantoms
        //             break;
        //         }
        //     }

        //     // 3. Füge neue echte Kerze hinzu (update oder replace)
        //     const lastRealTime = realData.length > 0 ? realData[realData.length - 1].time : 0;
        //     if (candle.time > lastRealTime) {
        //         // Neue Kerze am Ende
        //         realData.push(candle);
        //     } else if (candle.time === lastRealTime) {
        //         // Update letzte Kerze
        //         realData[realData.length - 1] = candle;
        //     } else {
        //         // Kerze in der Mitte? Füge hinzu und sortiere
        //         realData.push(candle);
        //         realData.sort((a, b) => a.time - b.time);
        //     }

        //     // 4. Regeneriere Phantom-Kerzen
        //     const extendedData = extendDataWithFuture(realData, 100);

        //     // 5. Setze Chart-Daten neu
        //     candlestickSeries.setData(extendedData);

        //     console.log('🔮 updateCandleWithPhantoms:', realData.length, 'real +', 100, 'phantom =', extendedData.length, 'total');

        //     // 📊 INDICATOR SYSTEM: Update all indicators with new candle
        //     if (window.IndicatorManager) {
        //         window.IndicatorManager.updateAllIndicators(candle);
        //     }

        //     return realData.length; // Return number of real candles
        // }

        // Unbegrenzte coordinateToTime - Funktioniert auch AUSSERHALB der Daten
        // Extrapoliert Zeit basierend auf X-Koordinate, Candle-Spacing und letzter Kerze
        function coordinateToTimeUnlimited(xCoordinate) {
            if (!chart || !candlestickSeries) {
                console.warn('⚠️ coordinateToTimeUnlimited: Chart nicht initialisiert');
                return null;
            }

            // 1. Versuche native coordinateToTime() für Koordinaten INNERHALB der Daten
            const nativeTime = chart.timeScale().coordinateToTime(xCoordinate);
            if (nativeTime !== null) {
                return nativeTime;
            }

            // 2. EXTRAPOLATION: Berechne Zeit für Koordinaten AUSSERHALB der Daten
            const data = candlestickSeries.data();
            if (!data || data.length < 2) {
                console.warn('⚠️ coordinateToTimeUnlimited: Nicht genug Daten für Extrapolation');
                return null;
            }

            // Letzte Kerze als Referenz
            const lastCandle = data[data.length - 1];
            const lastX = chart.timeScale().timeToCoordinate(lastCandle.time);

            if (lastX === null) {
                console.warn('⚠️ coordinateToTimeUnlimited: Letzte Kerze nicht auf Chart');
                return null;
            }

            // Berechne Pixel pro Candle (durchschnittlich über letzte 10 Kerzen)
            const sampleSize = Math.min(10, data.length - 1);
            let totalPixelSpacing = 0;
            let validSamples = 0;

            for (let i = data.length - 1; i >= data.length - sampleSize; i--) {
                const x1 = chart.timeScale().timeToCoordinate(data[i].time);
                const x2 = chart.timeScale().timeToCoordinate(data[i - 1].time);
                if (x1 !== null && x2 !== null) {
                    totalPixelSpacing += Math.abs(x1 - x2);
                    validSamples++;
                }
            }

            const pixelsPerCandle = validSamples > 0 ? totalPixelSpacing / validSamples : 10; // Fallback: 10px

            // Berechne Zeit-Delta basierend auf X-Offset
            const deltaX = xCoordinate - lastX;
            const deltaCandlesEstimate = deltaX / pixelsPerCandle;
            const timeframeSeconds = getTimeframeSeconds(window.currentTimeframe || '5m');
            const deltaTimeSeconds = Math.round(deltaCandlesEstimate * timeframeSeconds);

            const extrapolatedTime = lastCandle.time + deltaTimeSeconds;

            console.log(`🔮 Extrapoliere Zeit: X=${xCoordinate.toFixed(1)}, LastX=${lastX.toFixed(1)}, ΔX=${deltaX.toFixed(1)}, PixPerCandle=${pixelsPerCandle.toFixed(1)}, ΔCandles=${deltaCandlesEstimate.toFixed(2)}, Zeit=${extrapolatedTime}`);

            return extrapolatedTime;
        }

        function initChart() {
            // ⭐ GUARD: Verhindere Doppel-Initialisierung (Race Condition Fix)
            if (isInitialized || chart) {
                console.log('⚠️ Chart bereits initialisiert, überspringe Doppel-Init');
                return;
            }

            // ⭐ SOFORT setzen (nicht am Ende!) → verhindert Race Condition
            isInitialized = true;

            console.log('🔧 initChart() aufgerufen');

            const chartContainer = document.getElementById('chart_container');
            console.log('🔧 Chart Container:', chartContainer);

            if (!chartContainer) {
                console.error('❌ Chart Container nicht gefunden!');
                isInitialized = false;  // Reset bei Fehler
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
                    borderColor: '#485c7b',
                    rightOffset: 500  // 🔮 500 Pixel "Zukunft" rechts → unbegrenzte Interaktion
                },
                grid: {
                    vertLines: { visible: false },
                    horzLines: { visible: false }
                }
            });

            // Make chart globally available for PnL rendering
            window.chart = chart;

            candlestickSeries = chart.addCandlestickSeries({
                upColor: '#089981',
                downColor: '#f23645',
                borderUpColor: '#089981',
                borderDownColor: '#f23645',
                wickUpColor: '#089981',
                wickDownColor: '#f23645'
            });

            // Make candlestickSeries globally available for PnL rendering
            window.candlestickSeries = candlestickSeries;

            // Smart Positioning System initialisieren
            try {
                window.smartPositioning = new SmartChartPositioning(chart, candlestickSeries);
                console.log('INIT: Smart Positioning System initialisiert');

                // Lazy Loading System initialisieren
                window.lazyLoadSystem = new IntelligentZoomSystem(chart, candlestickSeries, '5m');
                console.log('INIT: Lazy Load System initialisiert');

                // Chart-Daten sofort laden
                loadInitialData();

                // SOFORTIGER TEST der Smart Positioning
                window.testSmartPositioning = function() {
                    // console.log('DIRECT TEST: Smart Positioning wird getestet...');
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
                        // console.log('DIRECT TEST: Test-Daten erstellt, rufe setStandardPosition auf...');
                        window.smartPositioning.setStandardPosition(testData);
                        // console.log('DIRECT TEST: setStandardPosition aufgerufen');
                    } else {
                        console.error('DIRECT TEST: Smart Positioning nicht verfügbar');
                    }
                };

            } catch (error) {
                console.error('INIT ERROR: Fehler bei Smart Positioning Initialisierung:', error);
                window.smartPositioning = null;
            }

            console.log('🔧 CandlestickSeries und Smart Positioning erstellt:', candlestickSeries);

            // 🛡️ EMERGENCY GLOBAL ERROR HANDLER: "Value is null" Protection
            window.emergencyChartRecovery = {
                enabled: true,
                recoveryCount: 0,
                maxRecoveries: 3,

                handleValueIsNullError: function(error) {
                    if (this.recoveryCount >= this.maxRecoveries) {
                        console.error('[EMERGENCY-RECOVERY] Max recovery attempts reached, forcing page reload');
                        location.reload();
                        return;
                    }

                    this.recoveryCount++;
                    console.warn(`[EMERGENCY-RECOVERY] Attempt ${this.recoveryCount}: Value is null detected, triggering chart recreation`);

                    // Force chart recreation via backend
                    fetch('/api/chart/emergency_chart_recreation', { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            console.log('[EMERGENCY-RECOVERY] Chart recreation requested:', data);
                            // The backend will trigger chart recreation on next timeframe switch
                        })
                        .catch(err => {
                            console.error('[EMERGENCY-RECOVERY] Failed to request chart recreation:', err);
                            // Fallback: Page reload after brief delay
                            setTimeout(() => location.reload(), 2000);
                        });
                }
            };

            // Global error handler für LightweightCharts "Value is null" errors
            window.addEventListener('error', function(event) {
                if (event.error && event.error.message &&
                    event.error.message.includes('Value is null') &&
                    window.emergencyChartRecovery && window.emergencyChartRecovery.enabled) {

                    console.error('[EMERGENCY-RECOVERY] Global "Value is null" error detected:', event.error);
                    event.preventDefault(); // Prevent default error handling

                    window.emergencyChartRecovery.handleValueIsNullError(event.error);
                }
            });

            console.log('🛡️ Emergency Chart Recovery System aktiviert');

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

            // ⭐⭐⭐ Position Box Observer: VEREINFACHT (kein Cache mehr!) ⭐⭐⭐
            // Bei JEDEM Zoom/Pan Event → Boxes neu zeichnen
            // Koordinaten werden in drawPositionBox() frisch berechnet
            let redrawScheduled = false;

            // X-Achse Observer (Zeit/Zoom/Pan)
            chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
                // 🎯 USER-DRAG DETECTION: Deaktiviere Autoscale bei manuellem Zoom/Pan
                if (!window.isProgrammaticRangeChange && window.autoscaleEnabled) {
                    // User hat manuell gezoomt/gepannt → Autoscale OFF
                    window.autoscaleEnabled = false;

                    const autoscaleBtn = document.getElementById('autoscaleBtn');
                    if (autoscaleBtn) {
                        autoscaleBtn.classList.remove('active');
                        autoscaleBtn.title = 'Autoscale: OFF';
                        console.log('⚖️ Autoscale deaktiviert (User-Drag erkannt)');
                    }
                } else if (window.isProgrammaticRangeChange) {
                    // Programmatische Änderung (Go To Date, Init) → Flag zurücksetzen
                    window.isProgrammaticRangeChange = false;
                }

                // ⭐ MULTI-BOX: Prüfe Manager statt Singleton
                if (window.positionBoxManager && window.positionBoxManager.count() > 0 && !redrawScheduled) {
                    redrawScheduled = true;
                    requestAnimationFrame(() => {
                        if (window.positionBoxManager && window.positionBoxManager.count() > 0) {
                            // ⭐ EINFACH: Zeichne alle Boxes neu
                            // X-Koordinaten: Kerzen-Index → stabil
                            // Y-Koordinaten: frisch → reagiert auf vertikalen Pan
                            window.positionBoxManager.drawAll();

                            // console.log(`🔄 ${window.positionBoxManager.count()} Boxes neu gezeichnet (Zoom/Pan Event)`);
                        }

                        // Redraw limit orders too
                        if (window.activeLimitOrders && window.activeLimitOrders.length > 0) {
                            drawLimitOrders();
                        }

                        // 💰 Render PnL labels after zoom/pan
                        renderLivePnLLabels();

                        redrawScheduled = false;
                    });
                }
            });

            // ⭐⭐⭐ BUGFIX: Y-Achse Observer (Preis-Skala Zoom) ⭐⭐⭐
            // TradingView hat keine direkte API für Preis-Skala Events
            // Lösung: Polling-Mechanismus mit Throttling
            let lastPriceRange = null;
            let priceScaleCheckInterval = null;

            function checkPriceScaleChange() {
                // ⭐⭐⭐ BUG FIX: Pausiere Observer während Box-Drag ⭐⭐⭐
                if (window.isBoxDragging) {
                    return;  // Keine Updates während Drag → verhindert Interferenz
                }

                if (!candlestickSeries || !window.positionBoxManager || window.positionBoxManager.count() === 0) {
                    return;
                }

                try {
                    // Hole aktuelle Preis-Range vom sichtbaren Bereich
                    const visibleRange = chart.timeScale().getVisibleLogicalRange();
                    if (!visibleRange) return;

                    // Sample einen Preis um Preis-Koordinaten zu testen
                    const seriesData = candlestickSeries.data();
                    if (!seriesData || seriesData.length === 0) return;

                    // Verwende ersten sichtbaren Preis als Referenz
                    const samplePrice = seriesData[Math.floor(visibleRange.from)]?.high || seriesData[0]?.high;
                    if (!samplePrice) return;

                    // Berechne Y-Koordinate für Sample-Preis
                    const currentY = candlestickSeries.priceToCoordinate(samplePrice);

                    // Erstelle eindeutige Range-Signatur
                    const currentRange = `${samplePrice.toFixed(2)}_${currentY?.toFixed(0)}`;

                    // Prüfe ob sich Preis-Skala geändert hat
                    if (lastPriceRange !== null && lastPriceRange !== currentRange) {
                        // Preis-Skala hat sich geändert → Boxes neu zeichnen
                        if (!redrawScheduled) {
                            redrawScheduled = true;
                            requestAnimationFrame(() => {
                                window.positionBoxManager.drawAll();

                                // 💰 Render PnL labels after price scale change
                                renderLivePnLLabels();

                                redrawScheduled = false;
                                // console.log('🔄 Boxes neu gezeichnet (Preis-Skala Event)');
                            });
                        }
                    }

                    lastPriceRange = currentRange;
                } catch (error) {
                    console.warn('⚠️ Preis-Skala Check Error:', error);
                }
            }

            // Starte Polling (60 FPS → ~16ms, verwende 50ms für Balance)
            priceScaleCheckInterval = setInterval(checkPriceScaleChange, 50);

            // Cleanup bei Page Unload
            window.addEventListener('beforeunload', () => {
                if (priceScaleCheckInterval) {
                    clearInterval(priceScaleCheckInterval);
                }
            });

            // ⭐ EVENT-BASED REDRAW: Boxes werden nur bei Chart-Events neu gezeichnet
            // Observer Pattern (subscribeVisibleLogicalRangeChange) übernimmt Redraw bei Zoom/Pan
            // Kein continuous redraw mehr → Massive Performance-Verbesserung + stabile Koordinaten

            // Responsive Resize - VEREINFACHT (kein Cache mehr!)
            window.addEventListener('resize', () => {
                chart.applyOptions({
                    width: chartContainer.clientWidth,
                    height: chartContainer.clientHeight
                });

                // ⭐ Position Boxes mitskalieren bei Window Resize (MULTI-BOX Support)
                if (window.positionBoxManager && window.positionBoxManager.count() > 0 && window.positionCanvas) {
                    // Update Canvas Größe
                    const canvas = window.positionCanvas;
                    canvas.width = chartContainer.clientWidth;
                    canvas.height = chartContainer.clientHeight;

                    // ⭐ EINFACH: Zeichne alle Boxes neu (Koordinaten werden frisch berechnet)
                    window.positionBoxManager.drawAll();
                    console.log(`🔄 ${window.positionBoxManager.count()} Position Boxes neu gezeichnet nach Window Resize`);
                }

                // 💰 Update PnL labels canvas size on resize
                if (window.pnlLabelsCanvas) {
                    window.pnlLabelsCanvas.width = chartContainer.clientWidth;
                    window.pnlLabelsCanvas.height = chartContainer.clientHeight;
                }

                // 💰 Render PnL labels after resize
                renderLivePnLLabels();
            });

            // ⚖️ Autoscale Toggle Button
            window.autoscaleEnabled = true;  // Standard: aktiviert (global für Go To Date Persistenz)
            window.isProgrammaticRangeChange = false;  // Flag: Unterscheidet User-Drag vs. System-Navigation
            const autoscaleBtn = document.getElementById('autoscaleBtn');

            if (autoscaleBtn) {
                autoscaleBtn.addEventListener('click', () => {
                    window.autoscaleEnabled = !window.autoscaleEnabled;

                    // Update Chart Options
                    chart.priceScale('right').applyOptions({
                        autoScale: window.autoscaleEnabled
                    });

                    // Update Button Styling
                    if (window.autoscaleEnabled) {
                        autoscaleBtn.classList.add('active');
                        autoscaleBtn.title = 'Autoscale: ON';
                    } else {
                        autoscaleBtn.classList.remove('active');
                        autoscaleBtn.title = 'Autoscale: OFF';
                    }

                    console.log('⚖️ Autoscale:', window.autoscaleEnabled ? 'ON' : 'OFF');
                });
            }

            // LADE ECHTE NQ-DATEN über WebSocket
            console.log('🔄 Lade echte NQ-Daten...');

            // REMOVED: Redundanter setTimeout-Call (loadInitialData wird bereits bei Zeile 498 sofort aufgerufen)
            // Dieser doppelte Call verursachte den "Value is null" Crash
            // setTimeout(() => {
            //     loadInitialData();
            // }, 1000);

            // Chart Click Handler für Position Box Tool
            chart.subscribeClick((param) => {
                // Check for close button clicks first (highest priority)
                if (param.point && window.closeButtonPositions) {
                    const clickX = param.point.x;
                    const clickY = param.point.y;

                    console.log(`[Close] Click at (${clickX}, ${clickY}), checking ${Object.keys(window.closeButtonPositions).length} buttons`);

                    for (const positionId in window.closeButtonPositions) {
                        const btn = window.closeButtonPositions[positionId];
                        console.log(`[Close] Button ${positionId} bounds: x=${btn.x}-${btn.x+btn.width}, y=${btn.y}-${btn.y+btn.height}`);

                        if (clickX >= btn.x && clickX <= btn.x + btn.width &&
                            clickY >= btn.y && clickY <= btn.y + btn.height) {
                            console.log(`[Close] ✅ X button clicked for position ${positionId}`);

                            // Send close position request
                            if (ws && ws.readyState === WebSocket.OPEN) {
                                ws.send(JSON.stringify({
                                    type: 'close_position',
                                    position_id: positionId
                                }));
                                console.log(`[Close] Close request sent for ${positionId}`);
                            }
                            return; // Prevent other click handlers
                        }
                    }
                    console.log(`[Close] ❌ Click outside all close buttons`);
                }

                // Check for limit order close button clicks
                if (param.point && window.limitOrderCloseButtons) {
                    const clickX = param.point.x;
                    const clickY = param.point.y;

                    console.log(`[LimitClose] Click at (${clickX}, ${clickY}), checking ${Object.keys(window.limitOrderCloseButtons).length} limit order buttons`);

                    for (const limitId in window.limitOrderCloseButtons) {
                        const btn = window.limitOrderCloseButtons[limitId];

                        if (clickX >= btn.x && clickX <= btn.x + btn.width &&
                            clickY >= btn.y && clickY <= btn.y + btn.height) {
                            console.log(`[LimitClose] ✅ X button clicked for limit order ${btn.orderId}`);

                            // Cancel limit order
                            window.cancelLimitOrder(btn.orderId);
                            return; // Prevent other click handlers
                        }
                    }
                }

                // ⭐ MULTI-BOX SUPPORT: Mehrere Boxes erlaubt!
                // (Alte Guard wurde entfernt)

                // ⭐ GUARD: Position Tool muss explizit aktiviert sein
                if ((window.positionBoxMode || window.shortPositionMode) && param.point) {
                    const price = candlestickSeries.coordinateToPrice(param.point.y);
                    const clickY = param.point.y;  // Chart-relative Y-Koordinate
                    const clickX = param.point.x;  // Chart-relative X-Koordinate

                    // 🔮 UNBEGRENZTE ZEIT-EXTRAPOLATION FIX
                    // param.time ist undefined bei Clicks außerhalb Kerzen (rechts von letzter Kerze)
                    // Nutze coordinateToTimeUnlimited() für ECHTE Click-Position (nicht Mitte des Charts!)
                    let clickTime = param.time;
                    if (!clickTime) {
                        clickTime = coordinateToTimeUnlimited(clickX);
                        if (!clickTime) {
                            console.warn('⚠️ Konnte Zeit für Click nicht bestimmen');
                            return;
                        }
                        console.log(`🔮 Zeit extrapoliert: X=${clickX.toFixed(1)} → Zeit=${clickTime}`);
                    }

                    const isShort = window.shortPositionMode;
                    console.log('📦 Erstelle', isShort ? 'Short' : 'Long', 'Position Box bei Preis:', price, 'an Zeit:', clickTime, 'Position:', {x: clickX, y: clickY});
                    createPositionBox(clickTime, price, clickX, clickY, isShort);

                    // ⭐ ÄNDERUNG: Button DEAKTIVIEREN nach Box-Erstellung
                    window.positionBoxMode = false;
                    window.shortPositionMode = false;

                    // UI aktualisieren
                    const positionTool = document.getElementById('positionBoxTool');
                    const shortTool = document.getElementById('shortPositionTool');

                    if (positionTool) {
                        positionTool.classList.remove('active');
                        positionTool.style.background = '#333';
                        positionTool.style.color = '#fff';
                    }

                    if (shortTool) {
                        shortTool.classList.remove('active');
                        shortTool.style.background = '#333';
                        shortTool.style.color = '#fff';
                    }

                    // Box erstellt
                } else {
                    console.log('❌ Position Box Mode nicht aktiv oder ungültiger Klick');
                }
            });

            // ⭐ Kontinuierlicher Rendering-Loop für PnL Labels
            // Labels müssen bei jedem Frame neu gezeichnet werden, weil sich die Y-Koordinaten bei Zoom ändern
            function continuousLabelRendering() {
                if (window.positionLines && Object.keys(window.positionLines).length > 0) {
                    renderLivePnLLabels();
                }
                requestAnimationFrame(continuousLabelRendering);
            }
            requestAnimationFrame(continuousLabelRendering);
            console.log('[PnL] Continuous label rendering loop started');

            // ⭐ isInitialized bereits am Anfang gesetzt (Race Condition Prevention)
            // console.log('✅ Chart initialisiert, lade NQ-Daten...');
        }

        // Lade initiale Chart-Daten vom Server
        let initialDataLoaded = false; // CRITICAL: Prevent double-loading
        function loadInitialData() {
            // CRITICAL: Prevent double-loading which causes "Value is null" crash
            if (initialDataLoaded) {
                console.warn('⚠️ loadInitialData() bereits ausgeführt - Skip Duplikat-Call');
                return;
            }
            initialDataLoaded = true;

            // console.log('📊 Lade initiale NQ-Daten...');

            // Prüfe ob Chart und Series verfügbar sind
            if (!chart || !candlestickSeries) {
                console.error('❌ Chart oder CandlestickSeries nicht initialisiert!');
                console.log('Chart:', chart);
                console.log('CandlestickSeries:', candlestickSeries);
                initialDataLoaded = false; // Reset bei Fehler
                return;
            }

            fetch('/api/chart/status')
                .then(response => response.json())
                .then(data => {
                    // console.log('📊 Status:', data);
                    // Lade Chart-Daten
                    return fetch('/api/chart/data');
                })
                .then(response => response.json())
                .then(chartData => {
                    // console.log('📊 Chart-Daten erhalten:', chartData.data?.length || 0, 'Kerzen');
                    // console.log('DRASTIC: SOFORT nach Chart-Daten Log - 20% Freiraum wird ERZWUNGEN!');
                    if (chartData.data && chartData.data.length > 0) {
                        // Daten sind bereits im korrekten LightweightCharts Format (Unix-Timestamps)
                        const formattedData = chartData.data.filter(item =>
                            item && item.time &&
                            item.open != null && item.high != null &&
                            item.low != null && item.close != null
                        ).map(item => ({
                            time: item.time,  // Bereits Unix-Timestamp, keine Konvertierung nötig
                            open: parseFloat(item.open) || 0,
                            high: parseFloat(item.high) || 0,
                            low: parseFloat(item.low) || 0,
                            close: parseFloat(item.close) || 0
                        }));

                        // 📅 Erweitere Daten um Zukunfts-Kerzen für X-Achsen-Zeitstempel
                        const extendedData = formattedData; // No phantom candles
                        candlestickSeries.setData(extendedData);

                        // DRASTISCHE SOFORT-LÖSUNG: 20% Freiraum GARANTIERT
                        // CRITICAL FIX: Validiere Daten BEVOR setVisibleRange
                        if (!formattedData || formattedData.length < 2) {
                            console.error('❌ Nicht genug Daten für setVisibleRange:', formattedData?.length || 0);
                            return;
                        }

                        const firstTime = formattedData[0]?.time;
                        const lastTime = formattedData[formattedData.length - 1]?.time;

                        console.log('🔍 DEBUG setVisibleRange:', {
                            firstTime,
                            lastTime,
                            firstTimeType: typeof firstTime,
                            lastTimeType: typeof lastTime,
                            dataLength: formattedData.length
                        });

                        if (!firstTime || !lastTime || isNaN(firstTime) || isNaN(lastTime)) {
                            console.error('❌ Ungültige Zeit-Werte:', { firstTime, lastTime });
                            return;
                        }

                        // Fix: Stelle sicher, dass wir Min/Max korrekt ermitteln
                        const minTime = Math.min(firstTime, lastTime);
                        const maxTime = Math.max(firstTime, lastTime);
                        const span = maxTime - minTime;
                        const margin = span * 0.25;

                        window.isProgrammaticRangeChange = true;  // Flag: Programmatische Navigation (Initial Load)
                        chart.timeScale().setVisibleRange({
                            from: minTime,
                            to: maxTime + margin
                        });
                        // console.log('DRASTIC-EXEC: Freiraum gesetzt von', minTime, 'bis', maxTime + margin);

                        // FINALE DIREKTE LÖSUNG: 20% Freiraum OHNE Bedingungen (DEAKTIVIERT wegen Redundanz)
                        // Dieser Block wurde entfernt da bereits oben setVisibleRange aufgerufen wird
                        // console.log('✅ setVisibleRange bereits ausgeführt - Skip redundanter zweiter Call');

                        // ZUSÄTZLICHER SCHUTZ: Entfernt - Redundant zu obigem setVisibleRange
                        // console.log('✅ Chart-Position gesetzt - kein redundanter setTimeout mehr');

                        // console.log('✅ NQ-Daten geladen:', formattedData.length, 'Kerzen, Smart Positioning angewandt');

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
                // console.log('AUTO TEST: Smart Positioning nach 3 Sekunden...');
                if (window.testSmartPositioning) {
                    window.testSmartPositioning();
                } else {
                    console.error('AUTO TEST: testSmartPositioning Funktion nicht verfügbar');
                }
            }, 3000);

            // TEST: API-basierter Test nach 6 Sekunden
            setTimeout(() => {
                // console.log('API TEST: Smart Positioning mit echten Daten...');
                if (window.smartPositioning && candlestickSeries) {
                    try {
                        // Hole aktuelle Daten von der Chart API
                        fetch('/api/chart/data')
                            .then(response => response.json())
                            .then(data => {
                                if (data.data && data.data.length > 0) {
                                    // console.log('API TEST: Gefunden', data.data.length, 'Kerzen, wende Smart Positioning an');
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
                    // console.log('API TEST window.smartPositioning:', window.smartPositioning);
                    // console.log('API TEST candlestickSeries:', candlestickSeries);
                }
            }, 6000);

            ws.onopen = function(event) {
                // console.log('🔗 WebSocket verbunden');
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
                const balance = typeof accountData.balance === 'number'
                    ? accountData.balance
                    : parseFloat(accountData.balance);
                balanceEl.textContent = formatEUR(balance);
                balanceEl.className = 'account-value-amount neutral';
            } else {
                console.error(`❌ Element ${prefix}-balance NOT FOUND`);
            }

            // Update Realized PnL
            const realizedEl = document.getElementById(`${prefix}-realized`);
            if (realizedEl) {
                const realizedPnL = typeof accountData.realized_pnl === 'number'
                    ? accountData.realized_pnl
                    : parseFloat(accountData.realized_pnl);
                realizedEl.textContent = formatPnL(realizedPnL);
                realizedEl.className = `account-value-amount ${getPnLClass(realizedPnL)}`;
            }

            // Update Unrealized PnL
            const unrealizedEl = document.getElementById(`${prefix}-unrealized`);
            if (unrealizedEl) {
                const unrealizedPnL = typeof accountData.unrealized_pnl === 'number'
                    ? accountData.unrealized_pnl
                    : parseFloat(accountData.unrealized_pnl);
                unrealizedEl.textContent = formatPnL(unrealizedPnL);
                unrealizedEl.className = `account-value-amount ${getPnLClass(unrealizedPnL)}`;
            }
        }

        function formatEUR(value) {
            // Formatiert Zahl als EUR-String
            return new Intl.NumberFormat('de-DE', {
                style: 'decimal',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            }).format(value) + '€';
        }

        function formatPnL(value) {
            // Formatiert PnL mit Vorzeichen
            const sign = value >= 0 ? '+' : '';
            return sign + new Intl.NumberFormat('de-DE', {
                style: 'decimal',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            }).format(value) + '€';
        }

        function getPnLClass(pnlValue) {
            // Bestimmt CSS-Klasse basierend auf PnL-Wert
            if (typeof pnlValue === 'string') {
                if (pnlValue.includes('+')) return 'positive';
                if (pnlValue.includes('-')) return 'negative';
                return 'neutral';
            }
            // Numeric value
            if (pnlValue > 0) return 'positive';
            if (pnlValue < 0) return 'negative';
            return 'neutral';
        }

        // Account Data alle 5 Sekunden laden
        setInterval(loadAccountData, 5000);

        // Enhanced Multi-Timeframe Functions
        function handleIncompleteCandle(candle, incompleteInfo) {
            console.log(`🔄 INCOMPLETE CANDLE: ${incompleteInfo.timeframe}`);
            console.log(`   ⏱️  Progress: ${incompleteInfo.elapsed_minutes.toFixed(1)}/${incompleteInfo.total_minutes} min`);
            console.log(`   📊 Completion: ${Math.round(incompleteInfo.completion_ratio * 100)}%`);

            // Visual marking could be implemented here
            // For now, we log the incomplete status
            // Future: Add border styling or opacity to incomplete candles

            if (incompleteInfo.completion_ratio < 0.5) {
                console.log('   🟡 Early stage incomplete candle (< 50%)');
            } else if (incompleteInfo.completion_ratio < 0.9) {
                console.log('   🟠 Late stage incomplete candle (50-90%)');
            } else {
                console.log('   🔴 Nearly complete candle (90%+)');
            }
        }

        function updateTimeframeSyncDisplay(syncStatus) {
            console.log('🌐 MULTI-TIMEFRAME SYNC STATUS:');

            for (const [timeframe, status] of Object.entries(syncStatus)) {
                if (status.position) {
                    const positionTime = new Date(status.position).toLocaleTimeString();
                    console.log(`   ${timeframe}: ${positionTime}`);

                    if (status.incomplete_info && !status.incomplete_info.is_complete) {
                        const completion = Math.round(status.incomplete_info.completion_ratio * 100);
                        console.log(`        └── Incomplete: ${completion}%`);
                    }
                }
            }

            // Future: Update UI elements to show sync status visually
            // Could add timeframe indicators in sidebar or status bar
        }

        // ENHANCED DATA VALIDATION: Bulletproof protection against "Value is null" errors
        function validateCandle(candle, isSkipGenerated = false, debug = false) {
            // NULL/UNDEFINED checks first
            if (!candle) {
                if (debug) console.log('🔍 FILTER: Candle is null/undefined');
                return false;
            }
            if (candle.time === null || candle.time === undefined) {
                if (debug) console.log('🔍 FILTER: time is null/undefined:', candle);
                return false;
            }
            if (candle.open === null || candle.open === undefined) {
                if (debug) console.log('🔍 FILTER: open is null/undefined:', candle);
                return false;
            }
            if (candle.high === null || candle.high === undefined) {
                if (debug) console.log('🔍 FILTER: high is null/undefined:', candle);
                return false;
            }
            if (candle.low === null || candle.low === undefined) {
                if (debug) console.log('🔍 FILTER: low is null/undefined:', candle);
                return false;
            }
            if (candle.close === null || candle.close === undefined) {
                if (debug) console.log('🔍 FILTER: close is null/undefined:', candle);
                return false;
            }

            // Type and value validation
            if (typeof candle.time !== 'number' || candle.time <= 0) {
                if (debug) console.log('🔍 FILTER: Invalid time:', candle.time, typeof candle.time);
                return false;
            }

            const open = parseFloat(candle.open);
            const high = parseFloat(candle.high);
            const low = parseFloat(candle.low);
            const close = parseFloat(candle.close);

            // Enhanced NaN detection
            if (!Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
                if (debug) console.log('🔍 FILTER: NaN/Infinite values:', {open, high, low, close});
                return false;
            }

            // Relaxed price range validation (prevent only extreme outliers)
            const minPrice = 100;     // Relaxed minimum for broader CSV compatibility
            const maxPrice = 100000;  // Relaxed maximum for broader CSV compatibility
            if (open < minPrice || open > maxPrice) {
                if (debug) console.log('🔍 FILTER: open price out of range:', open);
                return false;
            }
            if (high < minPrice || high > maxPrice) {
                if (debug) console.log('🔍 FILTER: high price out of range:', high);
                return false;
            }
            if (low < minPrice || low > maxPrice) {
                if (debug) console.log('🔍 FILTER: low price out of range:', low);
                return false;
            }
            if (close < minPrice || close > maxPrice) {
                if (debug) console.log('🔍 FILTER: close price out of range:', close);
                return false;
            }

            // OHLC logic validation with tolerance for skip-generated candles
            if (isSkipGenerated) {
                const tolerance = 0.1; // Increased tolerance for skip candles
                if (high < (Math.max(open, close, low) - tolerance)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error (skip candle) - high too low:', {open, high, low, close});
                    return false;
                }
                if (low > (Math.min(open, close, high) + tolerance)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error (skip candle) - low too high:', {open, high, low, close});
                    return false;
                }
            } else {
                if (high < Math.max(open, close, low)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error - high too low:', {open, high, low, close});
                    return false;
                }
                if (low > Math.min(open, close, high)) {
                    if (debug) console.log('🔍 FILTER: OHLC logic error - low too high:', {open, high, low, close});
                    return false;
                }
            }

            return true;
        }

        function validateCandleData(data, isSkipGenerated = false) {
            if (!data || data.length === 0) return [];

            const originalLength = data.length;
            const validatedData = data.filter(candle => validateCandle(candle, isSkipGenerated)).map(item => ({
                time: item.time,
                open: parseFloat(item.open),
                high: parseFloat(item.high),
                low: parseFloat(item.low),
                close: parseFloat(item.close)
            }));

            // Log filter results
            const filteredCount = originalLength - validatedData.length;
            if (filteredCount > 0) {
                console.log(`🔍 VALIDATION: ${filteredCount}/${originalLength} candles filtered out`);

                // Debug first few filtered candles if many were removed
                if (filteredCount > originalLength * 0.5) {
                    console.warn('🚨 High filter rate detected, debugging first 3 filtered candles:');
                    let debugCount = 0;
                    for (const candle of data) {
                        if (!validateCandle(candle, isSkipGenerated, true) && debugCount < 3) {
                            debugCount++;
                        }
                    }
                }
            }

            // FALLBACK: If validation filters out ALL candles, use raw data with basic cleaning
            if (validatedData.length === 0 && data.length > 0) {
                console.warn('🚨 FALLBACK: All candles filtered out, using raw data with basic cleaning');
                return data.filter(item =>
                    item &&
                    typeof item.time === 'number' &&
                    item.time > 0 &&
                    item.open !== null &&
                    item.high !== null &&
                    item.low !== null &&
                    item.close !== null
                ).map(item => ({
                    time: item.time,
                    open: parseFloat(item.open) || 18500,
                    high: parseFloat(item.high) || 18505,
                    low: parseFloat(item.low) || 18495,
                    close: parseFloat(item.close) || 18500
                }));
            }

            return validatedData;
        }

        // Message Handler
        function handleMessage(message) {
            // console.log('📨 Message received:', message.type);

            switch(message.type) {
                case 'initial_data':
                    if (!isInitialized) initChart();

                    const data = message.data.data;
                    if (data && data.length > 0) {
                        const validatedData = validateCandleData(data);
                        // 📅 Erweitere Daten um Zukunfts-Kerzen für X-Achsen-Zeitstempel
                        const extendedData = validatedData; // No phantom candles
                        candlestickSeries.setData(extendedData);

                        // Store last candle close price for market orders
                        if (validatedData.length > 0) {
                            const lastCandle = validatedData[validatedData.length - 1];
                            window.lastCandleClose = lastCandle.close;
                        }

                        if (validatedData.length !== data.length) {
                            console.warn(`⚠️ ${data.length - validatedData.length} invalid candles removed from initial data`);
                        }

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

                        window.isProgrammaticRangeChange = true;  // Flag: Programmatische Navigation (Initial Data)
                        chart.timeScale().setVisibleRange({
                            from: firstVisibleTime,
                            to: lastVisibleTime + margin
                        });

                        console.log(`✅ Standard-Zoom: Kerzen ${startIndex}-${totalCandles-1} sichtbar (${visibleCandles} Kerzen mit 20% Freiraum)`);

                        // 📊 INDICATOR SYSTEM: Load saved indicators AFTER setVisibleRange completes
                        // Fix: setTimeout prevents "Value is null" error from setVisibleRange race condition
                        if (window.IndicatorManager) {
                            setTimeout(() => {
                                window.IndicatorManager.loadState();
                            }, 100);
                        }
                    }
                    break;

                case 'set_data':
                    if (!isInitialized) initChart();

                    const validatedSetData = validateCandleData(message.data);
                    candlestickSeries.setData(validatedSetData);

                    if (validatedSetData.length !== message.data.length) {
                        console.warn(`⚠️ ${message.data.length - validatedSetData.length} invalid candles removed from set_data`);
                    }

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
                    // Legacy Debug Skip: Direkte Chart-Update ohne Smart Positioning System
                    if (isInitialized && message.candle) {
                        candlestickSeries.update(message.candle);
                        console.log('⏭️ Debug Skip: Neue Kerze hinzugefügt:', message.candle);
                        console.log('📊 Candle Type:', message.candle_type || message.result_type);
                        console.log('🕒 Debug Time:', message.debug_time);
                        console.log('📈 Timeframe:', message.timeframe);

                        // Visual feedback für incomplete candles (if needed)
                        if (message.candle_type === 'incomplete_candle') {
                            console.log('⚠️ Incomplete Candle - noch nicht vollständig');
                        }
                    } else {
                        console.log('❌ Debug Skip fehlgeschlagen: Chart nicht initialisiert oder fehlende Kerze');
                    }
                    break;

                case 'debug_skip_sync':
                    // ENHANCED: Multi-Timeframe Debug Skip mit Sync & Incomplete Candle Support
                    if (isInitialized && message.candle) {
                        // Update Chart mit primary candle
                        candlestickSeries.update(message.candle);

                        console.log('🔄 Multi-TF Skip:', message.timeframe, '- Candle:', message.candle.time);
                        console.log('📊 Type:', message.candle_type);
                        console.log('⏰ Debug Time:', message.debug_time);

                        // Enhanced Incomplete Candle Visual Marking
                        if (message.candle_type === 'incomplete_candle' && message.incomplete_info) {
                            handleIncompleteCandle(message.candle, message.incomplete_info);
                        }

                        // Multi-Timeframe Sync Status Logging
                        if (message.sync_status) {
                            console.log('🌐 Sync Status:', message.sync_status);
                            updateTimeframeSyncDisplay(message.sync_status);
                        }

                        // Update document title with sync info
                        const completionInfo = message.incomplete_info ?
                            ` (${Math.round(message.incomplete_info.completion_ratio * 100)}% complete)` : '';
                        document.title = `${message.timeframe} Skip${completionInfo} - Multi-TF Sync`;

                    } else {
                        console.log('❌ Multi-TF Skip fehlgeschlagen:', !isInitialized ? 'Chart nicht initialisiert' : 'Fehlende Kerze');
                    }
                    break;

                case 'debug_play_toggled':
                    // Debug Play/Pause Toggle Response
                    console.log('▶️ Debug Play Toggle:', message.play_mode ? 'AKTIVIERT' : 'DEAKTIVIERT');

                    // Update Play/Pause Button Visual
                    const playPauseBtn = document.getElementById('playPauseBtn');
                    if (playPauseBtn) {
                        playPauseBtn.textContent = message.play_mode ? '⏸️' : '▶️';
                        console.log('🔄 Play Button Updated:', message.play_mode ? '⏸️' : '▶️');
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

                case 'chart_reinitialize':
                    if (isInitialized && message.data) {
                        console.log('📅 Chart Reinitialization: Go To Date triggered');
                        console.log('📊 New data received:', message.data.length, 'candles');
                        console.log('🎯 Target Date:', message.target_date);
                        console.log('📍 Current Index:', message.current_index);

                        // Lösche alle bestehenden Position-Overlays
                        clearAllPositions();

                        // Setze neue validierte Chart-Daten
                        const validatedGoToData = validateCandleData(message.data);
                        console.log('📊 Validated data length:', validatedGoToData.length);

                        // 📅 Erweitere Daten um Zukunfts-Kerzen für X-Achsen-Zeitstempel
                        const extendedGoToData = validatedGoToData; // No phantom candles
                        console.log('🔮 Extended data length:', extendedGoToData.length);
                        console.log('🔮 Last real candle time:', validatedGoToData[validatedGoToData.length - 1].time);
                        console.log('🔮 Last phantom candle time:', extendedGoToData[extendedGoToData.length - 1].time);

                        candlestickSeries.setData(extendedGoToData);

                        if (validatedGoToData.length !== message.data.length) {
                            console.warn(`⚠️ ${message.data.length - validatedGoToData.length} invalid candles removed from go_to_date`);
                        }

                        // ⚖️ AUTOSCALE PERSISTENZ: Stelle Autoscale-Einstellung nach Chart-Reinitialisierung wieder her
                        if (typeof window.autoscaleEnabled !== 'undefined') {
                            chart.priceScale('right').applyOptions({
                                autoScale: window.autoscaleEnabled
                            });
                            console.log('⚖️ Autoscale restored after chart_reinitialize:', window.autoscaleEnabled ? 'ON' : 'OFF');
                        }

                        // Positioniere Chart zu gewähltem Datum (zeige 50 Kerzen ab Startdatum)
                        if (extendedGoToData.length > 0) {
                            const startIndex = Math.max(0, message.current_index - 5); // 5 Kerzen Kontext vor Startdatum
                            const endIndex = Math.min(validatedGoToData.length - 1, message.current_index + 45); // 45 Kerzen nach Startdatum

                            const firstTime = validatedGoToData[startIndex].time;
                            const visibleEndTime = validatedGoToData[endIndex].time;
                            const timeSpan = visibleEndTime - firstTime;
                            const margin = timeSpan * 0.25; // 20% Freiraum rechts

                            // 🔮 setVisibleRange() schränkt Panning NICHT ein - Phantom-Kerzen erlauben weiteres Panning
                            window.isProgrammaticRangeChange = true;  // Flag: Programmatische Navigation (Go To Date)
                            chart.timeScale().setVisibleRange({
                                from: firstTime,
                                to: visibleEndTime + margin
                            });

                            console.log('✅ Chart reinitialized and positioned to:', message.target_date);
                            console.log('📊 Showing candles:', startIndex, 'to', endIndex, 'with 20% margin');
                            console.log('🔮 Extended data includes', extendedGoToData.length - validatedGoToData.length, 'phantom candles');
                        }

                        // Update Titel mit neuen Informationen
                        document.title = `Chart: ${message.target_date} (${message.data.length} Kerzen verfügbar)`;
                    } else {
                        console.error('❌ Chart Reinitialization failed: Chart not initialized or no data');
                    }
                    break;

                case 'go_to_date_complete':
                    if (isInitialized && message.data) {
                        console.log('[GO TO DATE] Memory-Performance Complete: Loading', message.data.length, 'candles');
                        console.log('[GO TO DATE] Target Date:', message.target_date);
                        console.log('[GO TO DATE] Performance Mode:', message.performance);

                        // Verwende visible_range Info vom Server falls verfügbar
                        if (message.visible_range) {
                            console.log('[GO TO DATE] Server Visible Range:', message.visible_range);
                        }

                        // Lösche alle bestehenden Position-Overlays
                        clearAllPositions();

                        // 🚀 CRITICAL FIX: Browser-Cache Invalidation nach GoTo-Operationen
                        // Verhindert veraltete Skip-Kerzen bei TF-Wechseln
                        const cacheCountBefore = window.timeframeCache.size;
                        window.timeframeCache.clear();
                        window.lastGoToDate = message.target_date; // Server-State für Cache-Validation
                        console.log(`[CACHE-INVALIDATION] Browser-Cache cleared: ${cacheCountBefore} entries removed`);
                        console.log(`[CACHE-INVALIDATION] Grund: GoTo-Operation zu ${message.target_date}`);

                        // Setze neue validierte historische Chart-Daten
                        const validatedHistoricalData = validateCandleData(message.data);

                        // 📅 Erweitere Daten um Zukunfts-Kerzen für X-Achsen-Zeitstempel
                        // 🔮 KRITISCH: Verhindert "Magische Wand" nach Go To Date
                        const extendedHistoricalData = validatedHistoricalData; // No phantom candles
                        console.log('🔮 go_to_date_complete: Extended data with', extendedHistoricalData.length - validatedHistoricalData.length, 'phantom candles');

                        candlestickSeries.setData(extendedHistoricalData);

                        // 📊 BUGFIX: Update Indikatoren nach Go To Date
                        if (window.IndicatorManager) {
                            window.IndicatorManager.syncWithTimeframe(extendedHistoricalData);
                            console.log('📊 Indikatoren nach Go To Date aktualisiert');
                        }

                        if (validatedHistoricalData.length !== message.data.length) {
                            console.warn(`⚠️ ${message.data.length - validatedHistoricalData.length} invalid candles removed from historical data`);
                        }

                        // ⚖️ AUTOSCALE PERSISTENZ: Stelle Autoscale-Einstellung nach Go To Date wieder her
                        if (typeof window.autoscaleEnabled !== 'undefined') {
                            chart.priceScale('right').applyOptions({
                                autoScale: window.autoscaleEnabled
                            });
                            console.log('⚖️ Autoscale restored after go_to_date_complete:', window.autoscaleEnabled ? 'ON' : 'OFF');
                        }

                        // HIGH-PERFORMANCE POSITIONING: Verwende Server-calculated Range
                        if (message.data.length > 0) {
                            let startIndex, endIndex;
                            const totalCandles = message.data.length;
                            const visibleCandles = 50; // FIXED: Variable außerhalb der Blöcke definieren

                            if (message.visible_range) {
                                // Verwende vom Memory Cache berechnete Range
                                startIndex = message.visible_range.start;
                                endIndex = message.visible_range.end;
                                console.log('[POSITIONING] Server-calculated range:', startIndex, '-', endIndex);
                            } else {
                                // Fallback: Standardberechnung (letzten 50 von 200)
                                startIndex = Math.max(0, totalCandles - visibleCandles);
                                endIndex = totalCandles - 1;
                                console.log('[POSITIONING] Fallback range:', startIndex, '-', endIndex);
                            }

                            // Zeitbereich für die sichtbaren Kerzen
                            const startTime = message.data[startIndex].time;
                            const endTime = message.data[endIndex].time;
                            const timeSpan = endTime - startTime;
                            const margin = timeSpan * 0.05; // 5% Margin für gefüllten Chart

                            window.isProgrammaticRangeChange = true;  // Flag: Programmatische Navigation (Go To Date)
                            chart.timeScale().setVisibleRange({
                                from: startTime - margin,
                                to: endTime + margin
                            });

                            console.log(`[GO TO DATE] Positioning: ${visibleCandles} von ${totalCandles} Kerzen angezeigt (Chart gefüllt)`);
                            console.log(`[GO TO DATE] Sichtbare Kerzen: Index ${startIndex}-${endIndex}`);
                            console.log(`[GO TO DATE] Zeitbereich: ${new Date(startTime * 1000).toISOString()} bis ${new Date(endTime * 1000).toISOString()}`);
                        }

                        // Update Titel mit neuen Informationen
                        document.title = `Go To Date: ${message.target_date} (${message.data.length} historische Kerzen)`;

                        // ADAPTIVE TIMEOUT FIX: Setze Go To Date Status für längere Timeouts
                        window.current_go_to_date = message.target_date;

                        // Server-Log für Debug
                        console.log('[GO TO DATE] Complete: Chart repositioniert, bereit für Skip-Button Navigation');

                    } else {
                        console.error('[GO TO DATE] Complete failed: Chart not initialized or no data');
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
                        // ENHANCED DATA VALIDATION: Zentrale Validierung gegen LightweightCharts Errors
                        const validatedData = validateCandleData(message.data);

                        if (validatedData.length < message.data.length) {
                            const removedCount = message.data.length - validatedData.length;
                            console.warn(`⚠️ ${removedCount} invalid candles removed from timeframe data`);
                        }

                        // 📅 Erweitere Daten um Zukunfts-Kerzen für X-Achsen-Zeitstempel
                        const extendedTFData = validatedData; // No phantom candles
                        candlestickSeries.setData(extendedTFData);

                        // NEUE LOGIK: Zeige nur letzten 50 Kerzen mit 80/20 Aufteilung bei TF-Wechsel
                        console.log(`[TIMEFRAME] ${message.timeframe}: ${validatedData.length} Kerzen geladen, zeige letzten 50 mit 80/20 Aufteilung`);
                        document.title = `Chart: ${validatedData.length} Kerzen verfügbar, 50 sichtbar (${message.timeframe})`;

                        // Berechne die letzten 50 Kerzen
                        const totalCandles = validatedData.length;
                        const visibleCandles = Math.min(50, totalCandles);
                        const startIndex = Math.max(0, totalCandles - visibleCandles);

                        const firstVisibleTime = validatedData[startIndex].time;
                        const lastVisibleTime = validatedData[totalCandles - 1].time;
                        const visibleSpan = lastVisibleTime - firstVisibleTime;

                        // 20% Freiraum rechts hinzufügen: 50 Kerzen sind 80%, also 20% zusätzlich
                        const margin = visibleSpan / 4; // visibleSpan / 4 = 20% von den 80%

                        window.isProgrammaticRangeChange = true;  // Flag: Programmatische Navigation (Timeframe Change)
                        chart.timeScale().setVisibleRange({
                            from: firstVisibleTime,
                            to: lastVisibleTime + margin
                        });

                        // Update current timeframe
                        window.currentTimeframe = message.timeframe;

                        // RACE CONDITION FIX: Synchronisiere Button-State mit tatsächlichem Timeframe
                        updateTimeframeButtons(message.timeframe);

                        console.log(`[SUCCESS] TF-Wechsel: Kerzen ${startIndex}-${totalCandles-1} sichtbar (${visibleCandles} Kerzen mit 20% Freiraum)`);
                    }
                    break;

                case 'revolutionary_skip_event':
                    // Revolutionary Skip Event: Handle incomplete candles und timeframe updates
                    if (isInitialized && message.candle && validateCandle(message.candle)) {
                        // Validated candle update
                        const validatedCandle = {
                            time: message.candle.time,
                            open: parseFloat(message.candle.open),
                            high: parseFloat(message.candle.high),
                            low: parseFloat(message.candle.low),
                            close: parseFloat(message.candle.close)
                        };
                        candlestickSeries.update(validatedCandle);

                        // Store last candle data for market orders and limit order triggers
                        window.lastCandleClose = validatedCandle.close;
                        window.lastCandle = validatedCandle;  // ⭐ Store full candle for high/low checks

                        // ⭐ Check limit orders on new candle (Skip Event)
                        if (typeof checkLimitOrders === 'function') {
                            checkLimitOrders(validatedCandle);
                        }

                        console.log('🚀 Revolutionary Skip:', message.timeframe, '- Candle:', message.candle.time);
                        console.log('📊 Candle Type:', message.candle_type);
                        console.log('⏰ Debug Time:', message.debug_time);

                        // Visual feedback für incomplete candles
                        if (message.candle_type === 'incomplete_candle') {
                            console.log('⚠️ Incomplete 15min Candle - wird bei nächstem Skip vervollständigt');
                        }

                        // Update document title
                        const completionInfo = message.candle_type === 'incomplete_candle' ? ' (incomplete)' : '';
                        document.title = `${message.timeframe} Revolutionary Skip${completionInfo}`;

                        // Set skip event completion flag for timeframe switch detection
                        window.skipEventJustCompleted = true;
                    } else if (isInitialized && message.candle && !validateCandle(message.candle)) {
                        console.error('❌ Invalid candle data in revolutionary_skip_event:', message.candle);
                    }
                    break;

                case 'unified_skip_event':
                    // Unified Skip Event: Handle new unified time architecture skip events
                    if (isInitialized && message.candle && validateCandle(message.candle)) {
                        // Validated candle update for unified architecture
                        const validatedCandle = {
                            time: message.candle.time,
                            open: parseFloat(message.candle.open),
                            high: parseFloat(message.candle.high),
                            low: parseFloat(message.candle.low),
                            close: parseFloat(message.candle.close)
                        };
                        candlestickSeries.update(validatedCandle);

                        // Store last candle data for market orders and limit order triggers
                        window.lastCandleClose = validatedCandle.close;
                        window.lastCandle = validatedCandle;  // ⭐ Store full candle for high/low checks

                        // ⭐ Check limit orders on new candle (Skip Event)
                        if (typeof checkLimitOrders === 'function') {
                            checkLimitOrders(validatedCandle);
                        }

                        console.log('[UNIFIED] Skip Event:', message.timeframe, '- Candle:', message.candle.time);
                        console.log('[UNIFIED] Candle Type:', message.candle_type);
                        console.log('[UNIFIED] Debug Time:', message.debug_time);

                        // 💰 Update PnL for all active positions
                        const currentPrice = validatedCandle.close;
                        if (window.positionLines) {
                            Object.keys(window.positionLines).forEach(positionId => {
                                const posData = window.positionLines[positionId];
                                if (posData && posData.position) {
                                    const position = posData.position;
                                    const direction = position.direction || 'long';
                                    const entry = position.entry_price;
                                    const size = position.size || 1;

                                    // Calculate unrealized PnL
                                    let pnl = 0;
                                    if (direction === 'long') {
                                        pnl = (currentPrice - entry) * size;
                                    } else {
                                        pnl = (entry - currentPrice) * size;
                                    }

                                    // Store updated PnL
                                    posData.unrealizedPnL = pnl;

                                    // PriceLine title remains empty - Canvas labels handle display
                                }
                            });

                            // Render PnL labels on Canvas
                            renderLivePnLLabels();
                        }

                        // Update document title with unified architecture info
                        document.title = `${message.timeframe} Unified Skip (${message.system})`;

                        // Set skip event completion flag for timeframe switch detection
                        window.skipEventJustCompleted = true;
                    } else if (isInitialized && message.candle && !validateCandle(message.candle)) {
                        console.error('[UNIFIED] Invalid candle data in unified_skip_event:', message.candle);
                    }
                    break;

                case 'unified_timeframe_changed':
                    // SUPER-DEFENSIVE Unified Timeframe Change Handler
                    console.log('[UNIFIED-TF] Timeframe Change Event:', message.timeframe, '- Data:', message.data?.length || 0, 'candles');

                    if (isInitialized && message.data && Array.isArray(message.data) && message.data.length > 0) {
                        // ULTRA-STRICT validation with debug logging
                        const validatedData = message.data.filter((candle, index) => {
                            const isValid = validateCandle(candle, false, true); // Enable debug logging
                            if (!isValid) {
                                console.warn(`[UNIFIED-TF] REJECTED candle ${index}:`, candle);
                                return false;
                            }
                            return true;
                        });

                        console.log(`[UNIFIED-TF] Validation: ${message.data.length} original -> ${validatedData.length} valid candles`);

                        if (validatedData.length > 0) {
                            try {
                                // SUPER-DEFENSIVE data cleaning: Force correct format
                                const cleanData = validatedData.map((candle, index) => {
                                    try {
                                        const clean = {
                                            time: Number(candle.time),
                                            open: Number(candle.open),
                                            high: Number(candle.high),
                                            low: Number(candle.low),
                                            close: Number(candle.close)
                                        };

                                        // FINAL validation before return
                                        if (!Number.isFinite(clean.time) || clean.time <= 0 ||
                                            !Number.isFinite(clean.open) || !Number.isFinite(clean.high) ||
                                            !Number.isFinite(clean.low) || !Number.isFinite(clean.close)) {
                                            console.error(`[UNIFIED-TF] EMERGENCY REJECT candle ${index}:`, clean);
                                            return null;
                                        }

                                        return clean;
                                    } catch (cleanError) {
                                        console.error(`[UNIFIED-TF] Error cleaning candle ${index}:`, cleanError, candle);
                                        return null;
                                    }
                                }).filter(candle => candle !== null);

                                console.log(`[UNIFIED-TF] Final clean data: ${cleanData.length} candles`);

                                if (cleanData.length > 0) {
                                    // MULTIPLE TRY-CATCH layers for maximum safety
                                    try {
                                        // Clear existing data first
                                        candlestickSeries.setData([]);
                                        console.log('[UNIFIED-TF] Data cleared successfully');

                                        // Add small delay to prevent race conditions
                                        setTimeout(() => {
                                            try {
                                                // Set cleaned data
                                                candlestickSeries.setData(cleanData);
                                                console.log('[UNIFIED-TF] SUCCESS: Chart data set with', cleanData.length, 'candles for', message.timeframe);
                                                document.title = `${message.timeframe} Chart (${cleanData.length} candles)`;
                                            } catch (setDataError) {
                                                console.error('[UNIFIED-TF] FATAL: setData failed:', setDataError);
                                                console.error('[UNIFIED-TF] Sample clean data:', cleanData.slice(0, 3));

                                                // EMERGENCY fallback: reload page
                                                console.error('[UNIFIED-TF] EMERGENCY: Reloading page due to chart corruption');
                                                location.reload();
                                            }
                                        }, 50);

                                    } catch (clearError) {
                                        console.error('[UNIFIED-TF] Error clearing data:', clearError);
                                    }
                                } else {
                                    console.error('[UNIFIED-TF] No clean candles after final filtering');
                                }

                            } catch (outerError) {
                                console.error('[UNIFIED-TF] Outer processing error:', outerError);
                            }
                        } else {
                            console.error('[UNIFIED-TF] No valid candles after initial filtering for', message.timeframe);
                        }
                    } else {
                        console.error('[UNIFIED-TF] Invalid or empty data in unified_timeframe_changed:', message.data?.length || 'no data');
                    }
                    break;

                case 'debug_control_timeframe_changed':
                    // Debug Control Timeframe Change: Server bestätigt Debug Control Variable Update
                    console.log('🔧 Debug Control TF Change:', message.debug_control_timeframe);
                    console.log('📊 Old Timeframe:', message.old_timeframe);

                    // Detect timeframe switch mode: After skip event + different timeframe = needs special handling
                    if (window.skipEventJustCompleted && message.debug_control_timeframe !== message.old_timeframe) {
                        console.log('🚨 TIMEFRAME SWITCH MODE DETECTED: Skip->Different TF');
                        window.timeframeSwitchMode = true;
                        window.previousSkipTimeframe = message.old_timeframe;

                        // Clear skip flag to prevent interference
                        window.skipEventJustCompleted = false;
                    }

                    // Visual feedback (optional - könnte Button-State updates enthalten)
                    if (message.debug_control_timeframe) {
                        console.log(`✅ Debug Control jetzt auf ${message.debug_control_timeframe} gesetzt`);
                    }
                    break;

                case 'chart_series_recreation':
                    // 🚀 CHART SERIES RECREATION: Complete chart destruction and recreation
                    console.log('[CHART-RECREATION] Chart series recreation command received:', message.command);
                    console.log('[CHART-RECREATION] Reason:', message.reason);

                    try {
                        // PHASE 1: Complete chart destruction
                        console.log('[CHART-RECREATION] Phase 1: Destroying existing chart series...');

                        // Remove all series from chart
                        chart.removeSeries(candlestickSeries);
                        console.log('[CHART-RECREATION] Candlestick series removed');

                        // Small delay to ensure destruction is complete
                        setTimeout(() => {
                            try {
                                // PHASE 2: Create new candlestick series with fresh state
                                console.log('[CHART-RECREATION] Phase 2: Creating new candlestick series...');
                                candlestickSeries = chart.addCandlestickSeries({
                                    upColor: '#089981',
                                    downColor: '#f23645',
                                    borderVisible: false,
                                    wickUpColor: '#089981',
                                    wickDownColor: '#f23645'
                                });

                                // Update global reference after recreation
                                window.candlestickSeries = candlestickSeries;

                                console.log('[CHART-RECREATION] ✅ Chart series recreation completed successfully');
                                console.log('[CHART-RECREATION] Version:', message.command?.version);

                                // Update title to indicate recreation
                                document.title = `Chart Recreated (v${message.command?.version || 'unknown'})`;

                            } catch (recreationError) {
                                console.error('[CHART-RECREATION] FATAL: Recreation failed:', recreationError);
                                console.error('[CHART-RECREATION] EMERGENCY: Reloading page...');
                                location.reload();
                            }
                        }, 100); // Longer delay for complete destruction

                    } catch (destructionError) {
                        console.error('[CHART-RECREATION] Error during destruction:', destructionError);
                        console.error('[CHART-RECREATION] EMERGENCY: Reloading page...');
                        location.reload();
                    }
                    break;

                case 'bulletproof_timeframe_changed':
                    // 🚀 BULLETPROOF TIMEFRAME CHANGE: Enhanced timeframe switching with lifecycle management
                    console.log('[BULLETPROOF-TF] Bulletproof timeframe change received:', message.timeframe);
                    console.log('[BULLETPROOF-TF] Transaction ID:', message.transaction_id);
                    console.log('[BULLETPROOF-TF] Chart recreation required:', message.chart_recreation);

                    if (message.chart_recreation && message.recreation_command) {
                        // Chart recreation was already handled, now just set the data
                        console.log('[BULLETPROOF-TF] Chart recreation completed, setting data...');
                    }

                    // 🛡️ EMERGENCY SAFETY CHECK: Verify candlestickSeries exists after chart recreation
                    if (!candlestickSeries || typeof candlestickSeries.setData !== 'function') {
                        console.error('[BULLETPROOF-TF] CRITICAL: candlestickSeries is invalid after chart recreation');
                        console.error('[BULLETPROOF-TF] EMERGENCY: Triggering page reload...');
                        location.reload();
                        return;
                    }

                    if (isInitialized && message.data && Array.isArray(message.data) && message.data.length > 0) {
                        try {
                            // Use the same ultra-defensive validation as unified_timeframe_changed
                            const validatedData = message.data.filter((candle, index) => {
                                const isValid = validateCandle(candle, false, true);
                                if (!isValid) {
                                    console.warn(`[BULLETPROOF-TF] REJECTED candle ${index}:`, candle);
                                    return false;
                                }
                                return true;
                            });

                            console.log(`[BULLETPROOF-TF] Validation: ${message.data.length} original -> ${validatedData.length} valid candles`);

                            if (validatedData.length > 0) {
                                const cleanData = validatedData.map((candle, index) => {
                                    try {
                                        const clean = {
                                            time: Number(candle.time),
                                            open: Number(candle.open),
                                            high: Number(candle.high),
                                            low: Number(candle.low),
                                            close: Number(candle.close)
                                        };

                                        if (!Number.isFinite(clean.time) || clean.time <= 0 ||
                                            !Number.isFinite(clean.open) || !Number.isFinite(clean.high) ||
                                            !Number.isFinite(clean.low) || !Number.isFinite(clean.close)) {
                                            console.error(`[BULLETPROOF-TF] EMERGENCY REJECT candle ${index}:`, clean);
                                            return null;
                                        }

                                        return clean;
                                    } catch (cleanError) {
                                        console.error(`[BULLETPROOF-TF] Error cleaning candle ${index}:`, cleanError, candle);
                                        return null;
                                    }
                                }).filter(candle => candle !== null);

                                console.log(`[BULLETPROOF-TF] Final clean data: ${cleanData.length} candles`);

                                if (cleanData.length > 0) {
                                    // BULLETPROOF DATA SETTING: Use recreation-safe approach
                                    try {
                                        if (message.chart_recreation) {
                                            // Chart was just recreated, set data directly without clearing
                                            console.log('[BULLETPROOF-TF] Setting data on recreated chart...');

                                            // Extra safety check before setting data
                                            if (!candlestickSeries || typeof candlestickSeries.setData !== 'function') {
                                                throw new Error('candlestickSeries became invalid during data setting');
                                            }

                                            candlestickSeries.setData(cleanData);
                                            console.log('[BULLETPROOF-TF] ✅ SUCCESS: Data set on recreated chart');
                                        } else {
                                            // Standard approach for non-recreation scenarios
                                            console.log('[BULLETPROOF-TF] Using standard data setting...');
                                            candlestickSeries.setData([]);
                                            setTimeout(() => {
                                                try {
                                                    candlestickSeries.setData(cleanData);
                                                    console.log('[BULLETPROOF-TF] ✅ SUCCESS: Standard data setting completed');
                                                } catch (delayedError) {
                                                    console.error('[BULLETPROOF-TF] Delayed setData error:', delayedError);
                                                    location.reload();
                                                }
                                            }, 50);
                                        }
                                    } catch (setDataError) {
                                        console.error('[BULLETPROOF-TF] CRITICAL: setData failed:', setDataError);
                                        console.error('[BULLETPROOF-TF] EMERGENCY: Triggering page reload...');
                                        location.reload();
                                        return;
                                    }

                                    document.title = `${message.timeframe} Bulletproof (${cleanData.length} candles)`;

                                    // Log validation summary
                                    if (message.validation_summary) {
                                        console.log('[BULLETPROOF-TF] Validation summary:', message.validation_summary);
                                    }

                                } else {
                                    console.error('[BULLETPROOF-TF] No clean candles after final filtering');
                                }
                            } else {
                                console.error('[BULLETPROOF-TF] No valid candles after initial filtering');
                            }
                        } catch (error) {
                            console.error('[BULLETPROOF-TF] Processing error:', error);
                            console.error('[BULLETPROOF-TF] EMERGENCY: Reloading page...');
                            location.reload();
                        }
                    } else {
                        console.error('[BULLETPROOF-TF] Invalid or empty data:', message.data?.length || 'no data');
                    }
                    break;

                case 'emergency_recovery_required':
                    // 🚨 EMERGENCY RECOVERY: Handle critical chart corruption
                    console.error('[EMERGENCY] Recovery required:', message.error);
                    console.error('[EMERGENCY] Transaction ID:', message.transaction_id);
                    console.error('[EMERGENCY] Reloading page in 2 seconds...');

                    // Show user notification
                    alert(`Chart error detected: ${message.error}\nPage will reload automatically.`);

                    setTimeout(() => {
                        location.reload();
                    }, 2000);
                    break;

                case 'trade_executed':
                    // 🚀 Trade wurde erfolgreich ausgeführt
                    console.log('✅ Trade executed:', message.position_id);
                    console.log('📊 Account:', message.account_type);
                    console.log('💰 Position:', message.position);
                    console.log('🔍 DEBUG P&L Fields:', {
                        pnl: message.position?.pnl,
                        unrealized_pnl: message.position?.unrealized_pnl,
                        entry_price: message.position?.entry_price,
                        direction: message.position?.direction
                    });

                    // Zeige Position im Chart an
                    if (message.position) {
                        addPositionOverlay(message.position);

                        // 💰 Initial PnL render (starts at 0)
                        setTimeout(() => renderLivePnLLabels(), 100);
                    }

                    // Zeige Erfolgs-Notification
                    const accountLabel = message.account_type === 'ai' ? 'RL-KI' : 'Nutzer';
                    console.log(`✅ Trade auf ${accountLabel} Account ausgeführt`);
                    break;

                case 'position_closed':
                    // 🔴 Position wurde geschlossen
                    console.log('🔴 Position closed:', message.position_id);
                    console.log('💰 Realized PnL:', message.realized_pnl);
                    console.log('🔖 Reason:', message.close_reason);
                    console.log('💵 Close Price:', message.close_price);

                    // Entferne Position vom Chart
                    if (message.position_id) {
                        removePositionOverlay(message.position_id);

                        // Re-render PnL labels (falls noch andere Positionen offen)
                        setTimeout(() => renderLivePnLLabels(), 50);

                        // Zeige Notification
                        const pnlText = message.realized_pnl >= 0
                            ? `+${message.realized_pnl.toFixed(0)}€`
                            : `${message.realized_pnl.toFixed(0)}€`;
                        const reasonText = {
                            'manual': 'Manuell',
                            'stop_loss': 'Stop Loss',
                            'take_profit': 'Take Profit'
                        }[message.close_reason] || message.close_reason;

                        console.log(`🔴 Position geschlossen: ${reasonText} - ${pnlText}`);
                    }
                    break;

                case 'account_update':
                    // 💶 Account-Update empfangen
                    console.log('💰 Account Update:', message.accounts);

                    if (message.accounts) {
                        // Update RL-KI Account
                        if (message.accounts.ai_account) {
                            updateAccountDisplay('ai', message.accounts.ai_account);
                        }

                        // Update Nutzer Account
                        if (message.accounts.user_account) {
                            updateAccountDisplay('user', message.accounts.user_account);
                        }
                    }
                    break;

                case 'error':
                    // ❌ Error from backend
                    console.error('❌ Backend Error:', message.message);
                    alert(`Backend Error: ${message.message}`);
                    break;

                default:
                    console.log('[UNKNOWN] Unknown message type:', message.type);
            }
        }

        // Position Overlay Functions
        function addPositionOverlay(position) {
            const positionId = position.id;

            // RL Action Tracking
            if (window.RLSystem) {
                window.RLSystem.trackAction('add_position', {
                    position_id: positionId,
                    position_type: position.type,
                    entry_price: position.entry_price,
                    stop_loss: position.stop_loss,
                    take_profit: position.take_profit,
                    size: position.size,
                    current_timeframe: window.currentTimeframe,
                    timestamp: new Date()
                });
            }

            // ⭐ NEUE IMPLEMENTATION: Draggable PriceLines für executed Positions
            // Verwende candlestickSeries für PriceLines (TradingView API requirement)

            // Entry PriceLine (draggable, grün für Long, rot für Short)
            const entryColor = position.type === 'LONG' ? '#089981' : '#f23645';

            // Calculate PnL for title
            const currentPrice = position.entry_price; // Will be updated dynamically
            // ⭐ BUGFIX: Backend sendet unrealized_pnl (snake_case), nicht unrealizedPnL (camelCase)
            const unrealizedPnL = position.unrealized_pnl || position.pnl || position.unrealizedPnL || 0;
            const pnlText = `${unrealizedPnL >= 0 ? '+' : ''}${unrealizedPnL.toFixed(0)}€`;
            console.log('🔍 addPositionOverlay P&L:', {
                unrealized_pnl: position.unrealized_pnl,
                pnl: position.pnl,
                unrealizedPnL: position.unrealizedPnL,
                final: unrealizedPnL
            });

            const entryPriceLine = candlestickSeries.createPriceLine({
                price: position.entry_price,
                color: entryColor,
                lineWidth: 2,
                lineStyle: 0, // Solid
                axisLabelVisible: true,
                title: '' // Empty title - Canvas labels will be drawn instead
            });

            // Berechne potenzielle PnL für SL/TP
            const direction = position.direction || (position.type === 'LONG' ? 'long' : 'short');
            const size = position.size || 1;
            const entry = position.entry_price;

            // Stop Loss PriceLine mit potenziellem Verlust
            let slPriceLine = null;
            if (position.sl_price) {
                const slLoss = direction === 'long'
                    ? (position.sl_price - entry) * size
                    : (entry - position.sl_price) * size;
                slPriceLine = candlestickSeries.createPriceLine({
                    price: position.sl_price,
                    color: '#ff4444',
                    lineWidth: 2,
                    lineStyle: 0, // Solid
                    axisLabelVisible: true,
                    title: `SL ${slLoss >= 0 ? '+' : ''}${slLoss.toFixed(0)}€`
                });
            }

            // Take Profit PriceLine mit potenziellem Gewinn
            let tpPriceLine = null;
            if (position.tp_price) {
                const tpProfit = direction === 'long'
                    ? (position.tp_price - entry) * size
                    : (entry - position.tp_price) * size;
                tpPriceLine = candlestickSeries.createPriceLine({
                    price: position.tp_price,
                    color: '#44ff44',
                    lineWidth: 2,
                    lineStyle: 0, // Solid
                    axisLabelVisible: true,
                    title: `TP +${tpProfit.toFixed(0)}€`
                });
            }

            // Initialize positionLines if not exists
            if (!window.positionLines) {
                window.positionLines = {};
                console.log('[Position] Initialized window.positionLines');
            }

            // Speichere PriceLines für diese Position
            window.positionLines[positionId] = {
                entryPriceLine: entryPriceLine,
                slPriceLine: slPriceLine,
                tpPriceLine: tpPriceLine,
                position: position,
                unrealizedPnL: unrealizedPnL // ⭐ BUGFIX: Verwende P&L vom Backend, nicht hardcoded 0
            };

            console.log(`✅ Position overlay added: ${positionId} ${position.type}`, window.positionLines[positionId]);
        }

        function removePositionOverlay(positionId) {
            const positionData = window.positionLines[positionId];
            if (positionData) {
                // Entferne PriceLines
                if (positionData.entryPriceLine) {
                    candlestickSeries.removePriceLine(positionData.entryPriceLine);
                }
                if (positionData.slPriceLine) {
                    candlestickSeries.removePriceLine(positionData.slPriceLine);
                }
                if (positionData.tpPriceLine) {
                    candlestickSeries.removePriceLine(positionData.tpPriceLine);
                }

                // Lösche aus Container
                delete window.positionLines[positionId];

                // ⭐ BUGFIX: Lösche auch Close Button Position
                if (window.closeButtonPositions && window.closeButtonPositions[positionId]) {
                    delete window.closeButtonPositions[positionId];
                    console.log(`🔴 Close button removed for: ${positionId}`);
                }

                // ⭐ CRITICAL FIX: Immediately clear and re-render labels
                // Clear canvas if no more positions, otherwise re-render remaining
                if (Object.keys(window.positionLines).length === 0 && window.pnlLabelsCanvas && window.pnlLabelsCtx) {
                    // No more positions → clear canvas immediately
                    const canvas = window.pnlLabelsCanvas;
                    const ctx = window.pnlLabelsCtx;
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    console.log('🧹 Canvas cleared - no more positions');
                } else {
                    // Still have positions → re-render remaining labels
                    setTimeout(() => renderLivePnLLabels(), 50);
                }

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

        /**
         * Renders live PnL labels on Canvas for all active positions
         * Shows unrealized PnL on the left side of entry price lines
         */
        function renderLivePnLLabels() {
            // console.log('[PnL] renderLivePnLLabels() called'); // Removed: Called every frame

            // Create PnL labels canvas if it doesn't exist
            if (!window.pnlLabelsCanvas || !window.pnlLabelsCtx) {
                console.log('[PnL] Canvas not found, creating overlay...');

                const chartContainer = document.getElementById('chart_container');
                if (!chartContainer) {
                    console.error('[PnL] Chart container not found');
                    return;
                }

                // Create canvas overlay for PnL labels
                let canvas = document.getElementById('pnl-labels-canvas');
                if (!canvas) {
                    canvas = document.createElement('canvas');
                    canvas.id = 'pnl-labels-canvas';
                    canvas.style.position = 'absolute';
                    canvas.style.top = '0';
                    canvas.style.left = '0';
                    canvas.style.pointerEvents = 'none'; // Transparent for clicks - clicks handled on chart container
                    canvas.style.zIndex = '10'; // Above position-canvas
                    canvas.width = chartContainer.clientWidth;
                    canvas.height = chartContainer.clientHeight;
                    chartContainer.appendChild(canvas);
                }

                window.pnlLabelsCanvas = canvas;
                window.pnlLabelsCtx = canvas.getContext('2d');
                console.log('[PnL] Canvas overlay created');
            }

            if (!window.positionLines || Object.keys(window.positionLines).length === 0) {
                // console.warn('[PnL] No active positions'); // Removed: Called every frame
                // ⭐ CRITICAL FIX: Clear canvas when no positions exist
                if (window.pnlLabelsCanvas && window.pnlLabelsCtx) {
                    const canvas = window.pnlLabelsCanvas;
                    const ctx = window.pnlLabelsCtx;
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
                return;
            }

            if (!window.chart || !window.candlestickSeries) {
                // console.warn('[PnL] Chart or candlestickSeries not available'); // Removed: Called every frame
                return;
            }

            // console.log('[PnL] Rendering for', Object.keys(window.positionLines).length, 'positions'); // Removed: Called every frame

            const ctx = window.pnlLabelsCtx;
            const canvas = window.pnlLabelsCanvas;
            const chartContainer = document.getElementById('chart_container');

            if (!chartContainer) {
                console.error('[PnL] Chart container not found during rendering');
                return;
            }

            // ⭐⭐⭐ CRITICAL: Clear canvas before redrawing to prevent text overlap ⭐⭐⭐
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            // console.log('[PnL] Canvas cleared'); // Removed: Called every frame

            // Get chart time scale for price-to-pixel conversion
            const timeScale = window.chart.timeScale();

            // Store close button positions for click detection
            if (!window.closeButtonPositions) {
                window.closeButtonPositions = {};
            }
            window.closeButtonPositions = {}; // Reset

            // Iterate over all active positions
            Object.keys(window.positionLines).forEach(positionId => {
                const posData = window.positionLines[positionId];
                // console.log(`[PnL] Processing position ${positionId}:`, posData); // Removed: Called every frame

                if (!posData || !posData.position || !posData.entryPriceLine) {
                    // console.warn(`[PnL] Invalid position data for ${positionId}`); // Removed: Called every frame
                    return;
                }

                const position = posData.position;
                const entryPrice = position.entry_price;
                const pnl = posData.unrealizedPnL || 0;

                // console.log(`[PnL] Position ${positionId} data:`, { entryPrice, pnl }); // Removed: Called every frame

                // Convert price to Y coordinate using TradingView API
                // NOTE: priceToCoordinate() is called directly on the series, not on priceScale()!
                const yCoord = window.candlestickSeries.priceToCoordinate(entryPrice);

                if (yCoord === null || yCoord === undefined) {
                    // console.warn(`[PnL] Price not in visible range for ${positionId}`); // Removed: Called every frame
                    return;
                }

                // console.log(`[PnL] Y coordinate for ${positionId}: ${yCoord}`); // Removed: Called every frame

                // Three separate labels on right side: [Size] [PnL] [X]
                // Position labels BEFORE the price scale (Y-axis), not on top of it
                const chartWidth = chartContainer.clientWidth;
                const yPos = yCoord;
                const size = position.size || 1;

                // Get price scale width to position labels before it
                const priceScaleWidth = 70; // Price scale width (Y-axis)
                const marginRight = 15; // Margin from price scale (more space)

                // Format texts
                const sizeText = `${size}`;
                const pnlText = `${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)}€`;
                const closeText = 'X';

                // Colors - Modern Trading Theme
                const pnlColor = pnl >= 0 ? '#26a69a' : '#ef5350'; // Teal green / Soft red
                const pnlBgColor = pnl >= 0 ? 'rgba(38, 166, 154, 0.15)' : 'rgba(239, 83, 80, 0.15)'; // Light tint
                const sizeBgColor = 'rgba(66, 133, 244, 0.15)'; // Light blue tint
                const sizeColor = '#4285f4'; // Google blue
                const closeBgColor = 'rgba(239, 83, 80, 0.9)'; // Solid red
                const closeColor = '#ffffff';

                // Styling - Larger and more readable
                ctx.font = 'bold 13px Arial'; // Slightly larger font
                const padding = 6;
                const rectHeight = 22; // Taller boxes
                const gap = 5; // Gap between boxes

                // Measure widths
                const sizeWidth = ctx.measureText(sizeText).width + padding * 2;
                const pnlWidth = ctx.measureText(pnlText).width + padding * 2;
                const xWidth = ctx.measureText(closeText).width + padding * 2;

                // Calculate positions from right to left, before price scale
                let currentX = chartWidth - priceScaleWidth - marginRight;

                // === X Button (rightmost) ===
                const xBoxX = currentX - xWidth;
                const xBoxY = yPos - rectHeight / 2;

                // Modern rounded corners effect (fake with border)
                ctx.fillStyle = closeBgColor;
                ctx.fillRect(xBoxX, xBoxY, xWidth, rectHeight);
                ctx.strokeStyle = '#d32f2f'; // Darker red border
                ctx.lineWidth = 1.5;
                ctx.strokeRect(xBoxX, xBoxY, xWidth, rectHeight);

                ctx.fillStyle = closeColor;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(closeText, xBoxX + xWidth / 2, yPos);

                // Store X button for click detection
                window.closeButtonPositions[positionId] = {
                    x: xBoxX,
                    y: xBoxY,
                    width: xWidth,
                    height: rectHeight,
                    positionId: positionId
                };

                currentX = xBoxX - gap;

                // === PnL Label (middle) ===
                const pnlBoxX = currentX - pnlWidth;
                const pnlBoxY = yPos - rectHeight / 2;

                ctx.fillStyle = pnlBgColor;
                ctx.fillRect(pnlBoxX, pnlBoxY, pnlWidth, rectHeight);
                ctx.strokeStyle = pnlColor;
                ctx.lineWidth = 1.5;
                ctx.strokeRect(pnlBoxX, pnlBoxY, pnlWidth, rectHeight);

                ctx.fillStyle = pnlColor;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(pnlText, pnlBoxX + pnlWidth / 2, yPos);

                currentX = pnlBoxX - gap;

                // === Size Label (leftmost) ===
                const sizeBoxX = currentX - sizeWidth;
                const sizeBoxY = yPos - rectHeight / 2;

                ctx.fillStyle = sizeBgColor;
                ctx.fillRect(sizeBoxX, sizeBoxY, sizeWidth, rectHeight);
                ctx.strokeStyle = sizeColor;
                ctx.lineWidth = 1.5;
                ctx.strokeRect(sizeBoxX, sizeBoxY, sizeWidth, rectHeight);

                ctx.fillStyle = sizeColor;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(sizeText, sizeBoxX + sizeWidth / 2, yPos);

                // console.log(`[PnL] ✅ Successfully rendered PnL label for ${positionId}`); // Removed: Called every frame
            });

            // console.log('[PnL] renderLivePnLLabels() completed'); // Removed: Called every frame
        }

        // ===== POSITION BOX MANAGER - ENTERPRISE REPOSITORY PATTERN =====
        // Verwaltet mehrere Position Boxes gleichzeitig mit CRUD Operations
        window.positionBoxManager = {
            boxes: [],              // Array aller Position Boxes
            activeBoxId: null,      // Aktuell selektierte Box
            canvas: null,           // Shared Canvas für alle Boxes
            ctx: null,              // Shared Canvas Context

            // Initialisierung
            init(canvas, ctx) {
                this.canvas = canvas;
                this.ctx = ctx;
                console.log('📦 Position Box Manager initialized');
            },

            // CRUD: Create - Box hinzufügen
            add(box) {
                if (!box.id) {
                    box.id = 'BOX_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                }
                this.boxes.push(box);
                console.log(`➕ Box added: ${box.id} (Total: ${this.boxes.length})`);
                return box.id;
            },

            // CRUD: Read - Box abrufen
            get(id) {
                return this.boxes.find(box => box.id === id);
            },

            getAll() {
                return [...this.boxes];  // Return copy für Sicherheit
            },

            // CRUD: Update - Box aktualisieren
            update(id, changes) {
                const box = this.get(id);
                if (box) {
                    Object.assign(box, changes);
                    console.log(`✏️ Box updated: ${id}`);
                    return true;
                }
                return false;
            },

            // CRUD: Delete - Box entfernen
            remove(id) {
                const index = this.boxes.findIndex(box => box.id === id);
                if (index !== -1) {
                    this.boxes.splice(index, 1);
                    console.log(`🗑️ Box removed: ${id} (Remaining: ${this.boxes.length})`);
                    return true;
                }
                return false;
            },

            // Alle Boxes löschen
            clear() {
                const count = this.boxes.length;
                this.boxes = [];
                this.activeBoxId = null;
                console.log(`🧹 All boxes cleared (${count} boxes deleted)`);
            },

            // Query: Nur sichtbare Boxes (im Chart-Bereich)
            getVisible(timeScale, chartWidth) {
                return this.boxes.filter(box => {
                    try {
                        let x1, x2;

                        // ⭐⭐⭐ NEU: Verwende TIMESTAMPS (stabil bei Datenladen) ⭐⭐⭐
                        if (box.timeStart && box.timeEnd) {
                            const allData = candlestickSeries.data();

                            if (allData && allData.length > 0) {
                                const startCandle = allData.find(c => c.time === box.timeStart);
                                const endCandle = allData.find(c => c.time === box.timeEnd);

                                if (startCandle && endCandle) {
                                    x1 = timeScale.timeToCoordinate(startCandle.time);
                                    x2 = timeScale.timeToCoordinate(endCandle.time);
                                }
                            }
                        }

                        // Fallback: Direkte Timestamp-Konvertierung
                        if (x1 === null || x2 === null || x1 === undefined || x2 === undefined) {
                            x1 = timeScale.timeToCoordinate(box.timeStart);
                            x2 = timeScale.timeToCoordinate(box.timeEnd);
                        }

                        // Box ist sichtbar wenn MINDESTENS EINE Koordinate valide ist
                        if (x1 === null && x2 === null) {
                            return false;  // Komplett außerhalb
                        }

                        // Box ist sichtbar wenn im Chart-Bereich (mit 100px Toleranz)
                        const isVisible = (x1 !== null && x1 >= -100 && x1 <= chartWidth + 100) ||
                                         (x2 !== null && x2 >= -100 && x2 <= chartWidth + 100) ||
                                         (x1 !== null && x2 === null) ||  // Zukunfts-Box
                                         (x1 < 0 && x2 > chartWidth);

                        return isVisible;
                    } catch (error) {
                        console.warn(`⚠️ Error checking visibility for box ${box.id}:`, error);
                        return false;
                    }
                });
            },

            // Anzahl der Boxes
            count() {
                return this.boxes.length;
            },

            // Active Box Management
            setActive(id) {
                if (this.get(id)) {
                    this.activeBoxId = id;
                    console.log(`🎯 Active box: ${id}`);
                }
            },

            getActive() {
                return this.activeBoxId ? this.get(this.activeBoxId) : null;
            },

            // Rendering: Alle sichtbaren Boxes zeichnen
            drawAll() {
                if (!this.canvas || !this.ctx) {
                    console.warn('⚠️ Canvas not initialized');
                    return;
                }

                // ⭐ Setze Flag damit drawPositionBox() nicht clearRect() macht
                window._managerDrawing = true;

                // Clear canvas EINMAL
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

                // Get visible boxes
                const visibleBoxes = this.getVisible(
                    chart.timeScale(),
                    this.canvas.width
                );

                // console.log(`🎨 Drawing ${visibleBoxes.length} / ${this.boxes.length} boxes`);

                // Draw each visible box
                visibleBoxes.forEach(box => {
                    this.drawBox(box);
                });

                // ⭐ Reset Flag
                window._managerDrawing = false;
            },

            // Rendering: Eine spezifische Box zeichnen
            drawBox(box) {
                // ⭐ TEMPORÄRE LÖSUNG: Verwende alte drawPositionBox() mit Trick
                // Setze temporär currentPositionBox für Legacy-Kompatibilität
                const oldBox = window.currentPositionBox;
                window.currentPositionBox = box;

                // Rufe alte Draw-Funktion auf
                if (typeof drawPositionBox === 'function') {
                    drawPositionBox();
                } else {
                    console.warn('⚠️ drawPositionBox not available');
                }

                // Restore
                window.currentPositionBox = oldBox;
            }
        };

        // Position Box Functions - NEUE IMPLEMENTIERUNG MIT ECHTEN RECHTECKEN
        function createPositionBox(time, entryPrice, clickX, clickY, isShort = false) {
            // ⭐ ÄNDERUNG: Mehrere Boxes erlaubt - alte Box NICHT mehr löschen
            // (Für Backwards Compatibility: Legacy Code-Pfade bleiben)

            // 1:1 Risk:Reward Ratio (0.125% Risk, 0.125% Reward) - 50% kleiner
            const riskPercent = 0.00125; // 0.125%
            const rewardPercent = 0.00125; // 0.125%

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
            // console.log('📍 Click-Position:', clickX, clickY, 'Container Breite:', document.getElementById('chart_container')?.clientWidth);

            // Box Dimensionen - DYNAMISCH basierend auf Timeframe und Click-Zeit
            const centerTime = time || Math.floor(Date.now() / 1000);

            // Berechne angemessene Box-Breite basierend auf aktuellem Timeframe
            function getTimeframeBasedBoxWidth() {
                const tf = window.currentTimeframe || '5m';
                const timeframeMinutes = {
                    '1m': 1,
                    '2m': 2,
                    '3m': 3,
                    '5m': 5,
                    '15m': 15,
                    '30m': 30,
                    '1h': 60,
                    '4h': 240
                };

                const minutes = timeframeMinutes[tf] || 5;
                // ⭐ ÄNDERUNG: 15 Kerzen breit (statt 4) für bessere Sichtbarkeit
                const candleCount = 15;
                const boxWidthSeconds = minutes * 60 * candleCount;

                // console.log(`📏 Timeframe ${tf}: ${minutes}min * ${candleCount} Kerzen = ${boxWidthSeconds}s Box-Breite`);
                return boxWidthSeconds;
            }

            const boxWidth = getTimeframeBasedBoxWidth();

            // ⭐ FIX: Verwende MITTE des sichtbaren Chart-Bereichs (garantiert sichtbar!)
            const timeScale = chart.timeScale();
            const visibleRange = timeScale.getVisibleLogicalRange();

            let boxCenterTime = centerTime;  // Default: Click-Zeit

            if (visibleRange && candlestickSeries) {
                try {
                    // ⭐ Hole alle Daten von der Series
                    const allData = candlestickSeries.data();

                    if (allData && allData.length > 0) {
                        // ⭐⭐⭐ ZENTRIERUNG FIX: Finde Kerze basierend auf PIXEL-Position, nicht Zeit! ⭐⭐⭐
                        let clickIndex = -1;
                        let startIndex = -1;  // Deklaration vor if-Block
                        let endIndex = -1;    // Deklaration vor if-Block

                        if (clickX !== null && clickX !== undefined) {
                            // ⭐⭐⭐ FINALER ANSATZ: Box beginnt bei Click, geht IMMER 15 Kerzen nach rechts! ⭐⭐⭐

                            // 1. Finde Click-Kerze (am nächsten zum Click-Punkt)
                            let minClickDiff = Infinity;

                            for (let i = 0; i < allData.length; i++) {
                                const candleX = chart.timeScale().timeToCoordinate(allData[i].time);
                                if (candleX === null) continue;

                                const diff = Math.abs(candleX - clickX);
                                if (diff < minClickDiff) {
                                    minClickDiff = diff;
                                    clickIndex = i;
                                }
                            }

                            // 2. Box beginnt bei Click-Kerze und geht IMMER 15 Kerzen nach rechts (auch wenn keine Daten)
                            const candleCount = 15;
                            startIndex = clickIndex;  // ⭐ Box beginnt HIER

                            // ⭐⭐⭐ NEU: Keine Begrenzung auf vorhandene Kerzen! ⭐⭐⭐
                            // End-Index kann über die Daten hinausgehen - wird später virtuell berechnet
                            endIndex = clickIndex + candleCount - 1;  // 15 Kerzen total (Start-Kerze + 14 weitere)

                            // console.log(`🎯 Click-Kerze gefunden: Index ${clickIndex}, X-Position: ${clickX.toFixed(1)}px`);
                            // console.log(`📦 Box: Start-Index=${startIndex}, End-Index=${endIndex} (${candleCount} Kerzen - virtuell wenn nötig)`);
                        } else {
                            // Fallback: Zeit-basierte Suche (alte Methode)
                            let minDiff = Infinity;

                            for (let i = 0; i < allData.length; i++) {
                                const diff = Math.abs(allData[i].time - centerTime);
                                if (diff < minDiff) {
                                    minDiff = diff;
                                    clickIndex = i;
                                }
                            }

                            // Berechne Start/End für Fallback (ab Click-Kerze nach rechts, IMMER 15 Kerzen)
                            const candleCount = 15;
                            startIndex = clickIndex;
                            endIndex = clickIndex + candleCount - 1;  // ⭐ Keine Begrenzung!

                            console.log(`🎯 Kerze gefunden via Zeit: Index ${clickIndex}, Differenz: ${minDiff}s`);
                        }

                        // Fallback: Falls keine Kerze gefunden, verwende Chart-Mitte
                        if (clickIndex === -1) {
                            const middleLogical = (visibleRange.from + visibleRange.to) / 2;
                            clickIndex = Math.floor(Math.max(0, Math.min(allData.length - 1, middleLogical)));

                            // Berechne Start/End für Chart-Mitte-Fallback (ab Mitte nach rechts, IMMER 15 Kerzen)
                            const candleCount = 15;
                            startIndex = clickIndex;
                            endIndex = clickIndex + candleCount - 1;  // ⭐ Keine Begrenzung!
                        }

                        // ⭐ Zeit aus nächstgelegener Kerze holen
                        const nearestCandleTime = allData[clickIndex]?.time;

                        if (nearestCandleTime) {
                            boxCenterTime = nearestCandleTime;

                            // ⭐⭐⭐ NEU: Verwende die berechneten Start/End-Indices direkt! ⭐⭐⭐
                            // Keine Kerzen-Addition mehr - Indices wurden bereits pixel-basiert berechnet

                            // Validiere Start-Index (muss existieren)
                            const validStartIndex = Math.max(0, Math.min(allData.length - 1, startIndex));

                            // ⭐⭐⭐ NEU: End-Index NICHT begrenzen - wird virtuell berechnet! ⭐⭐⭐
                            const validEndIndex = endIndex;  // Kann über allData.length hinausgehen!

                            // ⭐⭐⭐ SPEICHERE INDICES in Temp-Variablen (für newBox) ⭐⭐⭐
                            window._boxStartIndex = validStartIndex;
                            window._boxEndIndex = validEndIndex;

                            // ⭐⭐⭐ ZEITEN: Start = echte Kerze, Ende = virtuell berechnet! ⭐⭐⭐
                            window._boxTimeStart = allData[validStartIndex].time;
                            // End-Zeit = Start-Zeit + (15 Kerzen * Timeframe) - IMMER genau 15 Kerzen!
                            window._boxTimeEnd = window._boxTimeStart + boxWidth;

                            // console.log(`📊 Box ab Click-Kerze nach rechts (Index ${clickIndex} von ${allData.length})`);
                            // console.log(`📍 Box Kerzen-Indices: Start=${validStartIndex}, Ende=${validEndIndex} (15 Kerzen - virtuell)`);
                            // console.log(`📍 Box Timestamps: Start=${window._boxTimeStart}, Ende=${window._boxTimeEnd} (+${boxWidth}s)`);
                        } else {
                            console.warn('⚠️ Keine Zeit in allData[middleIndex] - verwende centerTime');
                        }
                    } else {
                        console.warn('⚠️ Keine Daten verfügbar - verwende centerTime');
                    }
                } catch (error) {
                    console.error('❌ Fehler beim Ermitteln der sichtbaren Mitte:', error);
                }
            } else {
                console.warn('❌ Kein sichtbarer Bereich oder Series verfügbar - verwende centerTime');
            }

            // ⭐ FIX: Verwende exakte Kerzen-Zeiten (garantiert in Daten!)
            // Falls window._boxTimeStart/End gesetzt wurden, verwende diese, sonst Fallback
            const timeStart = window._boxTimeStart || (boxCenterTime - boxWidth / 2);
            const timeEnd = window._boxTimeEnd || (boxCenterTime + boxWidth / 2);

            // ⭐⭐⭐ Hole Kerzen-Indices aus Temp-Variablen ⭐⭐⭐
            const candleStartIndex = window._boxStartIndex !== undefined ? window._boxStartIndex : null;
            const candleEndIndex = window._boxEndIndex !== undefined ? window._boxEndIndex : null;

            // Cleanup: Temp-Variablen entfernen
            delete window._boxTimeStart;
            delete window._boxTimeEnd;
            delete window._boxStartIndex;
            delete window._boxEndIndex;

            // ⭐ Position Box Object erstellen (für Manager)
            const newBox = {
                id: null,  // Wird vom Manager gesetzt
                entryPrice: entryPrice,
                stopLoss: stopLoss,
                takeProfit: takeProfit,
                time: boxCenterTime,   // ⭐ Sichtbare Chart-Mitte (garantiert sichtbar!)

                // ⭐⭐⭐ NEU: PRIMÄRE KERZEN-INDEX-BINDUNG (eliminiert Zoom-Shift) ⭐⭐⭐
                candleStartIndex: candleStartIndex,  // Z.B. 95 (Start-Kerze im Daten-Array)
                candleEndIndex: candleEndIndex,      // Z.B. 110 (End-Kerze im Daten-Array)

                // Legacy: Timestamps als Fallback für TF-Wechsel
                timeStart: timeStart,  // Start-Zeit der Box
                timeEnd: timeEnd,      // End-Zeit der Box
                width: boxWidth,
                isResizing: false,
                resizeHandle: null,
                isShort: isShort,
                direction: isShort ? 'short' : 'long',  // ⭐ FIX: Direction explizit setzen

                // NEUE X-Koordinaten basierend auf Zeit und Click-Position
                clickX: clickX || null,  // Echte Click-X-Koordinate
                clickY: clickY || null,  // Echte Click-Y-Koordinate

                // Zeit-basierte X-Koordinaten anstatt Pixel-basierte (für Legacy-Kompatibilität)
                legacyTimeStart: timeStart,  // Start-Zeit der Box
                legacyTimeEnd: timeEnd,      // End-Zeit der Box

                // Fallback für Legacy-Support (schmale Box um Click-Position)
                x1Percent: clickX ? Math.max(0, (clickX - 30) / document.getElementById('chart_container').clientWidth) : 0.47,  // 30px links vom Klick
                x2Percent: clickX ? Math.min(1, (clickX + 30) / document.getElementById('chart_container').clientWidth) : 0.53,  // 30px rechts vom Klick

                // DIREKTE Y-KOORDINATEN FÜR SOFORTIGE UPDATES - Entry Level an exakter Click-Position
                entryY: clickY || null,  // ⭐ Verwende Click-Y für Entry Level
                slY: null,
                tpY: null

                // ⛔ ENTFERNT: coordinateCache
                // Koordinaten werden jetzt IMMER frisch in drawPositionBox() berechnet
                // Grund: Cache verursachte Bug bei vertikalem Pan (Y-Koordinaten blieben alt)
            };

            // ⭐ ÄNDERUNG: Box zu Manager hinzufügen statt Singleton
            const boxId = window.positionBoxManager.add(newBox);
            window.positionBoxManager.setActive(boxId);

            // ⭐ Backwards Compatibility: Auch als currentPositionBox setzen
            window.currentPositionBox = newBox;

            // Canvas erstellen (nur beim ersten Mal)
            if (!window.positionBoxManager.canvas) {
                createCanvasOverlay();
                setupIntelligentCanvasHover();
            }

            // ⭐ ÄNDERUNG: Alle Boxes zeichnen statt nur eine
            window.positionBoxManager.drawAll();

            // ⭐⭐⭐ DEAKTIVIERT: Price Lines für Position Tool nicht erwünscht ⭐⭐⭐
            // createPriceLines(entryPrice, stopLoss, takeProfit);

            // console.log(`📦 Neue Position Box erstellt: ${boxId} (Total: ${window.positionBoxManager.count()})`);

            // ⭐ REMOVED: Trade Modal wird NUR über Buy-Button ($) geöffnet
            // Trade Modal wird nicht automatisch bei Position Box Erstellung geöffnet

            return boxId;  // Return Box ID für weitere Verwendung
        }

        function createCanvasOverlay() {
            // ⭐ BUG FIX: Cleanup alte/fehlerhafte Canvas-Instanzen
            const existingCanvas = document.getElementById('position-canvas');
            if (existingCanvas) {
                // console.log('📄 Canvas bereits vorhanden, verwende existierenden');

                // Validiere Canvas-Position und Größe
                const chartContainer = document.getElementById('chart_container');
                if (!chartContainer) {
                    console.error('❌ Chart Container nicht gefunden!');
                    return;
                }

                // Stelle sicher dass Canvas korrekt im Container ist
                if (existingCanvas.parentElement !== chartContainer) {
                    console.warn('⚠️ Canvas hat falschen Parent, re-parenting...');
                    chartContainer.appendChild(existingCanvas);
                }

                // ⭐ BUG FIX: Setze overflow hidden auch bei existierendem Canvas
                chartContainer.style.overflow = 'hidden';

                // ⭐⭐⭐ ALIGNMENT FIX: Update Position relativ zu TradingView Canvas ⭐⭐⭐
                const tvCanvas = chartContainer.querySelector('canvas:not(#position-canvas)');
                if (tvCanvas) {
                    const tvRect = tvCanvas.getBoundingClientRect();
                    const containerRect = chartContainer.getBoundingClientRect();
                    const canvasTop = tvRect.top - containerRect.top;
                    const canvasLeft = tvRect.left - containerRect.left;

                    existingCanvas.style.top = `${canvasTop}px`;
                    existingCanvas.style.left = `${canvasLeft}px`;
                    console.log('📐 Canvas Position aktualisiert:', {top: canvasTop, left: canvasLeft});
                }

                // Update Größe falls Container-Größe sich geändert hat
                // ⭐ FIX: Verwende Container-Größe (KEIN DPR-Scaling)
                const targetWidth = chartContainer.clientWidth;
                const targetHeight = chartContainer.clientHeight;

                if (existingCanvas.width !== targetWidth || existingCanvas.height !== targetHeight) {
                    existingCanvas.width = targetWidth;
                    existingCanvas.height = targetHeight;
                    // ⭐ FIX: CSS-Größe auch aktualisieren
                    existingCanvas.style.width = `${chartContainer.clientWidth}px`;
                    existingCanvas.style.height = `${chartContainer.clientHeight}px`;

                    console.log('📏 Canvas-Größe aktualisiert:', existingCanvas.width, 'x', existingCanvas.height, '(CSS:', existingCanvas.style.width, 'x', existingCanvas.style.height, ')');
                }

                // ⭐ Update Manager References
                if (!window.positionBoxManager.canvas) {
                    window.positionBoxManager.init(existingCanvas, existingCanvas.getContext('2d'));
                }

                // Backwards Compatibility
                window.positionCanvas = existingCanvas;
                window.positionCtx = existingCanvas.getContext('2d');
                return;
            }

            // ⭐ Erstelle neuen Canvas (nur beim ersten Mal)
            const chartContainer = document.getElementById('chart_container');
            if (!chartContainer) {
                console.error('❌ Chart Container nicht gefunden - kann Canvas nicht erstellen!');
                return;
            }

            // Validiere Container-Dimensionen
            if (chartContainer.clientWidth === 0 || chartContainer.clientHeight === 0) {
                console.error('❌ Chart Container hat keine Dimensionen!', {
                    width: chartContainer.clientWidth,
                    height: chartContainer.clientHeight
                });
                return;
            }

            // ⭐⭐⭐ ALIGNMENT FIX: Finde TradingView Chart Canvas für exakte Positionierung ⭐⭐⭐
            const tvCanvas = chartContainer.querySelector('canvas');
            let canvasTop = 0;
            let canvasLeft = 0;

            if (tvCanvas) {
                const tvRect = tvCanvas.getBoundingClientRect();
                const containerRect = chartContainer.getBoundingClientRect();
                canvasTop = tvRect.top - containerRect.top;
                canvasLeft = tvRect.left - containerRect.left;
                // console.log('📐 TradingView Canvas Offset:', {top: canvasTop, left: canvasLeft});
            } else {
                console.warn('⚠️ TradingView Canvas nicht gefunden - verwende 0 Offset');
            }

            const canvas = document.createElement('canvas');
            canvas.id = 'position-canvas';
            canvas.style.position = 'absolute';
            canvas.style.top = `${canvasTop}px`;  // ⭐ Aligned mit TradingView Canvas
            canvas.style.left = `${canvasLeft}px`; // ⭐ Aligned mit TradingView Canvas
            // ⭐ FIX: CSS-Größe = Container-Größe (NICHT Canvas-Pixel-Größe!)
            canvas.style.width = `${chartContainer.clientWidth}px`;
            canvas.style.height = `${chartContainer.clientHeight}px`;
            canvas.style.maxWidth = '100%';  // ⭐ Verhindere Overflow
            canvas.style.maxHeight = '100%'; // ⭐ Verhindere Overflow
            canvas.style.pointerEvents = 'none';  // ⭐ STANDARD: 'none' → Events gehen zum Chart durch
            canvas.style.zIndex = '1000';

            // ⭐ FIX: Canvas intern = CSS-Größe (KEIN DPR-Scaling)
            // Grund: Vermeidet Koordinaten-Skalierungs-Probleme mit Hit-Testing
            canvas.width = chartContainer.clientWidth;
            canvas.height = chartContainer.clientHeight;

            // ⭐ DEBUG: Canvas-Größen
            console.log('🎨 Position Canvas erstellt (DPR-neutral):', {
                cssSize: `${canvas.style.width} x ${canvas.style.height}`,
                internalSize: `${canvas.width}px x ${canvas.height}px`,
                containerSize: `${chartContainer.clientWidth}px x ${chartContainer.clientHeight}px`
            });

            // ⭐⭐⭐ BUG FIX: Verhindere Canvas-Overflow ⭐⭐⭐
            chartContainer.style.position = 'relative';
            chartContainer.style.overflow = 'hidden';  // Kritisch: Verhindert zweiten Chart!

            chartContainer.appendChild(canvas);

            // console.log('📄 Canvas erstellt:', {
            //     width: canvas.width,
            //     height: canvas.height,
            //     top: canvas.style.top,
            //     left: canvas.style.left,
            //     tvCanvasSize: tvCanvas ? `${tvCanvas.width}x${tvCanvas.height}` : 'N/A'
            // });

            const ctx = canvas.getContext('2d');

            // ⭐ Initialize Manager mit Canvas
            window.positionBoxManager.init(canvas, ctx);

            // Backwards Compatibility
            window.positionCanvas = canvas;
            window.positionCtx = ctx;

            // Mouse Events für Resize
            canvas.addEventListener('mousedown', onCanvasMouseDown);
            canvas.addEventListener('mousemove', onCanvasMouseMove);
            canvas.addEventListener('mouseup', onCanvasMouseUp);

            // console.log('📄 Canvas Overlay erstellt:', {
            //     width: canvas.width,
            //     height: canvas.height,
            //     parent: chartContainer.id
            // });
        }

        // ⭐ ENTFERNT: Nicht mehr benötigt - Canvas bleibt immer 'auto'
        // Events werden jetzt selektiv in Event-Handlern verarbeitet

        // ⭐ FIX: Intelligente Hover-Detection - Cursor Updates
        function setupIntelligentCanvasHover() {
            const chartContainer = document.getElementById('chart_container');
            if (!chartContainer) return;

            // ⭐ NEUE STRATEGIE: Hover-Detection auf Chart Container, nicht Canvas
            // Canvas hat 'pointer-events: none' → Events gehen durch zum Chart
            // Wir schalten Canvas nur auf 'auto' wenn über Box/Buttons
            chartContainer.addEventListener('mousemove', function(e) {
                const canvas = window.positionCanvas;
                if (!canvas) {
                    return;
                }

                // ⭐ BUGFIX: Prüfe auch auf closeButtonPositions, nicht nur currentPositionBox
                const hasPositionBox = !!window.currentPositionBox;
                const hasCloseButtons = window.closeButtonPositions && Object.keys(window.closeButtonPositions).length > 0;

                if (!hasPositionBox && !hasCloseButtons) {
                    canvas.style.pointerEvents = 'none';
                    return;
                }

                const rect = canvas.getBoundingClientRect();

                // ⭐ FIX: Skaliere Mouse-Koordinaten von CSS zu Canvas
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;

                const x = (e.clientX - rect.left) * scaleX;
                const y = (e.clientY - rect.top) * scaleY;

                // Prüfe ob Maus über Position Box oder Buttons ist
                const box = window.currentPositionBox;
                const isOverBox = isPointOverPositionBox(x, y, box);
                const isOverButtons = isPointOverButtons(x, y);

                // ⭐ DYNAMISCHE POINTER-EVENTS: Nur aktivieren wenn über Box/Buttons
                if (isOverBox || isOverButtons) {
                    canvas.style.pointerEvents = 'auto';

                    // Cursor-Update für bessere UX
                    if (isOverButtons) {
                        canvas.style.cursor = 'pointer';
                    } else if (isOverBox) {
                        canvas.style.cursor = 'move';
                    }
                } else {
                    canvas.style.pointerEvents = 'none';  // Events gehen zum Chart durch
                    canvas.style.cursor = 'default';
                }
            });
        }

        // ⭐ NEUE FUNKTION: Prüft ob Punkt über Buttons (X oder Buy) liegt
        function isPointOverButtons(x, y) {
            // Prüfe Delete Button
            if (window.deleteButtonCoords) {
                const btn = window.deleteButtonCoords;
                const distance = Math.sqrt(
                    Math.pow(x - btn.x, 2) + Math.pow(y - btn.y, 2)
                );
                if (distance <= (btn.size / 2) + 5) {  // 5px extra Toleranz
                    return true;
                }
            }

            // Prüfe Buy Button (falls vorhanden)
            if (window.buyButtonCoords) {
                const btn = window.buyButtonCoords;
                const distance = Math.sqrt(
                    Math.pow(x - btn.x, 2) + Math.pow(y - btn.y, 2)
                );
                if (distance <= (btn.size / 2) + 5) {  // 5px extra Toleranz
                    return true;
                }
            }

            // ⭐ BUGFIX: Prüfe Close Buttons für aktive Positionen
            if (window.closeButtonPositions) {
                for (const positionId in window.closeButtonPositions) {
                    const btn = window.closeButtonPositions[positionId];
                    if (x >= btn.x && x <= btn.x + btn.width &&
                        y >= btn.y && y <= btn.y + btn.height) {
                        return true;
                    }
                }
            }

            return false;
        }

        // ⭐ HILFSFUNKTION: Prüft ob Punkt über Position Box liegt
        function isPointOverPositionBox(x, y, box) {
            if (!box || !window.positionCanvas) return false;

            try {
                const canvas = window.positionCanvas;
                if (!canvas) return false;

                const chartWidth = canvas.width;
                const chartHeight = canvas.height;

                // ⭐ ROBUSTE API-AUFRUFE: X-Koordinaten der Box
                let x1, x2;
                if (box.timeStart && box.timeEnd && chart && chart.timeScale) {
                    try {
                        const timeScale = chart.timeScale();
                        if (timeScale && typeof timeScale.timeToCoordinate === 'function') {
                            x1 = timeScale.timeToCoordinate(box.timeStart);
                            x2 = timeScale.timeToCoordinate(box.timeEnd);

                            // Validierung der API-Ergebnisse
                            if (isNaN(x1) || isNaN(x2) || x1 < -100 || x2 < -100 ||
                                x1 > chartWidth + 100 || x2 > chartWidth + 100) {
                                throw new Error('Invalid API coordinates');
                            }
                        } else {
                            throw new Error('TimeScale API not available');
                        }
                    } catch (apiError) {
                        console.warn('⚠️ TimeScale API Error, using fallback:', apiError);
                        x1 = chartWidth * (box.x1Percent || 0.47);
                        x2 = chartWidth * (box.x2Percent || 0.53);
                    }
                } else {
                    // Fallback für fehlende Zeit-Daten
                    x1 = chartWidth * (box.x1Percent || 0.47);
                    x2 = chartWidth * (box.x2Percent || 0.53);
                }

                // ⭐ KOORDINATEN-CACHE: Verwende gecachte Pixel-Koordinaten vom letzten Draw
                // Garantiert Konsistenz zwischen Draw & Hover Detection
                let entryY, slY, tpY;

                if (box.cachedPixelCoordinates) {
                    // Cache-Hit: Verwende gespeicherte Koordinaten (BEVORZUGT!)
                    entryY = box.cachedPixelCoordinates.entryY;
                    slY = box.cachedPixelCoordinates.slY;
                    tpY = box.cachedPixelCoordinates.tpY;
                } else {
                    // Cache-Miss: Berechne aus Preisen (Fallback)
                    if (candlestickSeries && typeof candlestickSeries.priceToCoordinate === 'function') {
                        try {
                            entryY = candlestickSeries.priceToCoordinate(box.entryPrice);
                            slY = candlestickSeries.priceToCoordinate(box.stopLoss);
                            tpY = candlestickSeries.priceToCoordinate(box.takeProfit);

                            // Validierung
                            if (isNaN(entryY) || isNaN(slY) || isNaN(tpY)) {
                                throw new Error('Invalid price to coordinate conversion');
                            }
                        } catch (error) {
                            console.warn('⚠️ priceToCoordinate failed, using fallback');
                            entryY = chartHeight * 0.5;
                            slY = chartHeight * 0.7;
                            tpY = chartHeight * 0.3;
                        }
                    } else {
                        // Fallback wenn API nicht verfügbar
                        entryY = chartHeight * 0.5;
                        slY = chartHeight * 0.7;
                        tpY = chartHeight * 0.3;
                    }
                }

                // Bounding Box mit Toleranz
                const tolerance = 15;  // Etwas größere Toleranz für bessere UX
                const minX = Math.min(x1, x2) - tolerance;
                const maxX = Math.max(x1, x2) + tolerance;
                const minY = Math.min(entryY, slY, tpY) - tolerance;
                const maxY = Math.max(entryY, slY, tpY) + tolerance;

                const isOver = x >= minX && x <= maxX && y >= minY && y <= maxY;

                return isOver;

            } catch (error) {
                console.warn('⚠️ Kritischer Fehler bei Position Box Hover-Detection:', error);
                return false;
            }
        }

        // ⭐ NEU: Koordinaten-Cache Update Funktion für Event-Based Redraw
        // Berechnet Koordinaten nur bei Chart-Events (Zoom/Pan/Resize), nicht jeden Frame
        // ⛔ ENTFERNT: updateBoxCoordinates()
        // Koordinaten-Cache wurde komplett entfernt
        // Koordinaten werden jetzt IMMER frisch in drawPositionBox() berechnet

        function drawPositionBox() {
            const box = window.currentPositionBox;

            // ⭐ FIX: Verwende Manager-Variablen als Fallback wenn globale nicht gesetzt
            const ctx = window.positionCtx || (window.positionBoxManager && window.positionBoxManager.ctx);
            const canvas = window.positionCanvas || (window.positionBoxManager && window.positionBoxManager.canvas);

            if (!box || !ctx || !canvas) {
                console.warn('❌ drawPositionBox: Missing box, context, or canvas', {
                    hasBox: !!box,
                    hasCtx: !!ctx,
                    hasCanvas: !!canvas,
                    hasManager: !!window.positionBoxManager
                });
                return;
            }

            // ⭐ ÄNDERUNG: NUR clearRect wenn NICHT vom Manager aufgerufen
            // Manager macht clearRect selbst vor der Schleife
            // Check: Wenn Manager drawAll() läuft, ist window._managerDrawing = true
            if (!window._managerDrawing) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }

            try {
                // ⭐⭐⭐ NEU: KERZEN-INDEX-BASIERTE KOORDINATEN (kein Cache!) ⭐⭐⭐
                // X-Koordinaten: Kerzen-Index → Zeit → Pixel
                // Y-Koordinaten: IMMER frisch (reagiert sofort auf vertikales Pan/Zoom)

                let x1, x2;

                // ========== X-KOORDINATEN: Timestamp-basiert (STABIL!) ==========
                // ⚠️ WICHTIG: Indices verschieben sich wenn neue Daten geladen werden!
                // → Wir verwenden TIMESTAMPS (box.timeStart/timeEnd) als Quelle der Wahrheit
                if (box.timeStart && box.timeEnd) {
                    // ⭐⭐⭐ NEUE STRATEGIE: Pixel-basierte Berechnung für virtuelle Kerzen! ⭐⭐⭐
                    const allData = candlestickSeries.data();

                    if (allData && allData.length > 1) {
                        // Start-Koordinate (existiert immer)
                        x1 = chart.timeScale().timeToCoordinate(box.timeStart);

                        // Versuche End-Zeit zu konvertieren
                        x2 = chart.timeScale().timeToCoordinate(box.timeEnd);

                        // Falls End-Zeit außerhalb (virtuell), berechne Pixel-Breite manuell
                        if (x2 === null || x2 === undefined) {
                            // Berechne durchschnittliche Kerzenbreite
                            const firstX = chart.timeScale().timeToCoordinate(allData[0].time);
                            const lastX = chart.timeScale().timeToCoordinate(allData[allData.length - 1].time);
                            const avgCandleWidth = (lastX - firstX) / (allData.length - 1);

                            // Box = 15 Kerzen breit
                            const boxPixelWidth = avgCandleWidth * 15;
                            x2 = x1 + boxPixelWidth;

                            // console.log(`🎯 Virtuelle Box-Breite: ${boxPixelWidth.toFixed(1)}px (15 x ${avgCandleWidth.toFixed(1)}px/Kerze)`);
                        }

                        // Debug: Prüfe ob Koordinaten gültig sind
                        if (x1 === null || x1 === undefined) {
                            console.log(`⚠️ Box ${box.id}: Start-Zeit außerhalb sichtbarem Bereich`);
                        }
                    }
                }

                // ========== Y-KOORDINATEN: IMMER FRISCH (kein Cache!) ==========
                let entryY = candlestickSeries.priceToCoordinate(box.entryPrice);
                let slY = candlestickSeries.priceToCoordinate(box.stopLoss);
                let tpY = candlestickSeries.priceToCoordinate(box.takeProfit);

                // ⭐⭐⭐ PERFORMANCE FIX: Addiere Drag-Offsets (Pixel-basiert!) ⭐⭐⭐
                if (box.dragOffsetX !== undefined && box.dragOffsetY !== undefined) {
                    x1 += box.dragOffsetX;
                    x2 += box.dragOffsetX;
                    entryY += box.dragOffsetY;
                    slY += box.dragOffsetY;
                    tpY += box.dragOffsetY;
                    // console.log('🤚 Drag-Offset angewendet:', {x: box.dragOffsetX, y: box.dragOffsetY});
                }

                // Validierung
                if (x1 === null || x2 === null || isNaN(entryY) || isNaN(slY) || isNaN(tpY)) {
                    console.warn(`⚠️ Box ${box.id}: Außerhalb sichtbarem Bereich oder ungültige Koordinaten`);
                    return;  // Box nicht zeichnen
                }

                // Debug-Logs deaktiviert für bessere Performance
                // console.log(`📐 Canvas Box ${box.id} Koordinaten:`);
                // console.log(`   X-Achse: x1=${x1?.toFixed(1)}px (Start), x2=${x2?.toFixed(1)}px (Ende), Breite=${(x2-x1).toFixed(1)}px`);
                // console.log(`   Y-Achse: Entry=${entryY.toFixed(1)}px, SL=${slY.toFixed(1)}px, TP=${tpY.toFixed(1)}px`);
                // console.log(`   Timestamps: Start=${box.timeStart}, Ende=${box.timeEnd}`);
                // if (box.clickX !== null && box.clickX !== undefined) {
                //     console.log(`   🎯 CLICK vs BOX: clickX=${box.clickX.toFixed(1)}px → boxX1=${x1?.toFixed(1)}px (Delta: ${(x1 - box.clickX).toFixed(1)}px)`);
                //     console.log(`   🎯 CLICK vs BOX: clickY=${box.clickY.toFixed(1)}px → entryY=${entryY.toFixed(1)}px (Delta: ${(entryY - box.clickY).toFixed(1)}px)`);
                // }

                // 🔄 REVERSE-CHECK (auskommentiert - zu verbose)
                // const entryPriceCheck = candlestickSeries.coordinateToPrice(entryY);
                // const slPriceCheck = candlestickSeries.coordinateToPrice(slY);
                // const tpPriceCheck = candlestickSeries.coordinateToPrice(tpY);
                // console.log(`🔄 REVERSE: entryY=${entryY.toFixed(1)}px→$${entryPriceCheck?.toFixed(2)} | slY=${slY.toFixed(1)}px→$${slPriceCheck?.toFixed(2)} | tpY=${tpY.toFixed(1)}px→$${tpPriceCheck?.toFixed(2)}`);

                // ⚙️ Verbose Debug (auskommentiert um Logs zu reduzieren)
                // console.log(`📊 Drawing Box ${box.id} (LIVE):`, {
                //     x: `${x1.toFixed(1)} → ${x2.toFixed(1)} (${(x2-x1).toFixed(0)}px)`,
                //     entryPx: entryY.toFixed(1),
                //     slPx: slY.toFixed(1),
                //     tpPx: tpY.toFixed(1),
                //     timestamps: `${box.timeStart} → ${box.timeEnd}`
                // });

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

                // Zeichne Entry Line (orange - matching Price Line)
                ctx.strokeStyle = '#FFA500';  // Orange statt weiß
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.moveTo(x1, entryY);
                ctx.lineTo(x2, entryY);
                ctx.stroke();

                // Zeichne Resize Handles in den Ecken
                drawResizeHandles(box, x1, x2, slTop, tpTop, slHeight, tpHeight);

                // Zeichne Buttons: Buy (links) und Delete (rechts)
                const buttonY = Math.min(slTop, tpTop);
                drawBuyButton(x2, buttonY, box.id);      // ⭐ Buy Button (grün, mit $)
                drawDeleteButton(x2, buttonY, box.id);   // Delete Button (rot, mit X)

                // ⭐ MULTI-BOX: Speichere Button-Koordinaten IN der Box
                box.deleteButton = {
                    x: x2,
                    y: buttonY - 25,  // Button ist 25px über buttonY
                    size: 20,
                    boxId: box.id
                };

                box.buyButton = {
                    x: x2 - 30,  // Buy Button ist 30px links vom Delete Button
                    y: buttonY - 25,
                    size: 20,
                    boxId: box.id
                };

                // Debug-Logs deaktiviert für bessere Performance
                // console.log('🔘 Buttons:', {...});

                // ⭐ KOORDINATEN-CACHE: Speichere berechnete Pixel-Koordinaten in der Box
                // Verhindert doppelte API-Aufrufe und garantiert Konsistenz zwischen Draw & Hover
                box.cachedPixelCoordinates = {
                    x1, x2, entryY, slY, tpY,
                    slTop, tpTop, slHeight, tpHeight,
                    timestamp: Date.now()  // Für Debugging
                };

                // ⭐⭐⭐ NEU: Speichere Koordinaten direkt in der Box (nicht global!) ⭐⭐⭐
                box.boxCoordinates = {
                    x1, x2, entryY, slY, tpY,
                    slTop, tpTop, slHeight, tpHeight,
                    deleteButtonX: x2,
                    deleteButtonY: Math.min(slTop, tpTop),
                    deleteButtonSize: 20
                };

                // ⭐ Backwards Compatibility: Setze auch globale Variable für aktive Box
                if (box === window.currentPositionBox || window.positionBoxManager?.activeBoxId === box.id) {
                    window.boxCoordinates = box.boxCoordinates;
                }

                // console.log('✅ Position Box gezeichnet erfolgreich');

            } catch (error) {
                console.error('❌ Kritischer Fehler beim Zeichnen der Position Box:', error);
                console.error('Error Stack:', error.stack);
            }
        }

        function drawResizeHandles(box, x1, x2, slTop, tpTop, slHeight, tpHeight) {
            // ⭐ WICHTIG: Hole ctx vom Manager für Multi-Box Support
            const ctx = window.positionCtx || (window.positionBoxManager && window.positionBoxManager.ctx);
            if (!ctx) {
                console.warn('⚠️ drawResizeHandles: Kein Context verfügbar');
                return;
            }
            const handleSize = 8;

            // Nur äußere Handles - KEINE auf der Entry-Linie
            const slBottom = slTop + slHeight;
            const tpBottom = tpTop + tpHeight;

            // ⭐ FIX: Handle-Position abhängig von Long/Short
            // Long: SL unten, TP oben → Handles an äußeren Kanten
            // Short: SL oben, TP unten → Handles an äußeren Kanten (vertauscht!)
            if (box.isShort) {
                // SHORT: SL ist OBEN, TP ist UNTEN
                // SL Box Handles (rot) - an der OBEREN Kante (slTop)
                drawHandle(ctx, x1, slTop, '#f23645', 'SL-TL'); // Top-Left
                drawHandle(ctx, x2, slTop, '#f23645', 'SL-TR'); // Top-Right

                // TP Box Handles (grün) - an der UNTEREN Kante (tpBottom)
                drawHandle(ctx, x1, tpBottom, '#089981', 'TP-BL'); // Bottom-Left
                drawHandle(ctx, x2, tpBottom, '#089981', 'TP-BR'); // Bottom-Right
            } else {
                // LONG: SL ist UNTEN, TP ist OBEN
                // SL Box Handles (rot) - an der UNTEREN Kante (slBottom)
                drawHandle(ctx, x1, slBottom, '#f23645', 'SL-BL'); // Bottom-Left
                drawHandle(ctx, x2, slBottom, '#f23645', 'SL-BR'); // Bottom-Right

                // TP Box Handles (grün) - an der OBEREN Kante (tpTop)
                drawHandle(ctx, x1, tpTop, '#089981', 'TP-TL'); // Top-Left
                drawHandle(ctx, x2, tpTop, '#089981', 'TP-TR'); // Top-Right
            }

            // DEAKTIVIERT: Mittlere Handles für Box-Breite
            // const middleY = (slTop + tpBottom) / 2;
            // drawHandle(ctx, x1, middleY, '#007bff', 'WIDTH-L');
            // drawHandle(ctx, x2, middleY, '#007bff', 'WIDTH-R');

            // Speichere Handle-Positionen - nur äußere Handles
            // ⭐⭐⭐ NEU: Speichere Handles direkt in der Box (nicht global!) ⭐⭐⭐
            if (box.isShort) {
                box.resizeHandles = {
                    'SL-TL': {x: x1, y: slTop, type: 'sl'},
                    'SL-TR': {x: x2, y: slTop, type: 'sl'},
                    'TP-BL': {x: x1, y: tpBottom, type: 'tp'},
                    'TP-BR': {x: x2, y: tpBottom, type: 'tp'}
                };
            } else {
                box.resizeHandles = {
                    'SL-BL': {x: x1, y: slBottom, type: 'sl'},
                    'SL-BR': {x: x2, y: slBottom, type: 'sl'},
                    'TP-TL': {x: x1, y: tpTop, type: 'tp'},
                    'TP-TR': {x: x2, y: tpTop, type: 'tp'}
                };
            }

            // ⭐ Backwards Compatibility: Setze auch globale Variable für aktive Box
            if (box === window.currentPositionBox || window.positionBoxManager?.activeBoxId === box.id) {
                window.resizeHandles = box.resizeHandles;
            }

            // Debug-Logs deaktiviert für bessere Performance
            // console.log(`🔧 Resize Handles für Box ${box.id}:`, {...});
        }

        function drawHandle(ctx, x, y, color, id) {
            const size = 12;  // ⭐ Vergrößert von 8 auf 12 für bessere Sichtbarkeit
            ctx.fillStyle = color;
            ctx.strokeStyle = '#ffffff';  // ⭐ Weißer Rand statt schwarz für besseren Kontrast
            ctx.lineWidth = 2;  // ⭐ Dickerer Rand

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

        // ⭐ NEUE FUNKTION: Buy Button zeichnen (mit Selected State)
        function drawBuyButton(x, y) {
            const ctx = window.positionCtx;
            const size = 20;
            const iconSize = 12;

            // Button Position: links vom Delete Button
            const buttonX = x - 30;  // 30px links vom Delete Button
            const buttonY = y - 25;

            // ⭐ VISUAL FEEDBACK: Selected State wenn Modal offen
            const isSelected = window.buyButtonSelected || false;

            // Zeichne Button Hintergrund (grün mit Transparenz, dunkler wenn selected)
            if (isSelected) {
                ctx.fillStyle = 'rgba(8, 153, 129, 1.0)';  // Volle Opazität
                ctx.strokeStyle = '#ffffff';  // Weißer Border
                ctx.lineWidth = 3;  // Dickerer Border
            } else {
                ctx.fillStyle = 'rgba(8, 153, 129, 0.8)';
                ctx.strokeStyle = '#089981';
                ctx.lineWidth = 2;
            }
            ctx.fillRect(buttonX - size/2, buttonY - size/2, size, size);
            ctx.strokeRect(buttonX - size/2, buttonY - size/2, size, size);

            // Zeichne Buy-Symbol (Pfeil nach oben + Dollar)
            ctx.strokeStyle = '#ffffff';
            ctx.fillStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.font = isSelected ? 'bold 12px Arial' : '12px Arial';  // Bold wenn selected
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // Zeichne "$" Symbol
            ctx.fillText('$', buttonX, buttonY);

            // Speichere Button Koordinaten für Click-Detection
            if (!window.buyButtonCoords) window.buyButtonCoords = {};
            window.buyButtonCoords = {
                x: buttonX,
                y: buttonY,
                size: size
            };
        }

        // NEUE MOUSE EVENT HANDLERS FÜR BOX-INTERNE RESIZE
        let isDragging = false;
        let dragHandle = null;

        // ⭐ NEU: Box-Drag State für Drag-to-Move Feature (window-global für Observer)
        window.isBoxDragging = false;
        let boxDragStartX = null;
        let boxDragStartY = null;
        let boxDragStartPrice = null;
        let boxDragStartTime = null;
        let boxDragStartSL = null;
        let boxDragStartTP = null;
        let dragCanvas = null;  // Speichere Canvas-Referenz für globale Events

        // ⭐⭐⭐ DRAG FIX: Globale Event Handler für schnelles Drag (auf document) ⭐⭐⭐
        function globalMouseMove(e) {
            if (!window.isBoxDragging || !dragCanvas) return;

            const rect = dragCanvas.getBoundingClientRect();
            const scaleX = dragCanvas.width / rect.width;
            const scaleY = dragCanvas.height / rect.height;

            const mouseX = (e.clientX - rect.left) * scaleX;
            const mouseY = (e.clientY - rect.top) * scaleY;

            // Berechne Delta in Pixel
            const deltaX = mouseX - boxDragStartX;
            const deltaY = mouseY - boxDragStartY;

            // Speichere NUR Pixel-Offsets
            const box = window.currentPositionBox;
            if (box) {
                box.dragOffsetX = deltaX;
                box.dragOffsetY = deltaY;
                drawPositionBox();
            }

            e.preventDefault();
        }

        function globalMouseUp(e) {
            if (!window.isBoxDragging) return;

            console.log('🤚 Box-Drag beendet (global)');

            // Berechne finale Preise/Zeit aus Pixel-Offsets
            const box = window.currentPositionBox;
            if (box && box.dragOffsetX !== undefined && box.dragOffsetY !== undefined) {
                try {
                    // Y-Achse: Konvertiere Pixel-Offset zu Preis-Delta
                    const startPriceY = candlestickSeries.priceToCoordinate(boxDragStartPrice);
                    const newPriceY = startPriceY + box.dragOffsetY;
                    const newEntryPrice = candlestickSeries.coordinateToPrice(newPriceY);

                    if (newEntryPrice && !isNaN(newEntryPrice)) {
                        const priceDelta = newEntryPrice - boxDragStartPrice;
                        box.entryPrice = boxDragStartPrice + priceDelta;
                        box.stopLoss = boxDragStartSL + priceDelta;
                        box.takeProfit = boxDragStartTP + priceDelta;
                    }

                    // X-Achse: Konvertiere Pixel-Offset zu Zeit-Delta
                    const seriesData = candlestickSeries.data();
                    if (seriesData && seriesData.length > 0) {
                        const startX = chart.timeScale().timeToCoordinate(boxDragStartTime);
                        if (startX !== null && !isNaN(startX)) {
                            const newX = startX + box.dragOffsetX;
                            // 🔮 UNBEGRENZTE ZEIT-EXTRAPOLATION FIX - Drag funktioniert auch in Zukunft
                            const newTime = coordinateToTimeUnlimited(newX);

                            if (newTime) {
                                const newCandle = seriesData.reduce((prev, curr) => {
                                    return Math.abs(curr.time - newTime) < Math.abs(prev.time - newTime) ? curr : prev;
                                });

                                if (newCandle) {
                                    const startIndex = seriesData.findIndex(c => c.time === boxDragStartTime);
                                    const newIndex = seriesData.indexOf(newCandle);
                                    const indexDelta = newIndex - startIndex;

                                    const originalEndIndex = seriesData.findIndex(c => c.time === box.timeEnd);
                                    if (originalEndIndex !== -1 && startIndex !== -1) {
                                        const newStartIndex = startIndex + indexDelta;
                                        const newEndIndex = originalEndIndex + indexDelta;

                                        if (newStartIndex >= 0 && newEndIndex < seriesData.length) {
                                            box.timeStart = seriesData[newStartIndex].time;
                                            box.timeEnd = seriesData[newEndIndex].time;
                                        }
                                    }
                                }
                            }
                        }
                    }
                } catch (error) {
                    console.error('❌ Fehler bei finaler Koordinaten-Konvertierung:', error);
                }

                // Lösche Offsets nach Anwendung
                delete box.dragOffsetX;
                delete box.dragOffsetY;

                // Redraw ohne Offsets (Price Lines deaktiviert)
                drawPositionBox();
                // createPriceLines(box.entryPrice, box.stopLoss, box.takeProfit);
            }

            // Reset Drag State
            window.isBoxDragging = false;
            boxDragStartX = null;
            boxDragStartY = null;
            boxDragStartPrice = null;
            boxDragStartSL = null;
            boxDragStartTP = null;
            boxDragStartTime = null;

            // Cursor und Canvas zurücksetzen
            if (dragCanvas) {
                const rect = dragCanvas.getBoundingClientRect();
                const scaleX = dragCanvas.width / rect.width;
                const scaleY = dragCanvas.height / rect.height;
                const mouseX = (e.clientX - rect.left) * scaleX;
                const mouseY = (e.clientY - rect.top) * scaleY;

                const isOverBox = isPointOverPositionBox(mouseX, mouseY, window.currentPositionBox);
                const isOverButtons = isPointOverButtons(mouseX, mouseY);

                if (isOverBox || isOverButtons) {
                    dragCanvas.style.cursor = 'pointer';
                    dragCanvas.style.pointerEvents = 'auto';
                } else {
                    dragCanvas.style.cursor = 'default';
                    dragCanvas.style.pointerEvents = 'none';
                }
            }

            dragCanvas = null;

            // Entferne globale Event Listener
            document.removeEventListener('mousemove', globalMouseMove);
            document.removeEventListener('mouseup', globalMouseUp);

            console.log('🔌 Globale Drag-Events entfernt');
            e.preventDefault();
        }

        function onCanvasMouseDown(e) {
            const canvas = e.target;
            const rect = canvas.getBoundingClientRect();

            // ⭐ FIX: Skaliere Mouse-Koordinaten von CSS zu Canvas
            // CSS-Koordinaten (Browser) → Canvas-Koordinaten (interne Pixel)
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;

            const mouseX = (e.clientX - rect.left) * scaleX;
            const mouseY = (e.clientY - rect.top) * scaleY;

            console.log('🖱️ Mouse Click:', {
                css: {x: e.clientX - rect.left, y: e.clientY - rect.top},
                canvas: {x: mouseX, y: mouseY},
                scale: {x: scaleX, y: scaleY}
            });

            // ⭐ PRIORITÄT 0: Close Position Button Check (HÖCHSTE PRIORITÄT!)
            if (window.closeButtonPositions) {
                for (const positionId in window.closeButtonPositions) {
                    const btn = window.closeButtonPositions[positionId];

                    // Check if click is within button bounds
                    if (mouseX >= btn.x && mouseX <= btn.x + btn.width &&
                        mouseY >= btn.y && mouseY <= btn.y + btn.height) {

                        console.log(`🔴 Close Position Button geklickt für Position: ${positionId}`);

                        // Sende Close Position Command an Server
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            const closeCommand = {
                                type: 'close_position',
                                position_id: positionId
                            };
                            ws.send(JSON.stringify(closeCommand));
                            console.log('📤 Close Position Command gesendet:', closeCommand);
                        } else {
                            console.error('❌ WebSocket nicht verbunden - kann Position nicht schließen');
                        }

                        e.preventDefault();
                        return;
                    }
                }
            }

            // ⭐ PRIORITÄT 1: Delete Button Check (HÖCHSTE PRIORITÄT für gute UX!)
            if (window.positionBoxManager) {
                const allBoxes = window.positionBoxManager.getAll();

                for (const box of allBoxes) {
                    if (box.deleteButton) {
                        const btn = box.deleteButton;
                        const distance = Math.sqrt(
                            Math.pow(mouseX - btn.x, 2) + Math.pow(mouseY - btn.y, 2)
                        );

                        // ⭐ Erhöhte Toleranz für Delete Button (größere Hitbox für bessere UX)
                        if (distance <= btn.size) {  // Volle Button-Größe als Toleranz (20px Radius)
                            console.log(`🗑️ Delete Button geklickt - lösche Box ${box.id}`);
                            console.log('📍 Delete Button:', {x: btn.x, y: btn.y, mouseX, mouseY, distance});

                            // ⭐⭐⭐ NEU: Entferne Price Lines wenn diese Box die aktive Box ist ⭐⭐⭐
                            if (window.currentPositionBox && window.currentPositionBox.id === box.id) {
                                removePriceLines();
                                window.currentPositionBox = null;  // Reset active box
                                console.log('📍 Price Lines der gelöschten Box entfernt');
                            }

                            // ⭐ Lösche NUR diese spezifische Box
                            window.positionBoxManager.remove(box.id);
                            window.positionBoxManager.drawAll();

                            e.preventDefault();
                            return;
                        }
                    }
                }
            }

            // ⭐ GUARD: Remaining handlers need currentPositionBox
            if (!window.currentPositionBox) {
                return; // No position box active, ignore other interactions
            }

            // ⭐ PRIORITÄT 2: Check if mouse is over any resize handle
            // ⭐⭐⭐ NEU: Check Handles von ALLEN Boxes, nicht nur der aktiven! ⭐⭐⭐
            if (window.positionBoxManager) {
                const allBoxes = window.positionBoxManager.getAll();

                for (const box of allBoxes) {
                    if (!box.resizeHandles) continue;

                    for (const [id, handle] of Object.entries(box.resizeHandles)) {
                        const distance = Math.sqrt(
                            Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                        );

                        if (distance <= 30) { // 30px click tolerance (erhöht für bessere UX)
                            isDragging = true;
                            dragHandle = id;
                            window.currentPositionBox = box;  // ⭐ Setze als aktive Box
                            window.positionBoxManager.setActive(box.id);
                            window.resizeHandles = box.resizeHandles;  // ⭐ Aktualisiere globale Handles

                            // Cursor für Eckhandles
                            e.target.style.cursor = 'nw-resize'; // Diagonal resize für Eckhandles
                            e.target.style.pointerEvents = 'auto';  // ⭐ Während Dragging Canvas aktiv halten
                            console.log(`🎯 Resize gestartet: ${id} auf Box ${box.id}`);
                            return;
                        }
                    }
                }
            }

            // ⭐ ENTRY-LINE NICHT MEHR VERSCHIEBBAR (Fixiert)
            // Entry-Line Drag Detection entfernt - nur SL/TP Resize-Handles erlaubt

            // ⭐ PRIORITÄT 4: Check if mouse is over buy button
            if (window.buyButtonCoords && window.currentPositionBox) {
                const btn = window.buyButtonCoords;
                const distance = Math.sqrt(
                    Math.pow(mouseX - btn.x, 2) + Math.pow(mouseY - btn.y, 2)
                );

                if (distance <= btn.size/2) {
                    console.log('💰 Buy Button geklickt - öffne Trade Setup Modal');

                    // ⭐ VISUAL FEEDBACK: Setze Selected State
                    window.buyButtonSelected = true;
                    drawPositionBox();  // Redraw mit Selected State

                    // Öffne Trade Setup Modal mit Position Box Daten
                    if (window.currentPositionBox) {
                        const positionData = {
                            symbol: 'NQ=F',
                            entryPrice: window.currentPositionBox.entryPrice || 18500,
                            stopLoss: window.currentPositionBox.stopLoss || 18400,
                            takeProfit: window.currentPositionBox.takeProfit || 18600,
                            direction: window.currentPositionBox.direction || 'long'
                        };

                        // ⭐ FIX: Korrekte Funktion ist openTradeModal, nicht showTradeModal
                        openTradeModal(positionData);
                    }

                    e.preventDefault();
                    return;
                }
            }

            // ⭐ PRIORITÄT 5: Box-Body Drag (gesamte Box verschieben)
            const isOverBox = isPointOverPositionBox(mouseX, mouseY, window.currentPositionBox);
            const isOverButtons = isPointOverButtons(mouseX, mouseY);

            if (isOverBox && !isOverButtons && !isDragging) {
                // Box-Body geklickt → Drag-to-Move aktivieren
                window.isBoxDragging = true;
                boxDragStartX = mouseX;
                boxDragStartY = mouseY;

                // Speichere Start-Position (Preis + Zeit)
                const box = window.currentPositionBox;
                boxDragStartPrice = box.entryPrice;
                boxDragStartSL = box.stopLoss;
                boxDragStartTP = box.takeProfit;
                boxDragStartTime = box.timeStart;

                e.target.style.cursor = 'grabbing';
                e.target.style.pointerEvents = 'auto';
                console.log('🤚 Box-Drag gestartet');

                // ⭐⭐⭐ DRAG FIX: Speichere Canvas und aktiviere globale Events ⭐⭐⭐
                dragCanvas = e.target;
                document.addEventListener('mousemove', globalMouseMove, {passive: false});
                document.addEventListener('mouseup', globalMouseUp, {passive: false});
                console.log('🔌 Globale Drag-Events aktiviert');

                // ⭐⭐⭐ SYNC FIX: Entferne Price Lines während Drag ⭐⭐⭐
                removePriceLines();

                e.preventDefault();
                return;
            }

            if (!isOverBox && !isOverButtons) {
                console.log('🎯 Click außerhalb Position Box - Event durchgelassen für Chart');
                // Event wird NICHT preventDefault() → fällt zum Chart durch
                return;
            }
        }

        function onCanvasMouseMove(e) {
            // ⭐ GUARD: Nur verarbeiten wenn Position Box existiert
            if (!window.currentPositionBox) {
                return;
            }

            const canvas = e.target;
            const rect = canvas.getBoundingClientRect();

            // ⭐ FIX: Skaliere Mouse-Koordinaten von CSS zu Canvas
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;

            const mouseX = (e.clientX - rect.left) * scaleX;
            const mouseY = (e.clientY - rect.top) * scaleY;

            // ⭐ Box-Drag wird jetzt durch globalMouseMove (auf document) gehandhabt
            // Grund: Verhindert "Mouse Outrun" bei schnellem Drag
            if (window.isBoxDragging) {
                return; // Globaler Handler übernimmt
            }

            if (!isDragging) {
                // Update cursor based on hover over handles
                let cursorType = 'default';
                for (const [id, handle] of Object.entries(window.resizeHandles || {})) {
                    const distance = Math.sqrt(
                        Math.pow(mouseX - handle.x, 2) + Math.pow(mouseY - handle.y, 2)
                    );
                    if (distance <= 20) {  // 20px hover tolerance (gleich wie click tolerance)
                        cursorType = 'nw-resize'; // Diagonal für Eckhandles
                        break;
                    }
                }

                // ⭐ NEU: Check hover over Delete Button
                if (cursorType === 'default' && window.deleteButtonCoords) {
                    const btn = window.deleteButtonCoords;
                    const distance = Math.sqrt(
                        Math.pow(mouseX - btn.x, 2) + Math.pow(mouseY - btn.y, 2)
                    );
                    if (distance <= btn.size/2) {
                        cursorType = 'pointer'; // Pointer für Delete Button
                    }
                }

                // ⭐ NEU: Check hover over Buy Button
                if (cursorType === 'default' && window.buyButtonCoords) {
                    const btn = window.buyButtonCoords;
                    const distance = Math.sqrt(
                        Math.pow(mouseX - btn.x, 2) + Math.pow(mouseY - btn.y, 2)
                    );
                    if (distance <= btn.size/2) {
                        cursorType = 'pointer'; // Pointer für Buy Button
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

                // ⭐ NEU: Check hover over Box-Body → pointer cursor
                if (cursorType === 'default') {
                    const isOverBox = isPointOverPositionBox(mouseX, mouseY, window.currentPositionBox);
                    const isOverButtons = isPointOverButtons(mouseX, mouseY);

                    if (isOverBox && !isOverButtons) {
                        cursorType = 'pointer'; // Pointer für Box-Body (verschiebbar)
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
            // ⭐ GUARD: Nur verarbeiten wenn Position Box existiert
            if (!window.currentPositionBox) {
                return;
            }

            // ⭐ Box-Drag wird jetzt durch globalMouseUp (auf document) gehandhabt
            // Grund: Verhindert "Mouse Outrun" bei schnellem Drag
            if (window.isBoxDragging) {
                return; // Globaler Handler übernimmt
            }

            if (isDragging) {
                console.log('🎯 Box Resize beendet:', dragHandle);
                isDragging = false;
                dragHandle = null;
                e.target.style.cursor = 'default';

                // ⭐ WICHTIG: Nach Dragging prüfen ob Mouse noch über Box ist
                const canvas = e.target;
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.width / rect.width;
                const scaleY = canvas.height / rect.height;
                const mouseX = (e.clientX - rect.left) * scaleX;
                const mouseY = (e.clientY - rect.top) * scaleY;

                const isOverBox = isPointOverPositionBox(mouseX, mouseY, window.currentPositionBox);
                const isOverButtons = isPointOverButtons(mouseX, mouseY);

                // ⭐ DYNAMISCHE POINTER-EVENTS: Nur 'auto' wenn noch über Box/Buttons
                if (!isOverBox && !isOverButtons) {
                    canvas.style.pointerEvents = 'none';  // Zurück zu 'none' → Chart wird wieder frei
                    console.log('🎯 Dragging beendet - Canvas deaktiviert (Mouse außerhalb Box)');
                } else {
                    console.log('🎯 Dragging beendet - Canvas bleibt aktiv (Mouse über Box)');
                }
            }
        }

        // ⭐⭐⭐ HILFSFUNKTION: Finde nächsten Kerzen-Index zu einer Zeit ⭐⭐⭐
        function findNearestCandleIndex(targetTime, allData) {
            if (!allData || allData.length === 0) {
                console.warn('⚠️ findNearestCandleIndex: Keine Daten verfügbar');
                return null;
            }

            let minDiff = Infinity;
            let nearestIndex = 0;

            for (let i = 0; i < allData.length; i++) {
                const diff = Math.abs(allData[i].time - targetTime);
                if (diff < minDiff) {
                    minDiff = diff;
                    nearestIndex = i;
                }
            }

            console.log(`🔍 findNearestCandleIndex: Zeit ${targetTime} → Index ${nearestIndex} (Diff: ${minDiff}s)`);
            return nearestIndex;
        }

        function updateBoxFromHandle(handleId, newPrice, newXPercent, mouseX) {
            const box = window.currentPositionBox;
            if (!box) return;

            // ⭐ ENTRY-LINE NICHT MEHR VERSCHIEBBAR (Fixiert)
            // Entry-Line Update Logic entfernt - handleId 'ENTRY-LINE' wird nicht mehr verarbeitet

            // ECKHANDLES: Sowohl Preise als auch Breite ändern (SL/TP Resize)

                // Update prices based on which handle was dragged
                if (handleId.includes('SL')) {
                    // ⭐ BEGRENZUNG: SL darf Entry-Preis nicht kreuzen (abhängig von Long/Short)
                    if (box.isShort) {
                        // SHORT: SL ist OBEN, darf nicht UNTER Entry gezogen werden
                        if (newPrice <= box.entryPrice) {
                            console.warn('⚠️ SHORT SL darf nicht unter Entry-Preis! Entry:', box.entryPrice, 'SL Versuch:', newPrice);
                            newPrice = box.entryPrice + 1; // 1 Punkt über Entry
                        }
                    } else {
                        // LONG: SL ist UNTEN, darf nicht ÜBER Entry gezogen werden
                        if (newPrice >= box.entryPrice) {
                            console.warn('⚠️ LONG SL darf nicht über Entry-Preis! Entry:', box.entryPrice, 'SL Versuch:', newPrice);
                            newPrice = box.entryPrice - 1; // 1 Punkt unter Entry
                        }
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
                    // ⭐ BEGRENZUNG: TP darf Entry-Preis nicht kreuzen (abhängig von Long/Short)
                    if (box.isShort) {
                        // SHORT: TP ist UNTEN, darf nicht ÜBER Entry gezogen werden
                        if (newPrice >= box.entryPrice) {
                            console.warn('⚠️ SHORT TP darf nicht über Entry-Preis! Entry:', box.entryPrice, 'TP Versuch:', newPrice);
                            newPrice = box.entryPrice - 1; // 1 Punkt unter Entry
                        }
                    } else {
                        // LONG: TP ist OBEN, darf nicht UNTER Entry gezogen werden
                        if (newPrice <= box.entryPrice) {
                            console.warn('⚠️ LONG TP darf nicht unter Entry-Preis! Entry:', box.entryPrice, 'TP Versuch:', newPrice);
                            newPrice = box.entryPrice + 1; // 1 Punkt über Entry
                        }
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

                // ⭐ HORIZONTALE RESIZE: X-Achse Bewegung für Eckhandles
                const isLeftHandle = handleId.includes('-TL') || handleId.includes('-BL');
                const isRightHandle = handleId.includes('-TR') || handleId.includes('-BR');

                if (isLeftHandle || isRightHandle) {
                    // Update Percentage-based coordinates (Fallback)
                    if (isLeftHandle) {
                        box.x1Percent = newXPercent;
                    } else if (isRightHandle) {
                        box.x2Percent = newXPercent;
                    }

                    // ⭐⭐⭐ WICHTIG: Update Kerzen-Index + Zeit für Canvas-Zeichnung ⭐⭐⭐
                    try {
                        // 🔮 UNBEGRENZTE ZEIT-EXTRAPOLATION FIX - Resize funktioniert auch in Zukunft
                        const newTime = coordinateToTimeUnlimited(mouseX);

                        if (newTime !== null && !isNaN(newTime)) {
                            // ⭐ NEU: Finde Kerzen-Index zur neuen Zeit
                            const allData = candlestickSeries.data();
                            const newIndex = findNearestCandleIndex(newTime, allData);

                            if (isLeftHandle) {
                                box.timeStart = newTime;
                                if (newIndex !== null) {
                                    box.candleStartIndex = newIndex;
                                    console.log(`◀️ LINKS Handle bewegt → Index: ${newIndex}, Zeit: ${newTime}`);
                                }
                            } else if (isRightHandle) {
                                box.timeEnd = newTime;
                                if (newIndex !== null) {
                                    box.candleEndIndex = newIndex;
                                    console.log(`▶️ RECHTS Handle bewegt → Index: ${newIndex}, Zeit: ${newTime}`);
                                }
                            }
                        }
                    } catch (error) {
                        console.warn('⚠️ Zeit-Konvertierung fehlgeschlagen, verwende Percentage:', error);
                    }
                }

            // Stelle sicher dass timeStart < timeEnd und x1 < x2
            if (box.timeStart && box.timeEnd && box.timeStart > box.timeEnd) {
                const temp = box.timeStart;
                box.timeStart = box.timeEnd;
                box.timeEnd = temp;
                console.log('🔄 Box Zeit-Seiten getauscht');
            }
            if (box.x1Percent && box.x2Percent && box.x1Percent > box.x2Percent) {
                const temp = box.x1Percent;
                box.x1Percent = box.x2Percent;
                box.x2Percent = temp;
                console.log('🔄 Box Percent-Seiten getauscht');
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
                // Entry Price Line (orange - besser sichtbar als weiß)
                // Note: PnL wird initial 0€ sein, wird später dynamisch aktualisiert
                const size = currentTradeSetup?.size || 1;
                window.positionPriceLines.entry = candlestickSeries.createPriceLine({
                    price: entryPrice,
                    color: '#FFA500',  // Orange statt weiß
                    lineWidth: 3,      // Dicker für bessere Sichtbarkeit
                    lineStyle: LightweightCharts.LineStyle.Solid,
                    axisLabelVisible: true,
                    title: '' // Empty title - Canvas labels will be drawn instead
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

                // console.log('📊 Price Lines erstellt:', {entry: entryPrice, sl: stopLoss, tp: takeProfit});
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

                // ⭐ CRITICAL FIX: Reset canvas references so it gets recreated next time
                if (window.positionBoxManager) {
                    window.positionBoxManager.canvas = null;
                    window.positionBoxManager.ctx = null;
                    // ⭐⭐ CRITICAL: Clear all boxes from manager (MUST be Array, not Object)
                    window.positionBoxManager.boxes = [];
                    window.positionBoxManager.activeBoxId = null;
                    console.log('🧹 Cleared all boxes from positionBoxManager');
                }
                window.positionCanvas = null;

                // ⭐⭐⭐ REAKTIVIERT: Cleanup Price Lines ⭐⭐⭐
                removePriceLines();

                // Lösche Box Object und globale Variablen
                window.currentPositionBox = null;
                window.positionCanvas = null;
                window.positionCtx = null;
                window.boxCoordinates = null;
                window.resizeHandles = null;
                window.deleteButtonCoords = null;
                window.buyButtonCoords = null;

                console.log('🗑️ Position Box entfernt - Chart ist wieder frei');
            }
        }

        // ===== GLOBAL FUNCTIONS FOR ONCLICK HANDLERS =====
        // Test global scope
        // console.log('🌍 Global functions being defined...');

        function togglePositionTool() {
            // Tool Button geklickt
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
                // Tool aktiviert
            } else {
                // ⭐ SAUBERES TOOL-DEAKTIVIEREN
                positionTool.classList.remove('active');
                positionTool.style.background = '#333';
                positionTool.style.color = '#fff';

                // Entferne aktive Position Box beim Deaktivieren
                if (window.currentPositionBox) {
                    removeCurrentPositionBox();
                }

                console.log('📦 Position Box Tool DEAKTIVIERT - Alle Boxen entfernt');
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
                // ⭐ SAUBERES TOOL-DEAKTIVIEREN
                shortTool.classList.remove('active');
                shortTool.style.background = '#333';
                shortTool.style.color = '#fff';

                // Entferne aktive Position Box beim Deaktivieren
                if (window.currentPositionBox) {
                    removeCurrentPositionBox();
                }

                console.log('📉 Short Position Tool DEAKTIVIERT - Alle Boxen entfernt');
            }
        }

        function clearAllPositions() {
            console.log('[CLEAR ALL] Button geklickt via onclick - FORCE DEAKTIVIERE TOOL');

            try {
                // Deaktiviere beide Position Tools komplett
                window.positionBoxMode = false;
                window.shortPositionMode = false;

                const positionTool = document.getElementById('positionBoxTool');
                if (positionTool) {
                    positionTool.classList.remove('active');
                    positionTool.style.background = '#333';
                    positionTool.style.color = '#fff';
                    console.log('[SUCCESS] Long Position Tool deaktiviert via onclick');
                } else {
                    console.error('[ERROR] positionBoxTool Element nicht gefunden beim Clear!');
                }

                const shortTool = document.getElementById('shortPositionTool');
                if (shortTool) {
                    shortTool.classList.remove('active');
                    shortTool.style.background = '#333';
                    shortTool.style.color = '#fff';
                    console.log('[SUCCESS] Short Position Tool deaktiviert via onclick');
                } else {
                    console.error('[ERROR] shortPositionTool Element nicht gefunden beim Clear!');
                }

                // Versuche Position Box zu entfernen (falls vorhanden)
                if (typeof removeCurrentPositionBox === 'function') {
                    removeCurrentPositionBox();
                    console.log('[SUCCESS] Position Box entfernt');
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

            // RL Action Tracking
            if (window.RLSystem) {
                window.RLSystem.trackAction('timeframe_change', {
                    from_timeframe: window.currentTimeframe,
                    to_timeframe: timeframe,
                    timestamp: new Date()
                });
            }

            console.log(`Wechsle zu Timeframe: ${timeframe}`);
            window.isTimeframeChanging = true;

            try {
                // Check browser cache first
                const cacheKey = `tf_${timeframe}`;
                if (window.timeframeCache.has(cacheKey)) {
                    console.log(`[CACHE-HIT] Browser Cache Hit für ${timeframe} (${window.timeframeCache.size} total entries)`);
                    const cachedData = window.timeframeCache.get(cacheKey);
                    console.log(`[CACHE-HIT] Cached data: ${cachedData.length} candles, first: ${new Date(cachedData[0]?.time * 1000).toISOString()}`);

                    // 🚀 CRITICAL FIX: Cache-Validation gegen Server-State
                    // Prüfe ob Cache-Daten nach GoTo-Operation noch gültig sind
                    let cacheValid = true;
                    if (window.lastGoToDate && cachedData.length > 0) {
                        const cacheDataDate = new Date(cachedData[0]?.time * 1000).toISOString().split('T')[0];
                        if (cacheDataDate !== window.lastGoToDate) {
                            console.log(`[CACHE-VALIDATION] Cache ungültig: Daten ${cacheDataDate} vs Server ${window.lastGoToDate}`);
                            window.timeframeCache.delete(cacheKey);
                            console.log(`[CACHE-INVALIDATION] Stale cache entry removed for ${timeframe}`);
                            cacheValid = false;
                        }
                    }

                    if (cacheValid) {
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
                }

                // 🚀 CACHE-MISS LOGGING: Detailliertes Logging für Server-Requests
                console.log(`[CACHE-MISS] No cache für ${timeframe} - Server-Request erforderlich (${window.timeframeCache.size} total entries)`);
                if (window.lastGoToDate) {
                    console.log(`[CACHE-MISS] Server-State: lastGoToDate=${window.lastGoToDate}`);
                }

                // Optimistic UI update
                updateTimeframeButtons(timeframe);

                // Performance-optimized API call mit adaptivem Timeout
                const controller = new AbortController();
                // ADAPTIVE TIMEOUT: Länger nach Go To Date wegen CSV-Processing
                const adaptiveTimeout = window.current_go_to_date ? 15000 : 8000; // 15s nach Go To Date, sonst 8s
                const timeoutId = setTimeout(() => controller.abort(), adaptiveTimeout);

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
                    const formattedData = result.data.filter(item =>
                        item && item.time &&
                        item.open != null && item.high != null &&
                        item.low != null && item.close != null
                    ).map(item => ({
                        time: item.time,  // Already correct format
                        open: parseFloat(item.open) || 0,  // Ensure float with fallback
                        high: parseFloat(item.high) || 0,
                        low: parseFloat(item.low) || 0,
                        close: parseFloat(item.close) || 0
                    }));

                    // Cache for instant future access
                    window.timeframeCache.set(cacheKey, formattedData);
                    console.log(`[CACHE-SET] Cached ${formattedData.length} candles für ${timeframe} (total cache: ${window.timeframeCache.size} entries)`);
                    console.log(`[CACHE-SET] Data range: ${new Date(formattedData[0]?.time * 1000).toISOString()} - ${new Date(formattedData[formattedData.length-1]?.time * 1000).toISOString()}`);

                    // Limit cache size to prevent memory issues
                    if (window.timeframeCache.size > 8) {
                        const firstKey = window.timeframeCache.keys().next().value;
                        window.timeframeCache.delete(firstKey);
                        console.log(`[CACHE-CLEANUP] Oldest cache entry removed: ${firstKey}`);
                    }

                    // Fast chart update mit Smart Positioning
                    candlestickSeries.setData(formattedData);

                    // Smart Positioning: Nach Timeframe-Wechsel zurück zu 50-Kerzen Standard
                    if (window.smartPositioning) {
                        window.smartPositioning.resetToStandardPosition(formattedData);
                    }

                    // 📊 INDICATOR SYSTEM: Sync indicators with new timeframe data
                    if (window.IndicatorManager) {
                        window.IndicatorManager.syncWithTimeframe(formattedData);
                    }

                    window.currentTimeframe = timeframe;
                } else {
                    console.error('Timeframe-Wechsel fehlgeschlagen:', result.message);
                    updateTimeframeButtons(window.currentTimeframe);
                }

            } catch (error) {
                if (error.name === 'AbortError') {
                    console.warn('Timeframe request timeout - aber WebSocket Daten könnten noch kommen');
                    // NICHT den Button-State zurücksetzen - WebSocket könnte noch antworten!
                    // Race Condition Fix: Lasse Button auf neuem Timeframe, falls WebSocket später antwortet
                } else {
                    console.error('Fehler beim Timeframe-Wechsel:', error);
                    // Nur bei echten Fehlern Button-State zurücksetzen
                    updateTimeframeButtons(window.currentTimeframe);
                }
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

        // Hilfsfunktion: Aktuelles Timeframe aus UI abrufen
        function getCurrentTimeframe() {
            // Zuerst prüfen: Debug Timeframe Selector
            const debugSelector = document.getElementById('debugTimeframSelector');
            if (debugSelector && debugSelector.value) {
                return debugSelector.value;
            }

            // Fallback: Chart Timeframe Button
            const activeButton = document.querySelector('.timeframe-btn.active');
            if (activeButton) {
                return activeButton.textContent.trim();
            }

            // Letzter Fallback
            return globalState?.currentTimeframe || '5m';
        }

        // Debug Skip Button Handler
        function handleDebugSkip() {
            // Dynamische Nachricht basierend auf Timeframe
            const currentTimeframe = getCurrentTimeframe();
            let skipMessage = "🚀 DEBUG SKIP: +1 Minute";

            if (currentTimeframe === '1m') {
                skipMessage = "🚀 DEBUG SKIP: +1 Minute";
            } else if (['2m', '3m', '5m', '15m', '30m'].includes(currentTimeframe)) {
                const timeframeMinutes = {'2m': 2, '3m': 3, '5m': 5, '15m': 15, '30m': 30};
                const skipMins = timeframeMinutes[currentTimeframe] || 1;
                skipMessage = `🚀 DEBUG SKIP: +${skipMins} Minutes`;
            } else if (['1h', '4h'].includes(currentTimeframe)) {
                const timeframeHours = {'1h': 1, '4h': 4};
                const skipHrs = timeframeHours[currentTimeframe] || 1;
                skipMessage = `🚀 DEBUG SKIP: +${skipHrs} Hour${skipHrs > 1 ? 's' : ''}`;
            }

            console.log(`${skipMessage} - Button clicked!`);
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

        // Debug Control Timeframe Handler - ONLY sets variable, NO chart reload
        function handleDebugTimeframe(timeframe) {
            console.log('🔧 DEBUG CONTROL: Variable-only change zu', timeframe);
            serverLog(`[DEBUG-CONTROL] Variable change to: ${timeframe}`);

            fetch(`/api/debug/set_control_timeframe/${timeframe}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Debug Control Response:', data);
                serverLog('✅ Debug Control Variable successful', data);
            })
            .catch(error => {
                console.error('❌ Debug Control Error:', error);
                serverLog('❌ Debug Control Variable failed', error);
            });
        }

        // Go To Date Modal Functions
        function openDateModal() {
            console.log('[GO TO DATE] Opening Modal...');
            const modal = document.getElementById('dateModal');
            const dateInput = document.getElementById('goToDateInput');

            // Setze ein verfügbares Datum als Default (Dezember 2024)
            // Die CSV-Daten gehen von 31. Dezember 2024 rückwärts
            const defaultDate = new Date('2024-12-25'); // Ein Datum das in den Daten ist
            const dateString = defaultDate.toISOString().split('T')[0];
            dateInput.value = dateString;

            // Setze min/max Werte für verfügbare Daten (ungefähr)
            dateInput.setAttribute('min', '2024-12-01'); // Ca. Startdatum der Daten
            dateInput.setAttribute('max', '2024-12-30'); // Enddatum der Daten

            modal.style.display = 'flex';
            dateInput.focus();
        }

        function closeDateModal() {
            console.log('[GO TO DATE] Closing Modal...');
            const modal = document.getElementById('dateModal');
            modal.style.display = 'none';
        }

        // ===== TRADE MODAL FUNCTIONS =====
        let currentTradeSetup = null;
        window.activeLimitOrders = [];  // Active limit orders array
        window.lastCandleClose = null;  // Store last candle close price
        window.lastCandle = null;  // ⭐ Store full candle data (open, high, low, close)

        // ⭐ BUGFIX: 1-Sekunden-Interval entfernt
        // Limit Orders werden NUR bei Skip Events (neue Kerzen) gecheckt
        // Verhindert sofortiges Triggern bei Platzierung wenn aktuelle Kerze bereits Entry-Line kreuzt

        function getCurrentMarketPrice() {
            // ⭐ Return full candle object for high/low checking in limit orders
            if (window.lastCandle !== null && window.lastCandle !== undefined) {
                return window.lastCandle;
            }
            // Fallback: return just close as candle if only close is available
            if (window.lastCandleClose !== null && window.lastCandleClose !== undefined) {
                return { close: window.lastCandleClose, high: window.lastCandleClose, low: window.lastCandleClose };
            }
            return null;
        }

                function openTradeModal(tradeData) {
            console.log('💰 Opening Trade Modal:', tradeData);

            currentTradeSetup = tradeData;

            // Restore saved order type from localStorage
            const savedOrderType = localStorage.getItem('preferredOrderType') || 'market';
            const orderTypeSelect = document.getElementById('orderType');
            if (orderTypeSelect) {
                orderTypeSelect.value = savedOrderType;
            }

            // Update Modal Content
            document.getElementById('tradeType').textContent = tradeData.isShort ? 'SHORT' : 'LONG';

            // Set entry price based on order type
            const currentMarketPrice = getCurrentMarketPrice();

            if (savedOrderType === 'market' && currentMarketPrice) {
                document.getElementById('tradeEntry').textContent = currentMarketPrice.toFixed(2);
                currentTradeSetup.entryPrice = currentMarketPrice;
            } else {
                document.getElementById('tradeEntry').textContent = tradeData.entryPrice.toFixed(2);
            }

            document.getElementById('tradeStopLoss').textContent = tradeData.stopLoss.toFixed(2);
            document.getElementById('tradeTakeProfit').textContent = tradeData.takeProfit.toFixed(2);

            // Calculate and update position size
            updatePositionSize();

            // Show modal
            const modal = document.getElementById('tradeModal');
            modal.style.display = 'flex';
        }

        function onOrderTypeChange() {
            const orderType = document.getElementById('orderType').value;
            console.log('📋 Order Type changed to:', orderType);

            // Save to localStorage
            localStorage.setItem('preferredOrderType', orderType);

            // Update entry price based on order type
            if (orderType === 'market') {
                const currentMarketPrice = getCurrentMarketPrice();
                if (currentMarketPrice && currentTradeSetup) {
                    document.getElementById('tradeEntry').textContent = currentMarketPrice.toFixed(2);
                    currentTradeSetup.entryPrice = currentMarketPrice;
                    updatePositionSize();
                }
            } else {
                // Limit Order - restore position box entry price
                if (window.currentPositionBox && currentTradeSetup) {
                    const boxEntryPrice = window.currentPositionBox.entryPrice;
                    document.getElementById('tradeEntry').textContent = boxEntryPrice.toFixed(2);
                    currentTradeSetup.entryPrice = boxEntryPrice;
                    updatePositionSize();
                }
            }
        }

                function closeTradeModal() {
            console.log('💰 Closing Trade Modal...');
            const modal = document.getElementById('tradeModal');
            modal.style.display = 'none';
            currentTradeSetup = null;

            // ⭐ VISUAL FEEDBACK: Entferne Selected State vom $ Button
            window.buyButtonSelected = false;
            if (window.currentPositionBox) {
                drawPositionBox();  // Redraw ohne Selected State
            }
        }

        function setRiskAmount(amount) {
            document.getElementById('riskAmount').value = amount;

            // Update active button
            document.querySelectorAll('.risk-preset-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');

            updatePositionSize();
        }

        function setRRRatio(risk, reward) {
            console.log(`📊 Setting R:R Ratio to ${risk}:${reward}`);

            // Update active button
            document.querySelectorAll('.rr-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');

            // Recalculate TP based on new ratio
            if (currentTradeSetup) {
                const entryPrice = currentTradeSetup.entryPrice;
                const stopLoss = currentTradeSetup.stopLoss;
                const riskAmount = Math.abs(entryPrice - stopLoss);
                const rewardAmount = riskAmount * (reward / risk);

                let newTakeProfit;
                if (currentTradeSetup.isShort) {
                    newTakeProfit = entryPrice - rewardAmount;
                } else {
                    newTakeProfit = entryPrice + rewardAmount;
                }

                currentTradeSetup.takeProfit = newTakeProfit;
                document.getElementById('tradeTakeProfit').textContent = newTakeProfit.toFixed(2);

                updatePositionSize();
            }
        }

        function checkLimitOrders(candle) {
            if (!window.activeLimitOrders || window.activeLimitOrders.length === 0) {
                return;
            }

            // ⭐ Extract candle data (support both full candle and fallback to just close)
            const currentPrice = candle.close || candle;
            const high = candle.high || currentPrice;
            const low = candle.low || currentPrice;

            const triggeredOrders = [];

            window.activeLimitOrders.forEach((order, index) => {
                let triggered = false;

                // ⭐⭐⭐ AUTOMATISCHE ORDER-TYPE ERKENNUNG ⭐⭐⭐
                // System erkennt automatisch ob Limit oder Stop gemeint ist
                // basierend auf Entry Price vs. Order Placement Price

                // Bestimme ob Order ÜBER oder UNTER dem Platzierungs-Preis liegt
                const currentPriceAtPlacement = order.currentPriceAtPlacement || currentPrice;
                const entryAbovePlacement = order.entryPrice > currentPriceAtPlacement;

                if (order.isShort) {
                    // SELL Orders (Short)
                    if (entryAbovePlacement) {
                        // Entry > Placement → SELL LIMIT (warte bis Preis STEIGT)
                        // ⭐ Check HIGH: Trigger wenn Docht Entry-Preis berührt oder überschreitet
                        triggered = high >= order.entryPrice;
                        // console.log('[SELL LIMIT] Wait for HIGH to RISE to', order.entryPrice, '- High:', high);
                    } else {
                        // Entry <= Placement → SELL STOP (warte bis Preis FÄLLT)
                        // ⭐ Check LOW: Trigger wenn Docht Entry-Preis berührt oder unterschreitet
                        triggered = low <= order.entryPrice;
                        // console.log('[SELL STOP] Wait for LOW to FALL to', order.entryPrice, '- Low:', low);
                    }
                } else {
                    // BUY Orders (Long)
                    if (entryAbovePlacement) {
                        // Entry > Placement → BUY STOP (warte bis Preis STEIGT)
                        // ⭐ Check HIGH: Trigger wenn Docht Entry-Preis berührt oder überschreitet
                        triggered = high >= order.entryPrice;
                        // console.log('[BUY STOP] Wait for HIGH to RISE to', order.entryPrice, '- High:', high);
                    } else {
                        // Entry <= Placement → BUY LIMIT (warte bis Preis FÄLLT)
                        // ⭐ Check LOW: Trigger wenn Docht Entry-Preis berührt oder unterschreitet
                        triggered = low <= order.entryPrice;
                        // console.log('[BUY LIMIT] Wait for LOW to FALL to', order.entryPrice, '- Low:', low);
                    }
                }

                if (triggered) {
                    const orderType = order.isShort
                        ? (entryAbovePlacement ? 'SELL LIMIT' : 'SELL STOP')
                        : (entryAbovePlacement ? 'BUY STOP' : 'BUY LIMIT');
                    console.log(`🎯 ${orderType} TRIGGERED at High=${high}, Low=${low}:`, order);
                    triggeredOrders.push({order, index});
                }
            });

            // Execute triggered orders (in reverse to avoid index issues)
            triggeredOrders.reverse().forEach(({order, index}) => {
                // Remove price line
                if (order.priceLine) {
                    candlestickSeries.removePriceLine(order.priceLine);
                }

                // Execute trade via backend
                const tradeData = {
                    entryPrice: order.entryPrice,
                    stopLoss: order.stopLoss,
                    takeProfit: order.takeProfit,
                    isShort: order.isShort,
                    riskEUR: order.riskEUR,
                    positionSize: order.positionSize,
                    isRLOnline: order.isRLOnline,
                    orderType: 'limit'  // Mark as limit order execution
                };

                console.log('📡 Executing Limit Order via backend:', tradeData);

                // Send via WebSocket (same as market orders)
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'execute_trade',
                        trade: tradeData
                    }));
                    console.log('✅ Limit Order command sent via WebSocket');
                } else {
                    console.error('❌ WebSocket not connected');
                }

                // Remove from active orders
                window.activeLimitOrders.splice(index, 1);

                // Remove from close buttons registry (using "limit_" prefix)
                const buttonKey = `limit_${order.id}`;
                if (window.limitOrderCloseButtons && window.limitOrderCloseButtons[buttonKey]) {
                    delete window.limitOrderCloseButtons[buttonKey];
                    console.log(`🗑️ Removed close button for order ${order.id}`);
                }
            });

            // Redraw canvas to remove executed order labels
            if (triggeredOrders.length > 0) {
                drawLimitOrders();
            }

            // Orders were triggered and removed from array
        }

                function placeLimitOrder() {
            console.log('📌 Placing Limit Order:', currentTradeSetup);

            const riskEUR = parseFloat(document.getElementById('riskAmount').value);
            const positionSizeText = document.getElementById('positionSize').textContent;
            const positionSize = parseFloat(positionSizeText.replace(' NQ', ''));

            // Get current market price for order type detection
            const currentMarketPrice = candlestickSeries.data().slice(-1)[0]?.close || currentTradeSetup.entryPrice;

            // Create limit order object
            const limitOrder = {
                id: Date.now(),
                entryPrice: currentTradeSetup.entryPrice,
                stopLoss: currentTradeSetup.stopLoss,
                takeProfit: currentTradeSetup.takeProfit,
                direction: currentTradeSetup.direction || (currentTradeSetup.isShort ? 'short' : 'long'),
                isShort: currentTradeSetup.direction === 'short',
                riskEUR: riskEUR,
                positionSize: positionSize,
                isRLOnline: window.RLSystem && window.RLSystem.mode === 'demo',
                currentPriceAtPlacement: currentMarketPrice,  // ⭐ Für automatische Order-Type Erkennung
                priceLine: null  // Will be created below
            };

            // Create price line visualization (without title - we use canvas label instead)
            const priceLine = candlestickSeries.createPriceLine({
                price: limitOrder.entryPrice,
                color: limitOrder.isShort ? '#ef4444' : '#22c55e',
                lineWidth: 2,
                lineStyle: 2,  // Dashed
                axisLabelVisible: true,
                title: ''  // No title - using canvas label
            });

            limitOrder.priceLine = priceLine;

            // Determine order type for logging
            const entryAboveCurrent = limitOrder.entryPrice > currentMarketPrice;
            const autoOrderType = limitOrder.isShort
                ? (entryAboveCurrent ? 'SELL LIMIT' : 'SELL STOP')
                : (entryAboveCurrent ? 'BUY STOP' : 'BUY LIMIT');

            // Add to active limit orders
            window.activeLimitOrders.push(limitOrder);
            console.log(`✅ ${autoOrderType} placed:`, limitOrder);
            console.log(`   Entry: ${limitOrder.entryPrice}, Current: ${currentMarketPrice}`);
            console.log('📊 Active Orders:', window.activeLimitOrders.length);

            // Draw limit order labels on canvas
            drawLimitOrders();

            // Close modal
            closeTradeModal();
        }

        // Draw all limit orders on canvas with close buttons
        function drawLimitOrders() {
            // Create or get canvas
            let canvas = document.getElementById('limitOrderCanvas');
            if (!canvas) {
                canvas = document.createElement('canvas');
                canvas.id = 'limitOrderCanvas';
                // ⭐ FIX: Canvas IMMER transparent - nur X-Button-Elements sind klickbar
                canvas.style.cssText = 'position: absolute; top: 0; left: 0; pointer-events: none; z-index: 11;';
                document.getElementById('chart_container').appendChild(canvas);
            }

            const container = document.getElementById('chart_container');
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;

            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // ⭐ FIX: Entferne alle alten DOM-Button-Elemente
            const oldButtons = document.querySelectorAll('.limit-order-close-btn');
            oldButtons.forEach(btn => btn.remove());

            // Initialize closeButtonPositions for limit orders
            if (!window.limitOrderCloseButtons) {
                window.limitOrderCloseButtons = {};
            }
            window.limitOrderCloseButtons = {};

            // If no orders, canvas is now clear - we're done
            if (!window.activeLimitOrders || window.activeLimitOrders.length === 0) {
                console.log('✅ Canvas cleared - no limit orders to draw');
                return;
            }

            window.activeLimitOrders.forEach((order) => {
                const y = candlestickSeries.priceToCoordinate(order.entryPrice);

                if (y === null) return;

                // Position: right side of chart, BEFORE the Y-axis (not on it)
                const x = canvas.width - 220;  // More left to be before Y-axis
                const boxWidth = 140;
                const boxHeight = 24;

                // Colors
                const bgColor = order.isShort ? 'rgba(239, 68, 68, 0.9)' : 'rgba(34, 197, 94, 0.9)';
                const borderColor = order.isShort ? '#ef4444' : '#22c55e';

                // Draw box
                ctx.fillStyle = bgColor;
                ctx.fillRect(x, y - boxHeight / 2, boxWidth, boxHeight);
                ctx.strokeStyle = borderColor;
                ctx.lineWidth = 2;
                ctx.strokeRect(x, y - boxHeight / 2, boxWidth, boxHeight);

                // Draw text
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 11px Arial';
                const text = `LIMIT ${order.isShort ? 'SHORT' : 'LONG'} ${order.entryPrice.toFixed(2)}`;
                ctx.fillText(text, x + 5, y + 4);

                // Draw close button (X)
                const btnX = x + boxWidth - 18;
                const btnY = y - 8;
                const btnSize = 16;

                ctx.fillStyle = '#fff';
                ctx.fillRect(btnX, btnY, btnSize, btnSize);
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 1;
                ctx.strokeRect(btnX, btnY, btnSize, btnSize);

                // Draw X
                ctx.strokeStyle = '#ef4444';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(btnX + 4, btnY + 4);
                ctx.lineTo(btnX + btnSize - 4, btnY + btnSize - 4);
                ctx.moveTo(btnX + btnSize - 4, btnY + 4);
                ctx.lineTo(btnX + 4, btnY + btnSize - 4);
                ctx.stroke();

                // ⭐ FIX: Erstelle echtes DOM-Button-Element (nicht nur Canvas-Grafik)
                const closeButton = document.createElement('button');
                closeButton.className = 'limit-order-close-btn';
                closeButton.style.cssText = `
                    position: absolute;
                    left: ${btnX}px;
                    top: ${btnY}px;
                    width: ${btnSize}px;
                    height: ${btnSize}px;
                    background: transparent;
                    border: none;
                    cursor: pointer;
                    z-index: 12;
                    padding: 0;
                `;
                closeButton.onclick = (e) => {
                    e.stopPropagation();
                    console.log(`[DOM Button] ✅ Close button clicked for order ${order.id}`);
                    window.cancelLimitOrder(order.id);
                };
                container.appendChild(closeButton);

                // Store button position for reference (using "limit_" prefix)
                window.limitOrderCloseButtons[`limit_${order.id}`] = {
                    x: btnX,
                    y: btnY,
                    width: btnSize,
                    height: btnSize,
                    orderId: order.id,
                    element: closeButton  // Store DOM reference
                };
            });

            console.log(`✅ Drew ${window.activeLimitOrders.length} limit orders on canvas with DOM buttons`);
        }

        window.cancelLimitOrder = function(orderId) {
            console.log('❌ Cancelling Limit Order:', orderId);

            const orderIndex = window.activeLimitOrders.findIndex(order => order.id === orderId);
            if (orderIndex === -1) {
                console.error('Order not found:', orderId);
                return;
            }

            const order = window.activeLimitOrders[orderIndex];

            // Remove price line from chart
            if (order.priceLine) {
                candlestickSeries.removePriceLine(order.priceLine);
            }

            // Remove from array
            window.activeLimitOrders.splice(orderIndex, 1);

            console.log('✅ Limit Order cancelled');
            console.log('📊 Remaining Limit Orders:', window.activeLimitOrders.length);

            // Redraw limit orders canvas
            if (window.activeLimitOrders.length > 0) {
                drawLimitOrders();
            } else {
                // Clear canvas if no more orders
                const canvas = document.getElementById('limitOrderCanvas');
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
            }
        };

                function updatePositionSize() {
            if (!currentTradeSetup) return;

            const riskEUR = parseFloat(document.getElementById('riskAmount').value);
            const entryPrice = currentTradeSetup.entryPrice;
            const stopLoss = currentTradeSetup.stopLoss;
            const takeProfit = currentTradeSetup.takeProfit;

            // Calculate position size based on risk
            const riskPerUnit = Math.abs(entryPrice - stopLoss);
            const positionSize = riskEUR / riskPerUnit;

            // Calculate max profit
            const rewardPerUnit = Math.abs(takeProfit - entryPrice);
            const maxProfit = positionSize * rewardPerUnit;

            // Update display
            document.getElementById('positionSize').textContent = `${positionSize.toFixed(2)} NQ`;
            document.getElementById('maxProfit').textContent = `+${maxProfit.toFixed(0)}€`;
        }

        function executeTrade() {
            console.log('🚀 Executing Trade:', currentTradeSetup);

            if (!currentTradeSetup) {
                console.error('❌ No trade setup available');
                return;
            }

            // Check order type
            const orderType = document.getElementById('orderType')?.value || 'market';
            console.log('📋 Order Type:', orderType);

            if (orderType === 'limit') {
                // Place limit order instead of executing immediately
                placeLimitOrder();
                return;
            }

            // Continue with Market Order execution...

            // Lese Trade-Parameter
            const riskEUR = parseFloat(document.getElementById('riskAmount').value);
            const positionSizeText = document.getElementById('positionSize').textContent;
            const positionSize = parseFloat(positionSizeText.replace(' NQ', ''));

            // Prüfe RL Status
            const isRLOnline = window.RLSystem && window.RLSystem.mode === 'demo';

            // Erstelle Trade-Daten für Backend
            const tradeData = {
                entryPrice: currentTradeSetup.entryPrice,
                stopLoss: currentTradeSetup.stopLoss,
                takeProfit: currentTradeSetup.takeProfit,
                isShort: currentTradeSetup.direction === 'short',
                riskEUR: riskEUR,
                positionSize: positionSize,
                isRLOnline: isRLOnline,
                orderType: 'market'  // Mark as market order execution
            };

            console.log('📡 Sending trade to backend:', tradeData);
            console.log(`📊 Account: ${isRLOnline ? 'RL-KI' : 'Nutzer'}`);

            // 🧹 Cleanup: Entferne alte Position-Tool Lines (Entry/SL/TP vom Drawing)
            // Diese werden durch addPositionOverlay() nach Trade-Execution neu erstellt
            removePriceLines();
            removeCurrentPositionBox();

            // Sende WebSocket Command
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'execute_trade',
                    trade: tradeData
                }));

                console.log('✅ Trade command sent to backend');

                // RL Action Tracking
                if (window.RLSystem) {
                    window.RLSystem.trackAction('trade_executed', tradeData);
                }

                // Schließe Modal
                closeTradeModal();
            } else {
                console.error('❌ WebSocket not connected');
                alert('Fehler: Keine Verbindung zum Server');
            }
        }

        function goToSelectedDate() {
            const dateInput = document.getElementById('goToDateInput');
            const selectedDate = dateInput.value;

            if (!selectedDate) {
                alert('Bitte wähle ein Datum aus!');
                return;
            }

            // RL Action Tracking
            if (window.RLSystem) {
                window.RLSystem.trackAction('go_to_date', {
                    selected_date: selectedDate,
                    current_timeframe: window.currentTimeframe,
                    timestamp: new Date()
                });
            }

            console.log('[GO TO DATE] Request:', selectedDate);
            serverLog('[GO TO DATE] Request: ' + selectedDate);

            // Modal schließen
            closeDateModal();

            // API Call zum Backend
            fetch('/api/debug/go_to_date', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date: selectedDate })
            })
            .then(response => response.json())
            .then(data => {
                console.log('✅ Go To Date Response:', data);
                serverLog('[SUCCESS] Go To Date successful: ' + data.message, data);

                if (data.status === 'success') {
                    console.log('[CHART] Chart wird zu neuem Datum reinitialisiert...');
                    // WebSocket wird automatisch das chart_reinitialize Event senden
                } else {
                    console.error('❌ Go To Date failed:', data.message);
                    alert('Fehler: ' + data.message);
                }
            })
            .catch(error => {
                console.error('❌ Go To Date Error:', error);
                serverLog('❌ Go To Date failed', error);
                alert('Fehler beim Laden des Datums: ' + error.message);
            });
        }

        // Modal schließen bei Escape-Taste
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                const modal = document.getElementById('dateModal');
                if (modal.style.display === 'flex') {
                    closeDateModal();
                }
            }
        });

        // Modal schließen bei Klick außerhalb
        document.addEventListener('click', function(event) {
            const modal = document.getElementById('dateModal');
            if (event.target === modal) {
                closeDateModal();
            }
        });

        // RL Trading System - Einfache und sichere Implementation
        window.RLSystem = {
            mode: 'offline',
            isRecording: false,
            demoActions: [],

            startDemo: function() {
                this.mode = 'demo';
                this.isRecording = true;
                this.updateUI();
                console.log('✅ RL Demo-Modus aktiviert - Tracking gestartet');
            },

            startBot: function() {
                this.mode = 'bot';
                this.isRecording = false;
                this.updateUI();
                console.log('✅ RL Bot-Modus aktiviert');
            },

            stop: function() {
                console.log(`📊 RL Session beendet - ${this.demoActions.length} Actions aufgezeichnet`);
                this.mode = 'offline';
                this.isRecording = false;
                this.updateUI();
            },

            updateUI: function() {
                const status = document.getElementById('rlStatus');
                const demoBtn = document.getElementById('rlDemoBtn');
                const botBtn = document.getElementById('rlBotBtn');
                const stopBtn = document.getElementById('rlStopBtn');

                if (status) {
                    if (this.mode === 'demo') {
                        status.textContent = '🟢 Demo';
                        status.style.color = '#4ade80';
                    } else if (this.mode === 'bot') {
                        status.textContent = '🤖 Bot';
                        status.style.color = '#60a5fa';
                    } else {
                        status.textContent = 'Offline';
                        status.style.color = '#666';
                    }
                }

                if (this.mode === 'offline') {
                    if (demoBtn) demoBtn.style.display = 'inline-block';
                    if (botBtn) botBtn.style.display = 'inline-block';
                    if (stopBtn) stopBtn.style.display = 'none';
                } else {
                    if (demoBtn) demoBtn.style.display = 'none';
                    if (botBtn) botBtn.style.display = 'none';
                    if (stopBtn) stopBtn.style.display = 'inline-block';
                }
            },

            trackAction: function(actionType, data) {
                if (this.mode === 'demo' && this.isRecording) {
                    const action = {
                        id: Date.now() + '_' + Math.random().toString(36).substr(2, 9),
                        type: actionType,
                        timestamp: new Date(),
                        data: data
                    };
                    this.demoActions.push(action);
                    console.log(`📝 RL Action tracked: ${actionType}`, data);
                }
            }
        };

        // Warte bis DOM und Script geladen sind
        document.addEventListener('DOMContentLoaded', function() {
            serverLog('🔧 DOM loaded - Initialisiere Chart und Event Handlers...');

            // WICHTIG: Chart zuerst initialisieren
            // console.log('🔧 Initialisiere Chart beim DOMContentLoaded...');
            initChart();

            // RL System UI initialisieren
            if (window.RLSystem) {
                window.RLSystem.updateUI();
                console.log('✅ RL System initialisiert');
            }

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
                // console.log('✅ Skip Button event listener attached');
            } else {
                console.error('❌ Skip Button not found!');
            }

            // Play/Pause Button
            const playPauseBtn = document.getElementById('playPauseBtn');
            console.log('🔧 Debug setup - PlayPause Button element:', playPauseBtn);
            if (playPauseBtn) {
                playPauseBtn.addEventListener('click', handleDebugPlayPause);
                // console.log('✅ PlayPause Button event listener attached');
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

            // Go To Date Button
            const goToDateBtn = document.getElementById('goToDateBtn');
            console.log('🔧 Debug setup - Go To Date Button element:', goToDateBtn);
            if (goToDateBtn) {
                goToDateBtn.addEventListener('click', openDateModal);
                // console.log('✅ Go To Date Button event listener attached');
            } else {
                console.error('❌ Go To Date Button not found!');
            }

            console.log('🛠️ Debug Controls Event Handlers konsolidiert und initialized');

            if (positionBoxTool) {
                positionBoxTool.addEventListener('click', togglePositionTool);
                // console.log('✅ Position Box Tool Event Handler registriert');
            } else {
                console.error('❌ positionBoxTool Button nicht gefunden');
            }

            if (shortPositionTool) {
                shortPositionTool.addEventListener('click', toggleShortPositionTool);
                // console.log('✅ Short Position Tool Event Handler registriert');
            } else {
                console.error('❌ shortPositionTool Button nicht gefunden');
            }

            if (clearAllBtn) {
                clearAllBtn.addEventListener('click', clearAllPositions);
                // console.log('✅ Clear All Button Event Handler registriert');
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

            // WebSocket und Account-Daten initialisieren
            connectWebSocket();
            loadAccountData();
        });

// ========================================
// Settings Modal Functions
// ========================================

function openSettingsModal() {
    const modal = document.getElementById('settingsModal');
    const aiInput = document.getElementById('aiBalanceInput');
    const userInput = document.getElementById('userBalanceInput');
    const warning = document.getElementById('settingsWarning');

    // Hole aktuelle Balances aus der UI
    const aiBalanceElem = document.getElementById('ai-balance');
    const userBalanceElem = document.getElementById('user-balance');

    if (aiBalanceElem && userBalanceElem) {
        // Parse Balance aus "500.000€" Format
        const aiBalance = parseFloat(aiBalanceElem.textContent.replace(/[.€\s]/g, ''));
        const userBalance = parseFloat(userBalanceElem.textContent.replace(/[.€\s]/g, ''));

        aiInput.value = aiBalance || 500000;
        userInput.value = userBalance || 500000;
    }

    // Verstecke Warnung
    warning.style.display = 'none';

    // Zeige Modal
    modal.style.display = 'flex';
    console.log('⚙️ Settings Modal geöffnet');
}

function closeSettingsModal() {
    const modal = document.getElementById('settingsModal');
    modal.style.display = 'none';
    console.log('⚙️ Settings Modal geschlossen');
}

function setBalancePreset(accountType, amount) {
    const inputId = accountType === 'ai' ? 'aiBalanceInput' : 'userBalanceInput';
    const input = document.getElementById(inputId);

    if (input) {
        input.value = amount;
        console.log(`⚙️ ${accountType} Balance Preset: ${amount}€`);
    }

    // Update active state für Preset-Buttons
    updatePresetButtonStates(accountType, amount);
}

function updatePresetButtonStates(accountType, selectedAmount) {
    // Finde die richtige Balance-Section
    const sections = document.querySelectorAll('.balance-section');
    const targetSection = accountType === 'ai' ? sections[0] : sections[1];

    if (!targetSection) return;

    // Entferne active state von allen Buttons in dieser Section
    const buttons = targetSection.querySelectorAll('.balance-preset-btn');
    buttons.forEach(btn => {
        btn.classList.remove('active');

        // Prüfe ob dieser Button der ausgewählte ist
        const btnAmount = parseInt(btn.textContent.replace(/[k€]/g, '')) * 1000;
        if (btnAmount === selectedAmount) {
            btn.classList.add('active');
        }
    });
}

async function applySettings() {
    const aiInput = document.getElementById('aiBalanceInput');
    const userInput = document.getElementById('userBalanceInput');
    const warning = document.getElementById('settingsWarning');
    const warningText = document.getElementById('settingsWarningText');

    const aiBalance = parseFloat(aiInput.value);
    const userBalance = parseFloat(userInput.value);

    console.log('💾 Applying Settings:', { aiBalance, userBalance });

    try {
        // API-Call zum Update der Balance
        const response = await fetch('/api/account/update-balance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ai_balance: aiBalance,
                user_balance: userBalance
            })
        });

        const data = await response.json();
        console.log('📡 Balance Update Response:', data);

        if (data.status === 'success') {
            // Update UI mit neuen Balances
            updateAccountBalanceDisplay(data.ai_account, data.user_account);

            // Schließe Modal
            closeSettingsModal();

            console.log('✅ Balances erfolgreich aktualisiert');
        } else {
            // Zeige Fehler-Warnung
            warningText.textContent = data.message || 'Fehler beim Aktualisieren der Balance';
            warning.style.display = 'block';
            console.error('❌ Balance Update Fehler:', data.message);
        }
    } catch (error) {
        console.error('❌ Fehler beim Balance Update:', error);
        warningText.textContent = 'Netzwerk-Fehler beim Aktualisieren der Balance';
        warning.style.display = 'block';
    }
}

function updateAccountBalanceDisplay(aiAccount, userAccount) {
    // RL-KI Account Update
    const aiBalanceElem = document.getElementById('ai-balance');
    const aiRealizedElem = document.getElementById('ai-realized');
    const aiUnrealizedElem = document.getElementById('ai-unrealized');

    if (aiBalanceElem) {
        aiBalanceElem.textContent = formatCurrency(aiAccount.balance);
        aiBalanceElem.className = 'account-value-amount neutral';
    }
    if (aiRealizedElem) {
        aiRealizedElem.textContent = formatCurrency(aiAccount.realized_pnl, true);
        aiRealizedElem.className = getPnLClass(aiAccount.realized_pnl);
    }
    if (aiUnrealizedElem) {
        aiUnrealizedElem.textContent = formatCurrency(aiAccount.unrealized_pnl, true);
        aiUnrealizedElem.className = getPnLClass(aiAccount.unrealized_pnl);
    }

    // Nutzer Account Update
    const userBalanceElem = document.getElementById('user-balance');
    const userRealizedElem = document.getElementById('user-realized');
    const userUnrealizedElem = document.getElementById('user-unrealized');

    if (userBalanceElem) {
        userBalanceElem.textContent = formatCurrency(userAccount.balance);
        userBalanceElem.className = 'account-value-amount neutral';
    }
    if (userRealizedElem) {
        userRealizedElem.textContent = formatCurrency(userAccount.realized_pnl, true);
        userRealizedElem.className = getPnLClass(userAccount.realized_pnl);
    }
    if (userUnrealizedElem) {
        userUnrealizedElem.textContent = formatCurrency(userAccount.unrealized_pnl, true);
        userUnrealizedElem.className = getPnLClass(userAccount.unrealized_pnl);
    }

    console.log('✅ Account Balance Display aktualisiert');
}

function formatCurrency(value, showSign = false) {
    const formatted = Math.abs(value).toLocaleString('de-DE', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });

    if (showSign && value !== 0) {
        return `${value > 0 ? '+' : '-'}${formatted}€`;
    }
    return `${formatted}€`;
}

function getPnLClass(value) {
    if (value > 0) return 'account-value-amount profit';
    if (value < 0) return 'account-value-amount loss';
    return 'account-value-amount neutral';
}

// ========================================
// Indicators Modal Functions
// ========================================

function openIndicatorsModal() {
    const modal = document.getElementById('indicatorsModal');
    modal.style.display = 'flex';
    console.log('📊 Indicators Modal geöffnet');
}

function closeIndicatorsModal() {
    const modal = document.getElementById('indicatorsModal');
    modal.style.display = 'none';
    console.log('📊 Indicators Modal geschlossen');
}

// ========================================
// Add EMA Dialog Functions
// ========================================

function openAddEMADialog() {
    closeIndicatorsModal(); // Close Indicators Modal first
    const modal = document.getElementById('addEMAModal');
    modal.style.display = 'flex';

    // Reset to default period
    const periodInput = document.getElementById('emaPeriodInput');
    if (periodInput) periodInput.value = 9;

    console.log('📈 Add EMA Dialog geöffnet');
}

function closeAddEMADialog() {
    const modal = document.getElementById('addEMAModal');
    modal.style.display = 'none';
    console.log('📈 Add EMA Dialog geschlossen');
}

function setEMAPeriod(period) {
    const periodInput = document.getElementById('emaPeriodInput');
    if (periodInput) {
        periodInput.value = period;
    }
}

function addEMAIndicator() {
    const periodInput = document.getElementById('emaPeriodInput');
    const period = parseInt(periodInput.value) || 9;

    // Validation
    if (period < 2 || period > 200) {
        alert('Period muss zwischen 2 und 200 liegen');
        return;
    }

    // Add via IndicatorManager
    if (window.IndicatorManager) {
        window.IndicatorManager.addIndicator('EMA', {
            period: period,
            color: '#000000' // Default black
        });

        console.log(`✅ EMA(${period}) hinzugefügt`);
    } else {
        console.error('❌ IndicatorManager nicht verfügbar');
    }

    // Close dialog
    closeAddEMADialog();
}

// ========================================
// Asset Name Update Function
// ========================================

function updateAssetName(assetSymbol) {
    const assetNameElem = document.getElementById('assetName');
    if (assetNameElem) {
        assetNameElem.textContent = assetSymbol;
        console.log(`🔍 Asset-Name aktualisiert: ${assetSymbol}`);
    }
}
