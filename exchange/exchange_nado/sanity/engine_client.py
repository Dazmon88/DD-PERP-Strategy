from pprint import pprint
import time

from eth_account import Account
from eth_account.signers.local import LocalAccount

from sanity import ENGINE_BACKEND_URL, LINKED_SIGNER_PRIVATE_KEY, SIGNER_PRIVATE_KEY
from nado_protocol.engine_client import EngineClient, EngineClientOpts
from nado_protocol.engine_client.types.execute import (
    BurnNlpParams,
    CancelOrdersParams,
    LinkSignerParams,
    LiquidateSubaccountParams,
    MintNlpParams,
    PlaceOrderParams,
    OrderParams,
    WithdrawCollateralParams,
)
from nado_protocol.engine_client.types.query import (
    QueryMaxOrderSizeParams,
)
from nado_protocol.engine_client.types.models import ApplyDelta, ApplyDeltaTx
from nado_protocol.utils.bytes32 import (
    bytes32_to_hex,
    str_to_hex,
    subaccount_to_bytes32,
    zero_subaccount,
    subaccount_to_hex,
)
from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
from nado_protocol.utils.order import build_appendix
from nado_protocol.utils.math import to_pow_10, to_x18
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.subaccount import SubaccountParams


def run():
    print("setting up engine client...")
    client = EngineClient(
        opts=EngineClientOpts(url=ENGINE_BACKEND_URL, signer=SIGNER_PRIVATE_KEY)
    )

    print("querying status...")
    status_data = client.get_status()
    print("status:", status_data)

    print("querying contracts...")
    contracts_data = client.get_contracts()
    pprint(contracts_data.json())

    client.endpoint_addr = contracts_data.endpoint_addr
    client.chain_id = contracts_data.chain_id

    print("querying product symbols...")
    product_symbols = client.get_product_symbols()
    pprint(product_symbols)

    print("querying symbols...")
    symbols = client.get_symbols(product_type="perp")
    pprint(symbols)

    print("querying BTC-PERP symbol...")
    btc_perp = client.get_symbols(product_ids=[2])
    pprint(btc_perp)

    print("querying assets...")
    assets = client.get_assets()
    pprint(assets)

    print("querying spot market pairs...")
    spot_pairs = client.get_pairs("spot")
    pprint(spot_pairs)

    print("querying perp market pairs...")
    perp_pairs = client.get_pairs("perp")
    pprint(perp_pairs)

    print("querying spots apr...")
    spots_apr = client.get_spots_apr()
    pprint(spots_apr)

    print("querying orderbook for BTC-PERP pair...")
    btc_perp_book = client.get_orderbook("BTC-PERP_USDT0", 10)
    pprint(btc_perp_book)

    order_price = 100_000

    print("placing order...")
    product_id = 1
    order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        priceX18=to_x18(order_price),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        nonce=gen_order_nonce(),
        appendix=build_appendix(OrderType.DEFAULT),
    )
    order_digest = client.get_order_digest(order, product_id)
    print("order digest:", order_digest)

    place_order = PlaceOrderParams(product_id=product_id, order=order)
    res = client.place_order(place_order)
    print("order result:", res.json(indent=2))

    print("placing order with custom id...")
    product_id = 1
    order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        priceX18=to_x18(order_price),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        nonce=gen_order_nonce(),
        appendix=build_appendix(OrderType.DEFAULT),
    )
    place_order = PlaceOrderParams(product_id=product_id, order=order, id=100)
    res = client.place_order(place_order)
    print("order with custom id result:", res.json(indent=2))

    try:
        print("querying order...")
        order = client.get_order(product_id, order_digest)
        print("order found", order.json(indent=2))
    except Exception as e:
        print("order not found:", e)

    sender = subaccount_to_hex(order.sender)

    print("querying subaccount info...")
    subaccount_info = client.get_subaccount_info(sender)
    print("subaccount info:", subaccount_info.json(indent=2))

    print("querying subaccount info with simulated transaction and pre_state...")
    # Simulate applying a delta to a perp product
    simulated_tx = ApplyDeltaTx(
        apply_delta=ApplyDelta(
            product_id=2,
            subaccount=sender,
            amount_delta="100000000000000000",
            v_quote_delta="3033500000000000000000",
        )
    )
    subaccount_info_with_pre_state = client.get_subaccount_info(
        sender, txs=[simulated_tx], pre_state=True
    )
    print(
        "subaccount info with simulation:",
        subaccount_info_with_pre_state.json(indent=2),
    )
    if subaccount_info_with_pre_state.pre_state:
        print("✓ pre_state returned successfully")
        print("pre_state healths:", subaccount_info_with_pre_state.pre_state.healths)
    else:
        print("✗ Warning: pre_state was not returned")

    print("querying subaccount open orders...")
    subaccount_open_orders = client.get_subaccount_open_orders(product_id, sender)
    print("subaccount open orders:", subaccount_open_orders.json(indent=2))

    cancel_order = CancelOrdersParams(
        sender=sender, productIds=[product_id], digests=[order_digest]
    )
    res = client.cancel_orders(cancel_order)
    print("cancel orders result:", res.json(indent=2))

    print("querying order after cancel...")
    try:
        order = client.get_order(product_id, order_digest)
        print("order found but should not be!")
        exit(1)
    except Exception as e:
        print("order not found:", e)

    print("querying subaccount open orders (after cancel)...")
    subaccount_open_orders = client.get_subaccount_open_orders(product_id, sender)
    print("subaccount open orders:", subaccount_open_orders.json(indent=2))

    print("querying market liquidity...")
    market_liquidity = client.get_market_liquidity(product_id, depth=10)
    print("market liquidity:", market_liquidity)

    print("querying all products...")
    all_products = client.get_all_products()
    print("all products:", all_products.json(indent=2))

    print("querying market price...")
    market_price = client.get_market_price(product_id)
    print("market price:", market_price.json(indent=2))

    print("querying max order size...")
    max_order_size = client.get_max_order_size(
        QueryMaxOrderSizeParams(
            sender=sender,
            product_id=product_id,
            price_x18=to_x18(order_price),
            direction="short",
        )
    )
    print("max order size:", max_order_size)

    print("querying max withdrawable...")
    max_withdrawable = client.get_max_withdrawable(product_id, sender)
    print("max withdrawable:", max_withdrawable.json(indent=2))

    # TODO: enable once max nlp mintable works
    # print("querying max nlp mintable...")
    # max_nlp_mintable = client.get_max_nlp_mintable(
    #     product_id=1,
    #     sender=sender,
    # )
    # print("max nlp mintable:", max_nlp_mintable.json(indent=2))

    print("querying fee rates...")
    fee_rates = client.get_fee_rates(sender=sender)
    print("fee rates:", fee_rates.json(indent=2))

    print("querying health groups...")
    health_groups = client.get_health_groups()
    print("health groups:", health_groups.json(indent=2))

    print("querying linked signer...")
    linked_signer = client.get_linked_signer(subaccount=sender)
    print("linked signer:", linked_signer.json(indent=2))

    print("minting nlp...")
    mint_nlp_params = MintNlpParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        quoteAmount=to_x18(2000),
    )
    # TODO: enable once NLP goes live for all
    # res = client.mint_nlp(mint_nlp_params)
    # print("mint nlp results:", res.json(indent=2))

    print("burning nlp...")
    burn_nlp_params = BurnNlpParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        nlpAmount=to_x18(1),
        nonce=client.tx_nonce(
            subaccount_to_hex(
                SubaccountParams(
                    subaccount_owner=client.signer.address, subaccount_name="default"
                )
            )
        ),
    )
    # TODO: enable once NLP goes live for all
    # res = client.burn_nlp(burn_nlp_params)
    # print("burn lp result:", res.json(indent=2))

    print("liquidating subaccount...")
    liquidate_subaccount_params = LiquidateSubaccountParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        liquidatee=subaccount_to_bytes32(
            "0x13df46D99A81DcA51A7fC9852a0c1b88072B6Ba9", "default"
        ),
        productId=1,
        isEncodedSpread=False,
        amount=to_x18(1),
    )
    try:
        res = client.liquidate_subaccount(liquidate_subaccount_params)
        print("liquidate subaccount result:", res.json(indent=2))
    except Exception as e:
        print("liquidate subaccount failed with error:", e)

    linked_signer: LocalAccount = Account.from_key(
        LINKED_SIGNER_PRIVATE_KEY or SIGNER_PRIVATE_KEY
    )

    print("linking signer...", linked_signer.address)
    link_signer_params = LinkSignerParams(
        sender=client.signer.address + str_to_hex("default"),
        signer=subaccount_to_bytes32(linked_signer.address, "default"),
    )

    try:
        res = client.link_signer(link_signer_params)
        print("link signer result:", res.json(indent=2))
    except Exception as e:
        print("link signer failed with error:", e)
    else:
        print(
            "linked signer:",
            client.get_linked_signer(
                subaccount=bytes32_to_hex(link_signer_params.sender)
            ).json(indent=2),
        )

        print("placing order as a linked signer...")
        client.linked_signer = linked_signer

        order = OrderParams(
            sender=SubaccountParams(
                subaccount_owner=client.signer.address, subaccount_name="default"
            ),
            priceX18=to_x18(order_price),
            amount=to_pow_10(1, 17),
            expiration=get_expiration_timestamp(40),
            nonce=gen_order_nonce(),
            appendix=build_appendix(OrderType.DEFAULT),
        )
        order_digest = client.get_order_digest(order, 2)
        print("order digest:", order_digest)

        place_order = PlaceOrderParams(product_id=2, order=order)
        res = client.place_order(place_order)
        print("order result:", res.json(indent=2))

    print("querying linked signer post update...")
    linked_signer_res = client.get_linked_signer(
        subaccount=bytes32_to_hex(link_signer_params.sender)
    )
    print("linked signer:", linked_signer_res.json(indent=2))

    print("revoking signer...")
    link_signer_params.signer = zero_subaccount()
    res = client.link_signer(link_signer_params)
    print("revoke signer result:", res.json(indent=2))

    client.linked_signer = None

    print("querying linked signer post revoking...")
    linked_signer_res = client.get_linked_signer(
        subaccount=bytes32_to_hex(link_signer_params.sender)
    )
    print("linked signer:", linked_signer_res.json(indent=2))

    print("withdrawing collateral...")
    withdraw_collateral_params = WithdrawCollateralParams(
        sender=SubaccountParams(
            subaccount_owner=client.signer.address, subaccount_name="default"
        ),
        productId=0,
        amount=to_pow_10(1, 6),
    )

    res = client.withdraw_collateral(withdraw_collateral_params)
    print("withdraw collateral result:", res.json(indent=2))
