"""
WebSocket Command Handler - Zentrale WebSocket-Logic
REFACTOR PHASE 5: Bidirectional WebSocket Communication

Empfängt WebSocket-Commands vom Client und nutzt Services für Logic
"""

from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def handle_websocket_commands(
    websocket: WebSocket,
    manager,
    chart_service,
    timeframe_service,
    navigation_service,
    debug_service,
    position_service,
    unified_time_manager,
    chart_lifecycle_manager,
    data_validator,
    DataIntegrityGuard,
    global_skip_events,
    universal_renderer,
    debug_control_timeframe
):
    """
    WebSocket Command Handler mit Service-Integration

    Args:
        websocket: WebSocket-Verbindung
        manager: WebSocketManager für Broadcasts
        *_service: Service-Instanzen für Business Logic
        unified_time_manager: Time Manager
        chart_lifecycle_manager: Chart Lifecycle Manager
        data_validator: Data Validator
        DataIntegrityGuard: Data Guard Klasse
        global_skip_events: Global Skip Events Liste
        universal_renderer: Skip Renderer
        debug_control_timeframe: Debug Timeframe Reference
    """

    await manager.connect(websocket)
    logger.info("[WS] Client connected")

    try:
        while True:
            # Empfange JSON-Daten vom Client
            data = await websocket.receive_json()
            command_type = data.get('type', '')

            logger.info(f"[WS] Received command: {command_type}")

            # ========== CHART COMMANDS ==========

            if command_type == 'timeframe_change':
                try:
                    target_timeframe = data.get('timeframe', '5m')
                    visible_candles = data.get('visible_candles', 200)
                    current_timeframe = manager.chart_state.get('interval', '5m')

                    transaction_id = f"ws_tf_{int(datetime.now().timestamp())}"

                    # Chart Lifecycle: Prepare Transition
                    transition_plan = chart_lifecycle_manager.prepare_timeframe_transition(
                        current_timeframe, target_timeframe
                    )

                    if transition_plan['needs_recreation']:
                        recreation_command = chart_lifecycle_manager.get_chart_recreation_command()

                        await manager.broadcast({
                            'type': 'chart_series_recreation',
                            'command': recreation_command,
                            'reason': transition_plan['reason'],
                            'transaction_id': transaction_id
                        })

                        import asyncio
                        await asyncio.sleep(0.1)

                    # Service: Switch Timeframe
                    switch_result = timeframe_service.switch_timeframe(
                        from_timeframe=current_timeframe,
                        to_timeframe=target_timeframe,
                        visible_candles=visible_candles
                    )

                    chart_data = switch_result['chart_data']

                    if not chart_data:
                        await websocket.send_json({
                            'type': 'error',
                            'message': f'Keine Daten für {target_timeframe} verfügbar',
                            'transaction_id': transaction_id
                        })
                        continue

                    # Skip Events Integration
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

                    # Validation
                    validated_data = DataIntegrityGuard.sanitize_chart_data(
                        chart_data, source=f"ws_tf_{target_timeframe}"
                    )

                    final_validated_data = data_validator.validate_chart_data(
                        validated_data, timeframe=target_timeframe,
                        source=f"ws_timeframe_change_{target_timeframe}"
                    )

                    # Update State
                    manager.chart_state['data'] = final_validated_data
                    manager.chart_state['interval'] = target_timeframe

                    if final_validated_data:
                        last_candle = final_validated_data[-1]
                        unified_time_manager.register_timeframe_activity(
                            target_timeframe, last_candle['time']
                        )

                    # Broadcast to all clients
                    current_global_time = unified_time_manager.get_current_time()

                    await manager.broadcast({
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
                            'data_source': 'timeframe_service_ws',
                            'skip_contamination': 'CLEAN'
                        }
                    })

                    chart_lifecycle_manager.complete_timeframe_transition(success=True)

                    logger.info(f"[WS] Timeframe changed: {current_timeframe} -> {target_timeframe}")

                except Exception as e:
                    logger.error(f"[WS] Timeframe change error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Timeframe-Switch failed: {str(e)}'
                    })


            elif command_type == 'add_position':
                try:
                    position = data.get('position')
                    if not position:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'No position data provided'
                        })
                        continue

                    manager.update_chart_state({
                        'type': 'add_position',
                        'position': position
                    })

                    await manager.broadcast({
                        'type': 'add_position',
                        'position': position
                    })

                    logger.info(f"[WS] Position added")

                except Exception as e:
                    logger.error(f"[WS] Add position error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Add position failed: {str(e)}'
                    })


            elif command_type == 'remove_position':
                try:
                    position_id = data.get('position_id')
                    if not position_id:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'No position_id provided'
                        })
                        continue

                    manager.update_chart_state({
                        'type': 'remove_position',
                        'position_id': position_id
                    })

                    await manager.broadcast({
                        'type': 'remove_position',
                        'position_id': position_id
                    })

                    logger.info(f"[WS] Position removed: {position_id}")

                except Exception as e:
                    logger.error(f"[WS] Remove position error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Remove position failed: {str(e)}'
                    })


            # ========== DEBUG COMMANDS ==========

            elif command_type == 'skip':
                try:
                    skip_timeframe = debug_control_timeframe

                    skip_result = navigation_service.skip_forward(skip_timeframe)

                    if not skip_result['success']:
                        await websocket.send_json({
                            'type': 'error',
                            'message': skip_result.get('error', 'Skip fehlgeschlagen')
                        })
                        continue

                    candle = skip_result['candle']
                    candle_type = skip_result['candle_type']
                    new_global_time = unified_time_manager.get_current_time()

                    # Update chart state
                    if hasattr(manager, 'chart_state') and 'data' in manager.chart_state:
                        manager.chart_state['data'].append(candle)

                    sync_status = unified_time_manager.get_timeframe_sync_status()

                    await manager.broadcast({
                        'type': 'unified_skip_event',
                        'candle': candle,
                        'candle_type': candle_type,
                        'debug_time': new_global_time.isoformat(),
                        'timeframe': skip_timeframe,
                        'system_type': 'navigation_service_ws',
                        'sync_status': sync_status,
                        'global_time': new_global_time.isoformat()
                    })

                    logger.info(f"[WS] Skip forward: {skip_timeframe}")

                except Exception as e:
                    logger.error(f"[WS] Skip error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Skip failed: {str(e)}'
                    })


            elif command_type == 'go_to_date':
                try:
                    target_date = data.get('date')
                    if not target_date:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Kein Datum angegeben'
                        })
                        continue

                    target_datetime = datetime.strptime(target_date, "%Y-%m-%d")
                    current_timeframe = manager.chart_state['interval']

                    goto_result = navigation_service.go_to_date(
                        target_date=target_datetime,
                        timeframe=current_timeframe,
                        visible_candles=200
                    )

                    if not goto_result['success']:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Keine Daten verfügbar',
                            'target_date': target_date
                        })
                        continue

                    chart_data = goto_result['chart_data']

                    # Clear global skip events
                    skip_events_count = len(global_skip_events)
                    global_skip_events.clear()
                    logger.info(f"[WS] Global Skip Events cleared: {skip_events_count} events")

                    manager.chart_state['data'] = chart_data
                    manager.chart_state['interval'] = current_timeframe

                    chart_lifecycle_manager.reset_to_clean_state()

                    await manager.broadcast({
                        'type': 'debug_control_timeframe_changed',
                        'debug_control_timeframe': debug_control_timeframe,
                        'old_timeframe': None,
                        'source': 'go_to_date_sync_ws'
                    })

                    await manager.broadcast({
                        'type': 'go_to_date_complete',
                        'data': chart_data,
                        'date': target_date,
                        'actual_date': goto_result['actual_date'].isoformat()
                    })

                    logger.info(f"[WS] Go to date: {target_date}")

                except Exception as e:
                    logger.error(f"[WS] Go to date error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Go to date failed: {str(e)}'
                    })


            elif command_type == 'set_speed':
                try:
                    speed = data.get('speed', 2)
                    result = debug_service.set_speed(speed)

                    await manager.broadcast({
                        'type': 'debug_speed_changed',
                        'speed': result['speed']
                    })

                    logger.info(f"[WS] Speed changed: {result['speed']}x")

                except Exception as e:
                    logger.error(f"[WS] Set speed error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Set speed failed: {str(e)}'
                    })


            elif command_type == 'toggle_play':
                try:
                    result = debug_service.toggle_play_mode()

                    await manager.broadcast({
                        'type': 'debug_play_toggled',
                        'play_mode': result['play_mode']
                    })

                    logger.info(f"[WS] Play mode: {result['play_mode']}")

                except Exception as e:
                    logger.error(f"[WS] Toggle play error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Toggle play failed: {str(e)}'
                    })


            elif command_type == 'get_debug_state':
                try:
                    state = debug_service.get_debug_state()

                    await websocket.send_json({
                        'type': 'debug_state',
                        'state': state
                    })

                except Exception as e:
                    logger.error(f"[WS] Get debug state error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Get debug state failed: {str(e)}'
                    })


            elif command_type == 'get_chart_data':
                try:
                    await websocket.send_json({
                        'type': 'chart_data',
                        'data': manager.chart_state.get('data', []),
                        'interval': manager.chart_state.get('interval', '5m'),
                        'count': len(manager.chart_state.get('data', []))
                    })

                except Exception as e:
                    logger.error(f"[WS] Get chart data error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Get chart data failed: {str(e)}'
                    })


            # ========== CLIENT LOG COMMAND ==========

            elif command_type == 'client_log':
                try:
                    log_message = data.get('message', '')
                    log_level = data.get('level', 'info')

                    prefix = {
                        'error': '[JS-ERROR]',
                        'warn': '[JS-WARN]',
                        'info': '[JS-INFO]',
                        'debug': '[JS-DEBUG]'
                    }.get(log_level, '[JS-LOG]')

                    logger.info(f"{prefix} {log_message}")

                except Exception as e:
                    logger.error(f"[WS] Client log error: {e}")


            # ========== UNKNOWN COMMAND ==========

            else:
                logger.warning(f"[WS] Unknown command: {command_type}")
                await websocket.send_json({
                    'type': 'error',
                    'message': f'Unknown command: {command_type}'
                })


    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("[WS] Client disconnected")

    except Exception as e:
        logger.error(f"[WS] Unexpected error: {e}")
        try:
            manager.disconnect(websocket)
        except:
            pass
