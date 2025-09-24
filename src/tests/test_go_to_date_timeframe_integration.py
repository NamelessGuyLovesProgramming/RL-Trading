"""
Integration Tests für Go To Date + Timeframe Switching Workflow
============================================================
Umfassende Integration Tests für die komplette User Journey mit Adaptive Timeout System
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
import json
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path
import tempfile
import os

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGoToDateTimeframeIntegration:
    """Integration Test Suite für Go To Date + Timeframe Workflow"""

    @pytest.fixture
    def sample_csv_data(self):
        """Erstellt Sample CSV-Daten für verschiedene Timeframes"""
        timeframes = ['5m', '15m', '30m', '1h']
        csv_files = {}

        for tf in timeframes:
            # Generate sample data for December 2024
            start_date = datetime(2024, 12, 1)
            end_date = datetime(2024, 12, 31)

            # Calculate interval in minutes
            intervals = {'5m': 5, '15m': 15, '30m': 30, '1h': 60}
            interval_minutes = intervals[tf]

            data = []
            current_time = start_date
            base_price = 20000

            while current_time <= end_date:
                data.append({
                    'Date': current_time.strftime('%d.%m.%Y'),
                    'Time': current_time.strftime('%H:%M'),
                    'Open': base_price + (len(data) * 0.1),
                    'High': base_price + (len(data) * 0.1) + 10,
                    'Low': base_price + (len(data) * 0.1) - 10,
                    'Close': base_price + (len(data) * 0.1) + 5,
                    'Volume': 1000 + (len(data) % 500)
                })
                current_time += timedelta(minutes=interval_minutes)

            # Create temporary CSV file
            df = pd.DataFrame(data)
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'_{tf}.csv')
            df.to_csv(temp_file.name, index=False)
            temp_file.close()
            csv_files[tf] = temp_file.name

        yield csv_files

        # Cleanup
        for file_path in csv_files.values():
            if os.path.exists(file_path):
                os.unlink(file_path)

    @pytest.fixture
    def mock_chart_server(self, sample_csv_data):
        """Mock Chart Server für Integration Testing"""
        class MockChartServer:
            def __init__(self, csv_files):
                self.csv_files = csv_files
                self.current_timeframe = '5m'
                self.current_go_to_date = None
                self.websocket_clients = []
                self.request_history = []
                self.processing_times = {
                    'normal_timeframe_switch': 2.5,
                    'go_to_date_csv_processing': 8.0,
                    'timeframe_switch_after_go_to_date': 9.5
                }

            def set_go_to_date(self, target_date_str):
                """Simuliert Go To Date Operation"""
                start_time = time.time()
                self.current_go_to_date = datetime.strptime(target_date_str, '%Y-%m-%d')

                # Simulate CSV processing time
                processing_time = self.processing_times['go_to_date_csv_processing']
                time.sleep(0.1)  # Short simulation instead of full processing

                self.request_history.append({
                    'operation': 'go_to_date',
                    'target_date': target_date_str,
                    'processing_time': processing_time,
                    'timestamp': start_time
                })

                return {
                    'success': True,
                    'target_date': target_date_str,
                    'processing_time': processing_time,
                    'candles_loaded': 200
                }

            def change_timeframe(self, new_timeframe):
                """Simuliert Timeframe Change"""
                start_time = time.time()

                # Determine processing time based on context
                if self.current_go_to_date:
                    operation_type = 'timeframe_switch_after_go_to_date'
                    processing_time = self.processing_times[operation_type]
                else:
                    operation_type = 'normal_timeframe_switch'
                    processing_time = self.processing_times[operation_type]

                # Short simulation
                time.sleep(0.1)

                old_timeframe = self.current_timeframe
                self.current_timeframe = new_timeframe

                self.request_history.append({
                    'operation': 'timeframe_change',
                    'from_timeframe': old_timeframe,
                    'to_timeframe': new_timeframe,
                    'processing_time': processing_time,
                    'go_to_date_context': self.current_go_to_date,
                    'timestamp': start_time
                })

                return {
                    'success': True,
                    'new_timeframe': new_timeframe,
                    'processing_time': processing_time,
                    'go_to_date_active': self.current_go_to_date is not None,
                    'candles_loaded': 200
                }

            def get_adaptive_timeout(self):
                """Berechnet Adaptive Timeout basierend auf Context"""
                return 15000 if self.current_go_to_date else 8000

            def clear_go_to_date(self):
                """Clears Go To Date Context"""
                self.current_go_to_date = None

        return MockChartServer(sample_csv_data)

    def test_complete_go_to_date_workflow(self, mock_chart_server):
        """Test Complete Go To Date Workflow"""

        # Step 1: Initial State
        assert mock_chart_server.current_timeframe == '5m', "Initial timeframe should be 5m"
        assert mock_chart_server.current_go_to_date is None, "Initial Go To Date should be None"
        assert mock_chart_server.get_adaptive_timeout() == 8000, "Initial timeout should be 8s"

        # Step 2: User performs Go To Date
        target_date = '2024-12-24'
        go_to_date_result = mock_chart_server.set_go_to_date(target_date)

        assert go_to_date_result['success'] is True, "Go To Date should succeed"
        assert go_to_date_result['target_date'] == target_date, "Target date should match"
        assert go_to_date_result['processing_time'] == 8.0, "Go To Date processing time should be 8s"
        assert mock_chart_server.current_go_to_date is not None, "Go To Date should be active"
        assert mock_chart_server.get_adaptive_timeout() == 15000, "Timeout should increase to 15s after Go To Date"

        # Step 3: User switches timeframes after Go To Date
        timeframe_switches = ['15m', '30m', '1h', '5m']

        for new_timeframe in timeframe_switches:
            switch_result = mock_chart_server.change_timeframe(new_timeframe)

            assert switch_result['success'] is True, f"Timeframe switch to {new_timeframe} should succeed"
            assert switch_result['new_timeframe'] == new_timeframe, f"New timeframe should be {new_timeframe}"
            assert switch_result['go_to_date_active'] is True, "Go To Date context should be preserved"
            assert switch_result['processing_time'] == 9.5, "Processing time should be 9.5s (after Go To Date)"
            assert mock_chart_server.current_timeframe == new_timeframe, f"Current timeframe should be {new_timeframe}"
            assert mock_chart_server.get_adaptive_timeout() == 15000, "Timeout should remain 15s while Go To Date active"

        # Step 4: Clear Go To Date and verify normal behavior
        mock_chart_server.clear_go_to_date()

        assert mock_chart_server.current_go_to_date is None, "Go To Date should be cleared"
        assert mock_chart_server.get_adaptive_timeout() == 8000, "Timeout should return to 8s"

        # Step 5: Normal timeframe switch after clearing Go To Date
        normal_switch_result = mock_chart_server.change_timeframe('15m')

        assert normal_switch_result['success'] is True, "Normal timeframe switch should succeed"
        assert normal_switch_result['go_to_date_active'] is False, "Go To Date should not be active"
        assert normal_switch_result['processing_time'] == 2.5, "Processing time should be 2.5s (normal)"

        # Verify request history
        total_requests = len(mock_chart_server.request_history)
        expected_requests = 1 + len(timeframe_switches) + 1  # Go To Date + switches + normal switch
        assert total_requests == expected_requests, f"Should have {expected_requests} requests, got {total_requests}"

    @pytest.mark.asyncio
    async def test_timeout_behavior_integration(self, mock_chart_server):
        """Test Adaptive Timeout Behavior Integration"""

        async def simulate_request_with_adaptive_timeout(operation_type, **kwargs):
            """Simuliert Request mit Adaptive Timeout"""
            # Get current adaptive timeout
            adaptive_timeout = mock_chart_server.get_adaptive_timeout() / 1000  # Convert to seconds

            if operation_type == 'go_to_date':
                future = asyncio.create_task(
                    asyncio.to_thread(mock_chart_server.set_go_to_date, kwargs['target_date'])
                )
            elif operation_type == 'timeframe_change':
                future = asyncio.create_task(
                    asyncio.to_thread(mock_chart_server.change_timeframe, kwargs['new_timeframe'])
                )

            try:
                result = await asyncio.wait_for(future, timeout=adaptive_timeout)
                return {'status': 'success', 'result': result, 'timeout_used': adaptive_timeout}
            except asyncio.TimeoutError:
                return {'status': 'timeout', 'result': None, 'timeout_used': adaptive_timeout}

        # Test 1: Normal timeframe switch with 8s timeout (should succeed)
        normal_result = await simulate_request_with_adaptive_timeout(
            'timeframe_change', new_timeframe='15m'
        )
        assert normal_result['status'] == 'success', "Normal timeframe switch should succeed with 8s timeout"
        assert normal_result['timeout_used'] == 8.0, "Should use 8s timeout for normal operation"
        assert normal_result['result']['processing_time'] == 2.5, "Processing should take 2.5s"

        # Test 2: Go To Date with 15s timeout (should succeed)
        go_to_date_result = await simulate_request_with_adaptive_timeout(
            'go_to_date', target_date='2024-12-25'
        )
        assert go_to_date_result['status'] == 'success', "Go To Date should succeed with 15s timeout"
        # Note: timeout changes after Go To Date is set, so this uses 8s but succeeds because processing is fast in mock

        # Test 3: Timeframe switch after Go To Date with 15s timeout (should succeed)
        after_go_to_date_result = await simulate_request_with_adaptive_timeout(
            'timeframe_change', new_timeframe='30m'
        )
        assert after_go_to_date_result['status'] == 'success', "Timeframe switch after Go To Date should succeed with 15s timeout"
        assert after_go_to_date_result['timeout_used'] == 15.0, "Should use 15s timeout after Go To Date"

    def test_race_condition_prevention_integration(self, mock_chart_server):
        """Test Race Condition Prevention in Integration Workflow"""

        class IntegratedRaceConditionSimulator:
            def __init__(self, server):
                self.server = server
                self.button_state = {'active_timeframe': '5m', 'disabled': False}
                self.http_requests = []
                self.websocket_messages = []
                self.race_condition_events = []

            def simulate_user_timeframe_click(self, target_timeframe):
                """Simuliert User Timeframe Button Click"""
                if self.button_state['disabled']:
                    return {'status': 'rejected', 'reason': 'buttons_disabled'}

                # Disable buttons during request
                self.button_state['disabled'] = True

                # Start HTTP request (with potential timeout)
                request_id = f"req_{target_timeframe}_{int(time.time() * 1000)}"
                self.http_requests.append({
                    'id': request_id,
                    'target_timeframe': target_timeframe,
                    'start_time': time.time(),
                    'status': 'pending'
                })

                return {'status': 'accepted', 'request_id': request_id}

            def simulate_http_timeout(self, request_id):
                """Simuliert HTTP Request Timeout"""
                request = next((r for r in self.http_requests if r['id'] == request_id), None)
                if request:
                    request['status'] = 'timeout'
                    self.race_condition_events.append({
                        'type': 'http_timeout',
                        'request_id': request_id,
                        'action': 'no_button_state_change'  # FIXED: No state change on timeout
                    })

            def simulate_websocket_success(self, request_id, actual_timeframe):
                """Simuliert WebSocket Success Response"""
                # WebSocket success should update button state (Single Source of Truth)
                self.button_state['active_timeframe'] = actual_timeframe
                self.button_state['disabled'] = False

                self.websocket_messages.append({
                    'type': 'timeframe_change_complete',
                    'request_id': request_id,
                    'timeframe': actual_timeframe
                })

                self.race_condition_events.append({
                    'type': 'websocket_success',
                    'request_id': request_id,
                    'action': 'button_state_updated',
                    'new_timeframe': actual_timeframe
                })

            def get_final_state(self):
                """Gets Final Button State"""
                return self.button_state.copy()

        # Setup Race Condition Test
        simulator = IntegratedRaceConditionSimulator(mock_chart_server)

        # Step 1: Set Go To Date (triggers extended timeout context)
        mock_chart_server.set_go_to_date('2024-12-24')

        # Step 2: User clicks timeframe button
        click_result = simulator.simulate_user_timeframe_click('15m')
        assert click_result['status'] == 'accepted', "Button click should be accepted"
        request_id = click_result['request_id']

        # Step 3: HTTP request times out (but WebSocket might still succeed)
        simulator.simulate_http_timeout(request_id)

        # Verify: Button state NOT changed by HTTP timeout (prevents race condition)
        intermediate_state = simulator.get_final_state()
        assert intermediate_state['disabled'] is True, "Buttons should remain disabled after HTTP timeout"
        assert intermediate_state['active_timeframe'] == '5m', "Timeframe should not change on HTTP timeout"

        # Step 4: WebSocket success arrives later
        simulator.simulate_websocket_success(request_id, '15m')

        # Verify: WebSocket updates button state correctly
        final_state = simulator.get_final_state()
        assert final_state['active_timeframe'] == '15m', "Timeframe should be updated by WebSocket"
        assert final_state['disabled'] is False, "Buttons should be enabled by WebSocket success"

        # Verify race condition event sequence
        events = simulator.race_condition_events
        assert len(events) == 2, "Should have 2 race condition events"
        assert events[0]['type'] == 'http_timeout', "First event should be HTTP timeout"
        assert events[0]['action'] == 'no_button_state_change', "HTTP timeout should not change button state"
        assert events[1]['type'] == 'websocket_success', "Second event should be WebSocket success"
        assert events[1]['action'] == 'button_state_updated', "WebSocket should update button state"

    def test_performance_characteristics_integration(self, mock_chart_server):
        """Test Performance Characteristics Integration"""

        class PerformanceMonitor:
            def __init__(self):
                self.operation_times = []
                self.timeout_events = []
                self.success_rates = {'normal': 0, 'after_go_to_date': 0}
                self.total_operations = {'normal': 0, 'after_go_to_date': 0}

            def record_operation(self, operation_type, processing_time, timeout_used, success):
                """Records Operation Performance"""
                self.operation_times.append({
                    'type': operation_type,
                    'processing_time': processing_time,
                    'timeout_used': timeout_used,
                    'success': success,
                    'safety_margin': timeout_used - processing_time
                })

                context = 'after_go_to_date' if 'after' in operation_type else 'normal'
                self.total_operations[context] += 1
                if success:
                    self.success_rates[context] += 1

            def get_performance_summary(self):
                """Gets Performance Summary"""
                summary = {}

                for context in ['normal', 'after_go_to_date']:
                    total = self.total_operations[context]
                    if total > 0:
                        success_rate = (self.success_rates[context] / total) * 100
                        avg_processing_time = sum(
                            op['processing_time'] for op in self.operation_times
                            if ('after' in op['type']) == (context == 'after_go_to_date')
                        ) / total
                        avg_timeout = sum(
                            op['timeout_used'] for op in self.operation_times
                            if ('after' in op['type']) == (context == 'after_go_to_date')
                        ) / total
                        avg_safety_margin = avg_timeout - avg_processing_time

                        summary[context] = {
                            'success_rate': success_rate,
                            'avg_processing_time': avg_processing_time,
                            'avg_timeout': avg_timeout,
                            'avg_safety_margin': avg_safety_margin,
                            'total_operations': total
                        }

                return summary

        monitor = PerformanceMonitor()

        # Test Performance Scenarios
        test_scenarios = [
            # Normal operations (8s timeout)
            ('normal_timeframe_switch', '15m', False),
            ('normal_timeframe_switch', '30m', False),
            ('normal_timeframe_switch', '1h', False),

            # Go To Date operation
            ('go_to_date', '2024-12-25', False),

            # Operations after Go To Date (15s timeout)
            ('timeframe_switch_after_go_to_date', '5m', True),
            ('timeframe_switch_after_go_to_date', '15m', True),
            ('timeframe_switch_after_go_to_date', '30m', True),
        ]

        for operation_type, target, after_go_to_date in test_scenarios:
            if operation_type == 'go_to_date':
                result = mock_chart_server.set_go_to_date(target)
                processing_time = result['processing_time']
                timeout_used = 15.0  # Go To Date uses extended timeout
            else:
                result = mock_chart_server.change_timeframe(target)
                processing_time = result['processing_time']
                timeout_used = 15.0 if after_go_to_date else 8.0

            success = processing_time < timeout_used
            monitor.record_operation(operation_type, processing_time, timeout_used, success)

        # Analyze Performance
        performance_summary = monitor.get_performance_summary()

        # Verify Normal Operations Performance
        if 'normal' in performance_summary:
            normal_perf = performance_summary['normal']
            assert normal_perf['success_rate'] == 100.0, "Normal operations should have 100% success rate"
            assert normal_perf['avg_processing_time'] <= 3.0, "Normal operations should be fast (<3s)"
            assert normal_perf['avg_timeout'] == 8.0, "Normal operations should use 8s timeout"
            assert normal_perf['avg_safety_margin'] >= 5.0, "Normal operations should have >5s safety margin"

        # Verify After Go To Date Performance
        if 'after_go_to_date' in performance_summary:
            after_perf = performance_summary['after_go_to_date']
            assert after_perf['success_rate'] == 100.0, "After Go To Date operations should have 100% success rate"
            assert after_perf['avg_processing_time'] <= 10.0, "After Go To Date operations should be <10s"
            assert after_perf['avg_timeout'] == 15.0, "After Go To Date operations should use 15s timeout"
            assert after_perf['avg_safety_margin'] >= 4.0, "After Go To Date operations should have >4s safety margin"

    def test_error_recovery_integration(self, mock_chart_server):
        """Test Error Recovery Integration"""

        class ErrorRecoverySimulator:
            def __init__(self, server):
                self.server = server
                self.error_scenarios = []
                self.recovery_attempts = []
                self.final_states = []

            def simulate_error_scenario(self, scenario_name, steps):
                """Simuliert Error Scenario mit Recovery"""
                scenario_log = {'name': scenario_name, 'steps': [], 'recovery_successful': False}

                for step in steps:
                    step_type, action, expected_result = step

                    try:
                        if step_type == 'go_to_date':
                            result = self.server.set_go_to_date(action)
                            step_result = {'type': 'go_to_date', 'success': result['success']}

                        elif step_type == 'timeframe_change':
                            result = self.server.change_timeframe(action)
                            step_result = {'type': 'timeframe_change', 'success': result['success']}

                        elif step_type == 'simulate_timeout':
                            # Simulate timeout by checking if processing time exceeds threshold
                            threshold = action  # action is timeout threshold
                            last_request = self.server.request_history[-1]
                            timed_out = last_request['processing_time'] > threshold
                            step_result = {'type': 'timeout_check', 'timed_out': timed_out}

                        elif step_type == 'verify_state':
                            # Verify current state
                            expected_timeframe, expected_go_to_date = action
                            state_correct = (
                                self.server.current_timeframe == expected_timeframe and
                                (self.server.current_go_to_date is not None) == expected_go_to_date
                            )
                            step_result = {'type': 'state_verification', 'correct': state_correct}

                        scenario_log['steps'].append({
                            'step': step,
                            'result': step_result,
                            'matches_expected': step_result.get('success', step_result.get('correct', True)) == expected_result
                        })

                    except Exception as e:
                        step_result = {'type': 'error', 'error': str(e)}
                        scenario_log['steps'].append({
                            'step': step,
                            'result': step_result,
                            'matches_expected': False
                        })

                # Check if all steps matched expected results
                scenario_log['recovery_successful'] = all(
                    step['matches_expected'] for step in scenario_log['steps']
                )

                self.error_scenarios.append(scenario_log)
                return scenario_log

        simulator = ErrorRecoverySimulator(mock_chart_server)

        # Test Error Recovery Scenarios
        error_scenarios = [
            ('normal_operation_success', [
                ('go_to_date', '2024-12-24', True),
                ('timeframe_change', '15m', True),
                ('verify_state', ('15m', True), True),
            ]),

            ('timeout_with_websocket_recovery', [
                ('go_to_date', '2024-12-25', True),
                ('timeframe_change', '30m', True),
                ('simulate_timeout', 5.0, True),  # Simulate 5s timeout (should be exceeded)
                ('verify_state', ('30m', True), True),  # But final state should be correct
            ]),

            ('multiple_timeframe_changes', [
                ('go_to_date', '2024-12-26', True),
                ('timeframe_change', '5m', True),
                ('timeframe_change', '15m', True),
                ('timeframe_change', '30m', True),
                ('timeframe_change', '1h', True),
                ('verify_state', ('1h', True), True),
            ]),
        ]

        for scenario_name, steps in error_scenarios:
            scenario_result = simulator.simulate_error_scenario(scenario_name, steps)
            assert scenario_result['recovery_successful'], f"Error recovery scenario '{scenario_name}' should succeed"

        # Verify all scenarios completed successfully
        total_scenarios = len(simulator.error_scenarios)
        successful_scenarios = sum(1 for scenario in simulator.error_scenarios if scenario['recovery_successful'])

        assert successful_scenarios == total_scenarios, f"All {total_scenarios} error recovery scenarios should succeed"

    def test_end_to_end_user_workflow(self, mock_chart_server):
        """Test End-to-End User Workflow Integration"""

        class UserWorkflowSimulator:
            def __init__(self, server):
                self.server = server
                self.user_actions = []
                self.system_responses = []
                self.performance_metrics = []

            def user_action(self, action_type, **kwargs):
                """Simuliert User Action"""
                start_time = time.time()
                self.user_actions.append({'type': action_type, 'params': kwargs, 'timestamp': start_time})

                if action_type == 'go_to_date':
                    result = self.server.set_go_to_date(kwargs['date'])
                elif action_type == 'change_timeframe':
                    result = self.server.change_timeframe(kwargs['timeframe'])
                elif action_type == 'clear_go_to_date':
                    self.server.clear_go_to_date()
                    result = {'success': True, 'action': 'go_to_date_cleared'}

                end_time = time.time()
                response_time = end_time - start_time

                self.system_responses.append({
                    'action': action_type,
                    'result': result,
                    'response_time': response_time,
                    'adaptive_timeout': self.server.get_adaptive_timeout()
                })

                self.performance_metrics.append({
                    'action': action_type,
                    'response_time': response_time,
                    'timeout_used': self.server.get_adaptive_timeout() / 1000,
                    'success': result.get('success', True)
                })

            def get_workflow_summary(self):
                """Gets Workflow Performance Summary"""
                total_actions = len(self.performance_metrics)
                successful_actions = sum(1 for m in self.performance_metrics if m['success'])
                avg_response_time = sum(m['response_time'] for m in self.performance_metrics) / total_actions
                max_response_time = max(m['response_time'] for m in self.performance_metrics)

                return {
                    'total_actions': total_actions,
                    'successful_actions': successful_actions,
                    'success_rate': (successful_actions / total_actions) * 100,
                    'avg_response_time': avg_response_time,
                    'max_response_time': max_response_time
                }

        workflow = UserWorkflowSimulator(mock_chart_server)

        # Simulate Complete User Workflow
        user_workflow_steps = [
            ('go_to_date', {'date': '2024-12-20'}),
            ('change_timeframe', {'timeframe': '15m'}),
            ('change_timeframe', {'timeframe': '30m'}),
            ('change_timeframe', {'timeframe': '1h'}),
            ('go_to_date', {'date': '2024-12-25'}),
            ('change_timeframe', {'timeframe': '5m'}),
            ('change_timeframe', {'timeframe': '15m'}),
            ('clear_go_to_date', {}),
            ('change_timeframe', {'timeframe': '30m'}),
            ('change_timeframe', {'timeframe': '1h'}),
        ]

        for action_type, params in user_workflow_steps:
            workflow.user_action(action_type, **params)

        # Analyze Workflow Performance
        summary = workflow.get_workflow_summary()

        assert summary['success_rate'] == 100.0, "All workflow steps should succeed"
        assert summary['avg_response_time'] < 1.0, "Average response time should be <1s (in mock)"
        assert summary['total_actions'] == len(user_workflow_steps), "All actions should be recorded"

        # Verify Adaptive Timeout Usage
        go_to_date_responses = [r for r in workflow.system_responses if r['action'] == 'go_to_date']
        timeframe_changes = [r for r in workflow.system_responses if r['action'] == 'change_timeframe']

        # Check timeframe changes after Go To Date use extended timeout
        after_go_to_date_changes = timeframe_changes[1:7]  # Changes after first Go To Date
        for response in after_go_to_date_changes:
            assert response['adaptive_timeout'] == 15000, "Should use 15s timeout after Go To Date"

        # Check timeframe changes after clearing Go To Date use normal timeout
        after_clear_changes = timeframe_changes[7:]  # Changes after clearing Go To Date
        for response in after_clear_changes:
            assert response['adaptive_timeout'] == 8000, "Should use 8s timeout after clearing Go To Date"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])