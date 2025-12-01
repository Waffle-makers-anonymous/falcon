"""Main entry point for Falcon trading application"""

import asyncio
import sys
from datetime import datetime
from falcon.config import get_config
from falcon.connection import IBConnection


async def display_account_info(conn: IBConnection):
    """Display account information and updates"""
    try:
        # Get accounts
        accounts = conn.get_accounts()
        print(f"\nAvailable accounts: {', '.join(accounts)}")

        # Get account summary for the first account
        summary = await conn.get_account_summary()

        print("\n" + "=" * 60)
        print(f"ACCOUNT SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print(f"Account: {summary.get('account', 'N/A')}")
        print(f"Trading Mode: {summary.get('trading_mode', 'N/A').upper()}")
        print(f"Account Type: {summary.get('AccountType', 'N/A')}")
        print("-" * 60)
        print(f"Net Liquidation: ${summary.get('NetLiquidation', 'N/A')}")
        print(f"Total Cash: ${summary.get('TotalCashValue', 'N/A')}")
        print(f"Buying Power: ${summary.get('BuyingPower', 'N/A')}")
        print(f"Available Funds: ${summary.get('AvailableFunds', 'N/A')}")
        print("-" * 60)
        print(f"Gross Position Value: ${summary.get('GrossPositionValue', 'N/A')}")
        print(f"Unrealized P&L: ${summary.get('UnrealizedPnL', 'N/A')}")
        print(f"Realized P&L: ${summary.get('RealizedPnL', 'N/A')}")
        print("=" * 60)

    except Exception as e:
        print(f"Error displaying account info: {e}")


async def main():
    """Main application loop"""
    # Load configuration
    config = get_config()

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
            print(f"   - Paper trading: port 4001")
            print(f"   - Live trading: port 4002")
            sys.exit(1)

        # Display account information
        await display_account_info(conn)

        print("\nPress Ctrl+C to exit...")

        # Keep the connection alive and refresh account info periodically
        while True:
            await asyncio.sleep(30)  # Update every 30 seconds
            await display_account_info(conn)

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        await conn.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
