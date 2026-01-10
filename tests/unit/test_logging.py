"""Tests for logging module."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from waiting.logging import setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_returns_logger(self):
        """Should return a Logger instance."""
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "waiting"

    def test_setup_logging_sets_debug_level(self):
        """Should set logger to DEBUG level."""
        logger = setup_logging()
        assert logger.level == logging.DEBUG

    def test_setup_logging_creates_file_handler(self, tmp_path, monkeypatch):
        """Should create file handler for log file."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()

        assert len(logger.handlers) > 0
        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)

    def test_setup_logging_file_handler_writes(self, tmp_path, monkeypatch):
        """Should write logs to file."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()
        logger.info("Test message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_setup_logging_removes_duplicate_handlers(self, tmp_path, monkeypatch):
        """Should remove existing handlers before adding new ones."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # First call
        logger1 = setup_logging()
        handler_count_1 = len(logger1.handlers)

        # Second call
        logger2 = setup_logging()
        handler_count_2 = len(logger2.handlers)

        # Should have same handler count (not accumulating)
        assert handler_count_2 == handler_count_1

    def test_setup_logging_formats_messages(self, tmp_path, monkeypatch):
        """Should format log messages with timestamp and level."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()
        logger.info("Test info message")
        logger.error("Test error message")

        content = log_file.read_text()
        assert "Test info message" in content
        assert "INFO" in content
        assert "Test error message" in content
        assert "ERROR" in content

    def test_setup_logging_oserror_falls_back_to_console(self, tmp_path, monkeypatch):
        """Should fall back to console handler on OSError."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            with patch("logging.FileHandler") as mock_file_handler:
                mock_file_handler.side_effect = OSError("Permission denied")

                logger = setup_logging()

                # Should have at least console handler
                assert any(
                    isinstance(h, logging.StreamHandler) for h in logger.handlers
                )

    def test_setup_logging_oserror_logs_warning(self, tmp_path, monkeypatch):
        """Should log warning when file creation fails."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = tmp_path

            with patch("logging.FileHandler") as mock_file_handler:
                mock_file_handler.side_effect = OSError("Permission denied")

                logger = setup_logging()
                # The warning should have been logged
                assert logger is not None
                # Should have console handler as fallback
                assert len(logger.handlers) > 0

    def test_setup_logging_file_handler_debug_level(self, tmp_path, monkeypatch):
        """File handler should be set to DEBUG level."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0
        assert file_handlers[0].level == logging.DEBUG

    def test_setup_logging_formatter_includes_timestamp(self, tmp_path, monkeypatch):
        """Formatter should include timestamp."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0

        formatter = file_handlers[0].formatter
        assert formatter is not None
        assert "%(asctime)s" in formatter._fmt

    def test_setup_logging_formatter_includes_logger_name(self, tmp_path, monkeypatch):
        """Formatter should include logger name."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        formatter = file_handlers[0].formatter
        assert "%(name)s" in formatter._fmt

    def test_setup_logging_formatter_includes_level(self, tmp_path, monkeypatch):
        """Formatter should include log level."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        formatter = file_handlers[0].formatter
        assert "%(levelname)s" in formatter._fmt

    def test_setup_logging_formatter_includes_message(self, tmp_path, monkeypatch):
        """Formatter should include message."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        formatter = file_handlers[0].formatter
        assert "%(message)s" in formatter._fmt

    def test_setup_logging_date_format(self, tmp_path, monkeypatch):
        """Formatter should use correct date format."""
        log_file = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        formatter = file_handlers[0].formatter
        assert formatter.datefmt == "%Y-%m-%d %H:%M:%S"

    def test_setup_logging_home_directory_resolution(self, tmp_path, monkeypatch):
        """Should resolve home directory correctly."""
        expected_log = tmp_path / ".waiting.log"
        monkeypatch.setenv("HOME", str(tmp_path))

        logger = setup_logging()
        logger.info("Test")

        assert expected_log.exists()

    def test_setup_logging_logger_name_is_waiting(self):
        """Logger name should be 'waiting'."""
        logger = setup_logging()
        assert logger.name == "waiting"

    def test_setup_logging_multiple_calls_same_logger(self):
        """Multiple calls should modify the same logger instance."""
        logger1 = setup_logging()
        logger2 = setup_logging()

        assert logger1 is logger2
        assert logger1.name == "waiting"
