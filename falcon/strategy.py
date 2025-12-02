"""Strategy definition and management for stock screening"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class TradingBias(Enum):
    """Trading bias for strategies"""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class TradingStyle(Enum):
    """Trading style categories"""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    VALUE = "value"
    VOLATILITY = "volatility"
    CUSTOM = "custom"


@dataclass
class ScreenFilters:
    """Filtering criteria for stock screening"""

    # Price filters
    price_min: Optional[float] = None
    price_max: Optional[float] = None

    # Volume filters
    volume_min: Optional[int] = None
    volume_max: Optional[int] = None
    avg_volume_min: Optional[int] = None

    # Market cap filters (in USD)
    market_cap_min: Optional[float] = None
    market_cap_max: Optional[float] = None

    # Performance filters
    price_change_min: Optional[float] = None  # Percentage
    price_change_max: Optional[float] = None

    # Volatility filters
    volatility_min: Optional[float] = None
    volatility_max: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class StrategyPerformance:
    """Track strategy performance metrics"""

    total_runs: int = 0
    successful_picks: int = 0
    failed_picks: int = 0
    avg_return: float = 0.0
    last_run: Optional[str] = None
    last_result_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyPerformance':
        return cls(**data)

    def update_run(self, result_count: int):
        """Update metrics after a run"""
        self.total_runs += 1
        self.last_run = datetime.now().isoformat()
        self.last_result_count = result_count

    def record_result(self, successful: bool, return_pct: float):
        """Record the result of a pick"""
        if successful:
            self.successful_picks += 1
        else:
            self.failed_picks += 1

        # Update average return
        total_picks = self.successful_picks + self.failed_picks
        if total_picks > 0:
            self.avg_return = (
                (self.avg_return * (total_picks - 1) + return_pct) / total_picks
            )

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.successful_picks + self.failed_picks
        return (self.successful_picks / total * 100) if total > 0 else 0.0


@dataclass
class ScreeningStrategy:
    """Definition of a stock screening strategy"""

    name: str
    description: str
    scan_code: str
    filters: ScreenFilters = field(default_factory=ScreenFilters)

    # Strategy metadata
    bias: TradingBias = TradingBias.NEUTRAL
    style: TradingStyle = TradingStyle.CUSTOM
    instrument: str = "STK"  # Stock, OPT, FUT, etc.
    location_code: str = "STK.US.MAJOR"  # US major exchanges (NYSE, NASDAQ, AMEX)

    # Performance tracking
    performance: StrategyPerformance = field(default_factory=StrategyPerformance)

    # Metadata
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    modified: str = field(default_factory=lambda: datetime.now().isoformat())
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy to dictionary for persistence"""
        return {
            "name": self.name,
            "description": self.description,
            "scan_code": self.scan_code,
            "filters": self.filters.to_dict(),
            "bias": self.bias.value,
            "style": self.style.value,
            "instrument": self.instrument,
            "location_code": self.location_code,
            "performance": self.performance.to_dict(),
            "created": self.created,
            "modified": self.modified,
            "enabled": self.enabled,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScreeningStrategy':
        """Create strategy from dictionary"""
        # Extract nested objects
        filters_data = data.pop("filters", {})
        performance_data = data.pop("performance", {})

        # Convert enums
        if "bias" in data:
            data["bias"] = TradingBias(data["bias"])
        if "style" in data:
            data["style"] = TradingStyle(data["style"])

        # Create objects
        filters = ScreenFilters(**filters_data)
        performance = StrategyPerformance.from_dict(performance_data)

        return cls(
            filters=filters,
            performance=performance,
            **data
        )

    def update_modified(self):
        """Update the modified timestamp"""
        self.modified = datetime.now().isoformat()


# Predefined strategies
PREDEFINED_STRATEGIES = {
    "momentum_long": ScreeningStrategy(
        name="momentum_long",
        description="Ross Cameron style momentum - Low float, high volume % gainers in $2-$20 range",
        scan_code="TOP_PERC_GAIN",
        filters=ScreenFilters(
            price_min=2.0,
            price_max=20.0,
            volume_min=500_000,  # Reduced from 1M to get more results
            # Removed market cap filters - too restrictive for major exchanges
        ),
        bias=TradingBias.LONG,
        style=TradingStyle.MOMENTUM,
        tags=["momentum", "long", "gainers", "ross_cameron", "day_trading"],
    ),

    "short_bias": ScreeningStrategy(
        name="short_bias",
        description="Alex Temiz style shorts - Overextended parabolic gainers due for pullback",
        scan_code="TOP_PERC_GAIN",  # Looking for stocks that went UP too much
        filters=ScreenFilters(
            price_min=1.0,
            price_max=30.0,
            volume_min=2_000_000,       # High volume = retail interest/pump
            market_cap_min=5_000_000,   # Very small caps for big moves
            market_cap_max=300_000_000, # Not too large - need volatility
        ),
        bias=TradingBias.SHORT,
        style=TradingStyle.MEAN_REVERSION,  # Fading overextended moves
        tags=["short", "overextended", "parabolic", "alex_temiz", "fade"],
    ),

    "high_volume_breakout": ScreeningStrategy(
        name="high_volume_breakout",
        description="Breakout candidates with unusual volume",
        scan_code="HOT_BY_VOLUME",
        filters=ScreenFilters(
            price_min=10.0,
            price_max=200.0,
            volume_min=2_000_000,
        ),
        bias=TradingBias.LONG,
        style=TradingStyle.BREAKOUT,
        tags=["breakout", "volume", "long"],
    ),

    "high_volatility": ScreeningStrategy(
        name="high_volatility",
        description="High option implied volatility - potential for big moves",
        scan_code="HIGH_OPT_IMP_VOLAT",
        filters=ScreenFilters(
            price_min=5.0,
            price_max=500.0,
            volume_min=500_000,
        ),
        bias=TradingBias.NEUTRAL,
        style=TradingStyle.VOLATILITY,
        tags=["volatility", "options"],
    ),
}
