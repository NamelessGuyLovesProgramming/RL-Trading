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
    account_service,
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


            elif command_type == 'execute_trade':
                try:
                    # Trade-Daten vom Client
                    trade_data = data.get('trade')
                    if not trade_data:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'No trade data provided'
                        })
                        continue

                    # Extrahiere Trade-Details
                    entry_price = trade_data.get('entryPrice')
                    stop_loss = trade_data.get('stopLoss')
                    take_profit = trade_data.get('takeProfit')
                    direction = 'short' if trade_data.get('isShort', False) else 'long'
                    position_size = trade_data.get('positionSize', 1.0)
                    risk_eur = trade_data.get('riskEUR', 100.0)
                    is_rl_online = trade_data.get('isRLOnline', False)

                    # Validiere Trade-Daten
                    if not all([entry_price, stop_loss, take_profit]):
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Incomplete trade data (entry, stop_loss, take_profit required)'
                        })
                        continue

                    # Erstelle Position mit PositionService
                    position_result = position_service.create_position(
                        entry_price=entry_price,
                        sl_price=stop_loss,
                        tp_price=take_profit,
                        direction=direction,
                        size=position_size,
                        symbol='NQ'
                    )

                    if not position_result['success']:
                        error_msg = f"Position creation failed: {position_result.get('error', 'Unknown error')}"
                        logger.error(f"[WS] {error_msg}")
                        logger.error(f"[WS] Trade data: Entry={entry_price}, SL={stop_loss}, TP={take_profit}, Direction={direction}")
                        await websocket.send_json({
                            'type': 'error',
                            'message': error_msg
                        })
                        continue

                    position_id = position_result['position_id']
                    position_data = position_result['position_data']

                    # Füge Position-ID hinzu
                    position_data['id'] = position_id

                    # Registriere Trade im Account (RL-KI oder Nutzer)
                    account_result = account_service.execute_trade(
                        position_data=position_data,
                        is_rl_online=is_rl_online
                    )

                    if not account_result['success']:
                        await websocket.send_json({
                            'type': 'error',
                            'message': f"Account execution failed: {account_result.get('error', 'Unknown error')}"
                        })
                        continue

                    account_type = account_result['account_type']
                    account_summary = account_result['account_summary']

                    logger.info(f"[WS] Preparing broadcasts for trade {position_id}...")

                    # Broadcast Trade Execution zu allen Clients
                    logger.info(f"[WS] Broadcasting trade_executed...")
                    await manager.broadcast({
                        'type': 'trade_executed',
                        'position': position_data,
                        'position_id': position_id,
                        'account_type': account_type,
                        'account_summary': account_summary,
                        'execution_time': datetime.now().isoformat()
                    })
                    logger.info(f"[WS] trade_executed broadcast complete")

                    # Broadcast Account Update
                    logger.info(f"[WS] Broadcasting account_update...")
                    all_accounts = account_service.get_all_accounts_summary()
                    await manager.broadcast({
                        'type': 'account_update',
                        'accounts': all_accounts
                    })
                    logger.info(f"[WS] account_update broadcast complete")

                    logger.info(f"[WS] Trade executed: {position_id} on {account_type} account")
                    logger.info(f"[WS] Direction: {direction}, Entry: {entry_price}, Size: {position_size}")

                except Exception as e:
                    logger.error(f"[WS] Execute trade error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Execute trade failed: {str(e)}'
                    })


            elif command_type == 'close_position':
                try:
                    # Position ID vom Client
                    position_id = data.get('position_id')
                    if not position_id:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'No position_id provided'
                        })
                        continue

                    # Finde aktuelle Position
                    active_positions = account_service.get_active_positions()
                    position = next((p for p in active_positions if p.get('id') == position_id), None)

                    if not position:
                        await websocket.send_json({
                            'type': 'error',
                            'message': f'Position {position_id} not found'
                        })
                        continue

                    # Aktuellen Preis vom Unified Time Manager holen
                    current_time = unified_time_manager.get_current_time()
                    current_candle = manager.chart_state.get('data', [])[-1] if manager.chart_state.get('data') else None

                    if not current_candle:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'No current price available'
                        })
                        continue

                    close_price = current_candle['close']
                    account_type = position.get('account_type', 'user')

                    # Position schließen
                    close_result = account_service.close_position(
                        position_id=position_id,
                        close_price=close_price,
                        close_reason='manual',
                        account_type=account_type
                    )

                    if not close_result['success']:
                        await websocket.send_json({
                            'type': 'error',
                            'message': f"Position close failed: {close_result.get('error', 'Unknown error')}"
                        })
                        continue

                    realized_pnl = close_result['realized_pnl']
                    account_summary = close_result['account_summary']

                    logger.info(f"[WS] Position manually closed: {position_id}")
                    logger.info(f"[WS] Close price: {close_price}, Realized PnL: {realized_pnl:+.2f}€")

                    # Broadcast Position Closure
                    await manager.broadcast({
                        'type': 'position_closed',
                        'position_id': position_id,
                        'close_price': close_price,
                        'close_reason': 'manual',
                        'realized_pnl': realized_pnl,
                        'account_type': account_type,
                        'close_time': datetime.now().isoformat()
                    })

                    # Broadcast Account Update
                    all_accounts = account_service.get_all_accounts_summary()
                    await manager.broadcast({
                        'type': 'account_update',
                        'accounts': all_accounts
                    })

                    logger.info(f"[WS] Manual close broadcasted for position {position_id}")

                except Exception as e:
                    logger.error(f"[WS] Close position error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Close position failed: {str(e)}'
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

                    # 💰 Update Position PnL & Check SL/TP
                    current_price = candle['close']
                    candle_high = candle['high']
                    candle_low = candle['low']

                    active_positions = account_service.get_active_positions()
                    logger.info(f"[WS SKIP] Active positions: {len(active_positions)}")

                    positions_to_close = []

                    for position in active_positions:
                        position_id = position['id']
                        account_type = position.get('account_type', 'user')
                        direction = position['direction']
                        entry = position['entry_price']
                        sl = position['sl_price']
                        tp = position['tp_price']

                        logger.info(f"[WS SKIP] Checking position {position_id}: {direction}, Entry={entry}, SL={sl}, TP={tp}")
                        logger.info(f"[WS SKIP] Candle: High={candle_high}, Low={candle_low}, Close={current_price}")

                        # Update unrealized PnL
                        account_service.update_position_pnl(position_id, current_price, account_type)

                        # ⭐ BUGFIX: Check SL/TP using High/Low, not just Close!
                        # SL/TP werden getriggert wenn Candle sie berührt (High/Low)
                        # Close Price wird verwendet für PnL Berechnung

                        sl_hit = False
                        tp_hit = False

                        if direction == 'long':
                            # Long SL: Wird getriggert wenn Low <= SL
                            if candle_low <= sl:
                                sl_hit = True
                                logger.info(f"[WS SKIP] 🔴 SL HIT! Long position {position_id}: Low={candle_low} <= SL={sl}")
                            # Long TP: Wird getriggert wenn High >= TP
                            elif candle_high >= tp:
                                tp_hit = True
                                logger.info(f"[WS SKIP] 🟢 TP HIT! Long position {position_id}: High={candle_high} >= TP={tp}")
                        else:  # short
                            # Short SL: Wird getriggert wenn High >= SL
                            if candle_high >= sl:
                                sl_hit = True
                                logger.info(f"[WS SKIP] 🔴 SL HIT! Short position {position_id}: High={candle_high} >= SL={sl}")
                            # Short TP: Wird getriggert wenn Low <= TP
                            elif candle_low <= tp:
                                tp_hit = True
                                logger.info(f"[WS SKIP] 🟢 TP HIT! Short position {position_id}: Low={candle_low} <= TP={tp}")

                        if sl_hit:
                            # ⭐ EXAKTES RISK-MANAGEMENT: Schließe bei SL zum SL-Preis, nicht Close!
                            positions_to_close.append((position_id, sl, 'stop_loss', account_type))
                        elif tp_hit:
                            # ⭐ EXAKTES RISK-MANAGEMENT: Schließe bei TP zum TP-Preis, nicht Close!
                            positions_to_close.append((position_id, tp, 'take_profit', account_type))

                    # Close positions that hit SL/TP
                    for position_id, close_price, reason, account_type in positions_to_close:
                        close_result = account_service.close_position(position_id, close_price, reason, account_type)
                        if close_result['success']:
                            logger.info(f"[WS] Position closed: {position_id} - {reason} at {close_price}")

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
                    all_accounts = account_service.get_all_accounts_summary()
                    await manager.broadcast({
                        'type': 'account_update',
                        'accounts': all_accounts
                    })

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
