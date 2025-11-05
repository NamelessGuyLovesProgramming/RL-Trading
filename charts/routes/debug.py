"""
Debug Routes - API Endpoints für Debug-Funktionen
REFACTOR PHASE 5: Extrahiert aus chart_server.py
"""

from fastapi import APIRouter, Request
from typing import Dict, Any

# Router-Instanz
router = APIRouter(prefix="/api/debug", tags=["debug"])


def setup_debug_routes(app, debug_service, navigation_service,
                       unified_time_manager, manager, debug_controller,
                       global_skip_events, debug_control_timeframe, account_service, config_service, training_mode_service=None):
    """
    Registriert Debug-Routes am FastAPI App

    Args:
        app: FastAPI App-Instanz
        debug_service: DebugService-Instanz
        navigation_service: NavigationService-Instanz
        unified_time_manager: UnifiedTimeManager-Instanz
        manager: WebSocketManager-Instanz
        debug_controller: DebugController-Instanz
        global_skip_events: Global skip events list
        debug_control_timeframe: Debug control timeframe reference
        account_service: AccountService-Instanz
        config_service: ConfigService-Instanz
        training_mode_service: TrainingModeService-Instanz (optional)
    """

    def _build_market_context(candle: Dict[str, Any], timestamp: int, indicator_data: Dict = None) -> Dict[str, Any]:
        """
        Baut Market Context für RL Agent aus Candle-Daten und Indikator-Daten

        Args:
            candle: Aktuelle Kerze mit OHLCV
            timestamp: Unix timestamp
            indicator_data: Indikator-Daten vom Frontend (optional)

        Returns:
            Market Context Dictionary
        """
        # Default values
        in_fvg = False
        fvg_distance = 999
        near_session_high = False
        near_session_low = False
        session_high_broken = False
        session_low_broken = False
        session_high_first_break = False
        session_low_first_break = False
        volume_spike = False
        volume_ratio = 1.0
        current_session = 'unknown'

        # Use indicator data if available (NEW field names)
        if indicator_data:
            in_fvg = indicator_data.get('in_fvg', False)
            near_session_high = indicator_data.get('near_session_high', False)
            near_session_low = indicator_data.get('near_session_low', False)
            session_high_broken = indicator_data.get('session_high_broken', False)
            session_low_broken = indicator_data.get('session_low_broken', False)
            session_high_first_break = indicator_data.get('session_high_first_break', False)
            session_low_first_break = indicator_data.get('session_low_first_break', False)
            volume_spike = indicator_data.get('volume_spike', False)
            volume_ratio = indicator_data.get('volume_ratio', 1.0)
            current_session = indicator_data.get('current_session', 'unknown')

            # FVG distance (approximation based on FVG type)
            if in_fvg:
                fvg_distance = 0.001  # Very close (inside FVG)
            else:
                fvg_distance = indicator_data.get('distance_to_fvg', 999) or 999

        return {
            'current_price': candle['close'],
            'timestamp': timestamp,
            'patterns': {
                'in_fvg_zone': in_fvg,
                'fvg_distance': fvg_distance,
                'near_support_ob': near_session_low,  # Session Low = Support
                'near_resistance_ob': near_session_high,  # Session High = Resistance
                'near_session_high': near_session_high,
                'near_session_low': near_session_low,
                'session_high_broken': session_high_broken,
                'session_low_broken': session_low_broken,
                'session_high_first_break': session_high_first_break,  # ✅ NEU
                'session_low_first_break': session_low_first_break,    # ✅ NEU
                'liquidity_direction': 1 if near_session_low else (-1 if near_session_high else 0),
                'market_structure': 0  # TODO: Could be derived from session high/low
            },
            'session_info': {
                'session': current_session,
                'time_in_session': 0,
                'near_open': False,
                'near_close': False
            },
            'volume': {
                'spike': volume_spike,
                'ratio': volume_ratio
            }
        }

    # REFACTOR PHASE 4: Skip-Endpoint (bereits auf NavigationService migriert)
    @router.post("/skip")
    async def debug_skip(request: Request):
        """Skip-Operation über NavigationService"""
        # Variables passed as closure from setup_debug_routes
        try:
            # Parse request body for indicator data
            try:
                body = await request.json() if request.headers.get('content-type') == 'application/json' else {}
            except:
                body = {}
            indicator_data = body.get('indicator_data', None)

            if indicator_data:
                print(f"[SKIP-SERVICE] Indicator Data received: {indicator_data}")

            skip_timeframe = debug_control_timeframe
            chart_timeframe = manager.chart_state.get('interval', '5m')

            print(f"[SKIP-SERVICE] Skip-Request: {skip_timeframe}")

            skip_result = navigation_service.skip_forward(skip_timeframe)

            if not skip_result['success']:
                return {
                    "status": "error",
                    "message": skip_result.get('error', 'Skip fehlgeschlagen'),
                    "timeframe": skip_timeframe
                }

            candle = skip_result['candle']
            candle_type = skip_result['candle_type']
            new_global_time = unified_time_manager.get_current_time()

            # Update chart state
            if hasattr(manager, 'chart_state') and 'data' in manager.chart_state:
                manager.chart_state['data'].append(candle)

            # ⭐⭐⭐ SL/TP AUTO-CLOSE CHECK ⭐⭐⭐
            current_price = candle['close']
            candle_high = candle['high']
            candle_low = candle['low']

            active_positions = account_service.get_active_positions()
            print(f"[SKIP] Active positions: {len(active_positions)}")

            positions_to_close = []

            for position in active_positions:
                position_id = position['id']
                account_type = position.get('account_type', 'user')
                direction = position['direction']
                entry = position['entry_price']
                sl = position['sl_price']
                tp = position['tp_price']

                print(f"[SKIP] Checking position {position_id}: {direction}, Entry={entry}, SL={sl}, TP={tp}")
                print(f"[SKIP] Candle: High={candle_high}, Low={candle_low}, Close={current_price}")

                # Update unrealized PnL
                account_service.update_position_pnl(position_id, current_price, account_type)

                # Check SL/TP using High/Low, not just Close!
                sl_hit = False
                tp_hit = False

                if direction == 'long':
                    # Long SL: Wird getriggert wenn Low <= SL
                    if candle_low <= sl:
                        sl_hit = True
                        print(f"[SKIP] 🔴 SL HIT! Long position {position_id}: Low={candle_low} <= SL={sl}")
                    # Long TP: Wird getriggert wenn High >= TP
                    elif candle_high >= tp:
                        tp_hit = True
                        print(f"[SKIP] 🟢 TP HIT! Long position {position_id}: High={candle_high} >= TP={tp}")
                else:  # short
                    # Short SL: Wird getriggert wenn High >= SL
                    if candle_high >= sl:
                        sl_hit = True
                        print(f"[SKIP] 🔴 SL HIT! Short position {position_id}: High={candle_high} >= SL={sl}")
                    # Short TP: Wird getriggert wenn Low <= TP
                    elif candle_low <= tp:
                        tp_hit = True
                        print(f"[SKIP] 🟢 TP HIT! Short position {position_id}: Low={candle_low} <= TP={tp}")

                if sl_hit:
                    # EXAKTES RISK-MANAGEMENT: Schließe bei SL zum SL-Preis
                    positions_to_close.append((position_id, sl, 'stop_loss', account_type))
                elif tp_hit:
                    # EXAKTES RISK-MANAGEMENT: Schließe bei TP zum TP-Preis
                    positions_to_close.append((position_id, tp, 'take_profit', account_type))

            # Close positions that hit SL/TP
            for position_id, close_price, reason, account_type in positions_to_close:
                close_result = account_service.close_position(position_id, close_price, reason, account_type)
                if close_result['success']:
                    print(f"[SKIP] Position closed: {position_id} - {reason} at {close_price}")

                    # Broadcast position closure
                    await manager.broadcast({
                        'type': 'position_closed',
                        'position_id': position_id,
                        'close_price': close_price,
                        'close_reason': reason,
                        'realized_pnl': close_result['realized_pnl'],
                        'account_type': account_type
                    })

                    # 🤖 AI TRADE FEEDBACK: Wenn AI Trade geschlossen wurde → Feedback Modal öffnen
                    if position_id.startswith('ai_'):
                        print(f"[AI-TRADING] 🎯 AI Trade closed - Opening Feedback Modal for {position_id}")
                        await manager.broadcast({
                            'type': 'ai_position_closed',
                            'trade_id': position_id,
                            'close_price': close_price,
                            'close_reason': reason,
                            'realized_pnl': close_result['realized_pnl'],
                            'outcome': 'win' if close_result['realized_pnl'] > 0 else 'loss'
                        })

            # Broadcast updated accounts after PnL updates
            if active_positions:  # Nur wenn Positionen existieren
                all_accounts = account_service.get_all_accounts_summary()
                await manager.broadcast({
                    'type': 'account_update',
                    'accounts': all_accounts
                })

            # ═══════════════════════════════════════════════════════
            # 🤖 AI TRADING INTEGRATION
            # ═══════════════════════════════════════════════════════
            # Wenn Training Mode aktiv → AI trifft Trade-Entscheidung
            if training_mode_service and training_mode_service.is_active:
                print(f"[AI-TRADING] Training Mode active - Building market context...")

                # Build Market Context für AI (mit Indikator-Daten vom Frontend)
                market_context = _build_market_context(candle, int(new_global_time.timestamp()), indicator_data)

                # AI trifft Entscheidung
                ai_decision = training_mode_service.on_skip(market_context)

                # Wenn AI traded → Log only (Feedback Modal erst bei Position Close!)
                if ai_decision:
                    print(f"[AI-TRADING] ✅ Trade executed: {ai_decision['action'].upper()} @ {ai_decision['position']['entry_price']}")
                    print(f"[AI-TRADING] Trade ID: {ai_decision['trade_id']} - Waiting for SL/TP hit for feedback...")

            timeframe_display = {
                '1m': "1min", '2m': "2min", '3m': "3min", '5m': "5min",
                '15m': "15min", '30m': "30min", '1h': "1h", '4h': "4h"
            }
            display_name = timeframe_display.get(skip_timeframe, skip_timeframe)
            skip_message = f"Skip +{display_name} -> {new_global_time.strftime('%H:%M:%S')}"

            sync_status = unified_time_manager.get_timeframe_sync_status()

            await manager.broadcast({
                'type': 'unified_skip_event',
                'candle': candle,
                'candle_type': candle_type,
                'debug_time': new_global_time.isoformat(),
                'timeframe': skip_timeframe,
                'system_type': 'navigation_service',
                'sync_status': sync_status,
                'global_time': new_global_time.isoformat()
            })

            print(f"[SKIP-SERVICE] SUCCESS: {skip_message}")
            return {
                "status": "success",
                "message": f"{skip_message} - {candle_type}",
                "candle": candle,
                "candle_type": candle_type,
                "debug_time": new_global_time.isoformat(),
                "timeframe": skip_timeframe,
                "system": "navigation_service"
            }
        except Exception as e:
            print(f"[ERROR] Skip-Fehler: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}


    # ⚡ PERFORMANCE: Batch-Skip Endpoint für High-Speed Playback
    @router.post("/skip_batch")
    async def debug_skip_batch(request: dict):
        """⚡ Führt mehrere Skips in einem Request aus (Performance-Optimierung)"""
        try:
            count = request.get("count", 1)
            skip_timeframe = debug_control_timeframe

            print(f"[SKIP-BATCH] Request: {count} skips for {skip_timeframe}")

            if count < 1:
                return {"status": "error", "message": "Count must be >= 1"}

            if count > 100:  # Safety limit
                return {"status": "error", "message": "Count too large (max 100)"}

            candles = []
            last_candle = None
            last_candle_type = None

            # Führe N Skips durch (ohne Position Checks)
            for i in range(count):
                skip_result = navigation_service.skip_forward(skip_timeframe)

                if not skip_result['success']:
                    print(f"[SKIP-BATCH] Stopped at {i+1}/{count}: {skip_result.get('error')}")
                    break

                last_candle = skip_result['candle']
                last_candle_type = skip_result['candle_type']
                candles.append(last_candle)

                # Update chart state
                if hasattr(manager, 'chart_state') and 'data' in manager.chart_state:
                    manager.chart_state['data'].append(last_candle)

            if not candles:
                return {"status": "error", "message": "No candles skipped"}

            new_global_time = unified_time_manager.get_current_time()

            # ⚡ OPTIMIZATION: Position Check NUR für LETZTE Kerze!
            current_price = last_candle['close']
            candle_high = last_candle['high']
            candle_low = last_candle['low']

            active_positions = account_service.get_active_positions()
            positions_to_close = []

            for position in active_positions:
                position_id = position['id']
                account_type = position.get('account_type', 'user')
                direction = position['direction']
                sl = position['sl_price']
                tp = position['tp_price']

                # SL/TP Check
                sl_hit = False
                tp_hit = False
                close_price = None
                close_reason = None

                if direction == 'long':
                    if candle_low <= sl:
                        sl_hit = True
                        close_price = sl
                        close_reason = 'sl'
                    elif candle_high >= tp:
                        tp_hit = True
                        close_price = tp
                        close_reason = 'tp'
                else:  # short
                    if candle_high >= sl:
                        sl_hit = True
                        close_price = sl
                        close_reason = 'sl'
                    elif candle_low <= tp:
                        tp_hit = True
                        close_price = tp
                        close_reason = 'tp'

                if sl_hit or tp_hit:
                    positions_to_close.append({
                        'position_id': position_id,
                        'close_price': close_price,
                        'close_reason': close_reason,
                        'account_type': account_type
                    })

            # Close Positionen
            for close_info in positions_to_close:
                result = account_service.close_position(
                    close_info['position_id'],
                    close_info['close_price'],
                    close_info['account_type']
                )

                if result['success']:
                    await manager.broadcast({
                        'type': 'position_closed',
                        'position_id': close_info['position_id'],
                        'close_price': close_info['close_price'],
                        'close_reason': close_info['close_reason'],
                        'pnl': result.get('pnl', 0)
                    })

            # Account Update Broadcast (falls Positionen geschlossen)
            if positions_to_close:
                await manager.broadcast({
                    'type': 'account_update',
                    'ai': account_service.get_account_balance('ai'),
                    'user': account_service.get_account_balance('user')
                })

            # ⚡ OPTIMIZATION: NUR 1 Broadcast für alle Kerzen
            sync_status = unified_time_manager.get_timeframe_sync_status()

            await manager.broadcast({
                'type': 'batch_skip_event',
                'candles': candles,
                'count': len(candles),
                'final_candle': last_candle,
                'candle_type': last_candle_type,
                'debug_time': new_global_time.isoformat(),
                'timeframe': skip_timeframe,
                'system_type': 'navigation_service',
                'sync_status': sync_status,
                'global_time': new_global_time.isoformat()
            })

            print(f"[SKIP-BATCH] SUCCESS: Skipped {len(candles)} candles -> {new_global_time.strftime('%H:%M:%S')}")

            return {
                "status": "success",
                "candles": candles,
                "count": len(candles),
                "final_time": new_global_time.isoformat(),
                "timeframe": skip_timeframe
            }

        except Exception as e:
            print(f"[ERROR] Batch-Skip-Fehler: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}


    # REFACTOR PHASE 4: GoTo-Endpoint (bereits auf NavigationService migriert)
    @router.post("/go_to_date")
    async def debug_go_to_date(date_data: dict):
        """Go To Date über NavigationService"""
        # Variables passed as closure from setup_debug_routes
        try:
            from datetime import datetime

            target_date = date_data.get("date")
            if not target_date:
                return {"status": "error", "message": "Kein Datum angegeben"}

            target_datetime = datetime.strptime(target_date, "%Y-%m-%d")
            current_timeframe = manager.chart_state['interval']

            print(f"[GOTO-SERVICE] Request: {target_date} in {current_timeframe}")

            goto_result = navigation_service.go_to_date(
                target_date=target_datetime,
                timeframe=current_timeframe,
                visible_candles=200
            )

            if not goto_result['success']:
                return {
                    "status": "error",
                    "message": "Keine Daten verfügbar",
                    "target_date": target_date
                }

            chart_data = goto_result['chart_data']

            # Legacy compatibility
            skip_events_count = len(global_skip_events)
            global_skip_events.clear()
            print(f"[GOTO-RESET] Global Skip Events cleared: {skip_events_count} events")

            manager.chart_state['data'] = chart_data
            manager.chart_state['interval'] = current_timeframe

            from charts.core import ChartSeriesLifecycleManager
            chart_lifecycle_manager = ChartSeriesLifecycleManager()
            chart_lifecycle_manager.reset_to_clean_state()

            await manager.broadcast({
                'type': 'debug_control_timeframe_changed',
                'debug_control_timeframe': debug_control_timeframe,
                'old_timeframe': None,
                'source': 'go_to_date_sync'
            })

            # Sichere actual_date Extraktion
            actual_date_for_broadcast = target_date
            if 'actual_date' in goto_result and goto_result['actual_date']:
                try:
                    actual_date_for_broadcast = goto_result['actual_date'].isoformat()
                except:
                    actual_date_for_broadcast = str(goto_result['actual_date'])

            await manager.broadcast({
                'type': 'go_to_date_complete',
                'data': chart_data,
                'date': target_date,
                'actual_date': actual_date_for_broadcast
            })

            print(f"[GOTO-SERVICE] SUCCESS: {len(chart_data)} candles loaded for {target_date}")

            # AUTO-SAVE: Zeit persistieren für Neustart
            try:
                actual_date_obj = goto_result.get('actual_date')
                if actual_date_obj:
                    saved_time = actual_date_obj.isoformat() if hasattr(actual_date_obj, 'isoformat') else str(actual_date_obj)
                    config_service.update_time_config(initial_go_to_date=saved_time)
                    print(f"[GOTO-PERSISTENCE] Time saved: {saved_time}")
                else:
                    print(f"[GOTO-PERSISTENCE] WARNING: No actual_date in goto_result")
            except Exception as persist_error:
                print(f"[GOTO-PERSISTENCE] WARNING: Could not save time: {persist_error}")

            return {
                "status": "success",
                "message": f"Go To Date: {target_date}",
                "data": chart_data,
                "count": len(chart_data),
                "target_date": target_date,
                "actual_date": saved_time,
                "system": "navigation_service"
            }
        except Exception as e:
            print(f"[ERROR] Go To Date Fehler: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Go To Date Fehler: {str(e)}"}


    # Reset Time Persistence - Zurück zum Datenende
    @router.post("/reset_time")
    async def debug_reset_time():
        """Löscht gespeicherte Zeit und kehrt zum Datenende zurück"""
        try:
            # Lösche gespeicherte Zeit aus Config
            config_service.update_time_config(initial_go_to_date=None)
            print(f"[RESET-TIME] Persistence cleared - zurück zum Datenende")

            # Lade letzte verfügbare Daten
            from datetime import datetime
            current_timeframe = manager.chart_state['interval']

            # NavigationService verwendet das Datenende als Default
            goto_result = navigation_service.go_to_date(
                target_date=datetime(2024, 12, 31),  # Datenende
                timeframe=current_timeframe,
                visible_candles=200
            )

            if goto_result['success']:
                chart_data = goto_result['chart_data']
                manager.chart_state['data'] = chart_data

                # Broadcast Update
                await manager.broadcast({
                    'type': 'go_to_date_complete',
                    'data': chart_data,
                    'date': '2024-12-31',
                    'actual_date': goto_result['actual_date'].isoformat()
                })

                return {
                    "status": "success",
                    "message": "Zeit zurückgesetzt - am Datenende",
                    "actual_date": goto_result['actual_date'].isoformat()
                }
            else:
                return {"status": "error", "message": "Fehler beim Zurücksetzen"}

        except Exception as e:
            print(f"[ERROR] Reset Time Fehler: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Reset Fehler: {str(e)}"}


    # REFACTOR PHASE 4: Set Speed (bereits auf DebugService migriert)
    @router.post("/set_speed")
    async def debug_set_speed(speed_data: dict):
        """Set Speed über DebugService"""
        try:
            speed = speed_data.get("speed", 2)
            result = debug_service.set_speed(speed)

            await manager.broadcast({
                'type': 'debug_speed_changed',
                'speed': result['speed'],
                'debug_state': debug_controller.get_state()
            })

            return {
                "status": "success",
                "message": f"Geschwindigkeit auf {result['speed']}x gesetzt",
                "system": "debug_service"
            }
        except Exception as e:
            print(f"Fehler beim Setzen der Geschwindigkeit: {e}")
            return {"status": "error", "message": str(e)}


    # REFACTOR PHASE 4: Toggle Play (bereits auf DebugService migriert)
    @router.post("/toggle_play")
    async def debug_toggle_play():
        """Toggle Play über DebugService"""
        try:
            result = debug_service.toggle_play_mode()

            await manager.broadcast({
                'type': 'debug_play_toggled',
                'play_mode': result['play_mode']
            })

            return {
                "status": "success",
                "message": f"Play-Modus {'aktiviert' if result['play_mode'] else 'deaktiviert'}",
                "play_mode": result['play_mode'],
                "system": "debug_service"
            }
        except Exception as e:
            print(f"Fehler beim Toggle Play/Pause: {e}")
            return {"status": "error", "message": str(e)}


    # REFACTOR PHASE 4: Get State (bereits auf DebugService migriert)
    @router.get("/state")
    async def debug_get_state():
        """Debug State über DebugService"""
        try:
            state = debug_service.get_debug_state()
            # Flache Response - nicht verschachtelt!
            return {
                "status": "success",
                **state,  # Spread state fields direkt in response
                "system": "debug_service"
            }
        except Exception as e:
            print(f"Fehler beim Holen des Debug-Status: {e}")
            return {"status": "error", "message": str(e)}


    # Simple Debug-Log Endpoint (kein Service nötig)
    @router.post("/log")
    async def debug_log_from_client(request: Request):
        """JavaScript Debug-Logs im Terminal"""
        try:
            data = await request.json()
            log_message = data.get('message', '')
            log_level = data.get('level', 'info')

            prefix = {
                'error': '[JS-ERROR]',
                'warn': '[JS-WARN]',
                'info': '[JS-INFO]',
                'debug': '[JS-DEBUG]'
            }.get(log_level, '[JS-LOG]')

            print(f"{prefix} {log_message}")

            return {"status": "success", "message": "Log received"}
        except Exception as e:
            print(f"Fehler beim JavaScript Debug-Log: {e}")
            return {"status": "error", "message": str(e)}


    # Registriere Router an App
    app.include_router(router)

    print("[PHASE 5] Debug-Router registriert ✅")
