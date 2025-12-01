"""Tests for main application module"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from falcon.main import display_account_info


@pytest.mark.unit
class TestDisplayAccountInfo:
    """Tests for display_account_info function"""

    async def test_display_account_info_success(self, mock_env_vars, mock_ib, sample_account_data, capsys):
        """Test successful account info display"""
        from falcon.connection import IBConnection
        from falcon.config import IBConfig

        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            await display_account_info(conn)

        captured = capsys.readouterr()

        # Check that output contains key information
        assert "DUE692582" in captured.out
        assert "ACCOUNT SUMMARY" in captured.out
        assert "PAPER" in captured.out
        assert "INDIVIDUAL" in captured.out

    async def test_display_account_info_handles_error(self, mock_env_vars, mock_ib, capsys):
        """Test that display_account_info handles errors gracefully"""
        from falcon.connection import IBConnection
        from falcon.config import IBConfig

        config = IBConfig()
        mock_ib.managedAccounts.side_effect = Exception("Test error")

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            await display_account_info(conn)

        captured = capsys.readouterr()

        # Should print error message without crashing
        assert "Error" in captured.out


@pytest.mark.unit
class TestMainModule:
    """Tests for main module components"""

    def test_main_module_imports(self):
        """Test that main module can be imported"""
        import falcon.main

        assert hasattr(falcon.main, "main")
        assert hasattr(falcon.main, "display_account_info")
