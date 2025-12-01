"""Tests for strategy definition and performance tracking"""

import pytest
from datetime import datetime
from falcon.strategy import (
    ScreeningStrategy,
    ScreenFilters,
    StrategyPerformance,
    TradingBias,
    TradingStyle,
    PREDEFINED_STRATEGIES,
)


class TestScreenFilters:
    """Test ScreenFilters dataclass"""

    def test_empty_filters(self):
        """Test empty filters to_dict excludes None values"""
        filters = ScreenFilters()
        assert filters.to_dict() == {}

    def test_partial_filters(self):
        """Test partial filters only include set values"""
        filters = ScreenFilters(
            price_min=10.0,
            volume_min=1_000_000
        )
        result = filters.to_dict()
        assert result == {
            "price_min": 10.0,
            "volume_min": 1_000_000
        }

    def test_all_filters(self):
        """Test all filters are included"""
        filters = ScreenFilters(
            price_min=5.0,
            price_max=100.0,
            volume_min=500_000,
            volume_max=10_000_000,
            avg_volume_min=1_000_000,
            market_cap_min=100_000_000,
            market_cap_max=1_000_000_000,
            price_change_min=-5.0,
            price_change_max=15.0,
            volatility_min=0.2,
            volatility_max=2.0,
        )
        result = filters.to_dict()
        assert len(result) == 11
        assert result["price_min"] == 5.0
        assert result["volatility_max"] == 2.0


class TestStrategyPerformance:
    """Test StrategyPerformance tracking"""

    def test_default_performance(self):
        """Test default performance metrics"""
        perf = StrategyPerformance()
        assert perf.total_runs == 0
        assert perf.successful_picks == 0
        assert perf.failed_picks == 0
        assert perf.avg_return == 0.0
        assert perf.last_run is None
        assert perf.last_result_count == 0
        assert perf.success_rate == 0.0

    def test_update_run(self):
        """Test run update increments counters"""
        perf = StrategyPerformance()
        perf.update_run(result_count=5)

        assert perf.total_runs == 1
        assert perf.last_result_count == 5
        assert perf.last_run is not None

        # Verify timestamp format
        datetime.fromisoformat(perf.last_run)

    def test_record_successful_result(self):
        """Test recording successful pick"""
        perf = StrategyPerformance()
        perf.record_result(successful=True, return_pct=5.5)

        assert perf.successful_picks == 1
        assert perf.failed_picks == 0
        assert perf.avg_return == 5.5
        assert perf.success_rate == 100.0

    def test_record_failed_result(self):
        """Test recording failed pick"""
        perf = StrategyPerformance()
        perf.record_result(successful=False, return_pct=-3.2)

        assert perf.successful_picks == 0
        assert perf.failed_picks == 1
        assert perf.avg_return == -3.2
        assert perf.success_rate == 0.0

    def test_multiple_results_avg_return(self):
        """Test average return calculation over multiple picks"""
        perf = StrategyPerformance()
        perf.record_result(successful=True, return_pct=10.0)
        perf.record_result(successful=True, return_pct=5.0)
        perf.record_result(successful=False, return_pct=-2.0)

        assert perf.successful_picks == 2
        assert perf.failed_picks == 1
        # Average: (10 + 5 - 2) / 3 = 4.33...
        assert abs(perf.avg_return - 4.333) < 0.01
        # Success rate: 2/3 = 66.67%
        assert abs(perf.success_rate - 66.67) < 0.1

    def test_to_dict(self):
        """Test converting performance to dict"""
        perf = StrategyPerformance(
            total_runs=5,
            successful_picks=3,
            failed_picks=2,
            avg_return=2.5,
            last_run="2025-12-01T10:00:00",
            last_result_count=10,
        )
        result = perf.to_dict()

        assert result["total_runs"] == 5
        assert result["successful_picks"] == 3
        assert result["avg_return"] == 2.5

    def test_from_dict(self):
        """Test creating performance from dict"""
        data = {
            "total_runs": 10,
            "successful_picks": 6,
            "failed_picks": 4,
            "avg_return": 1.5,
            "last_run": "2025-12-01T10:00:00",
            "last_result_count": 15,
        }
        perf = StrategyPerformance.from_dict(data)

        assert perf.total_runs == 10
        assert perf.successful_picks == 6
        assert perf.success_rate == 60.0


class TestScreeningStrategy:
    """Test ScreeningStrategy definition"""

    def test_minimal_strategy(self):
        """Test creating minimal strategy"""
        strategy = ScreeningStrategy(
            name="test_strategy",
            description="Test strategy",
            scan_code="TOP_PERC_GAIN",
        )

        assert strategy.name == "test_strategy"
        assert strategy.scan_code == "TOP_PERC_GAIN"
        assert strategy.bias == TradingBias.NEUTRAL
        assert strategy.style == TradingStyle.CUSTOM
        assert strategy.enabled is True
        assert strategy.tags == []

    def test_full_strategy(self):
        """Test creating full strategy with all fields"""
        filters = ScreenFilters(price_min=10.0, price_max=100.0)
        perf = StrategyPerformance(total_runs=5)

        strategy = ScreeningStrategy(
            name="full_strategy",
            description="Full test strategy",
            scan_code="HOT_BY_VOLUME",
            filters=filters,
            bias=TradingBias.LONG,
            style=TradingStyle.MOMENTUM,
            instrument="STK",
            location_code="STK.US",
            performance=perf,
            enabled=False,
            tags=["test", "momentum"],
        )

        assert strategy.bias == TradingBias.LONG
        assert strategy.style == TradingStyle.MOMENTUM
        assert strategy.enabled is False
        assert len(strategy.tags) == 2
        assert strategy.performance.total_runs == 5

    def test_to_dict(self):
        """Test converting strategy to dict"""
        strategy = ScreeningStrategy(
            name="test",
            description="Test",
            scan_code="TOP_PERC_GAIN",
            bias=TradingBias.SHORT,
            style=TradingStyle.MEAN_REVERSION,
            tags=["short", "fade"],
        )

        result = strategy.to_dict()

        assert result["name"] == "test"
        assert result["scan_code"] == "TOP_PERC_GAIN"
        assert result["bias"] == "short"
        assert result["style"] == "mean_reversion"
        assert "created" in result
        assert "modified" in result
        assert "filters" in result
        assert "performance" in result

    def test_from_dict(self):
        """Test creating strategy from dict"""
        data = {
            "name": "from_dict",
            "description": "From dict test",
            "scan_code": "MOST_ACTIVE",
            "filters": {"price_min": 5.0, "volume_min": 1_000_000},
            "bias": "long",
            "style": "breakout",
            "instrument": "STK",
            "location_code": "STK.US",
            "performance": {
                "total_runs": 3,
                "successful_picks": 2,
                "failed_picks": 1,
                "avg_return": 2.0,
                "last_run": None,
                "last_result_count": 0,
            },
            "created": "2025-12-01T00:00:00",
            "modified": "2025-12-01T01:00:00",
            "enabled": True,
            "tags": ["test"],
        }

        strategy = ScreeningStrategy.from_dict(data)

        assert strategy.name == "from_dict"
        assert strategy.bias == TradingBias.LONG
        assert strategy.style == TradingStyle.BREAKOUT
        assert strategy.filters.price_min == 5.0
        assert strategy.performance.total_runs == 3
        assert strategy.tags == ["test"]

    def test_update_modified(self):
        """Test updating modified timestamp"""
        strategy = ScreeningStrategy(
            name="test",
            description="Test",
            scan_code="TOP_PERC_GAIN",
        )

        original_modified = strategy.modified
        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)

        strategy.update_modified()

        assert strategy.modified != original_modified
        # Verify new timestamp is valid
        datetime.fromisoformat(strategy.modified)


class TestPredefinedStrategies:
    """Test predefined strategies"""

    def test_all_strategies_exist(self):
        """Test all expected predefined strategies exist"""
        expected = {
            "momentum_long",
            "short_bias",
            "high_volume_breakout",
            "high_volatility",
        }
        assert set(PREDEFINED_STRATEGIES.keys()) == expected

    def test_momentum_long_strategy(self):
        """Test Ross Cameron momentum_long strategy"""
        strategy = PREDEFINED_STRATEGIES["momentum_long"]

        assert strategy.name == "momentum_long"
        assert strategy.scan_code == "TOP_PERC_GAIN"
        assert strategy.bias == TradingBias.LONG
        assert strategy.style == TradingStyle.MOMENTUM
        assert strategy.filters.price_min == 2.0
        assert strategy.filters.price_max == 20.0
        assert strategy.filters.volume_min == 1_000_000
        assert strategy.filters.market_cap_min == 10_000_000
        assert strategy.filters.market_cap_max == 500_000_000
        assert "ross_cameron" in strategy.tags

    def test_short_bias_strategy(self):
        """Test Alex Temiz short_bias strategy"""
        strategy = PREDEFINED_STRATEGIES["short_bias"]

        assert strategy.name == "short_bias"
        # Critical: Should be TOP_PERC_GAIN (fade parabolic gainers)
        assert strategy.scan_code == "TOP_PERC_GAIN"
        assert strategy.bias == TradingBias.SHORT
        assert strategy.style == TradingStyle.MEAN_REVERSION
        assert strategy.filters.price_min == 1.0
        assert strategy.filters.price_max == 30.0
        assert strategy.filters.volume_min == 2_000_000
        assert strategy.filters.market_cap_min == 5_000_000
        assert strategy.filters.market_cap_max == 300_000_000
        assert "alex_temiz" in strategy.tags

    def test_high_volume_breakout_strategy(self):
        """Test high_volume_breakout strategy"""
        strategy = PREDEFINED_STRATEGIES["high_volume_breakout"]

        assert strategy.name == "high_volume_breakout"
        assert strategy.scan_code == "HOT_BY_VOLUME"
        assert strategy.bias == TradingBias.LONG
        assert strategy.style == TradingStyle.BREAKOUT

    def test_high_volatility_strategy(self):
        """Test high_volatility strategy"""
        strategy = PREDEFINED_STRATEGIES["high_volatility"]

        assert strategy.name == "high_volatility"
        assert strategy.scan_code == "HIGH_OPT_IMP_VOLAT"
        assert strategy.bias == TradingBias.NEUTRAL
        assert strategy.style == TradingStyle.VOLATILITY

    def test_all_strategies_enabled(self):
        """Test all predefined strategies are enabled by default"""
        for name, strategy in PREDEFINED_STRATEGIES.items():
            assert strategy.enabled is True, f"{name} should be enabled"

    def test_all_strategies_have_filters(self):
        """Test all predefined strategies have price/volume filters"""
        for name, strategy in PREDEFINED_STRATEGIES.items():
            filters = strategy.filters.to_dict()
            assert "price_min" in filters, f"{name} should have price_min"
            assert "volume_min" in filters, f"{name} should have volume_min"
