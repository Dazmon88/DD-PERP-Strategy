from nado_protocol.utils.expiration import (
    OrderType,
    get_expiration_timestamp,
)
from nado_protocol.utils.order import (
    build_appendix,
    order_execution_type,
    order_reduce_only,
)


def test_simple_expiration():
    """Test that get_expiration_timestamp now returns timestamp + seconds."""
    import time

    seconds_from_now = 40
    before = int(time.time())
    result = get_expiration_timestamp(seconds_from_now)
    after = int(time.time())
    # Should be approximately current time + seconds_from_now
    assert before + seconds_from_now <= result <= after + seconds_from_now + 1


def test_order_types_via_appendix():
    """Test that order types are now handled via build_appendix."""
    for order_type in [
        OrderType.DEFAULT,
        OrderType.IOC,
        OrderType.FOK,
        OrderType.POST_ONLY,
    ]:
        appendix = build_appendix(order_type)
        extracted_order_type = order_execution_type(appendix)
        assert extracted_order_type == order_type


def test_reduce_only_via_appendix():
    """Test that reduce_only is now handled via build_appendix."""
    # Test reduce_only=True
    reduce_only_appendix = build_appendix(OrderType.FOK, reduce_only=True)
    assert order_reduce_only(reduce_only_appendix)
    assert order_execution_type(reduce_only_appendix) == OrderType.FOK

    # Test reduce_only=False
    non_reduce_only_appendix = build_appendix(OrderType.FOK, reduce_only=False)
    assert not order_reduce_only(non_reduce_only_appendix)
    assert order_execution_type(non_reduce_only_appendix) == OrderType.FOK
