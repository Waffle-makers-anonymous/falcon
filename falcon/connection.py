"""IB Gateway connection management"""

import asyncio
from typing import Optional
from ib_insync import IB, util
from falcon.config import IBConfig


class IBConnection:
    """Manages connection to Interactive Brokers Gateway"""

    def __init__(self, config: IBConfig):
        self.config = config
        self.ib = IB()
        self._connected = False

    async def connect(self) -> bool:
        """Connect to IB Gateway"""
        try:
            print(f"Connecting to IB Gateway at {self.config.host}:{self.config.port}...")
            print(f"Trading Mode: {self.config.trading_mode.upper()}")

            await self.ib.connectAsync(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.client_id,
                timeout=10
            )

            self._connected = True
            print("Successfully connected to IB Gateway!")
            return True

        except Exception as e:
            print(f"Failed to connect to IB Gateway: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from IB Gateway"""
        if self._connected:
            self.ib.disconnect()
            self._connected = False
            print("Disconnected from IB Gateway")

    @property
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway"""
        return self._connected and self.ib.isConnected()

    def get_accounts(self) -> list[str]:
        """Get list of account IDs"""
        if not self.is_connected:
            raise ConnectionError("Not connected to IB Gateway")
        return self.ib.managedAccounts()

    async def get_account_summary(self, account: Optional[str] = None) -> dict:
        """Get account summary information"""
        if not self.is_connected:
            raise ConnectionError("Not connected to IB Gateway")

        # If no account specified, use the first available account
        if account is None:
            accounts = self.get_accounts()
            if not accounts:
                raise ValueError("No accounts available")
            account = accounts[0]

        # Request account summary
        summary_tags = [
            "AccountType", "NetLiquidation", "TotalCashValue",
            "BuyingPower", "GrossPositionValue", "UnrealizedPnL",
            "RealizedPnL", "AvailableFunds"
        ]

        summary_items = await self.ib.accountSummaryAsync(account)

        # Convert to dictionary
        summary_dict = {
            "account": account,
            "trading_mode": self.config.trading_mode
        }

        for item in summary_items:
            if item.tag in summary_tags:
                summary_dict[item.tag] = item.value

        return summary_dict

    async def subscribe_account_updates(self, account: Optional[str] = None, callback=None):
        """Subscribe to realtime account updates"""
        if not self.is_connected:
            raise ConnectionError("Not connected to IB Gateway")

        if account is None:
            accounts = self.get_accounts()
            if not accounts:
                raise ValueError("No accounts available")
            account = accounts[0]

        # Subscribe to account updates
        self.ib.reqAccountUpdates(account)

        # Set up event handler if callback provided
        if callback:
            self.ib.accountSummaryEvent += callback
