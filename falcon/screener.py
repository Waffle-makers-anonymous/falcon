"""Stock screener using IB Gateway scanner functionality"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from ib_insync import IB, ScannerSubscription, ScanData
from falcon.strategy import ScreeningStrategy, ScreenFilters
from falcon.connection import IBConnection


@dataclass
class ScreenResult:
    """Result from a screening operation"""

    symbol: str
    rank: int
    contract_id: int
    exchange: str
    currency: str

    # Market data
    distance: Optional[str] = None
    benchmark: Optional[str] = None
    projection: Optional[str] = None

    # Additional metadata
    legs_str: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "rank": self.rank,
            "contract_id": self.contract_id,
            "exchange": self.exchange,
            "currency": self.currency,
            "distance": self.distance,
            "benchmark": self.benchmark,
            "projection": self.projection,
            "legs_str": self.legs_str,
        }


class Screener:
    """Stock screener using IB Gateway"""

    def __init__(self, connection: IBConnection, database=None):
        """
        Initialize screener with IB connection

        Args:
            connection: Active IBConnection instance
            database: Optional ScreenDatabase for persisting results
        """
        self.connection = connection
        self.ib = connection.ib
        self.database = database

    async def run_strategy(
        self,
        strategy: ScreeningStrategy,
        max_results: int = 50,
        save_to_db: bool = True
    ) -> List[ScreenResult]:
        """
        Execute a screening strategy

        Args:
            strategy: ScreeningStrategy to execute
            max_results: Maximum number of results to return
            save_to_db: Whether to save results to database (if database is configured)

        Returns:
            List of ScreenResult objects

        Raises:
            ConnectionError: If not connected to IB Gateway
        """
        if not self.connection.is_connected:
            raise ConnectionError("Not connected to IB Gateway")

        # Create scanner subscription
        scanner = self._create_scanner_subscription(strategy)

        # Request scanner data
        scanner_data = await self.ib.reqScannerDataAsync(scanner)

        # Convert to ScreenResult objects
        results = []
        for i, item in enumerate(scanner_data[:max_results]):
            result = self._scanner_item_to_result(item, i + 1)

            # Apply additional filters if needed
            if self._passes_filters(result, strategy.filters):
                results.append(result)

        # Update strategy performance
        strategy.performance.update_run(len(results))
        strategy.update_modified()

        # Save to database if configured
        if save_to_db and self.database and results:
            self.database.save_screen_run(strategy, results)

        return results

    def _create_scanner_subscription(
        self,
        strategy: ScreeningStrategy
    ) -> ScannerSubscription:
        """Create IB scanner subscription from strategy"""

        scanner_params = {
            "instrument": strategy.instrument,
            "locationCode": strategy.location_code,
            "scanCode": strategy.scan_code,
        }

        filters = strategy.filters

        # Add price filters
        if filters.price_min is not None:
            scanner_params["abovePrice"] = filters.price_min
        if filters.price_max is not None:
            scanner_params["belowPrice"] = filters.price_max

        # Add volume filters
        if filters.volume_min is not None:
            scanner_params["aboveVolume"] = filters.volume_min

        # Add market cap filters
        if filters.market_cap_min is not None:
            scanner_params["marketCapAbove"] = filters.market_cap_min
        if filters.market_cap_max is not None:
            scanner_params["marketCapBelow"] = filters.market_cap_max

        return ScannerSubscription(**scanner_params)

    def _scanner_item_to_result(
        self,
        item: ScanData,
        rank: int
    ) -> ScreenResult:
        """Convert IB ScanData to ScreenResult"""

        contract = item.contractDetails.contract

        return ScreenResult(
            symbol=contract.symbol,
            rank=rank,
            contract_id=contract.conId,
            exchange=contract.primaryExchange or contract.exchange,
            currency=contract.currency,
            distance=item.distance,
            benchmark=item.benchmark,
            projection=item.projection,
            legs_str=item.legsStr,
        )

    def _passes_filters(
        self,
        result: ScreenResult,
        filters: ScreenFilters
    ) -> bool:
        """
        Check if result passes additional filters

        Note: Most filtering is done by IB scanner, but this allows
        for additional client-side filtering if needed.
        """
        # For now, all results from IB scanner pass
        # This can be extended for more complex filtering logic
        return True

    async def get_available_scans(self) -> List[Dict[str, str]]:
        """
        Get list of available scan codes from IB

        Returns:
            List of dictionaries with scan information
        """
        if not self.connection.is_connected:
            raise ConnectionError("Not connected to IB Gateway")

        # Request scanner parameters
        params = await self.ib.reqScannerParametersAsync()

        # Parse XML response to extract scan codes
        # This returns an XML string that needs to be parsed
        # For now, return empty list - can be enhanced later
        return []

    async def run_multiple_strategies(
        self,
        strategies: List[ScreeningStrategy],
        max_results_per_strategy: int = 50
    ) -> Dict[str, List[ScreenResult]]:
        """
        Run multiple strategies and return combined results

        Args:
            strategies: List of strategies to execute
            max_results_per_strategy: Max results per strategy

        Returns:
            Dictionary mapping strategy names to results
        """
        results = {}

        for strategy in strategies:
            if strategy.enabled:
                try:
                    strategy_results = await self.run_strategy(
                        strategy,
                        max_results=max_results_per_strategy
                    )
                    results[strategy.name] = strategy_results
                except Exception as e:
                    print(f"Error running strategy '{strategy.name}': {e}")
                    results[strategy.name] = []

        return results


def format_screen_results(
    results: List[ScreenResult],
    strategy_name: str
) -> str:
    """Format screening results for display"""

    if not results:
        return f"\n{strategy_name}: No results found\n"

    output = [
        f"\n{'='*80}",
        f"{strategy_name.upper()} - {len(results)} Results",
        f"{'='*80}",
        f"{'Rank':<6} {'Symbol':<10} {'Exchange':<12} {'Currency':<8} {'Distance':<10}",
        f"{'-'*80}"
    ]

    for result in results:
        output.append(
            f"{result.rank:<6} "
            f"{result.symbol:<10} "
            f"{result.exchange:<12} "
            f"{result.currency:<8} "
            f"{result.distance or 'N/A':<10}"
        )

    output.append(f"{'='*80}\n")

    return "\n".join(output)
