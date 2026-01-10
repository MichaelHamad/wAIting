"""Tests for the __main__ entry point."""

from unittest.mock import MagicMock, patch

import pytest

from waiting.__main__ import main


class TestMain:
    """Test the main entry point."""

    def test_main_no_args_shows_help(self, capsys):
        """Test main() with no args shows help."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.show_help.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main([])

            mock_cli.show_help.assert_called_once()
            assert exit_code == 0

    def test_main_help_flag_shows_help(self, capsys):
        """Test main() with --help shows help."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.show_help.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main(["--help"])

            mock_cli.show_help.assert_called_once()
            assert exit_code == 0

    def test_main_help_short_flag_shows_help(self):
        """Test main() with -h shows help."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.show_help.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main(["-h"])

            mock_cli.show_help.assert_called_once()
            assert exit_code == 0

    def test_main_help_word_shows_help(self):
        """Test main() with 'help' shows help."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.show_help.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main(["help"])

            mock_cli.show_help.assert_called_once()
            assert exit_code == 0

    def test_main_enable_command(self):
        """Test main() with 'enable' command."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.enable.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main(["enable"])

            mock_cli.enable.assert_called_once()
            assert exit_code == 0

    def test_main_disable_command(self):
        """Test main() with 'disable' command."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.disable.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main(["disable"])

            mock_cli.disable.assert_called_once()
            assert exit_code == 0

    def test_main_status_command(self):
        """Test main() with 'status' command."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.status.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main(["status"])

            mock_cli.status.assert_called_once()
            assert exit_code == 0

    def test_main_unknown_command_shows_help(self, capsys):
        """Test main() with unknown command shows help and returns error."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.show_help.return_value = 0
            mock_cli_class.return_value = mock_cli

            exit_code = main(["unknown"])

            captured = capsys.readouterr()
            assert "Unknown command" in captured.err
            mock_cli.show_help.assert_called_once()

    def test_main_enable_with_error_returns_error_code(self):
        """Test main() returns error code from CLI command."""
        with patch("waiting.__main__.CLI") as mock_cli_class:
            mock_cli = MagicMock()
            mock_cli.enable.return_value = 1
            mock_cli_class.return_value = mock_cli

            exit_code = main(["enable"])

            assert exit_code == 1

    def test_main_with_none_args_uses_sys_argv(self):
        """Test main() with None args defaults to sys.argv[1:]."""
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["waiting", "status"]

            with patch("waiting.__main__.CLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.status.return_value = 0
                mock_cli_class.return_value = mock_cli

                exit_code = main(None)

                mock_cli.status.assert_called_once()
                assert exit_code == 0
        finally:
            sys.argv = original_argv

    def test_main_empty_with_none_args_shows_help(self):
        """Test main(None) with sys.argv has no command shows help."""
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["waiting"]

            with patch("waiting.__main__.CLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.show_help.return_value = 0
                mock_cli_class.return_value = mock_cli

                exit_code = main(None)

                mock_cli.show_help.assert_called_once()
                assert exit_code == 0
        finally:
            sys.argv = original_argv
