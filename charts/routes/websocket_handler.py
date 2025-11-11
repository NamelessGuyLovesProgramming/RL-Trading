"""
WebSocket Command Handler - Zentrale WebSocket-Logic
REFACTOR PHASE 5: Bidirectional WebSocket Communication

Empfängt WebSocket-Commands vom Client und nutzt Services für Logic
"""

from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import json
import logging
from typing import Optional, Dict, Any
import pandas as pd

# Feature Extraction für RL Context (NEW: 17 Features)
from charts.core.market_context_extractor import MarketContextExtractor, calculate_trade_features

logger = logging.getLogger(__name__)

# Initialize Market Context Extractor
market_context_extractor = MarketContextExtractor()


def _extract_market_context_features(data_loader, entry_time: str, entry_price: float,
                                     sl_price: float, tp_price: float) -> Dict[str, float]:
    """
    Extrahiert Market-Context Features (10-16) zum Entry-Zeitpunkt

    Args:
        data_loader: DataLoader instance mit OHLC-Daten
        entry_time: Entry Timestamp (ISO string)
        entry_price: Entry Preis
        sl_price: Stop Loss Preis
        tp_price: Take Profit Preis

    Returns:
        Dictionary mit 7 Market-Context Features
    """
    try:
        # Hole DataFrame
        df = data_loader.df.copy()

        # Konvertiere zu lowercase wenn nötig
        if 'Open' in df.columns:
            df.columns = df.columns.str.lower()

        # Ensure index is datetime
        if 'timestamp' not in df.index.names:
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
            else:
                # Use index as timestamp if available
                df.index = pd.to_datetime(df.index)

        # Find entry candle index
        entry_dt = pd.to_datetime(entry_time)
        time_diffs = (df.index - entry_dt).abs()
        entry_idx = time_diffs.argmin()

        logger.info(f"[FEATURES] Extracting market context at entry_idx={entry_idx}, time={entry_time}")

        # Extract market context features (7 features)
        features = market_context_extractor.extract_at_entry(
            df=df,
            entry_idx=entry_idx,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price
        )

        logger.info(f"[FEATURES] Extracted {len(features)} market context features")
        logger.debug(f"[FEATURES] Sample: EMA={features.get('distance_to_ema20_pct'):.2f}%, "
                    f"Volume={features.get('volume_ratio'):.2f}x, "
                    f"R:R={features.get('rr_ratio'):.2f}")

        return features

    except Exception as e:
        logger.error(f"[FEATURES] Error extracting market context: {e}", exc_info=True)
        return {
            'distance_to_ema20_pct': 0.0,
            'volume_ratio': 1.0,
            'atr_value': 0.0,
            'recent_high_distance_pct': 0.0,
            'recent_low_distance_pct': 0.0,
            'position_in_range': 0.5,
            'rr_ratio': 0.0
        }


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
    session_high_broken = False
    session_low_broken = False
    session_high_first_break = False
    session_low_first_break = False
    volume_spike = False
    volume_ratio = 1.0
    current_session = 'unknown'

    # Use indicator data if available (NEW field names)
    if indicator_data:
        logger.info(f"[WS] [AI-TRADING] Indicator Data received: {list(indicator_data.keys())}")
        in_fvg = indicator_data.get('in_fvg', False)
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
    else:
        logger.warning(f"[WS] [AI-TRADING] ⚠️ NO INDICATOR DATA - Using defaults!")

    market_context = {
        'current_price': candle['close'],
        'timestamp': timestamp,
        'patterns': {
            'in_fvg_zone': in_fvg,
            'fvg_distance': fvg_distance,
            'near_support_ob': False,
            'near_resistance_ob': False,
            'session_high_broken': session_high_broken,
            'session_low_broken': session_low_broken,
            'session_high_first_break': session_high_first_break,
            'session_low_first_break': session_low_first_break,
            'liquidity_direction': 0,
            'market_structure': 0
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

    # Log built context
    logger.info(f"[WS] [AI-TRADING] Market Context: in_fvg={in_fvg}, session={current_session}, volume_spike={volume_spike}")

    return market_context


async def handle_websocket_commands(
    websocket: WebSocket,
    manager,
    chart_service,
    timeframe_service,
    navigation_service,
    debug_service,
    position_service,
    account_service,
    config_service,
    unified_time_manager,
    chart_lifecycle_manager,
    data_validator,
    DataIntegrityGuard,
    global_skip_events,
    universal_renderer,
    debug_control_timeframe,
    feedback_system,
    training_service
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

                    # ⭐ BUGFIX: Limit Order PnL Sofortberechnung
                    # Bei Limit Orders: Position wird INNERHALB Kerze getriggert
                    # → Sofort P&L mit aktuellem Close-Preis berechnen statt auf nächsten Skip zu warten
                    order_type = trade_data.get('orderType', 'market')
                    if order_type == 'limit':
                        # Hole aktuellen Candle Close
                        current_candle = manager.chart_state.get('data', [])[-1] if manager.chart_state.get('data') else None
                        if current_candle:
                            current_price = current_candle['close']

                            # Berechne P&L sofort nach Trade Execution
                            pnl_update = account_service.update_position_pnl(position_id, current_price, account_type)

                            if pnl_update['success']:
                                unrealized_pnl = pnl_update['unrealized_pnl']
                                logger.info(f"[WS] 🎯 Limit Order P&L calculated immediately: {unrealized_pnl:+.2f}€")

                                # Update account_summary UND position_data mit neuen P&L Werten
                                account_summary = pnl_update['account_summary']
                                position_data['pnl'] = unrealized_pnl
                                position_data['unrealized_pnl'] = unrealized_pnl
                            else:
                                logger.warning(f"[WS] Could not calculate initial P&L for limit order: {pnl_update.get('error')}")

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

                    # Speichere Account State (inkl. neue Position) in Config
                    config_service.save_account_state(account_service.to_dict())

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

                    # Speichere Account State (Position wurde geschlossen) in Config
                    config_service.save_account_state(account_service.to_dict())

                    # Trigger Feedback Modal für User Trades (Demo Collection)
                    if account_type == 'user':
                        # Hole Position Details für Feedback Modal
                        position_data = close_result.get('closed_position', {})
                        await manager.broadcast({
                            'type': 'show_feedback_modal',
                            'trade_data': {
                                'trade_id': position_id,
                                'action': position_data.get('direction', 'unknown'),
                                'entry_price': position_data.get('entry_price', 0),
                                'sl_price': position_data.get('sl_price', 0),
                                'tp_price': position_data.get('tp_price', 0),
                                'close_price': close_price,
                                'realized_pnl': realized_pnl,
                                'source': 'user'
                            }
                        })
                        logger.info(f"[WS] Feedback modal triggered for user trade: {position_id}")

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

                            realized_pnl = close_result['realized_pnl']

                            # Broadcast position closure
                            await manager.broadcast({
                                'type': 'position_closed',
                                'position_id': position_id,
                                'close_price': close_price,
                                'close_reason': reason,
                                'realized_pnl': realized_pnl,
                                'account_type': account_type
                            })

                            # ⚡ FIX: Trigger Feedback Modal für User Trades bei SL/TP
                            if account_type == 'user':
                                position_data = close_result.get('closed_position', {})
                                await manager.broadcast({
                                    'type': 'show_feedback_modal',
                                    'trade_data': {
                                        'trade_id': position_id,
                                        'action': position_data.get('direction', 'unknown'),
                                        'entry_price': position_data.get('entry_price', 0),
                                        'sl_price': position_data.get('sl_price', 0),
                                        'tp_price': position_data.get('tp_price', 0),
                                        'close_price': close_price,
                                        'realized_pnl': realized_pnl,
                                        'source': 'user'
                                    }
                                })
                                logger.info(f"[WS] Feedback modal triggered for SL/TP close: {position_id} ({reason})")

                    # Broadcast updated accounts after PnL updates
                    all_accounts = account_service.get_all_accounts_summary()
                    await manager.broadcast({
                        'type': 'account_update',
                        'accounts': all_accounts
                    })

                    # ========== TRAINING MODE INTEGRATION ==========
                    # Wenn Training Mode aktiv: KI analysiert und tradet eventuell
                    if training_service and training_service.is_active:
                        try:
                            # Extract indicator data from WebSocket message (if available)
                            indicator_data = data.get('indicator_data', None)

                            # Build Market Context mit echten Indicator-Daten
                            market_context = _build_market_context(
                                candle=candle,
                                timestamp=int(new_global_time.timestamp()),
                                indicator_data=indicator_data
                            )

                            # KI trifft Entscheidung
                            ai_trade = training_service.on_skip(market_context)

                            if ai_trade:
                                # KI hat getrade! → Modal automatisch öffnen
                                logger.info(f"[WS] [AI-TRADE] {ai_trade['action'].upper()} @ ${ai_trade['position']['entry_price']:.2f}")

                                # Broadcast AI Trade Event mit Modal-Trigger
                                await manager.broadcast({
                                    'type': 'ai_trade_executed',
                                    'trade_id': ai_trade['trade_id'],
                                    'action': ai_trade['action'],
                                    'position': ai_trade['position'],
                                    'account_summary': ai_trade['account_summary'],
                                    'hints': ai_trade.get('hints', []),  # Optional - kommt beim Position Close
                                    'reasoning': ai_trade['reasoning'],
                                    'confidence': ai_trade['confidence'],
                                    'auto_open_modal': True  # ← Trigger für Frontend
                                })

                                # Update Account Summary nach AI Trade
                                all_accounts = account_service.get_all_accounts_summary()
                                await manager.broadcast({
                                    'type': 'account_update',
                                    'accounts': all_accounts
                                })

                        except Exception as e:
                            logger.error(f"[WS] Training Mode on_skip error: {e}")
                            import traceback
                            logger.error(traceback.format_exc())

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


            # ========== TRADE FEEDBACK COMMAND ==========

            elif command_type == 'trade_feedback':
                try:
                    if not feedback_system:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Feedback System nicht verfügbar'
                        })
                        continue

                    # Trade Feedback Daten vom Client
                    feedback_data = data.get('data')
                    if not feedback_data:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Keine Feedback-Daten übermittelt'
                        })
                        continue

                    trade_id = feedback_data.get('trade_id')
                    ratings = feedback_data.get('ratings', {})
                    notes = feedback_data.get('notes', '')
                    overall_score = feedback_data.get('overall_score', 0.0)

                    logger.info(f"[WS] Trade Feedback empfangen für {trade_id}")
                    logger.info(f"[WS] Ratings: {ratings}")
                    logger.info(f"[WS] Overall Score: {overall_score}")
                    logger.info(f"[WS] Notes: {notes[:50]}..." if len(notes) > 50 else f"[WS] Notes: {notes}")

                    # Konvertiere Ratings zu HumanEvaluation
                    from src.feedback_storage import HumanEvaluation

                    # Ratings sind bereits 0.0-1.0, müssen nicht konvertiert werden
                    human_eval = HumanEvaluation(
                        entry_timing=ratings.get('entry_timing', 0.0),
                        pattern_recognition=ratings.get('pattern_recognition', 0.0),
                        sl_placement=ratings.get('sl_placement', 0.0),
                        tp_placement=ratings.get('tp_placement', 0.0),
                        liquidity_sweeps=ratings.get('liquidity_sweeps', 0.0),
                        volume_analysis=ratings.get('volume_analysis', 0.0),
                        overall_score=overall_score,
                        notes=notes
                    )

                    # Hole Trade Position Details
                    # WICHTIG: Position könnte bereits geschlossen sein
                    # Feedback kann auch nach Trade-Close kommen
                    active_positions = account_service.get_active_positions()
                    position = next((p for p in active_positions if p.get('id') == trade_id), None)

                    if not position:
                        # Position bereits geschlossen oder nicht gefunden
                        # ⚡ FIX: Verwende Trade-Daten aus Feedback statt Dummy-Werte
                        logger.warning(f"[WS] Position {trade_id} nicht aktiv - verwende Daten aus Feedback")

                        # Extrahiere Trade-Daten aus Feedback (vom Frontend gesendet)
                        action = feedback_data.get('action', 'hold')
                        entry_price = feedback_data.get('entry_price', 0.0)
                        sl_price = feedback_data.get('sl_price', 0.0)
                        tp_price = feedback_data.get('tp_price', 0.0)
                        close_price = feedback_data.get('close_price')
                        realized_pnl = feedback_data.get('realized_pnl', 0.0)
                        entry_time_str = feedback_data.get('entry_time', datetime.now().isoformat())
                        exit_time_str = feedback_data.get('exit_time', datetime.now().isoformat())
                        source = feedback_data.get('source', 'user')
                        is_long = action.lower() == 'buy'

                        # NEW: Extract 17 Features
                        # Market Context Features (10-16): Snapshot at entry time
                        market_features = _extract_market_context_features(
                            chart_service.data_loader,
                            entry_time=entry_time_str,
                            entry_price=entry_price,
                            sl_price=sl_price,
                            tp_price=tp_price
                        )

                        # Trade-Specific Features (7, 9): Duration & Max Drawdown
                        trade_features = calculate_trade_features(
                            df=chart_service.data_loader.df,
                            entry_time=entry_time_str,
                            exit_time=exit_time_str,
                            entry_price=entry_price,
                            is_long=is_long
                        )

                        # Simple Rating (Feature 17): Convert overall_score to 0.0/0.5/1.0
                        if overall_score >= 0.8:
                            rating = 1.0  # Good
                        elif overall_score >= 0.5:
                            rating = 0.5  # OK
                        else:
                            rating = 0.0  # Bad

                        # Combine all 17 features
                        features = {
                            # Trade Basics (1-9)
                            'entry_price': entry_price,
                            'sl_price': sl_price,
                            'tp_price': tp_price,
                            'exit_price': close_price,
                            'entry_time': entry_time_str,
                            'exit_time': exit_time_str,
                            'trade_duration_candles': trade_features.get('trade_duration_candles', 0),
                            'realized_pnl': realized_pnl,
                            'max_drawdown_pct': trade_features.get('max_drawdown_pct', 0.0),
                            # Market Context (10-16)
                            **market_features,
                            # Human Rating (17)
                            'rating': rating
                        }

                        logger.info(f"[FEATURES] Complete 17-feature set extracted for closed position")

                        # TradeRecord mit echten Daten + Features erstellen
                        from src.feedback_storage import TradeRecord
                        trade_record = TradeRecord(
                            trade_id=trade_id,
                            timestamp=datetime.now().isoformat(),
                            action=action,
                            entry_price=entry_price,
                            sl_price=sl_price,
                            tp_price=tp_price,
                            exit_price=close_price,
                            pnl=realized_pnl,
                            state_hash='closed_position',
                            observation=[],
                            patterns={},  # Keep empty, features now in 'features' field
                            session_info={},
                            volume_info={},
                            human_evaluation=human_eval
                        )

                        # Add features field to trade_record dict
                        trade_dict = trade_record.to_dict()
                        trade_dict['features'] = features

                        # Speichere Feedback
                        feedback_system.storage.save_training_feedback(trade_dict)
                        logger.info(f"[WS] [OK] Feedback gespeichert für geschlossene Position: {action} @ {entry_price}")
                        logger.info(f"[WS] Features: Rating={rating}, R:R={features.get('rr_ratio'):.2f}, Duration={features.get('trade_duration_candles')} candles")

                        await websocket.send_json({
                            'type': 'trade_feedback_saved',
                            'trade_id': trade_id,
                            'message': f'Feedback gespeichert: {action} Trade @ {entry_price}'
                        })
                        continue

                    # Position aktiv - vollständige Feedback-Analyse
                    entry_price = position['entry_price']
                    sl_price = position['sl_price']
                    tp_price = position['tp_price']
                    direction = position['direction']
                    pnl = position.get('pnl', 0.0)
                    entry_time_str = position.get('entry_time', datetime.now().isoformat())

                    # Generiere State Hash für ähnliche Situationen
                    current_time = unified_time_manager.get_current_time()
                    state_hash = feedback_system.generate_state_hash_from_context(
                        timestamp=int(current_time.timestamp()),
                        entry_price=entry_price,
                        sl_price=sl_price,
                        tp_price=tp_price
                    )

                    # NEW: Extract Market Context Features (10-16)
                    market_features = _extract_market_context_features(
                        chart_service.data_loader,
                        entry_time=entry_time_str,
                        entry_price=entry_price,
                        sl_price=sl_price,
                        tp_price=tp_price
                    )

                    # Simple Rating (Feature 17): Convert overall_score to 0.0/0.5/1.0
                    if overall_score >= 0.8:
                        rating = 1.0  # Good
                    elif overall_score >= 0.5:
                        rating = 0.5  # OK
                    else:
                        rating = 0.0  # Bad

                    # Partial feature set (trade not closed yet)
                    features = {
                        # Trade Basics (1-9) - partial
                        'entry_price': entry_price,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                        'exit_price': None,  # Trade still active
                        'entry_time': entry_time_str,
                        'exit_time': None,  # Trade still active
                        'trade_duration_candles': None,  # Cannot calculate yet
                        'realized_pnl': pnl,  # Unrealized PnL for now
                        'max_drawdown_pct': None,  # Cannot calculate yet
                        # Market Context (10-16)
                        **market_features,
                        # Human Rating (17)
                        'rating': rating
                    }

                    logger.info(f"[FEATURES] Partial feature set extracted for active position (trade not closed yet)")

                    # Erstelle TradeRecord
                    from src.feedback_storage import TradeRecord
                    trade_record = TradeRecord(
                        trade_id=trade_id,
                        timestamp=datetime.now().isoformat(),
                        action=direction,
                        entry_price=entry_price,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        exit_price=None,  # Trade still active
                        pnl=pnl,
                        state_hash=state_hash,
                        observation=[],
                        patterns={},  # Keep empty, features now in 'features' field
                        session_info={},
                        volume_info={},
                        human_evaluation=human_eval
                    )

                    # Add features field to trade_record dict
                    trade_dict = trade_record.to_dict()
                    trade_dict['features'] = features

                    # Speichere Feedback
                    feedback_system.storage.save_training_feedback(trade_dict)
                    logger.info(f"[WS] [OK] Feedback gespeichert für {trade_id} (State Hash: {state_hash[:8]}...)")
                    logger.info(f"[WS] Features: Rating={rating}, R:R={features.get('rr_ratio'):.2f}")

                    # Berechne Feedback Reward für RL Training
                    feedback_reward = feedback_system.reward_manager.get_component('human').calculate(
                        state={},
                        action={},
                        env_info={'human_feedback': human_eval}
                    )

                    logger.info(f"[WS] Feedback Reward: {feedback_reward:+.3f}")

                    # Training Mode: KI lernt aus Feedback
                    if training_service and training_service.is_active:
                        training_service.on_feedback_received(trade_id, feedback_reward)

                    # Broadcast Feedback Saved Event
                    await manager.broadcast({
                        'type': 'trade_feedback_saved',
                        'trade_id': trade_id,
                        'overall_score': overall_score,
                        'feedback_reward': feedback_reward,
                        'message': 'Feedback erfolgreich gespeichert'
                    })

                    logger.info(f"[WS] Trade Feedback verarbeitet und gespeichert: {trade_id}")

                except Exception as e:
                    logger.error(f"[WS] Trade Feedback error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Trade Feedback failed: {str(e)}'
                    })


            # ========== BATCH FEEDBACK COMMAND ==========

            elif command_type == 'batch_feedback':
                try:
                    if not training_service:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Training Service nicht verfügbar'
                        })
                        continue

                    # Batch Feedback Daten vom Client
                    trade_id = data.get('trade_id')
                    overall_score = data.get('overall_score', 0.0)
                    ratings = data.get('ratings', {})
                    notes = data.get('notes', '')

                    logger.info(f"[BATCH] Feedback empfangen für {trade_id}")
                    logger.info(f"[BATCH] Overall Score: {overall_score:.2f}/5.0")

                    # Convert 5-star ratings (0-5) to reward (0-1)
                    # Overall score is average of 6 criteria, already normalized
                    feedback_reward = overall_score / 5.0

                    # Training Mode: KI lernt aus Feedback
                    training_service.on_feedback_received(trade_id, feedback_reward)

                    # Broadcast Success
                    await manager.broadcast({
                        'type': 'batch_feedback_saved',
                        'trade_id': trade_id,
                        'overall_score': overall_score,
                        'feedback_reward': feedback_reward,
                        'batch_number': training_service.total_batches,
                        'message': f'Batch #{training_service.total_batches} Feedback gespeichert - Weiter mit nächsten 10 Trades!'
                    })

                    logger.info(f"[BATCH] Feedback verarbeitet - Nächster Batch startet")

                except Exception as e:
                    logger.error(f"[BATCH] Batch Feedback error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Batch Feedback failed: {str(e)}'
                    })


            # ========== DELETE FEEDBACK COMMAND ==========

            elif command_type == 'delete_feedback':
                try:
                    if not feedback_system:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Feedback System nicht verfügbar'
                        })
                        continue

                    trade_id = data.get('trade_id')
                    if not trade_id:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Keine Trade ID übermittelt'
                        })
                        continue

                    logger.info(f"[WS] Delete Feedback Request für {trade_id}")

                    # Lösche Feedback aus Storage
                    success = feedback_system.storage.delete_training_feedback(trade_id)

                    if success:
                        # Broadcast Deletion Event
                        await manager.broadcast({
                            'type': 'trade_feedback_deleted',
                            'trade_id': trade_id,
                            'message': 'Feedback erfolgreich gelöscht'
                        })

                        logger.info(f"[WS] [OK] Feedback deleted for {trade_id}")
                    else:
                        await websocket.send_json({
                            'type': 'error',
                            'message': f'Feedback für {trade_id} nicht gefunden'
                        })

                except Exception as e:
                    logger.error(f"[WS] Delete Feedback error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Delete Feedback failed: {str(e)}'
                    })


            # ========== LIST FEEDBACK COMMAND ==========

            elif command_type == 'list_feedback':
                try:
                    if not feedback_system:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Feedback System nicht verfügbar'
                        })
                        continue

                    limit = data.get('limit', 100)
                    feedback_list = feedback_system.storage.list_all_feedback(limit=limit)

                    await websocket.send_json({
                        'type': 'feedback_list',
                        'feedbacks': feedback_list,
                        'count': len(feedback_list)
                    })

                    logger.info(f"[WS] Listed {len(feedback_list)} feedback entries")

                except Exception as e:
                    logger.error(f"[WS] List Feedback error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'List Feedback failed: {str(e)}'
                    })


            # ========== TOGGLE AI MODE COMMAND ==========

            elif command_type == 'toggle_ai_mode':
                try:
                    if not training_service:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Training Service nicht verfügbar'
                        })
                        continue

                    # Toggle Training Mode
                    status = training_service.toggle_mode()

                    # Hole AI Account Stats (persistente Trade-Zählung)
                    ai_account_summary = account_service.get_account_summary('ai')

                    # Broadcast zu allen Clients
                    await manager.broadcast({
                        'type': 'ai_mode_toggled',
                        'is_active': status['is_active'],
                        'session_id': status['session_id'],
                        'stats': status['stats'],
                        'account_stats': ai_account_summary  # ← Persistente Stats
                    })

                    logger.info(f"[WS] AI Mode toggled: {status['is_active']}")

                except Exception as e:
                    logger.error(f"[WS] Toggle AI Mode error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Toggle AI Mode failed: {str(e)}'
                    })


            # ========== GET AI STATUS COMMAND ==========

            elif command_type == 'get_ai_status':
                try:
                    if not training_service:
                        await websocket.send_json({
                            'type': 'error',
                            'message': 'Training Service nicht verfügbar'
                        })
                        continue

                    status = training_service.get_status()

                    # Hole AI Account Stats (persistente Trade-Zählung)
                    ai_account_summary = account_service.get_account_summary('ai')

                    await websocket.send_json({
                        'type': 'ai_status',
                        **status,
                        'account_stats': ai_account_summary  # ← Persistente Stats
                    })

                    logger.info(f"[WS] AI Status sent")

                except Exception as e:
                    logger.error(f"[WS] Get AI Status error: {e}")
                    await websocket.send_json({
                        'type': 'error',
                        'message': f'Get AI Status failed: {str(e)}'
                    })


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
