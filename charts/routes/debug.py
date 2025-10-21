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
                       global_skip_events, debug_control_timeframe, account_service):
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
    """

    # REFACTOR PHASE 4: Skip-Endpoint (bereits auf NavigationService migriert)
    @router.post("/skip")
    async def debug_skip():
        """Skip-Operation über NavigationService"""
        # Variables passed as closure from setup_debug_routes
        try:
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

            # Broadcast updated accounts after PnL updates
            if active_positions:  # Nur wenn Positionen existieren
                all_accounts = account_service.get_all_accounts_summary()
                await manager.broadcast({
                    'type': 'account_update',
                    'accounts': all_accounts
                })

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

            await manager.broadcast({
                'type': 'go_to_date_complete',
                'data': chart_data,
                'date': target_date,
                'actual_date': goto_result['actual_date'].isoformat()
            })

            print(f"[GOTO-SERVICE] SUCCESS: {len(chart_data)} candles loaded for {target_date}")

            return {
                "status": "success",
                "message": f"Go To Date: {target_date}",
                "data": chart_data,
                "count": len(chart_data),
                "target_date": target_date,
                "actual_date": goto_result['actual_date'].isoformat(),
                "system": "navigation_service"
            }
        except Exception as e:
            print(f"[ERROR] Go To Date Fehler: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"Go To Date Fehler: {str(e)}"}


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
