"""
Tests for the structured logging system.

This module tests:
- JSON formatting
- Correlation ID tracking
- Log rotation
- Function decorators
- Performance monitoring
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.logging_manager import (
    LoggingManager,
    JSONFormatter,
    ContextualFormatter,
    CorrelationIdFilter,
    LogContext,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    log_function_call,
    log_performance
)
from config.settings import LoggingSettings


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def logging_settings(temp_log_file):
    """Create logging settings for testing."""
    return LoggingSettings(
        level="DEBUG",
        file_enabled=True,
        file_path=temp_log_file,
        console_enabled=False,
        json_format=True,
        include_extra_fields=True
    )


@pytest.fixture
def logging_manager(logging_settings):
    """Create a logging manager for testing."""
    return LoggingManager(logging_settings)


class TestJSONFormatter:
    """Test JSON formatter functionality."""
    
    def test_basic_formatting(self):
        """Test basic JSON log formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-123"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test_logger"
        assert log_data["message"] == "Test message"
        assert log_data["correlation_id"] == "test-123"
        assert "timestamp" in log_data
    
    def test_exception_formatting(self):
        """Test exception information in JSON logs."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test exception")
        except Exception:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=True
            )
            record.correlation_id = "error-123"
            
            formatted = formatter.format(record)
            log_data = json.loads(formatted)
            
            assert "exception" in log_data
            assert log_data["exception"]["type"] == "ValueError"
            assert log_data["exception"]["message"] == "Test exception"
            assert "traceback" in log_data["exception"]
    
    def test_extra_fields(self):
        """Test extra fields in JSON logs."""
        formatter = JSONFormatter(include_extra_fields=True)
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test-123"
        record.user_id = 12345
        record.prediction_id = "pred-456"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert "extra" in log_data
        assert log_data["extra"]["user_id"] == 12345
        assert log_data["extra"]["prediction_id"] == "pred-456"


class TestCorrelationIdFilter:
    """Test correlation ID filter functionality."""
    
    def test_adds_correlation_id(self):
        """Test that filter adds correlation ID to records."""
        filter_obj = CorrelationIdFilter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Test without correlation ID
        result = filter_obj.filter(record)
        assert result is True
        assert record.correlation_id == "none"
        
        # Test with correlation ID
        set_correlation_id("test-correlation-123")
        result = filter_obj.filter(record)
        assert result is True
        assert record.correlation_id == "test-correlation-123"
        
        clear_correlation_id()


class TestLoggingManager:
    """Test logging manager functionality."""
    
    def test_initialization(self, logging_manager):
        """Test logging manager initialization."""
        assert logging_manager is not None
        assert isinstance(logging_manager.settings, LoggingSettings)
    
    def test_get_logger(self, logging_manager):
        """Test logger creation and retrieval."""
        logger1 = logging_manager.get_logger("test_module")
        logger2 = logging_manager.get_logger("test_module")
        
        assert logger1 is logger2  # Should return same instance
        assert logger1.name == "test_module"
    
    def test_correlation_id_management(self, logging_manager):
        """Test correlation ID management."""
        # Test setting correlation ID
        corr_id = logging_manager.set_correlation_id("test-123")
        assert corr_id == "test-123"
        assert logging_manager.get_correlation_id() == "test-123"
        
        # Test auto-generation
        auto_id = logging_manager.set_correlation_id()
        assert auto_id is not None
        assert len(auto_id) > 0
        assert logging_manager.get_correlation_id() == auto_id
        
        # Test clearing
        logging_manager.clear_correlation_id()
        assert logging_manager.get_correlation_id() is None
    
    def test_log_with_context(self, logging_manager, temp_log_file):
        """Test contextual logging."""
        logger = logging_manager.get_logger("test_context")
        
        context = LogContext(
            correlation_id="context-123",
            user_id=12345,
            guild_id=67890,
            prediction_id="pred-789",
            operation="test_operation",
            extra={"custom_field": "custom_value"}
        )
        
        logging_manager.log_with_context(
            logger,
            logging.INFO,
            "Test contextual message",
            context,
            additional_field="additional_value"
        )
        
        # Read log file and verify content
        with open(temp_log_file, 'r') as f:
            log_content = f.read()
        
        log_data = json.loads(log_content.strip())
        assert log_data["message"] == "Test contextual message"
        assert log_data["correlation_id"] == "context-123"
        assert log_data["extra"]["user_id"] == 12345
        assert log_data["extra"]["guild_id"] == 67890
        assert log_data["extra"]["prediction_id"] == "pred-789"
        assert log_data["extra"]["operation"] == "test_operation"
        assert log_data["extra"]["custom_field"] == "custom_value"
        assert log_data["extra"]["additional_field"] == "additional_value"


class TestFunctionDecorators:
    """Test function logging decorators."""
    
    def test_sync_function_decorator(self, logging_manager, temp_log_file):
        """Test synchronous function logging decorator."""
        logger = logging_manager.get_logger("test_decorator")
        
        @log_function_call(logger=logger, include_args=True, include_result=True)
        def test_function(x, y, z="default"):
            return x + y
        
        set_correlation_id("decorator-test-123")
        result = test_function(1, 2, z="custom")
        
        assert result == 3
        
        # Read log file and verify entries
        with open(temp_log_file, 'r') as f:
            log_lines = f.read().strip().split('\n')
        
        # Should have entry and exit logs
        assert len(log_lines) >= 2
        
        entry_log = json.loads(log_lines[0])
        exit_log = json.loads(log_lines[1])
        
        assert "Entering function test_function" in entry_log["message"]
        assert entry_log["extra"]["function"] == "test_function"
        assert entry_log["extra"]["args"] == [1, 2]
        assert entry_log["extra"]["kwargs"] == {"z": "custom"}
        
        assert "Exiting function test_function" in exit_log["message"]
        assert exit_log["extra"]["result"] == 3
        assert "duration" in exit_log["extra"]
        
        clear_correlation_id()
    
    @pytest.mark.asyncio
    async def test_async_function_decorator(self, logging_manager, temp_log_file):
        """Test asynchronous function logging decorator."""
        logger = logging_manager.get_logger("test_async_decorator")
        
        @log_function_call(logger=logger, include_args=True, include_result=True)
        async def async_test_function(value):
            await asyncio.sleep(0.01)
            return value * 2
        
        set_correlation_id("async-decorator-test-456")
        result = await async_test_function(5)
        
        assert result == 10
        
        # Read log file and verify entries
        with open(temp_log_file, 'r') as f:
            log_lines = f.read().strip().split('\n')
        
        # Should have entry and exit logs
        assert len(log_lines) >= 2
        
        entry_log = json.loads(log_lines[0])
        exit_log = json.loads(log_lines[1])
        
        assert "Entering async function async_test_function" in entry_log["message"]
        assert entry_log["extra"]["async"] is True
        assert entry_log["extra"]["args"] == [5]
        
        assert "Exiting async function async_test_function" in exit_log["message"]
        assert exit_log["extra"]["result"] == 10
        
        clear_correlation_id()
    
    def test_function_decorator_exception(self, logging_manager, temp_log_file):
        """Test function decorator with exceptions."""
        logger = logging_manager.get_logger("test_exception_decorator")
        
        @log_function_call(logger=logger)
        def failing_function():
            raise ValueError("Test exception")
        
        set_correlation_id("exception-test-789")
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Read log file and verify exception logging
        with open(temp_log_file, 'r') as f:
            log_lines = f.read().strip().split('\n')
        
        # Should have entry and exception logs
        assert len(log_lines) >= 2
        
        exception_log = json.loads(log_lines[-1])
        assert "Exception in function failing_function" in exception_log["message"]
        assert exception_log["extra"]["error"] == "Test exception"
        assert exception_log["extra"]["error_type"] == "ValueError"
        
        clear_correlation_id()


class TestPerformanceDecorator:
    """Test performance monitoring decorator."""
    
    def test_performance_warning(self, logging_manager, temp_log_file):
        """Test performance warning for slow functions."""
        logger = logging_manager.get_logger("test_performance")
        
        @log_performance(logger=logger, threshold_seconds=0.05)
        def slow_function():
            time.sleep(0.1)  # Intentionally slow
            return "completed"
        
        set_correlation_id("performance-test-123")
        result = slow_function()
        
        assert result == "completed"
        
        # Read log file and verify performance warning
        with open(temp_log_file, 'r') as f:
            log_content = f.read().strip()
        
        log_data = json.loads(log_content)
        assert "Slow function execution" in log_data["message"]
        assert log_data["extra"]["function"] == "slow_function"
        assert log_data["extra"]["duration"] > 0.05
        assert log_data["extra"]["threshold"] == 0.05
        
        clear_correlation_id()
    
    def test_no_performance_warning(self, logging_manager, temp_log_file):
        """Test no performance warning for fast functions."""
        logger = logging_manager.get_logger("test_fast_performance")
        
        @log_performance(logger=logger, threshold_seconds=0.1)
        def fast_function():
            time.sleep(0.01)  # Fast function
            return "completed"
        
        set_correlation_id("fast-performance-test-456")
        result = fast_function()
        
        assert result == "completed"
        
        # Read log file - should be empty (no performance warning)
        with open(temp_log_file, 'r') as f:
            log_content = f.read().strip()
        
        assert log_content == ""  # No logs should be written
        
        clear_correlation_id()


class TestGlobalFunctions:
    """Test global logging functions."""
    
    def test_global_logger_functions(self):
        """Test global logger management functions."""
        # Test correlation ID functions
        corr_id = set_correlation_id("global-test-123")
        assert corr_id == "global-test-123"
        assert get_correlation_id() == "global-test-123"
        
        clear_correlation_id()
        assert get_correlation_id() is None
        
        # Test logger creation
        logger = get_logger("global_test_module")
        assert logger.name == "global_test_module"
    
    def test_auto_correlation_id_generation(self):
        """Test automatic correlation ID generation."""
        corr_id = set_correlation_id()
        assert corr_id is not None
        assert len(corr_id) > 0
        assert get_correlation_id() == corr_id
        
        clear_correlation_id()


@pytest.mark.integration
class TestLoggingIntegration:
    """Integration tests for the logging system."""
    
    def test_file_rotation(self, temp_log_file):
        """Test log file rotation functionality."""
        # Create settings with small file size for testing rotation
        settings = LoggingSettings(
            level="DEBUG",
            file_enabled=True,
            file_path=temp_log_file,
            file_max_bytes=1000,  # Small size to trigger rotation
            file_backup_count=2,
            console_enabled=False,
            json_format=True
        )
        
        manager = LoggingManager(settings)
        logger = manager.get_logger("rotation_test")
        
        # Write enough logs to trigger rotation
        for i in range(50):
            logger.info(f"Test log message {i} with some additional content to make it longer")
        
        # Check that backup files were created
        log_path = Path(temp_log_file)
        backup_files = list(log_path.parent.glob(f"{log_path.name}.*"))
        
        # Should have at least one backup file
        assert len(backup_files) > 0
        
        # Cleanup backup files
        for backup_file in backup_files:
            backup_file.unlink()
    
    def test_concurrent_logging(self, logging_manager, temp_log_file):
        """Test concurrent logging with correlation IDs."""
        import threading
        
        def log_worker(worker_id):
            corr_id = set_correlation_id(f"worker-{worker_id}")
            logger = logging_manager.get_logger(f"worker_{worker_id}")
            
            for i in range(10):
                logger.info(f"Worker {worker_id} message {i}", extra={
                    'worker_id': worker_id,
                    'message_number': i
                })
            
            clear_correlation_id()
        
        # Start multiple worker threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=log_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Read log file and verify all messages were logged
        with open(temp_log_file, 'r') as f:
            log_lines = f.read().strip().split('\n')
        
        # Should have 30 log messages (3 workers * 10 messages each)
        assert len(log_lines) == 30
        
        # Verify correlation IDs are correct
        worker_messages = {}
        for line in log_lines:
            log_data = json.loads(line)
            worker_id = log_data['extra']['worker_id']
            if worker_id not in worker_messages:
                worker_messages[worker_id] = []
            worker_messages[worker_id].append(log_data)
        
        # Each worker should have 10 messages
        for worker_id in range(3):
            assert len(worker_messages[worker_id]) == 10
            # All messages from same worker should have same correlation ID
            correlation_ids = [msg['correlation_id'] for msg in worker_messages[worker_id]]
            assert len(set(correlation_ids)) == 1  # All should be the same
            assert correlation_ids[0] == f"worker-{worker_id}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])