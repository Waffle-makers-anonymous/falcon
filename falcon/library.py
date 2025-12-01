"""Strategy library for persisting and managing screening strategies"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict
from falcon.strategy import ScreeningStrategy, PREDEFINED_STRATEGIES


class StrategyLibrary:
    """Manage a library of screening strategies"""

    def __init__(self, library_path: Optional[str] = None):
        """
        Initialize strategy library

        Args:
            library_path: Path to strategy library directory.
                         Defaults to ~/.falcon/strategies
        """
        if library_path is None:
            library_path = os.path.expanduser("~/.falcon/strategies")

        self.library_path = Path(library_path)
        self.library_path.mkdir(parents=True, exist_ok=True)

        self._strategies: Dict[str, ScreeningStrategy] = {}
        self._load_strategies()

    def _load_strategies(self):
        """Load all strategies from library directory"""
        # Load predefined strategies first
        for name, strategy in PREDEFINED_STRATEGIES.items():
            self._strategies[name] = strategy

        # Load custom strategies from disk
        for strategy_file in self.library_path.glob("*.json"):
            try:
                strategy = self.load_strategy_from_file(strategy_file)
                self._strategies[strategy.name] = strategy
            except Exception as e:
                print(f"Warning: Failed to load strategy from {strategy_file}: {e}")

    def load_strategy_from_file(self, file_path: Path) -> ScreeningStrategy:
        """Load a strategy from a JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        return ScreeningStrategy.from_dict(data)

    def save_strategy(self, strategy: ScreeningStrategy, overwrite: bool = False):
        """
        Save a strategy to the library

        Args:
            strategy: Strategy to save
            overwrite: If True, overwrite existing strategy

        Raises:
            FileExistsError: If strategy exists and overwrite is False
        """
        file_path = self.library_path / f"{strategy.name}.json"

        if file_path.exists() and not overwrite:
            raise FileExistsError(
                f"Strategy '{strategy.name}' already exists. "
                "Use overwrite=True to replace it."
            )

        with open(file_path, 'w') as f:
            json.dump(strategy.to_dict(), f, indent=2)

        self._strategies[strategy.name] = strategy

    def get_strategy(self, name: str) -> Optional[ScreeningStrategy]:
        """Get a strategy by name"""
        return self._strategies.get(name)

    def list_strategies(
        self,
        bias: Optional[str] = None,
        style: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[ScreeningStrategy]:
        """
        List strategies with optional filtering

        Args:
            bias: Filter by trading bias (long, short, neutral)
            style: Filter by trading style (momentum, breakout, etc.)
            enabled_only: Only return enabled strategies

        Returns:
            List of matching strategies
        """
        strategies = list(self._strategies.values())

        if enabled_only:
            strategies = [s for s in strategies if s.enabled]

        if bias:
            strategies = [s for s in strategies if s.bias.value == bias]

        if style:
            strategies = [s for s in strategies if s.style.value == style]

        return strategies

    def delete_strategy(self, name: str):
        """
        Delete a strategy from the library

        Args:
            name: Name of strategy to delete

        Raises:
            ValueError: If strategy is a predefined strategy
            FileNotFoundError: If strategy doesn't exist
        """
        if name in PREDEFINED_STRATEGIES:
            raise ValueError(
                f"Cannot delete predefined strategy '{name}'. "
                "You can disable it instead."
            )

        if name not in self._strategies:
            raise FileNotFoundError(f"Strategy '{name}' not found")

        file_path = self.library_path / f"{name}.json"
        if file_path.exists():
            file_path.unlink()

        del self._strategies[name]

    def update_strategy(self, strategy: ScreeningStrategy):
        """Update an existing strategy"""
        if strategy.name not in self._strategies:
            raise FileNotFoundError(f"Strategy '{strategy.name}' not found")

        self.save_strategy(strategy, overwrite=True)

    def get_strategies_by_tag(self, tag: str) -> List[ScreeningStrategy]:
        """Get all strategies with a specific tag"""
        return [
            s for s in self._strategies.values()
            if tag in s.tags
        ]

    def export_library(self, export_path: str):
        """Export entire library to a JSON file"""
        export_data = {
            name: strategy.to_dict()
            for name, strategy in self._strategies.items()
            if name not in PREDEFINED_STRATEGIES  # Don't export predefined
        }

        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)

    def import_strategies(self, import_path: str, overwrite: bool = False):
        """Import strategies from a JSON file"""
        with open(import_path, 'r') as f:
            import_data = json.load(f)

        for name, strategy_dict in import_data.items():
            try:
                strategy = ScreeningStrategy.from_dict(strategy_dict)
                self.save_strategy(strategy, overwrite=overwrite)
            except Exception as e:
                print(f"Warning: Failed to import strategy '{name}': {e}")

    def get_top_performing_strategies(
        self,
        limit: int = 10,
        min_runs: int = 5
    ) -> List[ScreeningStrategy]:
        """
        Get top performing strategies by success rate

        Args:
            limit: Maximum number of strategies to return
            min_runs: Minimum number of runs required

        Returns:
            List of top performing strategies
        """
        # Filter strategies with minimum runs
        eligible = [
            s for s in self._strategies.values()
            if s.performance.total_runs >= min_runs
        ]

        # Sort by success rate
        eligible.sort(
            key=lambda s: s.performance.success_rate,
            reverse=True
        )

        return eligible[:limit]

    def __len__(self) -> int:
        """Return number of strategies in library"""
        return len(self._strategies)

    def __contains__(self, name: str) -> bool:
        """Check if strategy exists in library"""
        return name in self._strategies
