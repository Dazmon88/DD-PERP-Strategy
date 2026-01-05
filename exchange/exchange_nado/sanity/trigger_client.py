import time
from sanity import ENGINE_BACKEND_URL, SIGNER_PRIVATE_KEY, TRIGGER_BACKEND_URL
from nado_protocol.engine_client import EngineClient
from nado_protocol.engine_client.types import EngineClientOpts
from nado_protocol.engine_client.types.execute import OrderParams
from nado_protocol.trigger_client import TriggerClient
from nado_protocol.trigger_client.types import TriggerClientOpts
from nado_protocol.trigger_client.types.execute import (
    PlaceTriggerOrderParams,
    CancelTriggerOrdersParams,
)
from nado_protocol.trigger_client.types.models import (
    PriceTrigger,
    PriceTriggerData,
    LastPriceAbove,
    LastPriceBelow,
)
from nado_protocol.trigger_client.types.query import (
    ListTriggerOrdersParams,
    ListTriggerOrdersTx,
    ListTwapExecutionsParams,
)
from nado_protocol.utils.bytes32 import subaccount_to_hex
from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
from nado_protocol.utils.order import OrderAppendixTriggerType, build_appendix
from nado_protocol.utils.math import to_pow_10, to_x18
from nado_protocol.utils.subaccount import SubaccountParams
from nado_protocol.utils.time import now_in_millis


def run():
    print("setting up trigger client...")
    client = TriggerClient(
        opts=TriggerClientOpts(url=TRIGGER_BACKEND_URL, signer=SIGNER_PRIVATE_KEY)
    )

    engine_client = EngineClient(
        opts=EngineClientOpts(url=ENGINE_BACKEND_URL, signer=SIGNER_PRIVATE_KEY)
    )

    contracts_data = engine_client.get_contracts()
    client.endpoint_addr = contracts_data.endpoint_addr
    client.chain_id = contracts_data.chain_id

    print("placing trigger order...")
    order_price = 100_000

    product_id = 1
    order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        priceX18=to_x18(order_price),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        appendix=build_appendix(
            OrderType.DEFAULT, trigger_type=OrderAppendixTriggerType.PRICE
        ),
        nonce=client.order_nonce(),
    )
    order_digest = client.get_order_digest(order, product_id)
    print("order digest:", order_digest)

    place_order = PlaceTriggerOrderParams(
        product_id=product_id,
        order=order,
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceAbove(last_price_above=str(to_x18(120_000)))
            )
        ),
    )
    res = client.place_trigger_order(place_order)
    print("trigger order result:", res.json(indent=2))

    sender = subaccount_to_hex(order.sender)

    cancel_orders = CancelTriggerOrdersParams(
        sender=sender, productIds=[product_id], digests=[order_digest]
    )
    res = client.cancel_trigger_orders(cancel_orders)
    print("cancel trigger order result:", res.json(indent=2))

    product_id = 2
    order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        priceX18=to_x18(order_price),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        appendix=build_appendix(
            OrderType.DEFAULT, trigger_type=OrderAppendixTriggerType.PRICE
        ),
        nonce=client.order_nonce(),
    )
    order_digest = client.get_order_digest(order, product_id)
    print("order digest:", order_digest)

    place_order = PlaceTriggerOrderParams(
        product_id=product_id,
        order=order,
        trigger=PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=LastPriceAbove(last_price_above=str(to_x18(120_000)))
            )
        ),
    )
    res = client.place_trigger_order(place_order)

    print("listing trigger orders...")
    trigger_orders = client.list_trigger_orders(
        ListTriggerOrdersParams(
            tx=ListTriggerOrdersTx(
                sender=SubaccountParams(
                    subaccount_owner=client.signer.address, subaccount_name="default"
                ),
                recvTime=now_in_millis(90),
            ),
            pending=True,
            product_id=2,
        )
    )
    print("trigger orders:", trigger_orders.json(indent=2))

    print("\n" + "=" * 50)
    print("TWAP ORDER EXAMPLES")
    print("=" * 50)

    # Example 1: Basic TWAP order using convenience method (with defaults)
    print("\n1. Basic TWAP order (DCA strategy) - using defaults")
    print("-" * 40)

    twap_res = client.place_twap_order(
        product_id=1,
        price_x18=str(to_x18(52_000)),
        total_amount_x18=str(to_pow_10(5, 18)),
        times=10,
        slippage_frac=0.005,
        interval_seconds=3600,
    )
    print(f"TWAP order result: {twap_res.json(indent=2)}")

    # Get the order digest to track executions
    twap_order_digest = twap_res.data.digest
    print(f"TWAP order digest: {twap_order_digest}")

    # Example 2: TWAP order with custom amounts and subaccount parameters
    print("\n2. TWAP order with custom amounts (using subaccount parameters)")
    print("-" * 55)

    custom_amounts = [
        str(to_pow_10(2, 18)),
        str(to_pow_10(15, 17)),
        str(to_pow_10(1, 18)),
        str(to_pow_10(5, 17)),
    ]
    total_amount = str(to_pow_10(5, 18))

    custom_twap_res = client.place_twap_order(
        product_id=1,
        price_x18=str(to_x18(51_000)),
        total_amount_x18=total_amount,
        times=4,
        slippage_frac=0.01,
        interval_seconds=2700,
        custom_amounts_x18=custom_amounts,
        subaccount_name="default",
    )
    print(f"Custom TWAP order result: {custom_twap_res.json(indent=2)}")

    # Example 3: TWAP sell order with reduce_only
    print("\n3. TWAP sell order (reduce-only position closing)")
    print("-" * 50)

    reduce_twap_res = client.place_twap_order(
        product_id=1,
        price_x18=str(to_x18(48_000)),
        total_amount_x18=str(-to_pow_10(3, 18)),
        times=6,
        slippage_frac=0.0075,
        interval_seconds=1800,
        reduce_only=True,
    )
    print(f"Reduce-only TWAP result: {reduce_twap_res.json(indent=2)}")

    print("\n" + "=" * 50)
    print("PRICE TRIGGER ORDER EXAMPLES")
    print("=" * 50)

    # Example 4: Stop-loss order using convenience method (with defaults)
    print("\n4. Stop-loss order (last price below) - using defaults")
    print("-" * 40)

    stop_loss_res = client.place_price_trigger_order(
        product_id=1,
        price_x18=str(to_x18(45_000)),
        amount_x18=str(-to_pow_10(1, 18)),
        trigger_price_x18=str(to_x18(46_000)),
        trigger_type="last_price_below",
        reduce_only=True,
    )
    print(f"Stop-loss order result: {stop_loss_res.json(indent=2)}")

    # Example 5: Take-profit order
    print("\n5. Take-profit order (last price above)")
    print("-" * 40)

    take_profit_res = client.place_price_trigger_order(
        product_id=1,
        price_x18=str(to_x18(55_000)),
        amount_x18=str(-to_pow_10(1, 18)),
        trigger_price_x18=str(to_x18(54_000)),
        trigger_type="last_price_above",
        reduce_only=True,
    )
    print(f"Take-profit order result: {take_profit_res.json(indent=2)}")

    # Example 6: Oracle-based trigger order
    print("\n6. Oracle price trigger order")
    print("-" * 35)

    oracle_trigger_res = client.place_price_trigger_order(
        product_id=1,
        price_x18=str(to_x18(50_500)),
        amount_x18=str(to_pow_10(1, 18)),
        trigger_price_x18=str(to_x18(50_000)),
        trigger_type="oracle_price_above",
    )
    print(f"Oracle trigger order result: {oracle_trigger_res.json(indent=2)}")

    # Example 7: Mid price trigger order
    print("\n7. Mid price trigger order")
    print("-" * 30)

    mid_price_trigger_res = client.place_price_trigger_order(
        product_id=1,
        price_x18=str(to_x18(49_500)),
        amount_x18=str(to_pow_10(5, 17)),
        trigger_price_x18=str(to_x18(49_000)),
        trigger_type="mid_price_below",
    )
    print(f"Mid price trigger result: {mid_price_trigger_res.json(indent=2)}")

    print("\n" + "=" * 50)
    print("ADVANCED INTEGRATION SCENARIOS")
    print("=" * 50)

    # Example 8: Complete trading strategy - stop loss + take profit + DCA
    print("\n8. Complete trading strategy")
    print("-" * 30)
    print("Setting up: Stop-loss + Take-profit + DCA TWAP")

    strategy_stop_loss = client.place_price_trigger_order(
        product_id=1,
        price_x18=str(to_x18(44_000)),
        amount_x18=str(-to_pow_10(2, 18)),
        trigger_price_x18=str(to_x18(45_000)),
        trigger_type="last_price_below",
        reduce_only=True,
    )
    print(f"Strategy stop-loss: {strategy_stop_loss.status}")

    strategy_take_profit = client.place_price_trigger_order(
        product_id=1,
        price_x18=str(to_x18(58_000)),
        amount_x18=str(-to_pow_10(2, 18)),
        trigger_price_x18=str(to_x18(57_000)),
        trigger_type="last_price_above",
        reduce_only=True,
    )
    print(f"Strategy take-profit: {strategy_take_profit.status}")

    strategy_dca = client.place_twap_order(
        product_id=1,
        price_x18=str(to_x18(52_000)),
        total_amount_x18=str(to_pow_10(10, 18)),
        times=20,
        slippage_frac=0.005,
        interval_seconds=1800,
    )
    print(f"Strategy DCA TWAP: {strategy_dca.status}")

    print("\nComplete trading strategy deployed successfully!")
    print("- Stop-loss at $45k (protects downside)")
    print("- Take-profit at $57k (captures upside)")
    print("- DCA TWAP over 1 week (builds position gradually)")

    print("\n" + "=" * 50)
    print("QUERYING TWAP EXECUTIONS")
    print("=" * 50)

    print(f"\nQuerying TWAP order executions for digest: {twap_order_digest}")
    try:
        twap_executions = client.list_twap_executions(
            ListTwapExecutionsParams(digest=twap_order_digest)
        )
        print(f"TWAP executions response: {twap_executions.json(indent=2)}")

        if (
            hasattr(twap_executions.data, "executions")
            and twap_executions.data.executions
        ):
            executions = twap_executions.data.executions
            print(f"\nFound {len(executions)} TWAP execution(s)")
            for i, execution in enumerate(executions, 1):
                print(f"  Execution {i}:")
                print(f"    Execution ID: {execution.execution_id}")
                print(f"    Scheduled time: {execution.scheduled_time}")
                print(f"    Status: {execution.status}")
                print(f"    Updated at: {execution.updated_at}")
        else:
            print("No TWAP executions found yet (executions happen at intervals)")
    except Exception as e:
        print(f"Failed to query TWAP executions: {e}")

    print("\n" + "=" * 50)
    print("TWAP AND PRICE TRIGGER EXAMPLES COMPLETED")
    print("=" * 50)
