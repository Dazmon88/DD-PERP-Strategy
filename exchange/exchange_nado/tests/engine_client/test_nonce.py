import time
from nado_protocol.utils.nonce import gen_order_nonce


def test_nonce():
    nonce = gen_order_nonce()
    time_now = int(time.time()) * 1000

    assert (nonce >> 20) >= time_now and (nonce >> 20) <= time_now + 99 * 1000
