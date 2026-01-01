"""
Test Binance API connection and balance
"""

import ccxt
from config_loader import API_KEY, API_SECRET


def test_connection():
    print("\n" + "=" * 60)
    print("TESTING BINANCE API CONNECTION")
    print("=" * 60)

    # Test 1: FUTURES connection
    print("\n[TEST 1] Futures Account...")
    try:
        exchange_futures = ccxt.binance(
            {
                "apiKey": API_KEY,
                "secret": API_SECRET,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "future",
                    "adjustForTimeDifference": True,
                },
            }
        )

        exchange_futures.load_time_difference()
        print("✅ Connected to Binance Futures")

        # Check balance
        balance = exchange_futures.fetch_balance()
        total_usdc = balance["total"].get("USDC", 0)
        free_usdc = balance["free"].get("USDC", 0)

        print(f"   USDC Total: ${total_usdc:.2f}")
        print(f"   USDC Free: ${free_usdc:.2f}")

        if total_usdc > 0:
            print("✅ Futures wallet has balance!")
        else:
            print("⚠️  Futures wallet is EMPTY")
            print("   → Transfer USDC from Spot to Futures wallet")

    except Exception as e:
        print(f"❌ Futures connection failed: {e}")

    # Test 2: SPOT connection
    print("\n[TEST 2] Spot Account...")
    try:
        exchange_spot = ccxt.binance(
            {
                "apiKey": API_KEY,
                "secret": API_SECRET,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",
                },
            }
        )

        print("✅ Connected to Binance Spot")

        # Check balance
        balance = exchange_spot.fetch_balance()
        total_usdc = balance["total"].get("USDC", 0)
        free_usdc = balance["free"].get("USDC", 0)

        print(f"   USDC Total: ${total_usdc:.2f}")
        print(f"   USDC Free: ${free_usdc:.2f}")

        if total_usdc > 0:
            print("✅ Spot wallet has balance!")
            print("   → Consider transferring to Futures for trading")

    except Exception as e:
        print(f"❌ Spot connection failed: {e}")

    # Test 3: API Permissions
    print("\n[TEST 3] API Permissions...")
    try:
        exchange_futures = ccxt.binance(
            {
                "apiKey": API_KEY,
                "secret": API_SECRET,
                "options": {"defaultType": "future"},
            }
        )

        # Try to get account info
        account = exchange_futures.fapiPrivateGetAccount()
        print("✅ Futures trading permission: ENABLED")

    except Exception as e:
        if "API-key format invalid" in str(e):
            print("❌ API Key format invalid")
        elif "Signature for this request is not valid" in str(e):
            print("❌ API Secret incorrect")
        elif "does not have permission" in str(e):
            print("❌ API Key does NOT have Futures trading permission")
            print("   → Go to Binance → API Management → Enable Futures")
        else:
            print(f"❌ Permission check failed: {e}")

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    test_connection()
