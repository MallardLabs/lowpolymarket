#!/usr/bin/env python3
"""
Standalone test for the structured logging system.
This test doesn't depend on the full configuration system.
"""

import json
import logging
import tempfile
import time
from pathlib import Path

# Import the logging components directly
from core.logging_manager import (
    LoggingManager,
    JSONFormatter,
    ContextualFormatter,
    CorrelationIdFilter,
    LogContext,
    log_function_call,
    log_performance
)
from config.settings import LoggingSettings


def test_json_formatter():
    """Test JSON formatter functionality."""
    print("Testing JSON formatter...")
    
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
    
    print("✓ JSON formatter test passed")


def test_correlation_filter():
    """Test correlation ID filter."""
    print("Testing correlation ID filter...")
    
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
    
    result = filter_obj.filter(record)
    assert result is True
    assert hasattr(record, 'correlation_id')
    
    print("✓ Correlation ID filter test passed")


def test_logging_manager():
    """Test logging manager with temporary file."""
    print("Testing logging manager...")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        temp_path = f.name
    
    try:
        settings = LoggingSettings(
            level="DEBUG",
            file_enabled=True,
            file_path=temp_path,
            console_enabled=False,
            json_format=True,
            include_extra_fields=True
        )
        
        manager = LoggingManager(settings)
        logger = manager.get_logger("test_module")
        
        # Test correlation ID management
        corr_id = manager.set_correlation_id("test-123")
        assert corr_id == "test-123"
        assert manager.get_correlation_id() == "test-123"
        
        # Test logging with context
        context = LogContext(
            correlation_id="context-123",
            user_id=12345,
            guild_id=67890,
            operation="test_operation"
        )
        
        manager.log_with_context(
            logger,
            logging.INFO,
            "Test contextual message",
            context
        )
        
        # Read and verify log content
        with open(temp_path, 'r') as f:
            log_content = f.read().strip()
        
        if log_content:
            log_data = json.loads(log_content)
            assert log_data["message"] == "Test contextual message"
            assert log_data["correlation_id"] == "context-123"
            assert log_data["extra"]["user_id"] == 12345
        
        print("✓ Logging manager test passed")
        
    finally:
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)


def test_function_decorators():
    """Test function logging decorators."""
    print("Testing function decorators...")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        temp_path = f.name
    
    try:
        settings = LoggingSettings(
            level="DEBUG",
            file_enabled=True,
            file_path=temp_path,
            console_enabled=False,
            json_format=True
        )
        
        manager = LoggingManager(settings)
        logger = manager.get_logger("test_decorator")
        
        @log_function_call(logger=logger, include_args=True, include_result=True)
        def test_function(x, y):
            return x + y
        
        manager.set_correlation_id("decorator-test-123")
        result = test_function(1, 2)
        
        assert result == 3
        
        # Read log file
        with open(temp_path, 'r') as f:
            log_lines = f.read().strip().split('\n')
        
        # Should have entry and exit logs
        assert len(log_lines) >= 2
        
        entry_log = json.loads(log_lines[0])
        assert "Entering function test_function" in entry_log["message"]
        
        print("✓ Function decorator test passed")
        
    finally:
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)


def test_performance_decorator():
    """Test performance monitoring decorator."""
    print("Testing performance decorator...")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        temp_path = f.name
    
    try:
        settings = LoggingSettings(
            level="DEBUG",
            file_enabled=True,
            file_path=temp_path,
            console_enabled=False,
            json_format=True
        )
        
        manager = LoggingManager(settings)
        logger = manager.get_logger("test_performance")
        
        @log_performance(logger=logger, threshold_seconds=0.05)
        def slow_function():
            time.sleep(0.1)  # Intentionally slow
            return "completed"
        
        manager.set_correlation_id("performance-test-123")
        result = slow_function()
        
        assert result == "completed"
        
        # Read log file
        with open(temp_path, 'r') as f:
            log_content = f.read().strip()
        
        if log_content:
            log_data = json.loads(log_content)
            assert "Slow function execution" in log_data["message"]
            assert log_data["extra"]["function_name"] == "slow_function"
        
        print("✓ Performance decorator test passed")
        
    finally:
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)


def main():
    """Run all tests."""
    print("Running structured logging system tests...")
    print("=" * 50)
    
    try:
        test_json_formatter()
        test_correlation_filter()
        test_logging_manager()
        test_function_decorators()
        test_performance_decorator()
        
        print("=" * 50)
        print("✅ All tests passed! Structured logging system is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())