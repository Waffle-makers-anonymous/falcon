#!/usr/bin/env python
"""Quick test of IB Gateway connection"""

import asyncio
from ib_insync import IB

async def test():
    ib = IB()
    print("Attempting to connect to IB Gateway at 127.0.0.1:4002...")

    try:
        await ib.connectAsync('127.0.0.1', 4002, clientId=1)
        print("✓ Connected successfully!")

        accounts = ib.managedAccounts()
        print(f"✓ Found accounts: {accounts}")

        if accounts:
            account = accounts[0]
            print(f"✓ Using account: {account}")

            # Request account summary (use async version)
            summary = await ib.accountSummaryAsync(account)
            print(f"✓ Retrieved {len(summary)} account summary items")

            for item in summary[:10]:  # Show first 10 items
                print(f"  {item.tag}: {item.value}")

        ib.disconnect()
        print("✓ Disconnected")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
