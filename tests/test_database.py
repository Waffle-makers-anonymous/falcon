"""Tests for database functionality"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from falcon.database import ScreenDatabase, ScreenRun, StoredScreenResult
from falcon.strategy import (
    ScreeningStrategy,
    ScreenFilters,
    TradingBias,
    TradingStyle,
)
from falcon.screener import ScreenResult


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield ScreenDatabase(str(db_path))


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
def sample_results():
    """Create sample screen results"""
    return [
        ScreenResult(
            symbol="AAPL",
            rank=1,
            contract_id=12345,
            exchange="NASDAQ",
            currency="USD",
            distance="5.2%",
        ),
        ScreenResult(
            symbol="TSLA",
            rank=2,
            contract_id=67890,
            exchange="NASDAQ",
            currency="USD",
            distance="3.1%",
        ),
    ]


class TestDatabaseInit:
    """Test database initialization"""

    def test_init_creates_db_file(self):
        """Test that database file is created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = ScreenDatabase(str(db_path))

            assert db_path.exists()

    def test_init_creates_parent_dirs(self):
        """Test that parent directories are created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "dir" / "test.db"
            db = ScreenDatabase(str(db_path))

            assert db_path.exists()
            assert db_path.parent.exists()

    def test_schema_tables_created(self, temp_db):
        """Test that schema tables are created"""
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()

            # Check tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]

            assert "schema_version" in tables
            assert "screen_runs" in tables
            assert "screen_results" in tables

    def test_indexes_created(self, temp_db):
        """Test that indexes are created"""
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index'
            """)
            indexes = [row[0] for row in cursor.fetchall()]

            assert "idx_screen_runs_strategy" in indexes
            assert "idx_screen_results_run" in indexes
            assert "idx_screen_results_symbol" in indexes


class TestSaveScreenRun:
    """Test saving screen runs"""

    def test_save_screen_run_basic(self, temp_db, sample_strategy, sample_results):
        """Test basic screen run save"""
        run_id = temp_db.save_screen_run(sample_strategy, sample_results)

        assert run_id > 0

        # Verify run was saved
        run = temp_db.get_screen_run(run_id)
        assert run is not None
        assert run.strategy_name == "test_strategy"
        assert run.scan_code == "TOP_PERC_GAIN"
        assert run.result_count == 2

    def test_save_screen_run_with_timestamp(self, temp_db, sample_strategy, sample_results):
        """Test saving with custom timestamp"""
        custom_time = "2025-12-01T10:00:00"
        run_id = temp_db.save_screen_run(
            sample_strategy,
            sample_results,
            executed_at=custom_time
        )

        run = temp_db.get_screen_run(run_id)
        assert run.executed_at == custom_time

    def test_save_screen_run_saves_results(self, temp_db, sample_strategy, sample_results):
        """Test that results are saved with run"""
        run_id = temp_db.save_screen_run(sample_strategy, sample_results)

        results = temp_db.get_screen_results(run_id)
        assert len(results) == 2
        assert results[0].symbol == "AAPL"
        assert results[0].rank == 1
        assert results[1].symbol == "TSLA"
        assert results[1].rank == 2

    def test_save_screen_run_empty_results(self, temp_db, sample_strategy):
        """Test saving run with no results"""
        run_id = temp_db.save_screen_run(sample_strategy, [])

        run = temp_db.get_screen_run(run_id)
        assert run.result_count == 0

        results = temp_db.get_screen_results(run_id)
        assert len(results) == 0

    def test_save_screen_run_stores_filters(self, temp_db, sample_strategy, sample_results):
        """Test that strategy filters are stored"""
        run_id = temp_db.save_screen_run(sample_strategy, sample_results)

        run = temp_db.get_screen_run(run_id)
        assert run.filters is not None
        assert run.filters["price_min"] == 10.0
        assert run.filters["volume_min"] == 1_000_000


class TestRetrieveScreenRuns:
    """Test retrieving screen runs"""

    def test_get_screen_run_not_exists(self, temp_db):
        """Test getting non-existent run returns None"""
        run = temp_db.get_screen_run(999)
        assert run is None

    def test_get_recent_runs(self, temp_db, sample_strategy, sample_results):
        """Test getting recent runs"""
        # Create multiple runs
        for i in range(5):
            temp_db.save_screen_run(sample_strategy, sample_results)

        runs = temp_db.get_recent_runs(limit=3)
        assert len(runs) == 3

        # Should be in reverse chronological order
        for i in range(len(runs) - 1):
            assert runs[i].executed_at >= runs[i + 1].executed_at

    def test_get_recent_runs_by_strategy(self, temp_db, sample_results):
        """Test filtering recent runs by strategy"""
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

        # Create runs for both strategies
        temp_db.save_screen_run(strategy1, sample_results)
        temp_db.save_screen_run(strategy1, sample_results)
        temp_db.save_screen_run(strategy2, sample_results)

        # Get only strategy1 runs
        runs = temp_db.get_recent_runs(strategy_name="strategy1")
        assert len(runs) == 2
        assert all(r.strategy_name == "strategy1" for r in runs)

    def test_get_runs_by_date_range(self, temp_db, sample_strategy, sample_results):
        """Test getting runs by date range"""
        # Create runs at different times
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        today = datetime.now().isoformat()
        tomorrow = (datetime.now() + timedelta(days=1)).isoformat()

        temp_db.save_screen_run(sample_strategy, sample_results, yesterday)
        temp_db.save_screen_run(sample_strategy, sample_results, today)

        # Query range that includes both
        runs = temp_db.get_runs_by_date_range(yesterday, tomorrow)
        assert len(runs) == 2

        # Query range that includes only today
        runs = temp_db.get_runs_by_date_range(today, tomorrow)
        assert len(runs) == 1


class TestSymbolTracking:
    """Test symbol tracking and analysis"""

    def test_get_symbol_appearances(self, temp_db, sample_strategy):
        """Test tracking symbol appearances"""
        # Create runs where AAPL appears multiple times
        for i in range(3):
            results = [
                ScreenResult(
                    symbol="AAPL",
                    rank=1,
                    contract_id=12345,
                    exchange="NASDAQ",
                    currency="USD",
                )
            ]
            temp_db.save_screen_run(sample_strategy, results)

        appearances = temp_db.get_symbol_appearances("AAPL", days_back=30)
        assert len(appearances) == 3

        # Each appearance should have run and result
        for run, result in appearances:
            assert run.strategy_name == "test_strategy"
            assert result.symbol == "AAPL"

    def test_get_symbol_appearances_no_results(self, temp_db):
        """Test getting appearances for symbol that doesn't exist"""
        appearances = temp_db.get_symbol_appearances("NONEXISTENT", days_back=30)
        assert len(appearances) == 0

    def test_get_top_symbols(self, temp_db, sample_strategy):
        """Test getting most frequently screened symbols"""
        # Create runs with different symbols
        for i in range(3):
            results = [
                ScreenResult(
                    symbol="AAPL",
                    rank=1,
                    contract_id=12345,
                    exchange="NASDAQ",
                    currency="USD",
                )
            ]
            temp_db.save_screen_run(sample_strategy, results)

        for i in range(2):
            results = [
                ScreenResult(
                    symbol="TSLA",
                    rank=1,
                    contract_id=67890,
                    exchange="NASDAQ",
                    currency="USD",
                )
            ]
            temp_db.save_screen_run(sample_strategy, results)

        top_symbols = temp_db.get_top_symbols(days_back=30, limit=10)

        assert len(top_symbols) >= 2
        # AAPL should be first (3 appearances)
        assert top_symbols[0][0] == "AAPL"
        assert top_symbols[0][1] == 3
        # TSLA should be second (2 appearances)
        assert top_symbols[1][0] == "TSLA"
        assert top_symbols[1][1] == 2

    def test_get_top_symbols_by_strategy(self, temp_db):
        """Test filtering top symbols by strategy"""
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

        # AAPL in strategy1
        for i in range(2):
            results = [
                ScreenResult(
                    symbol="AAPL",
                    rank=1,
                    contract_id=12345,
                    exchange="NASDAQ",
                    currency="USD",
                )
            ]
            temp_db.save_screen_run(strategy1, results)

        # TSLA in strategy2
        results = [
            ScreenResult(
                symbol="TSLA",
                rank=1,
                contract_id=67890,
                exchange="NASDAQ",
                currency="USD",
            )
        ]
        temp_db.save_screen_run(strategy2, results)

        # Get top symbols for strategy1 only
        top_symbols = temp_db.get_top_symbols(
            strategy_name="strategy1",
            days_back=30,
            limit=10
        )

        assert len(top_symbols) == 1
        assert top_symbols[0][0] == "AAPL"


class TestBacktesting:
    """Test backtesting functionality"""

    def test_update_result_prices(self, temp_db, sample_strategy, sample_results):
        """Test updating forward-looking prices"""
        run_id = temp_db.save_screen_run(sample_strategy, sample_results)
        results = temp_db.get_screen_results(run_id)

        # Initially no backtesting data
        assert results[0].price_1d_later is None
        assert results[0].return_1d is None

        # Update first result with price at screen time
        with temp_db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE screen_results SET price_at_screen = ? WHERE id = ?",
                (100.0, results[0].id)
            )

        # Update with forward prices
        temp_db.update_result_prices(
            results[0].id,
            price_1d=105.0,
            price_1w=110.0,
            price_1m=95.0
        )

        # Verify prices and returns were calculated
        updated_results = temp_db.get_screen_results(run_id)
        assert updated_results[0].price_1d_later == 105.0
        assert updated_results[0].return_1d == 5.0  # 5% gain
        assert updated_results[0].return_1w == 10.0  # 10% gain
        assert updated_results[0].return_1m == -5.0  # 5% loss

    def test_get_strategy_statistics(self, temp_db, sample_strategy, sample_results):
        """Test getting strategy performance statistics"""
        # Create runs with some backtesting data
        for i in range(3):
            run_id = temp_db.save_screen_run(sample_strategy, sample_results)

            # Add backtesting data to first result
            results = temp_db.get_screen_results(run_id)
            with temp_db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE screen_results SET price_at_screen = ?, return_1d = ? WHERE id = ?",
                    (100.0, 5.0 if i % 2 == 0 else -3.0, results[0].id)
                )

        stats = temp_db.get_strategy_statistics("test_strategy", days_back=30)

        assert stats["strategy_name"] == "test_strategy"
        assert stats["total_runs"] == 3
        assert stats["total_results"] == 6  # 2 results per run
        assert stats["total_with_backtest_data"] == 3
        assert stats["winners_1d"] == 2  # 2 positive returns
        assert stats["losers_1d"] == 1  # 1 negative return

    def test_get_strategy_statistics_no_data(self, temp_db):
        """Test statistics for strategy with no runs"""
        stats = temp_db.get_strategy_statistics("nonexistent", days_back=30)

        assert stats["total_runs"] == 0
        assert stats["total_results"] == 0


class TestDatabaseMaintenance:
    """Test database maintenance operations"""

    def test_delete_old_runs(self, temp_db, sample_strategy, sample_results):
        """Test deleting old runs"""
        # Create old and recent runs
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        recent_date = datetime.now().isoformat()

        temp_db.save_screen_run(sample_strategy, sample_results, old_date)
        temp_db.save_screen_run(sample_strategy, sample_results, recent_date)

        # Delete runs older than 90 days
        deleted_count = temp_db.delete_old_runs(days_to_keep=90)

        assert deleted_count == 1

        # Verify only recent run remains
        runs = temp_db.get_recent_runs(limit=10)
        assert len(runs) == 1
        assert runs[0].executed_at == recent_date

    def test_delete_old_runs_cascades_to_results(self, temp_db, sample_strategy, sample_results):
        """Test that deleting runs also deletes results"""
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        run_id = temp_db.save_screen_run(sample_strategy, sample_results, old_date)

        # Verify results exist
        results = temp_db.get_screen_results(run_id)
        assert len(results) == 2

        # Delete old runs
        temp_db.delete_old_runs(days_to_keep=90)

        # Results should also be deleted
        results = temp_db.get_screen_results(run_id)
        assert len(results) == 0

    def test_delete_old_runs_none_to_delete(self, temp_db):
        """Test deleting when no old runs exist"""
        deleted_count = temp_db.delete_old_runs(days_to_keep=90)
        assert deleted_count == 0


class TestDataclasses:
    """Test dataclass serialization"""

    def test_screen_run_to_dict(self):
        """Test ScreenRun to_dict"""
        run = ScreenRun(
            id=1,
            strategy_name="test",
            scan_code="TOP_PERC_GAIN",
            executed_at="2025-12-01T10:00:00",
            result_count=5,
        )

        data = run.to_dict()
        assert data["id"] == 1
        assert data["strategy_name"] == "test"
        assert data["result_count"] == 5

    def test_stored_screen_result_to_dict(self):
        """Test StoredScreenResult to_dict"""
        result = StoredScreenResult(
            id=1,
            run_id=100,
            symbol="AAPL",
            exchange="NASDAQ",
            contract_id=12345,
            rank=1,
        )

        data = result.to_dict()
        assert data["id"] == 1
        assert data["symbol"] == "AAPL"
        assert data["rank"] == 1
