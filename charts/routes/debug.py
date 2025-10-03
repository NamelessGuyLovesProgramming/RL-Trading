"""
Debug Routes - API Endpoints für Debug-Funktionen
REFACTOR PHASE 5: Extrahiert aus chart_server.py
"""

from fastapi import APIRouter, Request
from typing import Dict, Any

# Router-Instanz
router = APIRouter(prefix="/api/debug", tags=["debug"])


def setup_debug_routes(app, debug_service, navigation_service,
                       unified_time_manager, manager, debug_controller):
    """
    Registriert Debug-Routes am FastAPI App

    Args:
        app: FastAPI App-Instanz
        debug_service: DebugService-Instanz
        navigation_service: NavigationService-Instanz
        unified_time_manager: UnifiedTimeManager-Instanz
        manager: WebSocketManager-Instanz
        debug_controller: DebugController-Instanz
    """

    # REFACTOR PHASE 4: Skip-Endpoint (bereits auf NavigationService migriert)
    @router.post("/skip")
    async def debug_skip():
        """Skip-Operation über NavigationService"""
        global global_skip_events, debug_control_timeframe

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

            # Legacy compatibility
            from charts.core import UniversalSkipRenderer
            universal_renderer = UniversalSkipRenderer()
            skip_event = universal_renderer.create_skip_event(candle, skip_timeframe)

            if hasattr(manager, 'chart_state') and 'data' in manager.chart_state:
                manager.chart_state['data'].append(candle)

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
        global global_skip_events, debug_control_timeframe

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
            return {
                "status": "success",
                "debug_state": state,
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
