"""CLI interface for running stock screens"""

import asyncio
import sys
from falcon.config import get_config
from falcon.connection import IBConnection
from falcon.screener import Screener, format_screen_results
from falcon.library import StrategyLibrary


async def main():
    """Main CLI entry point"""

    # Load configuration
    config = get_config()

    # Initialize strategy library
    library = StrategyLibrary()

    print(f"Loaded {len(library)} strategies from library")
    print()

    # Create connection
    conn = IBConnection(config)

    try:
        # Connect to IB Gateway
        connected = await conn.connect()

        if not connected:
            print("\nFailed to connect to IB Gateway.")
            print("Please ensure:")
            print("1. IB Gateway is running")
            print("2. API connections are enabled in Gateway settings")
            print("3. The correct port is configured in .env file")
            sys.exit(1)

        # Create screener
        screener = Screener(conn)

        # Get strategies to run
        if len(sys.argv) > 1:
            # Run specific strategy by name
            strategy_name = sys.argv[1]
            strategy = library.get_strategy(strategy_name)

            if strategy is None:
                print(f"Error: Strategy '{strategy_name}' not found")
                print("\nAvailable strategies:")
                for s in library.list_strategies(enabled_only=False):
                    print(f"  - {s.name}: {s.description}")
                sys.exit(1)

            strategies_to_run = [strategy]
        else:
            # Run all enabled strategies
            strategies_to_run = library.list_strategies(enabled_only=True)

        print(f"Running {len(strategies_to_run)} strategies...\n")

        # Run strategies
        all_results = {}
        for i, strategy in enumerate(strategies_to_run):
            print(f"Executing: {strategy.name}...")
            try:
                results = await screener.run_strategy(strategy, max_results=25)
                all_results[strategy.name] = results
                print(f"  Found {len(results)} results")

                # Save updated strategy (with performance metrics)
                library.update_strategy(strategy)

            except Exception as e:
                print(f"  Error: {e}")
                all_results[strategy.name] = []

            # Add delay between strategies to avoid IB scanner subscription limits
            # Skip delay after the last strategy
            if i < len(strategies_to_run) - 1:
                print("  Waiting 3 seconds before next strategy...")
                await asyncio.sleep(3)

        # Display all results
        print("\n" + "="*80)
        print("SCREENING RESULTS")
        print("="*80)

        for strategy_name, results in all_results.items():
            strategy = library.get_strategy(strategy_name)
            print(f"\n{strategy.description}")
            print(f"Bias: {strategy.bias.value.upper()} | Style: {strategy.style.value}")
            print(format_screen_results(results, strategy_name))

        # Show performance summary
        print("\n" + "="*80)
        print("STRATEGY PERFORMANCE SUMMARY")
        print("="*80)

        for strategy in strategies_to_run:
            perf = strategy.performance
            print(f"\n{strategy.name}:")
            print(f"  Total Runs: {perf.total_runs}")
            print(f"  Last Run: {perf.last_run or 'Never'}")
            print(f"  Last Results: {perf.last_result_count}")
            if perf.total_runs > 0:
                print(f"  Success Rate: {perf.success_rate:.1f}%")
                print(f"  Avg Return: {perf.avg_return:.2f}%")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await conn.disconnect()


def cli_main():
    """Entry point for CLI"""
    print("="*80)
    print("FALCON STOCK SCREENER")
    print("="*80)
    print()

    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
