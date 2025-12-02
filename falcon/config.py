"""Configuration management for Falcon"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Only load .env file if not in test mode
if not os.getenv("FALCON_TESTING"):
    load_dotenv()


def _get_host() -> str:
    return os.getenv("IB_HOST", "127.0.0.1")


def _get_port() -> int:
    return int(os.getenv("IB_PORT", "4001"))


def _get_client_id() -> int:
    return int(os.getenv("IB_CLIENT_ID", "1"))


def _get_trading_mode() -> str:
    return os.getenv("TRADING_MODE", "paper")


def _get_account() -> str | None:
    return os.getenv("IB_ACCOUNT")


def _get_location_code() -> str:
    return os.getenv("LOCATION_CODE", "STK.US.MAJOR")


@dataclass
class IBConfig:
    """Interactive Brokers Gateway configuration"""

    host: str = field(default_factory=_get_host)
    port: int = field(default_factory=_get_port)
    client_id: int = field(default_factory=_get_client_id)
    trading_mode: str = field(default_factory=_get_trading_mode)
    account: str | None = field(default_factory=_get_account)
    location_code: str = field(default_factory=_get_location_code)

    @property
    def is_paper_trading(self) -> bool:
        """Check if running in paper trading mode"""
        return self.trading_mode.lower() == "paper"

    def __post_init__(self):
        """Validate configuration"""
        if self.trading_mode.lower() not in ["paper", "live"]:
            raise ValueError("TRADING_MODE must be 'paper' or 'live'")

        # Warn if port doesn't match trading mode convention
        expected_port = 4001 if self.is_paper_trading else 4002
        if self.port != expected_port:
            print(f"Warning: Port {self.port} doesn't match convention for {self.trading_mode} trading (expected {expected_port})")

        # Warn if running in live mode without a specific account configured
        if not self.is_paper_trading and self.account is None:
            print("Warning: Running in live mode without IB_ACCOUNT specified. Will use default account from IB Gateway.")


def get_config() -> IBConfig:
    """Get the current configuration"""
    return IBConfig()
