"""Tests for screener functionality"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from ib_insync import IB, ScannerSubscription, ScanData, ContractDetails, Contract
from falcon.screener import Screener, ScreenResult
from falcon.connection import IBConnection
from falcon.strategy import (
    ScreeningStrategy,
    ScreenFilters,
    TradingBias,
    TradingStyle,
)


@pytest.fixture
def mock_ib():
    """Create mock IB instance"""
    ib = Mock(spec=IB)
    ib.isConnected.return_value = True
    ib.reqScannerDataAsync = AsyncMock()
    return ib


@pytest.fixture
def mock_connection(mock_ib):
    """Create mock IBConnection"""
    conn = Mock(spec=IBConnection)
    conn.ib = mock_ib
    # is_connected is a property, not a method
    type(conn).is_connected = property(lambda self: True)
    return conn


@pytest.fixture
def sample_strategy():
    """Create sample strategy for testing"""
    return ScreeningStrategy(
        name="test_strategy",
        description="Test strategy",
        scan_code="TOP_PERC_GAIN",
        filters=ScreenFilters(
            price_min=10.0,
            price_max=100.0,
            volume_min=1_000_000,
        ),
        bias=TradingBias.LONG,
        style=TradingStyle.MOMENTUM,
    )


@pytest.fixture
def sample_scan_data():
    """Create sample ScanData for testing"""
    contract = Contract()
    contract.symbol = "AAPL"
    contract.exchange = "NASDAQ"
    contract.primaryExchange = "NASDAQ"
    contract.currency = "USD"
    contract.conId = 12345

    details = ContractDetails()
    details.contract = contract
    details.marketName = "NMS"
    details.minTick = 0.01

    # ScanData requires all parameters in constructor
    scan_data = ScanData(
        rank=1,
        contractDetails=details,
        distance="",
        benchmark="",
        projection="",
        legsStr=""
    )

    return scan_data


class TestScreenResult:
    """Test ScreenResult dataclass"""

    def test_create_screen_result(self):
        """Test creating ScreenResult"""
        result = ScreenResult(
            rank=1,
            symbol="AAPL",
            exchange="NASDAQ",
            currency="USD",
            contract_id=12345,
        )

        assert result.rank == 1
        assert result.symbol == "AAPL"
        assert result.exchange == "NASDAQ"
        assert result.currency == "USD"
        assert result.contract_id == 12345

    def test_screen_result_to_dict(self):
        """Test converting ScreenResult to dict"""
        result = ScreenResult(
            symbol="TSLA",
            rank=2,
            contract_id=67890,
            exchange="NASDAQ",
            currency="USD",
            distance="5.2%",
            benchmark="SP500",
        )

        data = result.to_dict()

        assert data["symbol"] == "TSLA"
        assert data["rank"] == 2
        assert data["contract_id"] == 67890
        assert data["distance"] == "5.2%"
        assert data["benchmark"] == "SP500"


class TestScreener:
    """Test Screener class"""

    def test_init(self, mock_connection):
        """Test screener initialization"""
        screener = Screener(mock_connection)
        assert screener.connection == mock_connection
        assert screener.ib == mock_connection.ib

    def test_create_scanner_subscription(self, mock_connection, sample_strategy):
        """Test creating scanner subscription from strategy"""
        screener = Screener(mock_connection)
        scanner = screener._create_scanner_subscription(sample_strategy)

        assert isinstance(scanner, ScannerSubscription)
        assert scanner.instrument == "STK"
        assert scanner.locationCode == "STK.US"
        assert scanner.scanCode == "TOP_PERC_GAIN"
        assert scanner.abovePrice == 10.0
        assert scanner.belowPrice == 100.0
        assert scanner.aboveVolume == 1_000_000

    def test_create_scanner_subscription_no_filters(self, mock_connection):
        """Test creating scanner subscription without filters"""
        strategy = ScreeningStrategy(
            name="no_filters",
            description="No filters",
            scan_code="MOST_ACTIVE",
        )

        screener = Screener(mock_connection)
        scanner = screener._create_scanner_subscription(strategy)

        assert scanner.scanCode == "MOST_ACTIVE"
        # Scanner uses UNSET values instead of None
        # Just verify the scanner was created successfully
        assert scanner.instrument == "STK"
        assert scanner.locationCode == "STK.US"

    def test_create_scanner_subscription_market_cap(self, mock_connection):
        """Test scanner subscription with market cap filters"""
        strategy = ScreeningStrategy(
            name="market_cap",
            description="Market cap filters",
            scan_code="TOP_PERC_GAIN",
            filters=ScreenFilters(
                market_cap_min=100_000_000,
                market_cap_max=1_000_000_000,
            ),
        )

        screener = Screener(mock_connection)
        scanner = screener._create_scanner_subscription(strategy)

        assert scanner.marketCapAbove == 100_000_000
        assert scanner.marketCapBelow == 1_000_000_000

    @pytest.mark.asyncio
    async def test_run_strategy_not_connected(self, mock_ib, sample_strategy):
        """Test running strategy when not connected raises error"""
        conn = Mock(spec=IBConnection)
        conn.ib = mock_ib
        type(conn).is_connected = property(lambda self: False)

        screener = Screener(conn)

        with pytest.raises(ConnectionError, match="Not connected to IB Gateway"):
            await screener.run_strategy(sample_strategy)

    @pytest.mark.asyncio
    async def test_run_strategy_success(
        self, mock_connection, sample_strategy, sample_scan_data
    ):
        """Test successful strategy execution"""
        mock_connection.ib.reqScannerDataAsync.return_value = [sample_scan_data]

        screener = Screener(mock_connection)
        results = await screener.run_strategy(sample_strategy)

        assert len(results) == 1
        assert results[0].symbol == "AAPL"
        assert results[0].rank == 1
        assert results[0].exchange == "NASDAQ"
        assert results[0].contract_id == 12345

        # Verify scanner was called
        mock_connection.ib.reqScannerDataAsync.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_strategy_empty_results(self, mock_connection, sample_strategy):
        """Test strategy execution with no results"""
        mock_connection.ib.reqScannerDataAsync.return_value = []

        screener = Screener(mock_connection)
        results = await screener.run_strategy(sample_strategy)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_run_strategy_max_results(self, mock_connection, sample_strategy):
        """Test strategy execution respects max_results"""
        # Create multiple scan data items
        scan_data_list = []
        for i in range(10):
            contract = Contract()
            contract.symbol = f"SYM{i}"
            contract.exchange = "NASDAQ"
            contract.primaryExchange = "NASDAQ"
            contract.currency = "USD"
            contract.conId = 10000 + i

            details = ContractDetails()
            details.contract = contract

            # Create ScanData with all required parameters
            scan_data = ScanData(
                rank=i + 1,
                contractDetails=details,
                distance="",
                benchmark="",
                projection="",
                legsStr=""
            )

            scan_data_list.append(scan_data)

        mock_connection.ib.reqScannerDataAsync.return_value = scan_data_list

        screener = Screener(mock_connection)
        results = await screener.run_strategy(sample_strategy, max_results=5)

        # Should only return 5 results
        assert len(results) == 5
        assert results[0].symbol == "SYM0"
        assert results[4].symbol == "SYM4"

    @pytest.mark.asyncio
    async def test_run_strategy_error_handling(self, mock_connection, sample_strategy):
        """Test strategy execution handles errors"""
        mock_connection.ib.reqScannerDataAsync.side_effect = Exception("Scanner error")

        screener = Screener(mock_connection)

        with pytest.raises(Exception, match="Scanner error"):
            await screener.run_strategy(sample_strategy)

    @pytest.mark.asyncio
    async def test_run_multiple_strategies(self, mock_connection, sample_scan_data):
        """Test running multiple strategies"""
        mock_connection.ib.reqScannerDataAsync.return_value = [sample_scan_data]

        strategy1 = ScreeningStrategy(
            name="strategy1",
            description="Strategy 1",
            scan_code="TOP_PERC_GAIN",
        )
        strategy2 = ScreeningStrategy(
            name="strategy2",
            description="Strategy 2",
            scan_code="TOP_PERC_LOSE",
        )

        screener = Screener(mock_connection)
        results = await screener.run_multiple_strategies([strategy1, strategy2])

        assert len(results) == 2
        assert "strategy1" in results
        assert "strategy2" in results
        assert len(results["strategy1"]) == 1
        assert len(results["strategy2"]) == 1

    @pytest.mark.asyncio
    async def test_run_multiple_strategies_some_fail(
        self, mock_connection, sample_scan_data
    ):
        """Test running multiple strategies with some failures"""

        async def side_effect(scanner):
            if scanner.scanCode == "TOP_PERC_GAIN":
                return [sample_scan_data]
            else:
                raise Exception("Scanner error")

        mock_connection.ib.reqScannerDataAsync.side_effect = side_effect

        strategy1 = ScreeningStrategy(
            name="success",
            description="Success",
            scan_code="TOP_PERC_GAIN",
        )
        strategy2 = ScreeningStrategy(
            name="failure",
            description="Failure",
            scan_code="TOP_PERC_LOSE",
        )

        screener = Screener(mock_connection)
        results = await screener.run_multiple_strategies([strategy1, strategy2])

        assert len(results) == 2
        assert len(results["success"]) == 1
        # Failed strategy should return empty list
        assert len(results["failure"]) == 0

    @pytest.mark.asyncio
    async def test_scanner_item_to_result(self, mock_connection, sample_scan_data):
        """Test converting ScanData to ScreenResult"""
        screener = Screener(mock_connection)
        result = screener._scanner_item_to_result(sample_scan_data, rank=1)

        assert isinstance(result, ScreenResult)
        assert result.symbol == "AAPL"
        assert result.exchange == "NASDAQ"
        assert result.rank == 1

    def test_apply_price_filters(self, mock_connection):
        """Test price filters are applied correctly"""
        strategy = ScreeningStrategy(
            name="price_filter",
            description="Price filter test",
            scan_code="MOST_ACTIVE",
            filters=ScreenFilters(
                price_min=5.0,
                price_max=50.0,
            ),
        )

        screener = Screener(mock_connection)
        scanner = screener._create_scanner_subscription(strategy)

        assert scanner.abovePrice == 5.0
        assert scanner.belowPrice == 50.0

    def test_apply_volume_filters(self, mock_connection):
        """Test volume filters are applied correctly"""
        strategy = ScreeningStrategy(
            name="volume_filter",
            description="Volume filter test",
            scan_code="HOT_BY_VOLUME",
            filters=ScreenFilters(
                volume_min=2_000_000,
            ),
        )

        screener = Screener(mock_connection)
        scanner = screener._create_scanner_subscription(strategy)

        assert scanner.aboveVolume == 2_000_000

    @pytest.mark.asyncio
    async def test_strategy_performance_updated(
        self, mock_connection, sample_strategy, sample_scan_data
    ):
        """Test strategy performance is updated after run"""
        mock_connection.ib.reqScannerDataAsync.return_value = [sample_scan_data]

        screener = Screener(mock_connection)

        # Initial performance
        assert sample_strategy.performance.total_runs == 0
        assert sample_strategy.performance.last_result_count == 0

        results = await screener.run_strategy(sample_strategy)

        # Performance should be updated
        assert sample_strategy.performance.total_runs == 1
        assert sample_strategy.performance.last_result_count == 1
        assert sample_strategy.performance.last_run is not None
