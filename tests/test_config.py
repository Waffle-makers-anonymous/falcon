"""Tests for configuration module"""

import pytest
from falcon.config import IBConfig, get_config


@pytest.mark.unit
class TestIBConfig:
    """Tests for IBConfig dataclass"""

    def test_default_values(self, mock_env_vars):
        """Test that default configuration values are loaded correctly"""
        config = IBConfig()

        assert config.host == "127.0.0.1"
        assert config.port == 4001
        assert config.client_id == 1
        assert config.trading_mode == "paper"

    def test_paper_trading_mode(self, monkeypatch):
        """Test paper trading mode detection"""
        monkeypatch.setenv("TRADING_MODE", "paper")
        config = IBConfig()

        assert config.is_paper_trading is True
        assert config.trading_mode == "paper"

    def test_live_trading_mode(self, monkeypatch):
        """Test live trading mode detection"""
        monkeypatch.setenv("TRADING_MODE", "live")
        config = IBConfig()

        assert config.is_paper_trading is False
        assert config.trading_mode == "live"

    def test_invalid_trading_mode(self, monkeypatch):
        """Test that invalid trading mode raises ValueError"""
        monkeypatch.setenv("TRADING_MODE", "invalid")

        with pytest.raises(ValueError, match="TRADING_MODE must be 'paper' or 'live'"):
            IBConfig()

    def test_port_warning_paper_mode(self, monkeypatch, capsys):
        """Test warning when port doesn't match paper trading convention"""
        monkeypatch.setenv("TRADING_MODE", "paper")
        monkeypatch.setenv("IB_PORT", "4002")

        IBConfig()
        captured = capsys.readouterr()

        assert "Warning" in captured.out
        assert "4002" in captured.out
        assert "4001" in captured.out

    def test_port_warning_live_mode(self, monkeypatch, capsys):
        """Test warning when port doesn't match live trading convention"""
        monkeypatch.setenv("TRADING_MODE", "live")
        monkeypatch.setenv("IB_PORT", "4001")

        IBConfig()
        captured = capsys.readouterr()

        assert "Warning" in captured.out
        assert "4001" in captured.out
        assert "4002" in captured.out

    def test_custom_host(self, monkeypatch, mock_env_vars):
        """Test custom host configuration"""
        monkeypatch.setenv("IB_HOST", "192.168.1.100")
        config = IBConfig()

        assert config.host == "192.168.1.100"

    def test_custom_client_id(self, monkeypatch, mock_env_vars):
        """Test custom client ID configuration"""
        monkeypatch.setenv("IB_CLIENT_ID", "5")
        config = IBConfig()

        assert config.client_id == 5

    def test_get_config_function(self, mock_env_vars):
        """Test get_config helper function"""
        config = get_config()

        assert isinstance(config, IBConfig)
        assert config.host == "127.0.0.1"
        assert config.port == 4001


@pytest.mark.unit
class TestConfigEdgeCases:
    """Test edge cases and error handling"""

    def test_missing_env_vars_use_defaults(self, monkeypatch):
        """Test that missing env vars fall back to defaults"""
        # Clear all env vars
        for key in ["IB_HOST", "IB_PORT", "IB_CLIENT_ID", "TRADING_MODE"]:
            monkeypatch.delenv(key, raising=False)

        config = IBConfig()

        assert config.host == "127.0.0.1"
        assert config.port == 4001
        assert config.client_id == 1
        assert config.trading_mode == "paper"

    def test_port_as_string(self, monkeypatch, mock_env_vars):
        """Test that port string is converted to int"""
        monkeypatch.setenv("IB_PORT", "7497")
        config = IBConfig()

        assert config.port == 7497
        assert isinstance(config.port, int)

    def test_client_id_as_string(self, monkeypatch, mock_env_vars):
        """Test that client_id string is converted to int"""
        monkeypatch.setenv("IB_CLIENT_ID", "10")
        config = IBConfig()

        assert config.client_id == 10
        assert isinstance(config.client_id, int)
