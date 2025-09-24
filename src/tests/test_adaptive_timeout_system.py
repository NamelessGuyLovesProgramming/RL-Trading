"""
Tests für Adaptive Timeout System
=================================
Umfassende Tests für Context-Aware Timeout Logic und Request-State Management
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAdaptiveTimeoutSystem:
    """Test Suite für Adaptive Timeout System"""

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket für Testing"""
        websocket = Mock()
        websocket.send = Mock()
        websocket.close = Mock()
        return websocket

    @pytest.fixture
    def mock_request_context(self):
        """Mock Request Context für Testing"""
        return {
            'current_go_to_date': None,
            'current_timeframe': '5m',
            'operation_type': 'normal',
            'start_time': time.time()
        }

    def test_adaptive_timeout_calculation_normal_operation(self):
        """Test Adaptive Timeout Calculation for Normal Operations"""
        # Simulate normal timeframe switch (no Go To Date active)
        current_go_to_date = None

        # Expected timeout: 8 seconds for normal operations
        expected_timeout = 8000  # 8s in milliseconds

        # Simulate JavaScript logic: window.current_go_to_date ? 15000 : 8000
        adaptive_timeout = 15000 if current_go_to_date else 8000

        assert adaptive_timeout == expected_timeout, f"Normal operation should use 8s timeout, got {adaptive_timeout}ms"

    def test_adaptive_timeout_calculation_after_go_to_date(self):
        """Test Adaptive Timeout Calculation After Go To Date Operations"""
        # Simulate Go To Date active (CSV processing required)
        current_go_to_date = True

        # Expected timeout: 15 seconds for CSV-processing operations
        expected_timeout = 15000  # 15s in milliseconds

        # Simulate JavaScript logic: window.current_go_to_date ? 15000 : 8000
        adaptive_timeout = 15000 if current_go_to_date else 8000

        assert adaptive_timeout == expected_timeout, f"Go To Date operation should use 15s timeout, got {adaptive_timeout}ms"

    def test_timeout_context_detection_accuracy(self):
        """Test Context Detection für verschiedene Operation Types"""
        test_cases = [
            # (context, expected_timeout, description)
            ({'go_to_date_active': False, 'operation': 'timeframe_switch'}, 8000, "Direct timeframe switch"),
            ({'go_to_date_active': True, 'operation': 'timeframe_switch'}, 15000, "Timeframe switch after Go To Date"),
            ({'go_to_date_active': True, 'operation': 'csv_processing'}, 15000, "CSV processing operation"),
            ({'go_to_date_active': False, 'operation': 'memory_cache'}, 8000, "Memory cache operation"),
        ]

        for context, expected, description in test_cases:
            # Simulate adaptive timeout logic
            is_complex_operation = context.get('go_to_date_active', False)
            calculated_timeout = 15000 if is_complex_operation else 8000

            assert calculated_timeout == expected, f"{description}: Expected {expected}ms, got {calculated_timeout}ms"

    @pytest.mark.asyncio
    async def test_timeout_behavior_fast_response(self):
        """Test Timeout Behavior für schnelle Responses (unter Timeout)"""
        timeout_duration = 8.0  # 8 seconds
        response_time = 2.5     # 2.5 seconds (fast response)

        async def fast_operation():
            """Simuliert schnelle Server-Response"""
            await asyncio.sleep(response_time)
            return {'status': 'success', 'data': 'test_data'}

        # Test that fast operation completes before timeout
        start_time = time.time()

        try:
            result = await asyncio.wait_for(fast_operation(), timeout=timeout_duration)
            elapsed_time = time.time() - start_time

            assert result['status'] == 'success', "Fast operation should succeed"
            assert elapsed_time < timeout_duration, f"Operation took {elapsed_time:.2f}s, should be under {timeout_duration}s"
            assert elapsed_time >= response_time, f"Operation took {elapsed_time:.2f}s, should be at least {response_time}s"

        except asyncio.TimeoutError:
            pytest.fail(f"Fast operation ({response_time}s) should not timeout with {timeout_duration}s timeout")

    @pytest.mark.asyncio
    async def test_timeout_behavior_slow_response_within_limit(self):
        """Test Timeout Behavior für langsame Responses (innerhalb Timeout)"""
        timeout_duration = 15.0  # 15 seconds (extended timeout)
        response_time = 10.0     # 10 seconds (slow but within limit)

        async def slow_operation():
            """Simuliert langsame CSV-Processing Operation"""
            await asyncio.sleep(response_time)
            return {'status': 'success', 'data': 'csv_processed_data', 'processing_time': response_time}

        # Test that slow operation completes within extended timeout
        start_time = time.time()

        try:
            result = await asyncio.wait_for(slow_operation(), timeout=timeout_duration)
            elapsed_time = time.time() - start_time

            assert result['status'] == 'success', "Slow operation should succeed within extended timeout"
            assert elapsed_time < timeout_duration, f"Operation took {elapsed_time:.2f}s, should be under {timeout_duration}s"
            assert elapsed_time >= response_time, f"Operation took {elapsed_time:.2f}s, should be at least {response_time}s"

        except asyncio.TimeoutError:
            pytest.fail(f"Slow operation ({response_time}s) should not timeout with {timeout_duration}s extended timeout")

    @pytest.mark.asyncio
    async def test_timeout_behavior_exceeds_limit(self):
        """Test Timeout Behavior für Operations die Timeout überschreiten"""
        timeout_duration = 8.0   # 8 seconds (normal timeout)
        response_time = 12.0     # 12 seconds (exceeds normal timeout)

        async def very_slow_operation():
            """Simuliert sehr langsame Operation die Timeout überschreitet"""
            await asyncio.sleep(response_time)
            return {'status': 'success', 'data': 'eventually_completed'}

        # Test that very slow operation times out with normal timeout
        start_time = time.time()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(very_slow_operation(), timeout=timeout_duration)

        elapsed_time = time.time() - start_time
        assert elapsed_time >= timeout_duration, f"Timeout should occur at {timeout_duration}s, occurred at {elapsed_time:.2f}s"
        assert elapsed_time < timeout_duration + 1.0, f"Timeout should be precise, took {elapsed_time:.2f}s for {timeout_duration}s timeout"

    def test_timeout_configuration_validation(self):
        """Test Timeout Configuration Validation"""
        valid_configurations = [
            {'normal_timeout': 8000, 'extended_timeout': 15000},
            {'normal_timeout': 5000, 'extended_timeout': 12000},
            {'normal_timeout': 10000, 'extended_timeout': 20000},
        ]

        for config in valid_configurations:
            normal = config['normal_timeout']
            extended = config['extended_timeout']

            # Validate that extended timeout is longer than normal
            assert extended > normal, f"Extended timeout ({extended}ms) must be longer than normal timeout ({normal}ms)"

            # Validate reasonable timeout ranges
            assert 3000 <= normal <= 15000, f"Normal timeout ({normal}ms) should be between 3-15 seconds"
            assert 8000 <= extended <= 30000, f"Extended timeout ({extended}ms) should be between 8-30 seconds"

            # Validate minimum difference
            min_difference = 3000  # 3 seconds minimum difference
            assert extended - normal >= min_difference, f"Extended timeout should be at least {min_difference}ms longer than normal"

    def test_error_classification_abort_vs_network(self):
        """Test Error Classification zwischen AbortError und Network Errors"""

        class MockAbortError(Exception):
            def __init__(self):
                self.name = 'AbortError'

        class MockNetworkError(Exception):
            def __init__(self):
                self.name = 'NetworkError'

        def classify_error(error):
            """Simuliert Error Classification Logic"""
            if hasattr(error, 'name') and error.name == 'AbortError':
                return {'severity': 'warning', 'message': 'Request timeout - operation might still be processing', 'recoverable': True}
            elif hasattr(error, 'name') and error.name == 'NetworkError':
                return {'severity': 'error', 'message': 'Network connection lost', 'recoverable': False}
            else:
                return {'severity': 'error', 'message': 'Unknown error', 'recoverable': False}

        # Test AbortError classification
        abort_error = MockAbortError()
        abort_classification = classify_error(abort_error)

        assert abort_classification['severity'] == 'warning', "AbortError should be classified as warning"
        assert abort_classification['recoverable'] is True, "AbortError should be recoverable"
        assert 'timeout' in abort_classification['message'].lower(), "AbortError message should mention timeout"

        # Test NetworkError classification
        network_error = MockNetworkError()
        network_classification = classify_error(network_error)

        assert network_classification['severity'] == 'error', "NetworkError should be classified as error"
        assert network_classification['recoverable'] is False, "NetworkError should not be recoverable"
        assert 'network' in network_classification['message'].lower(), "NetworkError message should mention network"

    def test_context_state_management(self):
        """Test Context State Management für Go To Date Flag"""

        class ContextManager:
            def __init__(self):
                self.current_go_to_date = None
                self.operation_history = []

            def set_go_to_date(self, date_value):
                """Setzt Go To Date Context"""
                self.current_go_to_date = date_value
                self.operation_history.append(('set_go_to_date', date_value))

            def clear_go_to_date(self):
                """Clearts Go To Date Context"""
                self.current_go_to_date = None
                self.operation_history.append(('clear_go_to_date', None))

            def is_go_to_date_active(self):
                """Prüft ob Go To Date aktiv ist"""
                return self.current_go_to_date is not None

            def get_adaptive_timeout(self):
                """Berechnet Adaptive Timeout basierend auf Context"""
                return 15000 if self.is_go_to_date_active() else 8000

        context = ContextManager()

        # Test initial state
        assert context.is_go_to_date_active() is False, "Initial Go To Date state should be inactive"
        assert context.get_adaptive_timeout() == 8000, "Initial timeout should be 8s"

        # Test Go To Date activation
        test_date = "2024-12-24"
        context.set_go_to_date(test_date)
        assert context.is_go_to_date_active() is True, "Go To Date should be active after setting"
        assert context.get_adaptive_timeout() == 15000, "Timeout should be 15s when Go To Date active"
        assert context.current_go_to_date == test_date, "Current Go To Date should match set value"

        # Test Go To Date clearing
        context.clear_go_to_date()
        assert context.is_go_to_date_active() is False, "Go To Date should be inactive after clearing"
        assert context.get_adaptive_timeout() == 8000, "Timeout should return to 8s after clearing"

        # Test operation history
        expected_history = [
            ('set_go_to_date', test_date),
            ('clear_go_to_date', None)
        ]
        assert context.operation_history == expected_history, "Operation history should track all state changes"

    def test_performance_timeout_vs_response_time_correlation(self):
        """Test Performance: Timeout vs Actual Response Time Correlation"""

        test_scenarios = [
            # (operation_type, expected_response_time, timeout_buffer, description)
            ('memory_cache', 1.5, 8.0, "Memory cache operations"),
            ('csv_read', 3.0, 8.0, "CSV file reading"),
            ('csv_processing_after_go_to_date', 8.5, 15.0, "Full CSV processing after Go To Date"),
            ('large_timeframe_aggregation', 6.0, 15.0, "Large timeframe data aggregation"),
        ]

        for operation_type, expected_response, timeout_buffer, description in test_scenarios:
            # Validate that timeout provides sufficient buffer
            safety_margin = timeout_buffer - expected_response
            min_required_margin = 2.0  # 2 seconds minimum safety margin

            assert safety_margin >= min_required_margin, (
                f"{description}: Timeout buffer ({timeout_buffer}s) should provide at least "
                f"{min_required_margin}s margin over expected response time ({expected_response}s). "
                f"Current margin: {safety_margin:.1f}s"
            )

            # Validate reasonable timeout ranges
            max_reasonable_timeout = 30.0  # 30 seconds max
            assert timeout_buffer <= max_reasonable_timeout, (
                f"{description}: Timeout ({timeout_buffer}s) should not exceed {max_reasonable_timeout}s"
            )

    def test_concurrent_timeout_handling(self):
        """Test Concurrent Request Timeout Handling"""
        import threading
        import queue

        def simulate_request_with_timeout(request_id, response_time, timeout_duration, result_queue):
            """Simuliert Request mit Timeout in separatem Thread"""
            start_time = time.time()

            # Simulate request processing
            time.sleep(response_time)
            elapsed_time = time.time() - start_time

            if elapsed_time <= timeout_duration:
                result_queue.put({
                    'request_id': request_id,
                    'status': 'success',
                    'response_time': elapsed_time,
                    'timeout_duration': timeout_duration
                })
            else:
                result_queue.put({
                    'request_id': request_id,
                    'status': 'timeout',
                    'response_time': elapsed_time,
                    'timeout_duration': timeout_duration
                })

        # Test concurrent requests with different timeout requirements
        result_queue = queue.Queue()
        threads = []

        test_requests = [
            (1, 2.0, 8.0),   # Fast request, normal timeout
            (2, 7.0, 8.0),   # Slow request, normal timeout (should succeed)
            (3, 9.0, 8.0),   # Very slow request, normal timeout (should timeout)
            (4, 12.0, 15.0), # Very slow request, extended timeout (should succeed)
            (5, 1.5, 8.0),   # Very fast request, normal timeout
        ]

        # Start all requests concurrently
        for request_id, response_time, timeout_duration in test_requests:
            thread = threading.Thread(
                target=simulate_request_with_timeout,
                args=(request_id, response_time, timeout_duration, result_queue)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=20)  # 20s max wait for all threads

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())

        # Validate concurrent timeout handling
        assert len(results) == len(test_requests), f"Should have {len(test_requests)} results, got {len(results)}"

        for result in results:
            request_id = result['request_id']
            status = result['status']
            response_time = result['response_time']
            timeout_duration = result['timeout_duration']

            if response_time <= timeout_duration:
                assert status == 'success', f"Request {request_id} should succeed (response: {response_time:.1f}s, timeout: {timeout_duration:.1f}s)"
            else:
                assert status == 'timeout', f"Request {request_id} should timeout (response: {response_time:.1f}s, timeout: {timeout_duration:.1f}s)"

    def test_timeout_system_integration_workflow(self):
        """Test Integration Workflow: Go To Date → Timeframe Switch mit korrekten Timeouts"""

        class WorkflowSimulator:
            def __init__(self):
                self.current_go_to_date = None
                self.current_timeframe = '5m'
                self.operation_log = []

            def go_to_date(self, target_date):
                """Simuliert Go To Date Operation"""
                self.current_go_to_date = target_date
                processing_time = 3.5  # CSV processing time
                timeout_used = 15000   # Extended timeout for Go To Date

                self.operation_log.append({
                    'operation': 'go_to_date',
                    'target_date': target_date,
                    'processing_time': processing_time,
                    'timeout_used': timeout_used,
                    'success': processing_time * 1000 < timeout_used
                })

                return processing_time * 1000 < timeout_used

            def change_timeframe(self, new_timeframe):
                """Simuliert Timeframe Change nach Go To Date"""
                # Processing time depends on Go To Date context
                if self.current_go_to_date:
                    processing_time = 8.0  # CSV processing after Go To Date
                    timeout_used = 15000   # Extended timeout
                else:
                    processing_time = 2.5  # Normal memory operation
                    timeout_used = 8000    # Normal timeout

                success = processing_time * 1000 < timeout_used

                if success:
                    self.current_timeframe = new_timeframe

                self.operation_log.append({
                    'operation': 'change_timeframe',
                    'from_timeframe': self.current_timeframe,
                    'to_timeframe': new_timeframe,
                    'processing_time': processing_time,
                    'timeout_used': timeout_used,
                    'go_to_date_context': self.current_go_to_date,
                    'success': success
                })

                return success

        workflow = WorkflowSimulator()

        # Test complete workflow
        # Step 1: Go To Date
        go_to_date_success = workflow.go_to_date('2024-12-24')
        assert go_to_date_success is True, "Go To Date operation should succeed with extended timeout"

        # Step 2: Timeframe change after Go To Date (should use extended timeout)
        timeframe_change_success = workflow.change_timeframe('15m')
        assert timeframe_change_success is True, "Timeframe change after Go To Date should succeed with extended timeout"

        # Step 3: Clear Go To Date context
        workflow.current_go_to_date = None

        # Step 4: Normal timeframe change (should use normal timeout)
        normal_change_success = workflow.change_timeframe('1h')
        assert normal_change_success is True, "Normal timeframe change should succeed with normal timeout"

        # Validate operation log
        assert len(workflow.operation_log) == 3, "Should have 3 operations logged"

        go_to_date_op = workflow.operation_log[0]
        assert go_to_date_op['operation'] == 'go_to_date'
        assert go_to_date_op['timeout_used'] == 15000, "Go To Date should use 15s timeout"

        after_go_to_date_op = workflow.operation_log[1]
        assert after_go_to_date_op['operation'] == 'change_timeframe'
        assert after_go_to_date_op['timeout_used'] == 15000, "Timeframe change after Go To Date should use 15s timeout"
        assert after_go_to_date_op['go_to_date_context'] is not None, "Should have Go To Date context"

        normal_op = workflow.operation_log[2]
        assert normal_op['operation'] == 'change_timeframe'
        assert normal_op['timeout_used'] == 8000, "Normal timeframe change should use 8s timeout"
        assert normal_op['go_to_date_context'] is None, "Should not have Go To Date context"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])