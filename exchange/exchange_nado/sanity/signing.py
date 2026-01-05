from sanity import CLIENT_MODE, SIGNER_PRIVATE_KEY
from nado_protocol.contracts.types import NadoTxType
from nado_protocol.utils.bytes32 import subaccount_to_hex, subaccount_to_bytes32
from nado_protocol.contracts.eip712.sign import (
    build_eip712_typed_data,
    sign_eip712_typed_data,
)
from nado_protocol.client import NadoClient, create_nado_client


import time

from nado_protocol.engine_client.types.execute import (
    OrderParams,
)

from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
from nado_protocol.utils.order import build_appendix
from nado_protocol.utils.math import to_pow_10, to_x18
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.subaccount import SubaccountParams
from nado_protocol.utils.time import now_in_millis


def run():
    print("setting up nado client...")
    client: NadoClient = create_nado_client(CLIENT_MODE, SIGNER_PRIVATE_KEY)

    print("chain_id:", client.context.engine_client.get_contracts().chain_id)

    subaccount = subaccount_to_hex(client.context.signer.address, "default")

    print("subaccount:", subaccount)

    print("building StreamAuthentication signature...")
    authenticate_stream_typed_data = build_eip712_typed_data(
        tx=NadoTxType.AUTHENTICATE_STREAM,
        msg={
            "sender": subaccount_to_bytes32(subaccount),
            "expiration": now_in_millis(90),
        },
        verifying_contract=client.context.contracts.endpoint.address,
        chain_id=client.context.engine_client.chain_id,
    )
    authenticate_stream_signature = sign_eip712_typed_data(
        typed_data=authenticate_stream_typed_data, signer=client.context.signer
    )
    print("authenticate stream signature:", authenticate_stream_signature)

    print("building order signature...")
    order = OrderParams(
        sender=SubaccountParams(
            subaccount_owner=client.context.signer.address, subaccount_name="default"
        ),
        priceX18=to_x18(60000),
        amount=to_pow_10(1, 17),
        expiration=get_expiration_timestamp(40),
        appendix=build_appendix(OrderType.DEFAULT),
        nonce=gen_order_nonce(),
    )
    now = time.time()
    signature = client.context.engine_client._sign(
        "place_order", order.dict(), product_id=1
    )
    elapsed_time = (time.time() - now) * 1000
    print("place order signature:", signature, "elapsed_time:", elapsed_time)
