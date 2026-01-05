import time
from sanity import CLIENT_MODE, SIGNER_PRIVATE_KEY

from nado_protocol.client import NadoClient, create_nado_client
from nado_protocol.contracts.types import DepositCollateralParams
from nado_protocol.engine_client.types.execute import (
    BurnNlpParams,
    CancelAndPlaceParams,
    MarketOrderParams,
    MintNlpParams,
    OrderParams,
    PlaceMarketOrderParams,
    WithdrawCollateralParams,
)
from nado_protocol.engine_client.types.models import SpotProductBalance
from nado_protocol.engine_client.types.query import QueryMaxOrderSizeParams
from nado_protocol.utils.bytes32 import subaccount_to_bytes32, subaccount_to_hex
from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
from nado_protocol.utils.order import build_appendix
from nado_protocol.utils.math import round_x18, to_pow_10, to_x18
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.subaccount import SubaccountParams
from nado_protocol.utils.interest import (
    calc_deposit_rate_in_period,
    calc_borrow_rate_in_period,
)
from nado_protocol.utils.time import TimeInSeconds


def run():
    print("setting up nado client...")
    client: NadoClient = create_nado_client(CLIENT_MODE, SIGNER_PRIVATE_KEY)

    subaccount = subaccount_to_hex(client.context.signer.address, "default")
    print("subaccount:", subaccount)

    print("chain_id:", client.context.engine_client.get_contracts().chain_id)

    print("minting test tokens...")
    mint_tx_hash = client.spot._mint_mock_erc20(0, to_pow_10(100000, 6))
    print("mint tx hash:", mint_tx_hash)

    time.sleep(5)

    print("approving allowance...")
    approve_allowance_tx_hash = client.spot.approve_allowance(0, to_pow_10(100000, 6))
    print("approve allowance tx hash:", approve_allowance_tx_hash)

    time.sleep(5)

    print("querying my allowance...")
    token_allowance = client.spot.get_token_allowance(0, client.context.signer.address)
    print("token allowance:", token_allowance)

    print("depositing collateral...")
    deposit_tx_hash = client.spot.deposit(
        DepositCollateralParams(
            subaccount_name="default", product_id=0, amount=to_pow_10(100000, 6)
        )
    )
    print("deposit collateral tx hash:", deposit_tx_hash)

    time.sleep(5)

    print("querying my token balance...")
    token_balance = client.spot.get_token_wallet_balance(
        0, client.context.signer.address
    )

    print("my token balance:", token_balance)

    usdc_balance: SpotProductBalance = client.subaccount.get_engine_subaccount_summary(
        subaccount
    ).parse_subaccount_balance(0)
    while int(usdc_balance.balance.amount) == 0:
        print("waiting for deposit...")
        usdc_balance: SpotProductBalance = (
            client.subaccount.get_engine_subaccount_summary(
                subaccount
            ).parse_subaccount_balance(0)
        )
        time.sleep(1)

    order_price = 90_000

    owner = client.context.engine_client.signer.address
    print("placing order...")
    product_id = 1
    order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=owner,
            subaccount_name="default",
        ),
        priceX18=to_x18(order_price),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        appendix=build_appendix(OrderType.POST_ONLY),
        nonce=gen_order_nonce(),
    )
    res = client.market.place_order({"product_id": product_id, "order": order})
    print("order result:", res.json(indent=2))

    print("placing market order...")
    market_order = MarketOrderParams(
        sender=SubaccountParams(
            subaccount_owner=owner,
            subaccount_name="default",
        ),
        amount=-to_pow_10(1, 17),
    )
    res = client.market.place_market_order(
        PlaceMarketOrderParams(
            product_id=1, market_order=market_order, slippage=0.001  # 0.1%
        )
    )
    print("market order result:", res.json(indent=2))

    sender = subaccount_to_hex(order.sender)
    order.sender = subaccount_to_bytes32(order.sender)
    order_digest = client.context.engine_client.get_order_digest(order, product_id)
    print("order digest:", order_digest)

    print("querying open orders...")
    open_orders = client.market.get_subaccount_open_orders(1, sender)
    print("open orders:", open_orders.json(indent=2))

    print("querying my subaccounts...")
    my_subaccounts = client.subaccount.get_subaccounts(owner)
    print("my subaccounts:", my_subaccounts)

    print("querying subaccount summary...")
    subaccount_summary = client.subaccount.get_engine_subaccount_summary(subaccount)
    print("subaccount summary:", subaccount_summary.json(indent=2))

    print("cancelling order...")
    res = client.market.cancel_orders(
        {"productIds": [product_id], "digests": [order_digest], "sender": sender}
    )
    print("cancel order result:", res.json(indent=2))

    print("placing long perp order (`amount` provided is positive)")
    perp_product_id = 2
    perp_order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=owner,
            subaccount_name="default",
        ),
        priceX18=to_x18(order_price),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        appendix=build_appendix(OrderType.POST_ONLY),
        nonce=gen_order_nonce(),
    )

    perp_order.sender = subaccount_to_bytes32(perp_order.sender)
    perp_order_digest = client.context.engine_client.get_order_digest(
        perp_order, perp_product_id
    )
    print("order digest:", perp_order_digest)

    res = client.market.place_order(
        {"product_id": perp_product_id, "order": perp_order}
    )
    print("order result:", res.json(indent=2))

    print("placing short perp order (`amount` provided is negative)")
    perp_product_id = 2
    perp_order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=owner,
            subaccount_name="default",
        ),
        priceX18=to_x18(order_price + 40_000),
        amount=-to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        appendix=build_appendix(OrderType.POST_ONLY),
        nonce=gen_order_nonce(),
    )

    perp_order.sender = subaccount_to_bytes32(perp_order.sender)
    perp_order_digest = client.context.engine_client.get_order_digest(
        perp_order, perp_product_id
    )
    print("order digest:", perp_order_digest)

    res = client.market.place_order(
        {"product_id": perp_product_id, "order": perp_order}
    )
    print("order result:", res.json(indent=2))

    perp_order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=owner,
            subaccount_name="default",
        ),
        priceX18=to_x18(order_price),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(60),
        appendix=build_appendix(OrderType.POST_ONLY),
        nonce=gen_order_nonce(),
    )

    sender = subaccount_to_hex(perp_order.sender)

    print("cancelling perp order and placing a new one on the same request...")
    res = client.market.cancel_and_place(
        CancelAndPlaceParams(
            cancel_orders={
                "productIds": [perp_product_id],
                "digests": [perp_order_digest],
                "sender": sender,
            },
            place_order={"product_id": perp_product_id, "order": perp_order},
        )
    )

    print("cancel and place result:", res.json(indent=2))

    print("querying open orders after cancel...")
    open_orders = client.market.get_subaccount_open_orders(1, sender)
    print("open orders:", open_orders.json(indent=2))

    print("placing multiple orders...")
    for product_id in [1, 2]:
        order.nonce = gen_order_nonce()
        res = client.market.place_order(
            {"product_id": product_id, "order": order, "sender": sender}
        )
        print("order result:", res.json(indent=2))

    res = client.market.get_subaccount_multi_products_open_orders([1, 2], sender)
    print("querying multi-products open orders", res.json(indent=2))

    print("cancelling product orders...")
    res = client.market.cancel_product_orders({"productIds": [1, 2], "sender": sender})
    print("cancel product orders results:", res.json(indent=2))

    for product_id in [1, 2]:
        print(
            f"querying open orders after cancel product orders product_id={product_id}..."
        )
        open_orders = client.market.get_subaccount_open_orders(product_id, sender)
        print("open orders:", open_orders.json(indent=2))

    print("querying historical orders...")
    historical_orders = client.market.get_subaccount_historical_orders(
        {"subaccount": sender, "limit": 2}
    )
    print("subaccount historical orders:", historical_orders.json(indent=2))

    print("opening perp position...")
    btc_perp = [
        product
        for product in subaccount_summary.perp_products
        if product.product_id == 2
    ][0]
    order = OrderParams(
        sender=subaccount,
        priceX18=round_x18(
            btc_perp.oracle_price_x18, btc_perp.book_info.price_increment_x18
        )
        + to_x18(100),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(1000),
        appendix=build_appendix(OrderType.IOC),
        nonce=gen_order_nonce(),
    )
    res = client.market.place_order({"product_id": btc_perp.product_id, "order": order})
    print("order result:", res.json(indent=2))

    btc_perp_balance = [
        balance
        for balance in client.subaccount.get_engine_subaccount_summary(
            subaccount
        ).perp_balances
        if balance.product_id == 2
    ][0]
    print("perp balance:", btc_perp_balance.json(indent=2))

    print("closing perp position...")
    res = client.market.close_position(
        subaccount=SubaccountParams(
            subaccount_owner=client.context.signer.address, subaccount_name="default"
        ),
        product_id=2,
    )
    print("position close result:", res.json(indent=2))

    subaccount_summary = client.subaccount.get_engine_subaccount_summary(subaccount)
    print("subaccount summary post position close:", subaccount_summary.json(indent=2))

    print("querying all engine markets...")
    engine_markets = client.market.get_all_engine_markets()
    print("engine markets:", engine_markets.json(indent=2))

    print("querying all product symbols...")
    product_symbols = client.market.get_all_product_symbols()
    print("product symbols:", product_symbols)

    print("querying market liquidity...")
    market_liquidity = client.market.get_market_liquidity(1, 2)
    print("market liquidity:", market_liquidity.json(indent=2))

    print("querying latest market price...")
    latest_market_price = client.market.get_latest_market_price(1)
    print("latest market price:", latest_market_price.json(indent=2))

    print("querying oracle prices...")
    oracle_prices = client.context.indexer_client.get_oracle_prices([1, 2])
    print("oracle prices:", oracle_prices.json(indent=2))

    oracle_price = [
        oracle_price.oracle_price_x18
        for oracle_price in oracle_prices.prices
        if oracle_price.product_id == product_id
    ][0]

    print("querying max order size...")
    max_order_size = client.market.get_max_order_size(
        QueryMaxOrderSizeParams(
            sender=sender,
            product_id=product_id,
            price_x18=oracle_price,
            direction="short",
        )
    )
    print("max order size:", max_order_size.json(indent=2))

    print("querying max nlp mintable...")
    try:
        max_nlp_mintable = client.market.get_max_nlp_mintable(1, sender)
        print("max nlp mintable:", max_nlp_mintable.json(indent=2))
    except Exception as e:
        print("querying lp mintable failed with error:", e)

    print("querying candlesticks...")
    candlesticks = client.market.get_candlesticks(
        {"product_id": 1, "granularity": 300, "limit": 2}
    )
    print("candlesticks:", candlesticks.json(indent=2))

    print("querying funding rate...")
    funding_rate = client.market.get_perp_funding_rate(2)
    print("funding rate:", funding_rate.json(indent=2))

    print("querying product snapshots...")
    product_snapshots = client.market.get_product_snapshots(
        {"product_id": 1, "limit": 2}
    )
    print("product snapshots:", product_snapshots.json(indent=2))

    one_day_ago = int(time.time()) - 86400
    print("querying market snapshots...")
    market_snapshots = client.market.get_market_snapshots(
        {"interval": {"count": 2, "granularity": 3600, "max_time": one_day_ago}}
    )

    print(
        "market snapshots",
        market_snapshots.json(indent=2),
        len(market_snapshots.snapshots),
    )

    print("querying perp prices...")
    perp_prices = client.perp.get_prices(2)
    print("perp prices:", perp_prices.json(indent=2))

    print("minting nlp...")
    mint_nlp_params = MintNlpParams(
        sender=SubaccountParams(
            subaccount_owner=client.context.engine_client.signer.address,
            subaccount_name="default",
        ),
        quoteAmount=to_x18(2000),
    )
    # TODO: enable once NLP goes live for all
    # res = client.market.mint_nlp(mint_nlp_params)
    # print("mint nlp results:", res.json(indent=2))

    print("burning nlp...")
    burn_nlp_params = BurnNlpParams(
        sender=SubaccountParams(
            subaccount_owner=client.context.engine_client.signer.address,
            subaccount_name="default",
        ),
        nlpAmount=to_x18(1),
        nonce=client.context.engine_client.tx_nonce(
            subaccount_to_hex(
                SubaccountParams(
                    subaccount_owner=client.context.engine_client.signer.address,
                    subaccount_name="default",
                )
            )
        ),
    )
    # TODO: enable once nlp goes live for all
    # res = client.market.burn_nlp(burn_nlp_params)
    # print("burn nlp result:", res.json(indent=2))

    print("querying subaccount fee rates...")
    fee_rates = client.subaccount.get_subaccount_fee_rates(sender)
    print("fee rates:", fee_rates.json(indent=2))

    print("querying subaccount token rewards...")
    token_rewards = client.subaccount.get_subaccount_token_rewards(owner)
    print("token rewards:", token_rewards.json(indent=2))

    print("querying subaccount linked signer rate limits...")
    linked_signer_rate_limits = (
        client.subaccount.get_subaccount_linked_signer_rate_limits(sender)
    )
    print("linked signer rate limits:", linked_signer_rate_limits.json(indent=2))

    print("querying max withdrawable...")
    max_withdrawable = client.spot.get_max_withdrawable(0, sender)
    print("max withdrawable:", max_withdrawable.json(indent=2))

    print("withdrawing collateral...")
    withdraw_collateral_params = WithdrawCollateralParams(
        productId=0, amount=to_pow_10(10000, 6), sender=sender
    )
    res = client.spot.withdraw(withdraw_collateral_params)
    print("withdraw result:", res.json(indent=2))

    spot_products = client.market.get_all_engine_markets().spot_products
    for product in spot_products:
        deposit_apr = calc_deposit_rate_in_period(
            product, TimeInSeconds.YEAR, 0.2
        )  # 20% interest fee
        borrow_apr = calc_borrow_rate_in_period(product, TimeInSeconds.YEAR)

        print(
            "product:",
            product.product_id,
            "deposit APR:",
            f"{deposit_apr * 100:.2f}",
            "borrow APR:",
            f"{borrow_apr * 100:.2f}",
        ),

    print("getting interest and funding payments...")
    payments = client.subaccount.get_interest_and_funding_payments(
        subaccount, [1, 2], 10
    )
    print("interest and funding payments:", payments.json(indent=2))

    print("\n" + "=" * 50)
    print("CLIENT CONVENIENCE METHODS - TWAP & TRIGGERS")
    print("=" * 50)

    print("\nPlacing TWAP order via client.market.place_twap_order()...")
    try:
        twap_res = client.market.place_twap_order(
            product_id=1,
            price_x18=str(to_x18(52_000)),
            total_amount_x18=str(to_pow_10(5, 17)),
            times=5,
            slippage_frac=0.005,
            interval_seconds=1800,
        )
        print("TWAP order result:", twap_res.json(indent=2))
    except Exception as e:
        print("TWAP order failed (trigger client may not be configured):", e)

    print(
        "\nPlacing price trigger order via client.market.place_price_trigger_order()..."
    )
    try:
        trigger_res = client.market.place_price_trigger_order(
            product_id=1,
            price_x18=str(to_x18(45_000)),
            amount_x18=str(-to_pow_10(1, 18)),
            trigger_price_x18=str(to_x18(46_000)),
            trigger_type="last_price_below",
            reduce_only=True,
        )
        print("Price trigger order result:", trigger_res.json(indent=2))
    except Exception as e:
        print("Price trigger order failed (trigger client may not be configured):", e)
