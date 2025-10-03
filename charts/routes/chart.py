"""
Chart Routes - API Endpoints für Chart-Operationen
REFACTOR PHASE 5: Extrahiert aus chart_server.py
"""

from fastapi import APIRouter, Request
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

# Router-Instanz
router = APIRouter(prefix="/api/chart", tags=["chart"])


def setup_chart_routes(app, timeframe_service, manager, chart_lifecycle_manager,
                       unified_time_manager, data_validator, timeframe_data_repository,
                       DataIntegrityGuard, global_skip_events, universal_renderer):
    """
    Registriert Chart-Routes am FastAPI App

    Args:
        app: FastAPI App-Instanz
        timeframe_service: TimeframeService-Instanz
        manager: WebSocketManager-Instanz
        chart_lifecycle_manager: ChartSeriesLifecycleManager-Instanz
        unified_time_manager: UnifiedTimeManager-Instanz
        data_validator: ChartDataValidator-Instanz
        timeframe_data_repository: TimeframeDataRepository-Instanz
        DataIntegrityGuard: DataIntegrityGuard-Klasse
        global_skip_events: Global skip events list
        universal_renderer: UniversalSkipRenderer-Instanz
    """

    # REFACTOR PHASE 4: Timeframe-Switch (bereits auf TimeframeService migriert)
    @router.post("/change_timeframe")
    async def change_timeframe(request: Request):
        """Timeframe-Switch über TimeframeService"""

        transaction_id = f"tf_transition_{int(datetime.now().timestamp())}"
        print(f"[TF-SERVICE] Starting transaction {transaction_id}")

        try:
            data = await request.json()
            target_timeframe = data.get('timeframe', '5m')
            visible_candles = data.get('visible_candles', 200)
            current_timeframe = manager.chart_state.get('interval', '5m')

            print(f"[TF-SERVICE] Switching: {current_timeframe} -> {target_timeframe}")

            # PHASE 1: Chart Series Lifecycle
            transition_plan = chart_lifecycle_manager.prepare_timeframe_transition(
                current_timeframe, target_timeframe
            )

            if transition_plan['needs_recreation']:
                recreation_command = chart_lifecycle_manager.get_chart_recreation_command()
                print(f"[TF-SERVICE] Chart recreation: {recreation_command}")

                await manager.broadcast({
                    'type': 'chart_series_recreation',
                    'command': recreation_command,
                    'reason': transition_plan['reason'],
                    'transaction_id': transaction_id
                })
                await asyncio.sleep(0.1)

            # PHASE 2: Nutze TimeframeService
            switch_result = timeframe_service.switch_timeframe(
                from_timeframe=current_timeframe,
                to_timeframe=target_timeframe,
                visible_candles=visible_candles
            )

            chart_data = switch_result['chart_data']

            if not chart_data:
                chart_lifecycle_manager.complete_timeframe_transition(success=False)
                return {
                    "status": "error",
                    "message": f"Keine Daten für {target_timeframe} verfügbar",
                    "transaction_id": transaction_id
                }

            # PHASE 3: Skip Events Integration
            print(f"[TF-SERVICE] Integrating {len(global_skip_events)} skip events")

            if global_skip_events:
                skip_candles = universal_renderer.render_skip_candles_for_timeframe(target_timeframe)

                if skip_candles:
                    skip_candles_dict = {c['time']: c for c in skip_candles}
                    deduplicated_skip_candles = list(skip_candles_dict.values())

                    merged_data = []
                    skip_timestamps = {c['time'] for c in deduplicated_skip_candles}

                    for csv_candle in chart_data:
                        if csv_candle['time'] not in skip_timestamps:
                            merged_data.append(csv_candle)

                    merged_data.extend(deduplicated_skip_candles)
                    merged_data.sort(key=lambda x: x['time'])

                    chart_data = merged_data
                    print(f"[TF-SERVICE] Merged: {len(chart_data)} candles ({len(skip_candles)} skip)")

            # PHASE 4: Validation
            validated_data = DataIntegrityGuard.sanitize_chart_data(
                chart_data, source=f"tf_service_{target_timeframe}"
            )

            final_validated_data = data_validator.validate_chart_data(
                validated_data, timeframe=target_timeframe,
                source=f"change_timeframe_{target_timeframe}"
            )

            print(f"[TF-SERVICE] Validated: {len(chart_data)} -> {len(final_validated_data)} candles")

            # PHASE 5: Chart State Update
            manager.chart_state['data'] = final_validated_data
            manager.chart_state['interval'] = target_timeframe

            if final_validated_data:
                last_candle = final_validated_data[-1]
                unified_time_manager.register_timeframe_activity(
                    target_timeframe, last_candle['time']
                )

            # PHASE 6: WebSocket Broadcast
            current_global_time = unified_time_manager.get_current_time()

            bulletproof_message = {
                'type': 'bulletproof_timeframe_changed',
                'timeframe': target_timeframe,
                'data': final_validated_data,
                'transaction_id': transaction_id,
                'chart_recreation': transition_plan['needs_recreation'],
                'recreation_command': chart_lifecycle_manager.get_chart_recreation_command()
                    if transition_plan['needs_recreation'] else None,
                'global_time': current_global_time.isoformat() if current_global_time else None,
                'validation_summary': {
                    'original_count': len(chart_data),
                    'validated_count': len(final_validated_data),
                    'data_source': 'timeframe_service',
                    'skip_contamination': 'CLEAN'
                }
            }

            try:
                await manager.broadcast(bulletproof_message)
            except Exception as broadcast_error:
                print(f"[TF-SERVICE] Broadcast error: {broadcast_error}")
                await manager.broadcast({
                    'type': 'emergency_chart_reload',
                    'timeframe': target_timeframe,
                    'data': final_validated_data,
                    'transaction_id': transaction_id
                })

            chart_lifecycle_manager.complete_timeframe_transition(success=True)

            print(f"[TF-SERVICE] SUCCESS: Transaction {transaction_id} completed")

            return {
                "status": "success",
                "message": f"Timeframe-Switch: {current_timeframe} -> {target_timeframe}",
                "data": final_validated_data,
                "timeframe": target_timeframe,
                "count": len(final_validated_data),
                "transaction_id": transaction_id,
                "transition_plan": transition_plan,
                "global_time": current_global_time.isoformat() if current_global_time else None,
                "system": "timeframe_service"
            }

        except Exception as e:
            print(f"[TF-SERVICE] ERROR in transaction {transaction_id}: {str(e)}")
            import traceback
            traceback.print_exc()

            chart_lifecycle_manager.complete_timeframe_transition(success=False)
            chart_lifecycle_manager.mark_chart_corrupted(f"transition_error: {str(e)}")

            try:
                await manager.broadcast({
                    'type': 'emergency_recovery_required',
                    'transaction_id': transaction_id,
                    'error': str(e),
                    'recovery_action': 'page_reload'
                })
            except:
                pass

            return {
                "status": "error",
                "message": f"Timeframe-Switch failed: {str(e)}",
                "transaction_id": transaction_id,
                "recovery_required": True,
                "system": "timeframe_service"
            }


    # Position-Endpoints (einfach, kein Service nötig)
    @router.post("/add_position")
    async def add_position(position_data: dict):
        """Position Overlay hinzufügen"""
        position = position_data.get('position')
        if not position:
            return {"status": "error", "message": "No position data provided"}

        manager.update_chart_state({
            'type': 'add_position',
            'position': position
        })

        await manager.broadcast({
            'type': 'add_position',
            'position': position
        })

        return {"status": "success", "message": "Position overlay added"}


    @router.post("/remove_position")
    async def remove_position(position_data: dict):
        """Position Overlay entfernen"""
        position_id = position_data.get('position_id')
        if not position_id:
            return {"status": "error", "message": "No position_id provided"}

        manager.update_chart_state({
            'type': 'remove_position',
            'position_id': position_id
        })

        await manager.broadcast({
            'type': 'remove_position',
            'position_id': position_id
        })

        return {"status": "success", "message": "Position overlay removed"}


    @router.post("/sync_positions")
    async def sync_positions(positions_data: dict):
        """Alle Positionen synchronisieren"""
        positions = positions_data.get('positions', [])

        manager.chart_state['positions'] = positions

        await manager.broadcast({
            'type': 'positions_sync',
            'positions': positions
        })

        return {"status": "success", "message": f"Synchronized {len(positions)} positions"}


    # Info-Endpoints
    @router.get("/status")
    async def get_chart_status():
        """Chart-Status abrufen"""
        return {
            "status": "success",
            "chart_state": {
                "interval": manager.chart_state.get('interval', 'unknown'),
                "data_count": len(manager.chart_state.get('data', [])),
                "positions_count": len(manager.chart_state.get('positions', []))
            }
        }


    @router.get("/data")
    async def get_chart_data():
        """Aktuelle Chart-Daten abrufen"""
        return {
            "status": "success",
            "data": manager.chart_state.get('data', []),
            "interval": manager.chart_state.get('interval', '5m'),
            "count": len(manager.chart_state.get('data', []))
        }


    # Registriere Router an App
    app.include_router(router)

    print("[PHASE 5] Chart-Router registriert ✅")
