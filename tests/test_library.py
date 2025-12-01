"""Tests for strategy library"""

import pytest
import json
import tempfile
from pathlib import Path
from falcon.library import StrategyLibrary
from falcon.strategy import (
    ScreeningStrategy,
    ScreenFilters,
    StrategyPerformance,
    TradingBias,
    TradingStyle,
    PREDEFINED_STRATEGIES,
)


@pytest.fixture
def temp_library_path(tmp_path):
    """Create temporary library directory"""
    library_path = tmp_path / "test_strategies"
    library_path.mkdir()
    return str(library_path)


@pytest.fixture
def sample_custom_strategy():
    """Create a sample custom strategy"""
    return ScreeningStrategy(
        name="custom_test",
        description="Custom test strategy",
        scan_code="MOST_ACTIVE",
        filters=ScreenFilters(price_min=10.0, volume_min=1_000_000),
        bias=TradingBias.LONG,
        style=TradingStyle.BREAKOUT,
        tags=["custom", "test"],
    )


class TestStrategyLibraryInit:
    """Test library initialization"""

    def test_init_default_path(self):
        """Test initialization with default path"""
        library = StrategyLibrary()
        assert library.library_path.exists()
        # Should load predefined strategies
        assert len(library) >= len(PREDEFINED_STRATEGIES)

    def test_init_custom_path(self, temp_library_path):
        """Test initialization with custom path"""
        library = StrategyLibrary(temp_library_path)
        assert str(library.library_path) == temp_library_path
        assert library.library_path.exists()

    def test_loads_predefined_strategies(self, temp_library_path):
        """Test that predefined strategies are loaded"""
        library = StrategyLibrary(temp_library_path)

        for name in PREDEFINED_STRATEGIES.keys():
            assert name in library
            assert library.get_strategy(name) is not None


class TestStrategyPersistence:
    """Test saving and loading strategies"""

    def test_save_new_strategy(self, temp_library_path, sample_custom_strategy):
        """Test saving a new strategy"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        # Check file was created
        strategy_file = Path(temp_library_path) / "custom_test.json"
        assert strategy_file.exists()

        # Check strategy is in memory
        assert "custom_test" in library
        assert library.get_strategy("custom_test").name == "custom_test"

    def test_save_existing_strategy_without_overwrite(
        self, temp_library_path, sample_custom_strategy
    ):
        """Test saving existing strategy without overwrite raises error"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        with pytest.raises(FileExistsError, match="already exists"):
            library.save_strategy(sample_custom_strategy, overwrite=False)

    def test_save_existing_strategy_with_overwrite(
        self, temp_library_path, sample_custom_strategy
    ):
        """Test saving existing strategy with overwrite"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        # Modify and save again
        sample_custom_strategy.description = "Updated description"
        library.save_strategy(sample_custom_strategy, overwrite=True)

        # Load and verify update
        loaded = library.get_strategy("custom_test")
        assert loaded.description == "Updated description"

    def test_load_strategy_from_file(self, temp_library_path, sample_custom_strategy):
        """Test loading strategy from file"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        # Create new library instance to test loading from disk
        library2 = StrategyLibrary(temp_library_path)
        loaded = library2.get_strategy("custom_test")

        assert loaded is not None
        assert loaded.name == "custom_test"
        assert loaded.description == "Custom test strategy"
        assert loaded.scan_code == "MOST_ACTIVE"
        assert loaded.bias == TradingBias.LONG
        assert loaded.style == TradingStyle.BREAKOUT

    def test_load_corrupted_strategy_file(self, temp_library_path):
        """Test that corrupted strategy files are skipped with warning"""
        # Create corrupted JSON file
        corrupted_file = Path(temp_library_path) / "corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json ]")

        # Should not raise error, just print warning
        library = StrategyLibrary(temp_library_path)
        assert "corrupted" not in library


class TestStrategyRetrieval:
    """Test retrieving strategies"""

    def test_get_strategy_exists(self, temp_library_path):
        """Test getting existing strategy"""
        library = StrategyLibrary(temp_library_path)
        strategy = library.get_strategy("momentum_long")

        assert strategy is not None
        assert strategy.name == "momentum_long"

    def test_get_strategy_not_exists(self, temp_library_path):
        """Test getting non-existent strategy returns None"""
        library = StrategyLibrary(temp_library_path)
        strategy = library.get_strategy("nonexistent")

        assert strategy is None

    def test_list_all_strategies(self, temp_library_path, sample_custom_strategy):
        """Test listing all strategies"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        strategies = library.list_strategies(enabled_only=False)

        # Should have predefined + custom
        assert len(strategies) >= len(PREDEFINED_STRATEGIES) + 1

    def test_list_strategies_by_bias(self, temp_library_path):
        """Test listing strategies filtered by bias"""
        library = StrategyLibrary(temp_library_path)

        long_strategies = library.list_strategies(bias="long")
        short_strategies = library.list_strategies(bias="short")

        # All returned strategies should match filter
        for strategy in long_strategies:
            assert strategy.bias == TradingBias.LONG

        for strategy in short_strategies:
            assert strategy.bias == TradingBias.SHORT

        # Should have at least momentum_long
        long_names = [s.name for s in long_strategies]
        assert "momentum_long" in long_names

    def test_list_strategies_by_style(self, temp_library_path):
        """Test listing strategies filtered by style"""
        library = StrategyLibrary(temp_library_path)

        momentum_strategies = library.list_strategies(style="momentum")

        for strategy in momentum_strategies:
            assert strategy.style == TradingStyle.MOMENTUM

    def test_list_enabled_only(self, temp_library_path):
        """Test listing only enabled strategies"""
        library = StrategyLibrary(temp_library_path)

        # Create disabled strategy
        disabled_strategy = ScreeningStrategy(
            name="disabled_test",
            description="Disabled",
            scan_code="MOST_ACTIVE",
            enabled=False,
        )
        library.save_strategy(disabled_strategy)

        enabled_strategies = library.list_strategies(enabled_only=True)
        all_strategies = library.list_strategies(enabled_only=False)

        # enabled_strategies should not contain disabled strategy
        enabled_names = [s.name for s in enabled_strategies]
        assert "disabled_test" not in enabled_names

        # all_strategies should contain it
        all_names = [s.name for s in all_strategies]
        assert "disabled_test" in all_names

    def test_get_strategies_by_tag(self, temp_library_path):
        """Test getting strategies by tag"""
        library = StrategyLibrary(temp_library_path)

        # Create strategies with tags
        strategy1 = ScreeningStrategy(
            name="tagged1",
            description="Tagged 1",
            scan_code="MOST_ACTIVE",
            tags=["test", "momentum"],
        )
        strategy2 = ScreeningStrategy(
            name="tagged2",
            description="Tagged 2",
            scan_code="MOST_ACTIVE",
            tags=["test", "breakout"],
        )
        library.save_strategy(strategy1)
        library.save_strategy(strategy2)

        test_strategies = library.get_strategies_by_tag("test")
        momentum_strategies = library.get_strategies_by_tag("momentum")

        assert len(test_strategies) >= 2
        assert len(momentum_strategies) >= 1

        # Check ross_cameron tag exists
        ross_strategies = library.get_strategies_by_tag("ross_cameron")
        assert len(ross_strategies) >= 1


class TestStrategyDeletion:
    """Test deleting strategies"""

    def test_delete_custom_strategy(self, temp_library_path, sample_custom_strategy):
        """Test deleting custom strategy"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        assert "custom_test" in library

        library.delete_strategy("custom_test")

        assert "custom_test" not in library

        # File should be removed
        strategy_file = Path(temp_library_path) / "custom_test.json"
        assert not strategy_file.exists()

    def test_delete_predefined_strategy_fails(self, temp_library_path):
        """Test deleting predefined strategy raises error"""
        library = StrategyLibrary(temp_library_path)

        with pytest.raises(ValueError, match="Cannot delete predefined strategy"):
            library.delete_strategy("momentum_long")

    def test_delete_nonexistent_strategy(self, temp_library_path):
        """Test deleting non-existent strategy raises error"""
        library = StrategyLibrary(temp_library_path)

        with pytest.raises(FileNotFoundError, match="not found"):
            library.delete_strategy("nonexistent")


class TestStrategyUpdate:
    """Test updating strategies"""

    def test_update_existing_strategy(self, temp_library_path, sample_custom_strategy):
        """Test updating an existing strategy"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        # Modify strategy
        sample_custom_strategy.description = "Updated description"
        sample_custom_strategy.filters.price_min = 20.0

        library.update_strategy(sample_custom_strategy)

        # Verify update
        loaded = library.get_strategy("custom_test")
        assert loaded.description == "Updated description"
        assert loaded.filters.price_min == 20.0

    def test_update_nonexistent_strategy(self, temp_library_path):
        """Test updating non-existent strategy raises error"""
        library = StrategyLibrary(temp_library_path)

        strategy = ScreeningStrategy(
            name="nonexistent",
            description="Does not exist",
            scan_code="MOST_ACTIVE",
        )

        with pytest.raises(FileNotFoundError, match="not found"):
            library.update_strategy(strategy)


class TestPerformanceTracking:
    """Test performance-related features"""

    def test_get_top_performing_strategies(self, temp_library_path):
        """Test getting top performing strategies"""
        library = StrategyLibrary(temp_library_path)

        # Create strategies with different performance
        for i in range(5):
            perf = StrategyPerformance(
                total_runs=10,
                successful_picks=10 - i,  # Decreasing success
                failed_picks=i,
            )
            strategy = ScreeningStrategy(
                name=f"perf_test_{i}",
                description=f"Performance test {i}",
                scan_code="MOST_ACTIVE",
                performance=perf,
            )
            library.save_strategy(strategy)

        top_performers = library.get_top_performing_strategies(limit=3, min_runs=5)

        # Should return 3 strategies
        assert len(top_performers) == 3

        # Should be sorted by success rate (descending)
        for i in range(len(top_performers) - 1):
            assert (
                top_performers[i].performance.success_rate
                >= top_performers[i + 1].performance.success_rate
            )

        # Best performer should be first
        assert top_performers[0].name == "perf_test_0"

    def test_get_top_performing_min_runs_filter(self, temp_library_path):
        """Test min_runs filter for top performers"""
        library = StrategyLibrary(temp_library_path)

        # Strategy with few runs
        perf1 = StrategyPerformance(
            total_runs=3,
            successful_picks=3,
            failed_picks=0,
        )
        strategy1 = ScreeningStrategy(
            name="few_runs",
            description="Few runs",
            scan_code="MOST_ACTIVE",
            performance=perf1,
        )
        library.save_strategy(strategy1)

        # Strategy with many runs
        perf2 = StrategyPerformance(
            total_runs=10,
            successful_picks=7,
            failed_picks=3,
        )
        strategy2 = ScreeningStrategy(
            name="many_runs",
            description="Many runs",
            scan_code="MOST_ACTIVE",
            performance=perf2,
        )
        library.save_strategy(strategy2)

        # Should only return strategy with enough runs
        top_performers = library.get_top_performing_strategies(limit=10, min_runs=5)

        names = [s.name for s in top_performers]
        assert "few_runs" not in names
        assert "many_runs" in names


class TestImportExport:
    """Test import/export functionality"""

    def test_export_library(self, temp_library_path, sample_custom_strategy):
        """Test exporting library to JSON"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        export_file = Path(temp_library_path) / "export.json"
        library.export_library(str(export_file))

        assert export_file.exists()

        # Load and verify
        with open(export_file, 'r') as f:
            exported_data = json.load(f)

        # Should contain custom strategy but not predefined ones
        assert "custom_test" in exported_data
        assert "momentum_long" not in exported_data

    def test_import_strategies(self, temp_library_path):
        """Test importing strategies from JSON"""
        # Create export data
        export_data = {
            "imported1": {
                "name": "imported1",
                "description": "Imported 1",
                "scan_code": "MOST_ACTIVE",
                "filters": {},
                "bias": "long",
                "style": "momentum",
                "instrument": "STK",
                "location_code": "STK.US",
                "performance": {
                    "total_runs": 0,
                    "successful_picks": 0,
                    "failed_picks": 0,
                    "avg_return": 0.0,
                    "last_run": None,
                    "last_result_count": 0,
                },
                "created": "2025-12-01T00:00:00",
                "modified": "2025-12-01T00:00:00",
                "enabled": True,
                "tags": [],
            }
        }

        import_file = Path(temp_library_path) / "import.json"
        with open(import_file, 'w') as f:
            json.dump(export_data, f)

        library = StrategyLibrary(temp_library_path)
        library.import_strategies(str(import_file))

        # Verify import
        assert "imported1" in library
        imported = library.get_strategy("imported1")
        assert imported.name == "imported1"
        assert imported.description == "Imported 1"

    def test_import_with_overwrite(self, temp_library_path, sample_custom_strategy):
        """Test importing with overwrite"""
        library = StrategyLibrary(temp_library_path)
        library.save_strategy(sample_custom_strategy)

        # Create import with same name but different data
        export_data = {
            "custom_test": {
                "name": "custom_test",
                "description": "Overwritten description",
                "scan_code": "TOP_PERC_GAIN",
                "filters": {},
                "bias": "short",
                "style": "momentum",
                "instrument": "STK",
                "location_code": "STK.US",
                "performance": {
                    "total_runs": 0,
                    "successful_picks": 0,
                    "failed_picks": 0,
                    "avg_return": 0.0,
                    "last_run": None,
                    "last_result_count": 0,
                },
                "created": "2025-12-01T00:00:00",
                "modified": "2025-12-01T00:00:00",
                "enabled": True,
                "tags": [],
            }
        }

        import_file = Path(temp_library_path) / "import.json"
        with open(import_file, 'w') as f:
            json.dump(export_data, f)

        library.import_strategies(str(import_file), overwrite=True)

        # Verify overwrite
        loaded = library.get_strategy("custom_test")
        assert loaded.description == "Overwritten description"


class TestLibraryMagicMethods:
    """Test magic methods"""

    def test_len(self, temp_library_path, sample_custom_strategy):
        """Test __len__ method"""
        library = StrategyLibrary(temp_library_path)
        initial_len = len(library)

        library.save_strategy(sample_custom_strategy)

        assert len(library) == initial_len + 1

    def test_contains(self, temp_library_path, sample_custom_strategy):
        """Test __contains__ method"""
        library = StrategyLibrary(temp_library_path)

        assert "momentum_long" in library
        assert "nonexistent" not in library

        library.save_strategy(sample_custom_strategy)
        assert "custom_test" in library
