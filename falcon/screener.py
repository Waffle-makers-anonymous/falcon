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

    # Market data
    price: Optional[float] = None
    volume: Optional[int] = None
    impl_volatility: Optional[float] = None  # Implied volatility (annualized)

    # Original scanner fields (kept for compatibility)
    exchange: Optional[str] = None
    currency: Optional[str] = None
    distance: Optional[str] = None
    benchmark: Optional[str] = None
    projection: Optional[str] = None
    legs_str: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "rank": self.rank,
            "contract_id": self.contract_id,
            "price": self.price,
            "volume": self.volume,
            "impl_volatility": self.impl_volatility,
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

        try:
            # Request scanner data with timeout
            print(f"  Requesting scanner data...")
            scanner_data = await self.ib.reqScannerDataAsync(scanner)

            print(f"  Received {len(scanner_data)} items from scanner")

            # Convert to ScreenResult objects
            results = []
            for i, item in enumerate(scanner_data[:max_results]):
                result = self._scanner_item_to_result(item, i + 1)

                # Apply additional filters if needed
                if self._passes_filters(result, strategy.filters):
                    results.append(result)

            # Fetch market data for all results
            if results:
                print(f"  Fetching market data for {len(results)} results...")
                await self._fetch_market_data(results)

            # Update strategy performance
            strategy.performance.update_run(len(results))
            strategy.update_modified()

            # Save to database if configured
            if save_to_db and self.database and results:
                self.database.save_screen_run(strategy, results)

            return results

        except Exception as e:
            print(f"  Scanner error: {type(e).__name__}: {e}")
            # Update strategy performance even on error
            strategy.performance.update_run(0)
            strategy.update_modified()
            raise

    def _create_scanner_subscription(
        self,
        strategy: ScreeningStrategy
    ) -> ScannerSubscription:
        """Create IB scanner subscription from strategy"""

        # Use config location_code if available, otherwise use strategy's location_code
        location_code = self.connection.config.location_code if hasattr(self.connection.config, 'location_code') else strategy.location_code

        scanner_params = {
            "instrument": strategy.instrument,
            "locationCode": location_code,
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

        # Add market cap filters (values in millions)
        if filters.market_cap_min is not None:
            # Convert from actual value to millions for IB API
            scanner_params["marketCapAbove"] = filters.market_cap_min / 1_000_000
        if filters.market_cap_max is not None:
            # Convert from actual value to millions for IB API
            scanner_params["marketCapBelow"] = filters.market_cap_max / 1_000_000

        # Debug: Print scanner parameters
        print(f"  Scanner params: {scanner_params}")

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

    async def _fetch_market_data(self, results: List[ScreenResult]) -> None:
        """
        Fetch current market data for screening results

        Updates each result with:
        - price: Last traded price
        - volume: Current day volume
        - impl_volatility: Implied volatility (annualized %)
        """
        from ib_insync import Stock
        import asyncio

        for result in results:
            try:
                # Create contract for the stock
                contract = Stock(result.symbol, 'SMART', 'USD')

                # Qualify the contract
                await self.ib.qualifyContractsAsync(contract)

                # Request market data snapshot
                ticker = self.ib.reqMktData(contract, '', True, False)

                # Wait a bit for data to arrive
                await asyncio.sleep(1)

                # Extract market data
                if ticker.last and ticker.last > 0:
                    result.price = ticker.last
                elif ticker.close and ticker.close > 0:
                    result.price = ticker.close

                if ticker.volume and ticker.volume > 0:
                    result.volume = int(ticker.volume)

                if ticker.impliedVolatility and ticker.impliedVolatility > 0:
                    # Convert to percentage (IV is returned as decimal, e.g., 0.5 = 50%)
                    result.impl_volatility = ticker.impliedVolatility * 100

                # Cancel the market data subscription
                self.ib.cancelMktData(contract)

            except Exception as e:
                # If we can't get market data for a symbol, just skip it
                print(f"    Warning: Could not fetch market data for {result.symbol}: {e}")
                continue

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
        f"\n{'='*100}",
        f"{strategy_name.upper()} - {len(results)} Results",
        f"{'='*100}",
        f"{'Rank':<6} {'Symbol':<10} {'Price':<12} {'Volume':<15} {'Impl Vol %':<12}",
        f"{'-'*100}"
    ]

    for result in results:
        # Format price
        price_str = f"${result.price:.2f}" if result.price else "N/A"

        # Format volume with commas
        if result.volume:
            volume_str = f"{result.volume:,}"
        else:
            volume_str = "N/A"

        # Format implied volatility
        if result.impl_volatility:
            iv_str = f"{result.impl_volatility:.1f}%"
        else:
            iv_str = "N/A"

        output.append(
            f"{result.rank:<6} "
            f"{result.symbol:<10} "
            f"{price_str:<12} "
            f"{volume_str:<15} "
            f"{iv_str:<12}"
        )

    output.append(f"{'='*100}\n")

    return "\n".join(output)
