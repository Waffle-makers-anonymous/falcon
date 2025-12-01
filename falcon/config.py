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


@dataclass
class IBConfig:
    """Interactive Brokers Gateway configuration"""

    host: str = field(default_factory=_get_host)
    port: int = field(default_factory=_get_port)
    client_id: int = field(default_factory=_get_client_id)
    trading_mode: str = field(default_factory=_get_trading_mode)

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


def get_config() -> IBConfig:
    """Get the current configuration"""
    return IBConfig()
