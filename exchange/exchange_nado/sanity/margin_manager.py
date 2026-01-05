"""
Margin Manager Sanity Test

This script demonstrates the margin manager functionality using read-only access.
It can analyze any public subaccount without requiring a private key.

Usage:
    python -m sanity.margin_manager

To analyze a specific wallet, set the TEST_WALLET constant below.
"""

import sys
import time
from decimal import Decimal
from nado_protocol.client import create_nado_client, NadoClientMode
from nado_protocol.utils.bytes32 import subaccount_to_hex
from nado_protocol.utils.math import from_x18
from nado_protocol.utils.margin_manager import MarginManager, print_account_summary

# Wallet to analyze (can be any public wallet address)
# Example wallet from margin manager screenshot
TEST_WALLET = "0x8D7d64d6cF1D4F018Dd101482Ac71Ad49e30c560"


def run():
    """Test margin manager with a real subaccount."""
    print("\n" + "=" * 80)
    print("MARGIN MANAGER SANITY TEST")
    print(f"Testing wallet: {TEST_WALLET}")
    print("=" * 80)

    # Setup Nado client (read-only, no private key needed)
    print("\n[1/5] Setting up client...")
    try:
        client = create_nado_client(NadoClientMode.TESTNET)
    except Exception as e:
        print(f"  ✗ Error creating Nado client: {e}")
        sys.exit(1)

    subaccount = subaccount_to_hex(TEST_WALLET, "default")
    print(f"  Subaccount: {subaccount}")

    # Fetch subaccount info, isolated positions, and indexer events via helper
    print("\n[2/5] Fetching margin data...")
    current_timestamp = int(time.time())
    try:
        margin_manager = MarginManager.from_client(
            client,
            subaccount=subaccount,
            include_indexer_events=True,
            snapshot_timestamp=current_timestamp,
            snapshot_isolated=False,
            snapshot_active_only=True,
        )
        subaccount_info = margin_manager.subaccount_info
        print(f"  ✓ Found {len(subaccount_info.spot_balances)} spot balances")
        print(f"  ✓ Found {len(subaccount_info.perp_balances)} perp balances")
        print(f"  ✓ Found {len(margin_manager.isolated_positions)} isolated positions")
        print(f"  ✓ Retrieved {len(margin_manager.indexer_events)} indexer events")
    except Exception as e:
        print(f"  ✗ Error fetching margin data: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Inspect indexer snapshot events
    print("\n[3/5] Inspecting indexer snapshot...")
    indexer_snapshot_events = margin_manager.indexer_events
    if indexer_snapshot_events:
        print(f"  ✓ Retrieved {len(indexer_snapshot_events)} active balances")
        first_balance = indexer_snapshot_events[0]
        print(f"  Number of balances: {len(indexer_snapshot_events)}")
        print(f"  First balance product_id: {first_balance.product_id}")
    else:
        print("  ⚠ Warning: No snapshot data found for requested timestamp")

    # Calculate summary
    print("\n[4/5] Calculating account summary...")
    try:
        summary = margin_manager.calculate_account_summary()
        print("  ✓ Calculations complete")
    except Exception as e:
        print(f"  ✗ Error calculating summary: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Display results
    print("\n[5/5] Displaying summary...")
    print_account_summary(summary)

    # Additional detailed analysis
    print("\n" + "=" * 80)
    print("DETAILED ANALYSIS")
    print("=" * 80)

    # Show raw health values from engine
    # healths is a list: [initial, maintenance, unweighted]
    print("\n📋 RAW HEALTH VALUES (from engine)")
    print(
        f"  Initial Assets:      ${from_x18(int(subaccount_info.healths[0].assets)):,.2f}"
    )
    print(
        f"  Initial Liabilities: ${from_x18(int(subaccount_info.healths[0].liabilities)):,.2f}"
    )
    print(
        f"  Initial Health:      ${from_x18(int(subaccount_info.healths[0].health)):,.2f}"
    )
    print()
    print(
        f"  Maint Assets:        ${from_x18(int(subaccount_info.healths[1].assets)):,.2f}"
    )
    print(
        f"  Maint Liabilities:   ${from_x18(int(subaccount_info.healths[1].liabilities)):,.2f}"
    )
    print(
        f"  Maint Health:        ${from_x18(int(subaccount_info.healths[1].health)):,.2f}"
    )
    print()
    print(
        f"  Unweighted Health:   ${from_x18(int(subaccount_info.healths[2].health)):,.2f}"
    )

    # Show spot balances in detail
    if subaccount_info.spot_balances:
        print("\n💵 SPOT BALANCES DETAIL")
        for i, (balance, product) in enumerate(
            zip(subaccount_info.spot_balances, subaccount_info.spot_products)
        ):
            amount = Decimal(from_x18(int(balance.balance.amount)))
            oracle_price = Decimal(from_x18(int(product.oracle_price_x18)))
            value = amount * oracle_price

            if amount == 0:
                continue

            balance_type = "Deposit" if amount > 0 else "Borrow"
            print(f"\n  [{i}] Product ID {balance.product_id}")
            print(f"      Type:         {balance_type}")
            print(f"      Amount:       {amount:,.6f}")
            print(f"      Oracle Price: ${oracle_price:,.2f}")
            print(f"      Value:        ${value:,.2f}")
            print(f"      Weights:")
            print(
                f"        Long Initial:  {from_x18(int(product.risk.long_weight_initial_x18)):.4f}"
            )
            print(
                f"        Long Maint:    {from_x18(int(product.risk.long_weight_maintenance_x18)):.4f}"
            )
            print(
                f"        Short Initial: {from_x18(int(product.risk.short_weight_initial_x18)):.4f}"
            )
            print(
                f"        Short Maint:   {from_x18(int(product.risk.short_weight_maintenance_x18)):.4f}"
            )

    # Show perp balances in detail
    if subaccount_info.perp_balances:
        print("\n🔄 PERP BALANCES DETAIL")
        for i, (balance, product) in enumerate(
            zip(subaccount_info.perp_balances, subaccount_info.perp_products)
        ):
            amount = Decimal(from_x18(int(balance.balance.amount)))
            if amount == 0:
                continue

            oracle_price = Decimal(from_x18(int(product.oracle_price_x18)))
            v_quote = Decimal(from_x18(int(balance.balance.v_quote_balance)))
            notional = abs(amount * oracle_price)
            position_value = amount * oracle_price + v_quote

            position_type = "Long" if amount > 0 else "Short"
            print(f"\n  [{i}] Product ID {balance.product_id}")
            print(f"      Type:          {position_type}")
            print(f"      Size:          {amount:,.6f}")
            print(f"      Oracle Price:  ${oracle_price:,.2f}")
            print(f"      Notional:      ${notional:,.2f}")
            print(f"      V Quote:       ${v_quote:,.2f}")
            print(f"      Position Value: ${position_value:,.2f}")
            print(f"      Weights:")
            print(
                f"        Long Initial:  {from_x18(int(product.risk.long_weight_initial_x18)):.4f}"
            )
            print(
                f"        Long Maint:    {from_x18(int(product.risk.long_weight_maintenance_x18)):.4f}"
            )

    print("\n" + "=" * 80)
    print("TEST COMPLETE ✓")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run()
