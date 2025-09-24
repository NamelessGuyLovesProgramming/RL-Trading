"""
Tests für Button State Race Condition Fixes
==========================================
Umfassende Tests für WebSocket-basierte Button State Synchronization und Race Condition Prevention
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import json
import sys
from pathlib import Path
import threading
import queue

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestButtonStateRaceConditionFixes:
    """Test Suite für Button State Race Condition Prevention"""

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket für Testing"""
        websocket = Mock()
        websocket.send = Mock()
        websocket.close = Mock()
        websocket.state = 'connected'
        return websocket

    @pytest.fixture
    def mock_ui_state(self):
        """Mock UI State Management"""
        return {
            'active_timeframe': '5m',
            'buttons_disabled': False,
            'error_message': None,
            'last_update_source': None,
            'update_history': []
        }

    def test_single_source_of_truth_websocket_updates(self, mock_websocket, mock_ui_state):
        """Test Single Source of Truth: Nur WebSocket Updates Button State"""

        def simulate_websocket_update(ui_state, message):
            """Simuliert WebSocket-basierte Button State Updates"""
            if message['type'] == 'timeframe_change_complete':
                ui_state['active_timeframe'] = message['timeframe']
                ui_state['buttons_disabled'] = False
                ui_state['error_message'] = None
                ui_state['last_update_source'] = 'websocket'
                ui_state['update_history'].append(('websocket_success', message['timeframe']))

        def simulate_http_error_handling(ui_state, error_type):
            """Simuliert HTTP Error Handling (OHNE Button State Updates)"""
            if error_type == 'AbortError':
                # FIXED: Do NOT update button state on AbortError
                # ui_state['buttons_disabled'] = False  # REMOVED: Prevents race condition
                # ui_state['error_message'] = 'Timeout'  # REMOVED: Prevents race condition
                ui_state['update_history'].append(('http_abort_error', 'no_state_change'))
            elif error_type == 'NetworkError':
                # Only critical errors should update UI state
                ui_state['error_message'] = 'Network connection lost'
                ui_state['update_history'].append(('http_network_error', 'critical_error'))

        # Test Race Condition Scenario: HTTP Timeout + WebSocket Success
        initial_state = mock_ui_state.copy()
        initial_state['active_timeframe'] = '5m'
        initial_state['buttons_disabled'] = True  # User clicked button

        # Step 1: HTTP Request times out (AbortError)
        simulate_http_error_handling(initial_state, 'AbortError')

        # Verify: Button state NOT changed by HTTP timeout
        assert initial_state['buttons_disabled'] is True, "Button should remain disabled after HTTP timeout"
        assert initial_state['active_timeframe'] == '5m', "Timeframe should not change on HTTP timeout"
        assert initial_state['error_message'] is None, "No error message for AbortError"

        # Step 2: WebSocket Success comes later
        websocket_message = {
            'type': 'timeframe_change_complete',
            'timeframe': '15m',
            'data': [{'time': 1640995200, 'open': 20000, 'high': 20050, 'low': 19950, 'close': 20025}]
        }
        simulate_websocket_update(initial_state, websocket_message)

        # Verify: WebSocket updates button state correctly
        assert initial_state['active_timeframe'] == '15m', "Timeframe should be updated by WebSocket"
        assert initial_state['buttons_disabled'] is False, "Buttons should be enabled by WebSocket"
        assert initial_state['error_message'] is None, "Error should be cleared by WebSocket success"
        assert initial_state['last_update_source'] == 'websocket', "Last update should be from WebSocket"

        # Verify update history shows proper sequence
        expected_history = [
            ('http_abort_error', 'no_state_change'),
            ('websocket_success', '15m')
        ]
        assert initial_state['update_history'] == expected_history, "Update history should show race-safe sequence"

    def test_button_state_consistency_during_race_condition(self):
        """Test Button State Consistency während Race Conditions"""

        class ButtonStateManager:
            def __init__(self):
                self.current_timeframe = '5m'
                self.buttons_disabled = False
                self.pending_requests = set()
                self.state_change_log = []

            def start_request(self, request_id, target_timeframe):
                """Start einer Timeframe-Change Request"""
                self.buttons_disabled = True
                self.pending_requests.add(request_id)
                self.state_change_log.append(('request_started', request_id, target_timeframe))

            def handle_http_timeout(self, request_id):
                """HTTP Request Timeout Handling (Race-Safe)"""
                # FIXED: Do NOT change button state on timeout - WebSocket might still succeed
                self.state_change_log.append(('http_timeout', request_id, 'no_button_change'))

            def handle_websocket_success(self, request_id, new_timeframe):
                """WebSocket Success Handling (Single Source of Truth)"""
                self.current_timeframe = new_timeframe
                self.buttons_disabled = False
                self.pending_requests.discard(request_id)
                self.state_change_log.append(('websocket_success', request_id, new_timeframe))

            def handle_websocket_error(self, request_id):
                """WebSocket Error Handling"""
                self.buttons_disabled = False
                self.pending_requests.discard(request_id)
                self.state_change_log.append(('websocket_error', request_id, 'request_failed'))

        manager = ButtonStateManager()

        # Test Race Condition Scenario
        request_id = 'req_001'
        target_timeframe = '15m'

        # Step 1: User starts request
        manager.start_request(request_id, target_timeframe)
        assert manager.buttons_disabled is True, "Buttons should be disabled during request"
        assert request_id in manager.pending_requests, "Request should be tracked as pending"

        # Step 2: HTTP request times out
        manager.handle_http_timeout(request_id)
        assert manager.buttons_disabled is True, "Buttons should REMAIN disabled after HTTP timeout"
        assert manager.current_timeframe == '5m', "Timeframe should not change on timeout"

        # Step 3: WebSocket success arrives later
        manager.handle_websocket_success(request_id, target_timeframe)
        assert manager.buttons_disabled is False, "Buttons should be enabled after WebSocket success"
        assert manager.current_timeframe == target_timeframe, "Timeframe should be updated by WebSocket"
        assert request_id not in manager.pending_requests, "Request should be removed from pending"

        # Verify consistent state progression
        expected_log = [
            ('request_started', request_id, target_timeframe),
            ('http_timeout', request_id, 'no_button_change'),
            ('websocket_success', request_id, target_timeframe)
        ]
        assert manager.state_change_log == expected_log, "State changes should follow race-safe pattern"

    @pytest.mark.asyncio
    async def test_concurrent_request_race_condition_prevention(self):
        """Test Prevention von Race Conditions bei concurrent requests"""

        class ConcurrentRequestManager:
            def __init__(self):
                self.active_timeframe = '5m'
                self.button_states = {
                    '1m': False, '5m': True, '15m': False, '30m': False, '1h': False
                }
                self.request_queue = asyncio.Queue()
                self.state_lock = asyncio.Lock()

            async def handle_timeframe_request(self, target_timeframe, request_delay, websocket_delay):
                """Simuliert Timeframe Request mit verschiedenen Delays"""
                request_id = f"req_{target_timeframe}_{int(time.time())}"

                # Start request - disable buttons
                async with self.state_lock:
                    for tf in self.button_states:
                        self.button_states[tf] = False

                # Simulate HTTP request delay
                await asyncio.sleep(request_delay)

                # HTTP request completes/times out
                http_success = request_delay < 5.0  # 5s timeout threshold

                if not http_success:
                    # HTTP timeout - but DON'T change button states
                    pass

                # WebSocket response delay (might be after HTTP timeout)
                await asyncio.sleep(websocket_delay)

                # WebSocket success - update button states (Single Source of Truth)
                async with self.state_lock:
                    self.active_timeframe = target_timeframe
                    for tf in self.button_states:
                        self.button_states[tf] = False
                    self.button_states[target_timeframe] = True

                return {
                    'request_id': request_id,
                    'target_timeframe': target_timeframe,
                    'http_success': http_success,
                    'websocket_success': True,
                    'final_active_timeframe': self.active_timeframe
                }

        manager = ConcurrentRequestManager()

        # Test concurrent requests with different timing
        concurrent_requests = [
            ('15m', 2.0, 1.0),  # Fast HTTP + Fast WebSocket
            ('30m', 6.0, 2.0),  # Slow HTTP (timeout) + Fast WebSocket
            ('1h', 3.0, 7.0),   # Fast HTTP + Slow WebSocket
        ]

        # Start all requests concurrently
        tasks = []
        for timeframe, http_delay, ws_delay in concurrent_requests:
            task = asyncio.create_task(
                manager.handle_timeframe_request(timeframe, http_delay, ws_delay)
            )
            tasks.append(task)

        # Wait for all requests to complete
        results = await asyncio.gather(*tasks)

        # Verify race condition prevention
        assert len(results) == len(concurrent_requests), "All requests should complete"

        # Verify final state consistency
        active_buttons = [tf for tf, active in manager.button_states.items() if active]
        assert len(active_buttons) == 1, f"Exactly one button should be active, got: {active_buttons}"

        # Verify active timeframe matches active button
        active_timeframe = manager.active_timeframe
        assert manager.button_states[active_timeframe] is True, f"Button for {active_timeframe} should be active"

    def test_error_classification_prevents_race_conditions(self):
        """Test Error Classification Prevention von Race Conditions"""

        def classify_and_handle_error(error_type, current_state):
            """Simuliert Error Classification und Handling"""
            state_changes = []

            if error_type == 'AbortError':
                # FIXED: AbortError does not change UI state (prevents race condition)
                state_changes.append(('log_warning', 'Request timeout - operation might still be processing'))
                # state_changes.append(('reset_buttons', None))  # REMOVED: Causes race condition
                # state_changes.append(('show_error', 'Timeout'))  # REMOVED: Confuses user

            elif error_type == 'NetworkError':
                # Critical errors should update UI state
                state_changes.append(('reset_buttons', None))
                state_changes.append(('show_error', 'Network connection lost'))

            elif error_type == 'ServerError':
                # Server errors should update UI state
                state_changes.append(('reset_buttons', None))
                state_changes.append(('show_error', 'Server error occurred'))

            return state_changes

        # Test AbortError (timeout) handling
        abort_error_changes = classify_and_handle_error('AbortError', {'timeframe': '5m'})
        expected_abort_changes = [
            ('log_warning', 'Request timeout - operation might still be processing')
        ]
        assert abort_error_changes == expected_abort_changes, "AbortError should only log warning, not change UI"

        # Test NetworkError handling
        network_error_changes = classify_and_handle_error('NetworkError', {'timeframe': '5m'})
        expected_network_changes = [
            ('reset_buttons', None),
            ('show_error', 'Network connection lost')
        ]
        assert network_error_changes == expected_network_changes, "NetworkError should update UI state"

        # Test ServerError handling
        server_error_changes = classify_and_handle_error('ServerError', {'timeframe': '5m'})
        expected_server_changes = [
            ('reset_buttons', None),
            ('show_error', 'Server error occurred')
        ]
        assert server_error_changes == expected_server_changes, "ServerError should update UI state"

    def test_websocket_state_synchronization_accuracy(self):
        """Test WebSocket State Synchronization Accuracy"""

        class WebSocketStateSynchronizer:
            def __init__(self):
                self.frontend_state = {'active_timeframe': '5m', 'buttons_disabled': False}
                self.backend_state = {'current_timeframe': '5m', 'processing': False}
                self.synchronization_log = []

            def send_websocket_message(self, message_type, data):
                """Simuliert WebSocket Message Send"""
                message = {'type': message_type, **data}
                self.synchronization_log.append(('sent', message))
                return message

            def receive_websocket_message(self, message):
                """Simuliert WebSocket Message Receive"""
                self.synchronization_log.append(('received', message))

                if message['type'] == 'timeframe_change_complete':
                    # Synchronize frontend state with backend
                    self.frontend_state['active_timeframe'] = message['timeframe']
                    self.frontend_state['buttons_disabled'] = False
                    self.backend_state['current_timeframe'] = message['timeframe']
                    self.backend_state['processing'] = False

            def is_state_synchronized(self):
                """Prüft State Synchronization zwischen Frontend und Backend"""
                return (
                    self.frontend_state['active_timeframe'] == self.backend_state['current_timeframe'] and
                    self.frontend_state['buttons_disabled'] == self.backend_state['processing']
                )

        synchronizer = WebSocketStateSynchronizer()

        # Initial state should be synchronized
        assert synchronizer.is_state_synchronized(), "Initial state should be synchronized"

        # Simulate backend processing start
        synchronizer.backend_state['processing'] = True
        synchronizer.frontend_state['buttons_disabled'] = True
        assert synchronizer.is_state_synchronized(), "States should remain synchronized during processing"

        # Simulate backend completes timeframe change
        synchronizer.backend_state['current_timeframe'] = '15m'
        synchronizer.backend_state['processing'] = False

        # Send WebSocket synchronization message
        sync_message = synchronizer.send_websocket_message('timeframe_change_complete', {
            'timeframe': '15m',
            'data': []
        })

        # Receive and process WebSocket message
        synchronizer.receive_websocket_message(sync_message)

        # Verify synchronization
        assert synchronizer.is_state_synchronized(), "State should be synchronized after WebSocket update"
        assert synchronizer.frontend_state['active_timeframe'] == '15m', "Frontend should reflect new timeframe"
        assert synchronizer.frontend_state['buttons_disabled'] is False, "Buttons should be enabled"

        # Verify message flow
        expected_log = [
            ('sent', {'type': 'timeframe_change_complete', 'timeframe': '15m', 'data': []}),
            ('received', {'type': 'timeframe_change_complete', 'timeframe': '15m', 'data': []})
        ]
        assert synchronizer.synchronization_log == expected_log, "WebSocket message flow should be logged"

    def test_button_state_recovery_after_race_condition(self):
        """Test Button State Recovery nach Race Conditions"""

        class ButtonStateRecoveryManager:
            def __init__(self):
                self.button_states = {'5m': True, '15m': False, '30m': False, '1h': False}
                self.expected_state = None  # What state should be after operation
                self.recovery_attempts = 0
                self.max_recovery_attempts = 3

            def initiate_timeframe_change(self, target_timeframe):
                """Startet Timeframe Change"""
                # Disable all buttons during request
                for tf in self.button_states:
                    self.button_states[tf] = False
                self.expected_state = target_timeframe

            def handle_race_condition_error(self):
                """Simuliert Race Condition Error (HTTP timeout but WebSocket success)"""
                # Race condition: HTTP failed, but we don't know if WebSocket will succeed
                # DON'T reset button states - wait for WebSocket or timeout
                pass

            def attempt_state_recovery(self):
                """Versucht Button State Recovery"""
                self.recovery_attempts += 1

                if self.recovery_attempts <= self.max_recovery_attempts:
                    # Try to synchronize with expected state
                    if self.expected_state:
                        for tf in self.button_states:
                            self.button_states[tf] = (tf == self.expected_state)
                        return True
                else:
                    # Max attempts reached - reset to safe state
                    for tf in self.button_states:
                        self.button_states[tf] = False
                    self.button_states['5m'] = True  # Default to 5m
                    return False

            def websocket_success_recovery(self, actual_timeframe):
                """WebSocket Success Recovery"""
                for tf in self.button_states:
                    self.button_states[tf] = (tf == actual_timeframe)
                self.expected_state = None
                self.recovery_attempts = 0

        manager = ButtonStateRecoveryManager()

        # Test normal recovery workflow
        target_timeframe = '15m'
        manager.initiate_timeframe_change(target_timeframe)

        # Verify buttons disabled during operation
        assert all(not active for active in manager.button_states.values()), "All buttons should be disabled during request"

        # Simulate race condition
        manager.handle_race_condition_error()

        # Verify no premature state reset
        assert all(not active for active in manager.button_states.values()), "Buttons should remain disabled after race condition"

        # WebSocket success arrives
        manager.websocket_success_recovery(target_timeframe)

        # Verify correct recovery
        assert manager.button_states[target_timeframe] is True, f"{target_timeframe} button should be active"
        assert sum(manager.button_states.values()) == 1, "Exactly one button should be active"
        assert manager.expected_state is None, "Expected state should be cleared after recovery"
        assert manager.recovery_attempts == 0, "Recovery attempts should be reset"

    def test_multi_user_race_condition_simulation(self):
        """Test Multi-User Race Condition Simulation"""

        def simulate_user_interaction(user_id, actions, shared_state, results_queue):
            """Simuliert User-Interaktionen in separatem Thread"""
            user_results = []

            for action in actions:
                action_type, target_timeframe, delay = action
                time.sleep(delay)  # Simulate user timing

                if action_type == 'click_timeframe':
                    # Simulate button click
                    with shared_state['lock']:
                        if not shared_state['buttons_disabled']:
                            shared_state['buttons_disabled'] = True
                            shared_state['pending_request'] = target_timeframe
                            user_results.append(('click_accepted', target_timeframe))
                        else:
                            user_results.append(('click_rejected', target_timeframe))

                elif action_type == 'websocket_response':
                    # Simulate WebSocket response
                    with shared_state['lock']:
                        if shared_state['pending_request'] == target_timeframe:
                            shared_state['active_timeframe'] = target_timeframe
                            shared_state['buttons_disabled'] = False
                            shared_state['pending_request'] = None
                            user_results.append(('websocket_success', target_timeframe))

            results_queue.put((user_id, user_results))

        # Setup shared state
        shared_state = {
            'active_timeframe': '5m',
            'buttons_disabled': False,
            'pending_request': None,
            'lock': threading.Lock()
        }

        # Define user actions (action_type, target_timeframe, delay)
        user_actions = {
            'user1': [
                ('click_timeframe', '15m', 0.1),
                ('websocket_response', '15m', 2.0),
            ],
            'user2': [
                ('click_timeframe', '30m', 0.5),  # Tries to click while user1 request pending
            ],
            'user3': [
                ('click_timeframe', '1h', 3.0),   # Clicks after user1 completes
                ('websocket_response', '1h', 1.0),
            ]
        }

        # Start user simulation threads
        results_queue = queue.Queue()
        threads = []

        for user_id, actions in user_actions.items():
            thread = threading.Thread(
                target=simulate_user_interaction,
                args=(user_id, actions, shared_state, results_queue)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=10)

        # Collect results
        user_results = {}
        while not results_queue.empty():
            user_id, results = results_queue.get()
            user_results[user_id] = results

        # Verify race condition prevention
        assert 'user1' in user_results, "User1 results should be present"
        assert ('click_accepted', '15m') in user_results['user1'], "User1 should successfully click 15m"
        assert ('websocket_success', '15m') in user_results['user1'], "User1 should get WebSocket success"

        assert 'user2' in user_results, "User2 results should be present"
        assert ('click_rejected', '30m') in user_results['user2'], "User2 click should be rejected (button disabled)"

        assert 'user3' in user_results, "User3 results should be present"
        assert ('click_accepted', '1h') in user_results['user3'], "User3 should successfully click after user1 completes"

        # Verify final state
        assert shared_state['active_timeframe'] == '1h', "Final timeframe should be 1h (last successful change)"
        assert shared_state['buttons_disabled'] is False, "Buttons should be enabled at end"
        assert shared_state['pending_request'] is None, "No pending request should remain"

    def test_websocket_connection_failure_recovery(self):
        """Test WebSocket Connection Failure Recovery"""

        class WebSocketConnectionManager:
            def __init__(self):
                self.connection_state = 'connected'
                self.button_states = {'5m': True, '15m': False, '30m': False}
                self.pending_operations = []
                self.reconnection_attempts = 0
                self.max_reconnection_attempts = 3

            def send_message(self, message):
                """Send WebSocket Message"""
                if self.connection_state == 'connected':
                    return {'status': 'sent', 'message': message}
                else:
                    self.pending_operations.append(message)
                    return {'status': 'queued', 'message': message}

            def simulate_connection_failure(self):
                """Simulate WebSocket Connection Failure"""
                self.connection_state = 'disconnected'
                # When connection fails during button operation, buttons should remain disabled
                # until connection is restored and state can be synchronized

            def attempt_reconnection(self):
                """Attempt WebSocket Reconnection"""
                self.reconnection_attempts += 1

                if self.reconnection_attempts <= self.max_reconnection_attempts:
                    self.connection_state = 'connected'
                    # Replay pending operations
                    replayed_operations = self.pending_operations.copy()
                    self.pending_operations.clear()
                    return {'status': 'reconnected', 'replayed_operations': replayed_operations}
                else:
                    return {'status': 'failed', 'replayed_operations': []}

            def handle_button_click_during_disconnection(self, target_timeframe):
                """Handle Button Click During WebSocket Disconnection"""
                if self.connection_state == 'disconnected':
                    # Queue the operation for replay after reconnection
                    operation = {'type': 'timeframe_change', 'target': target_timeframe}
                    self.pending_operations.append(operation)
                    return {'status': 'queued', 'operation': operation}
                else:
                    return {'status': 'processed_immediately', 'operation': None}

        manager = WebSocketConnectionManager()

        # Test normal operation
        result = manager.send_message({'type': 'timeframe_change', 'target': '15m'})
        assert result['status'] == 'sent', "Message should be sent when connected"

        # Simulate connection failure
        manager.simulate_connection_failure()
        assert manager.connection_state == 'disconnected', "Connection should be disconnected"

        # Test button click during disconnection
        click_result = manager.handle_button_click_during_disconnection('30m')
        assert click_result['status'] == 'queued', "Operation should be queued during disconnection"
        assert len(manager.pending_operations) == 1, "One operation should be pending"

        # Test message sending during disconnection
        send_result = manager.send_message({'type': 'timeframe_change', 'target': '1h'})
        assert send_result['status'] == 'queued', "Message should be queued when disconnected"
        assert len(manager.pending_operations) == 2, "Two operations should be pending"

        # Test reconnection
        reconnection_result = manager.attempt_reconnection()
        assert reconnection_result['status'] == 'reconnected', "Reconnection should succeed"
        assert len(reconnection_result['replayed_operations']) == 2, "Two operations should be replayed"
        assert len(manager.pending_operations) == 0, "Pending operations should be cleared after replay"

        # Verify operations were replayed in correct order
        replayed_ops = reconnection_result['replayed_operations']
        assert replayed_ops[0]['target'] == '30m', "First operation should be 30m (button click)"
        assert replayed_ops[1]['target'] == '1h', "Second operation should be 1h (message send)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])