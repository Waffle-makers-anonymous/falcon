"""Pytest configuration and fixtures"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock
from ib_insync import IB, AccountValue


@pytest.fixture(autouse=True)
def set_test_mode(monkeypatch):
    """Set test mode to prevent loading .env file"""
    monkeypatch.setenv("FALCON_TESTING", "1")


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing"""
    monkeypatch.setenv("IB_HOST", "127.0.0.1")
    monkeypatch.setenv("IB_PORT", "4001")
    monkeypatch.setenv("IB_CLIENT_ID", "1")
    monkeypatch.setenv("TRADING_MODE", "paper")


@pytest.fixture
def mock_ib():
    """Create a mock IB instance"""
    mock = MagicMock(spec=IB)
    mock.isConnected.return_value = True
    mock.managedAccounts.return_value = ["DUE692582"]

    # Mock async methods
    mock.connectAsync = AsyncMock(return_value=None)
    mock.accountSummaryAsync = AsyncMock(return_value=[
        AccountValue(account="DUE692582", tag="AccountType", value="INDIVIDUAL", currency="", modelCode=""),
        AccountValue(account="DUE692582", tag="NetLiquidation", value="1033883.10", currency="USD", modelCode=""),
        AccountValue(account="DUE692582", tag="TotalCashValue", value="1031299.27", currency="USD", modelCode=""),
        AccountValue(account="DUE692582", tag="BuyingPower", value="4125197.08", currency="USD", modelCode=""),
        AccountValue(account="DUE692582", tag="AvailableFunds", value="1031299.27", currency="USD", modelCode=""),
        AccountValue(account="DUE692582", tag="GrossPositionValue", value="0.00", currency="USD", modelCode=""),
    ])

    return mock


@pytest.fixture
def sample_account_data():
    """Sample account data for testing"""
    return {
        "account": "DUE692582",
        "trading_mode": "paper",
        "AccountType": "INDIVIDUAL",
        "NetLiquidation": "1033883.10",
        "TotalCashValue": "1031299.27",
        "BuyingPower": "4125197.08",
        "AvailableFunds": "1031299.27",
        "GrossPositionValue": "0.00",
    }
