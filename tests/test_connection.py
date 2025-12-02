"""Tests for connection module"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from falcon.config import IBConfig
from falcon.connection import IBConnection


@pytest.mark.unit
class TestIBConnectionInit:
    """Tests for IBConnection initialization"""

    def test_init(self, mock_env_vars):
        """Test IBConnection initialization"""
        config = IBConfig()
        conn = IBConnection(config)

        assert conn.config == config
        assert conn.ib is not None
        assert conn._connected is False


@pytest.mark.unit
class TestIBConnectionConnect:
    """Tests for connection establishment"""

    async def test_successful_connection(self, mock_env_vars, mock_ib):
        """Test successful connection to IB Gateway"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            result = await conn.connect()

        assert result is True
        assert conn._connected is True
        mock_ib.connectAsync.assert_called_once_with(
            host="127.0.0.1",
            port=4001,
            clientId=1,
            timeout=10
        )

    async def test_failed_connection(self, mock_env_vars):
        """Test failed connection to IB Gateway"""
        config = IBConfig()
        mock_ib = MagicMock()
        mock_ib.connectAsync = AsyncMock(side_effect=ConnectionRefusedError("Connection refused"))

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            result = await conn.connect()

        assert result is False
        assert conn._connected is False

    async def test_connect_with_custom_timeout(self, mock_env_vars, mock_ib):
        """Test connection with default timeout"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            await conn.connect()

        # Verify timeout parameter is passed
        call_kwargs = mock_ib.connectAsync.call_args.kwargs
        assert call_kwargs["timeout"] == 10


@pytest.mark.unit
class TestIBConnectionDisconnect:
    """Tests for disconnection"""

    async def test_disconnect_when_connected(self, mock_env_vars, mock_ib):
        """Test disconnection when connected"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            await conn.disconnect()

        assert conn._connected is False
        mock_ib.disconnect.assert_called_once()

    async def test_disconnect_when_not_connected(self, mock_env_vars, mock_ib):
        """Test disconnection when not connected"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = False
            await conn.disconnect()

        # Should not call disconnect on IB
        mock_ib.disconnect.assert_not_called()


@pytest.mark.unit
class TestIBConnectionStatus:
    """Tests for connection status"""

    def test_is_connected_true(self, mock_env_vars, mock_ib):
        """Test is_connected when connected"""
        config = IBConfig()
        mock_ib.isConnected.return_value = True

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True

            assert conn.is_connected is True

    def test_is_connected_false_not_flagged(self, mock_env_vars, mock_ib):
        """Test is_connected when internal flag is false"""
        config = IBConfig()
        mock_ib.isConnected.return_value = True

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = False

            assert conn.is_connected is False

    def test_is_connected_false_ib_not_connected(self, mock_env_vars, mock_ib):
        """Test is_connected when IB reports not connected"""
        config = IBConfig()
        mock_ib.isConnected.return_value = False

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True

            assert conn.is_connected is False


@pytest.mark.unit
class TestIBConnectionAccounts:
    """Tests for account retrieval"""

    def test_get_accounts_success(self, mock_env_vars, mock_ib):
        """Test successful account retrieval"""
        config = IBConfig()
        mock_ib.managedAccounts.return_value = ["DUE692582", "DUE692583"]

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            accounts = conn.get_accounts()

        assert accounts == ["DUE692582", "DUE692583"]
        mock_ib.managedAccounts.assert_called_once()

    def test_get_accounts_not_connected(self, mock_env_vars, mock_ib):
        """Test get_accounts when not connected"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = False

            with pytest.raises(ConnectionError, match="Not connected to IB Gateway"):
                conn.get_accounts()


@pytest.mark.unit
class TestIBConnectionAccountSummary:
    """Tests for account summary retrieval"""

    async def test_get_account_summary_with_account(self, mock_env_vars, mock_ib):
        """Test getting account summary with specified account"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            summary = await conn.get_account_summary("DUE692582")

        assert summary["account"] == "DUE692582"
        assert summary["trading_mode"] == "paper"
        assert summary["AccountType"] == "INDIVIDUAL"
        assert summary["NetLiquidation"] == "1033883.10"
        mock_ib.accountSummaryAsync.assert_called_once_with("DUE692582")

    async def test_get_account_summary_default_account(self, mock_env_vars, mock_ib):
        """Test getting account summary with default (first) account"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            summary = await conn.get_account_summary()

        assert summary["account"] == "DUE692582"
        mock_ib.accountSummaryAsync.assert_called_once_with("DUE692582")

    async def test_get_account_summary_configured_account(self, monkeypatch, mock_ib):
        """Test getting account summary with configured account from config"""
        monkeypatch.setenv("IB_ACCOUNT", "U1234567")
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            summary = await conn.get_account_summary()

        # Should use configured account, not the first from managedAccounts
        assert summary["account"] == "U1234567"
        mock_ib.accountSummaryAsync.assert_called_once_with("U1234567")

    async def test_get_account_summary_configured_account_overrides_default(self, monkeypatch, mock_ib):
        """Test that configured account takes precedence over first available account"""
        monkeypatch.setenv("IB_ACCOUNT", "U7654321")
        mock_ib.managedAccounts.return_value = ["DUE692582", "U7654321", "U9999999"]
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            summary = await conn.get_account_summary()

        # Should use configured account U7654321, not first account DUE692582
        assert summary["account"] == "U7654321"
        mock_ib.accountSummaryAsync.assert_called_once_with("U7654321")

    async def test_get_account_summary_not_connected(self, mock_env_vars, mock_ib):
        """Test get_account_summary when not connected"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = False

            with pytest.raises(ConnectionError, match="Not connected to IB Gateway"):
                await conn.get_account_summary()

    async def test_get_account_summary_no_accounts(self, mock_env_vars, mock_ib):
        """Test get_account_summary when no accounts available"""
        config = IBConfig()
        mock_ib.managedAccounts.return_value = []

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            with pytest.raises(ValueError, match="No accounts available"):
                await conn.get_account_summary()


@pytest.mark.unit
class TestIBConnectionAccountUpdates:
    """Tests for account updates subscription"""

    async def test_subscribe_account_updates_default_account(self, mock_env_vars, mock_ib):
        """Test subscribing to account updates with default (first) account"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            await conn.subscribe_account_updates()

        mock_ib.reqAccountUpdates.assert_called_once_with("DUE692582")

    async def test_subscribe_account_updates_configured_account(self, monkeypatch, mock_ib):
        """Test subscribing to account updates with configured account"""
        monkeypatch.setenv("IB_ACCOUNT", "U1234567")
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            await conn.subscribe_account_updates()

        # Should use configured account, not the first from managedAccounts
        mock_ib.reqAccountUpdates.assert_called_once_with("U1234567")

    async def test_subscribe_account_updates_explicit_account(self, mock_env_vars, mock_ib):
        """Test subscribing to account updates with explicitly specified account"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            await conn.subscribe_account_updates("EXPLICIT123")

        # Explicit account parameter should override configured account
        mock_ib.reqAccountUpdates.assert_called_once_with("EXPLICIT123")

    async def test_subscribe_account_updates_not_connected(self, mock_env_vars, mock_ib):
        """Test subscribe_account_updates when not connected"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = False

            with pytest.raises(ConnectionError, match="Not connected to IB Gateway"):
                await conn.subscribe_account_updates()

    async def test_subscribe_account_updates_no_accounts(self, mock_env_vars, mock_ib):
        """Test subscribe_account_updates when no accounts available"""
        config = IBConfig()
        mock_ib.managedAccounts.return_value = []

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            with pytest.raises(ValueError, match="No accounts available"):
                await conn.subscribe_account_updates()


@pytest.mark.unit
class TestIBConnectionEdgeCases:
    """Tests for edge cases and error handling"""

    async def test_multiple_connections(self, mock_env_vars, mock_ib):
        """Test connecting multiple times"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)

            # First connection
            result1 = await conn.connect()
            assert result1 is True

            # Second connection (should work)
            result2 = await conn.connect()
            assert result2 is True

            # connectAsync should be called twice
            assert mock_ib.connectAsync.call_count == 2

    async def test_get_account_summary_filters_tags(self, mock_env_vars, mock_ib, sample_account_data):
        """Test that only requested tags are included in summary"""
        config = IBConfig()

        with patch("falcon.connection.IB", return_value=mock_ib):
            conn = IBConnection(config)
            conn._connected = True
            mock_ib.isConnected.return_value = True

            summary = await conn.get_account_summary()

            # Check that summary includes expected fields
            expected_tags = [
                "AccountType", "NetLiquidation", "TotalCashValue",
                "BuyingPower", "GrossPositionValue", "AvailableFunds"
            ]

            for tag in expected_tags:
                assert tag in summary, f"Expected tag {tag} not in summary"
