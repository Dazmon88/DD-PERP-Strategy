import pytest
from nado_protocol.utils.twap import (
    create_twap_order,
    validate_twap_order,
    estimate_twap_completion_time,
    calculate_equal_amounts,
)
from nado_protocol.utils.order import (
    OrderAppendixTriggerType,
    order_twap_data,
    order_trigger_type,
    order_execution_type,
    order_reduce_only,
)
from nado_protocol.utils.expiration import OrderType
from nado_protocol.utils.bytes32 import hex_to_bytes32


def test_create_basic_twap_order(senders):
    """Test creating a basic TWAP order with equal amounts."""
    order = create_twap_order(
        product_id=1,
        sender=senders[0],
        price_x18="50000000000000000000000",
        total_amount_x18="1000000000000000000",
        expiration=1700000000,
        nonce=123456,
        times=5,
        slippage_frac=0.01,
        interval_seconds=300,
    )

    assert order.product_id == 1
    assert order.order.sender == hex_to_bytes32(senders[0])
    assert order.order.amount == 1000000000000000000
    assert order.trigger.time_trigger.interval == 300
    assert order.trigger.time_trigger.amounts is None

    # Check appendix encoding
    appendix = int(order.order.appendix)

    # Should be TWAP trigger type (2)
    trigger_type = order_trigger_type(appendix)
    assert trigger_type == OrderAppendixTriggerType.TWAP

    # Should be IOC execution type
    execution_type = order_execution_type(appendix)
    assert execution_type == OrderType.IOC

    # Check TWAP data
    times, slippage = order_twap_data(appendix)
    assert times == 5
    assert abs(slippage - 0.01) < 1e-6


def test_create_custom_amounts_twap_order():
    """Test creating a TWAP order with custom amounts."""
    custom_amounts_x18 = ["400", "300", "200", "100"]
    total_amount_x18 = "1000"

    order = create_twap_order(
        product_id=2,
        sender="0x" + "2" * 64,
        price_x18="25000000000000000000000",
        total_amount_x18=total_amount_x18,
        expiration=1700000000,
        nonce=789012,
        times=4,
        slippage_frac=0.005,
        interval_seconds=600,
        custom_amounts_x18=custom_amounts_x18,
    )

    assert order.trigger.time_trigger.amounts == custom_amounts_x18

    # Should be TWAP_CUSTOM_AMOUNTS trigger type (3)
    appendix = int(order.order.appendix)
    trigger_type = order_trigger_type(appendix)
    assert trigger_type == OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS


def test_validate_twap_order_equal_distribution():
    """Test TWAP validation for equal distribution."""
    # Valid case
    validate_twap_order("1000", 5)

    # Invalid case - not divisible
    with pytest.raises(ValueError, match="must be divisible"):
        validate_twap_order("1001", 5)


def test_validate_twap_order_custom_amounts():
    """Test TWAP validation for custom amounts."""
    # Valid case
    validate_twap_order("1000", 3, ["400", "300", "300"])

    # Invalid case - wrong length
    with pytest.raises(ValueError, match="length.*must equal"):
        validate_twap_order("1000", 3, ["400", "300"])

    # Invalid case - wrong sum
    with pytest.raises(ValueError, match="Sum.*must equal"):
        validate_twap_order("1000", 3, ["400", "300", "200"])


def test_estimate_twap_completion_time():
    """Test TWAP completion time estimation."""
    # 5 executions with 300 second intervals = 4 * 300 = 1200 seconds
    time = estimate_twap_completion_time(5, 300)
    assert time == 1200

    # Single execution should take 0 time
    time = estimate_twap_completion_time(1, 300)
    assert time == 0


def test_calculate_equal_amounts():
    """Test calculating equal amounts for TWAP executions."""
    amounts = calculate_equal_amounts("1000", 5)
    assert amounts == ["200", "200", "200", "200", "200"]

    # Test with negative amounts (sell orders)
    amounts = calculate_equal_amounts("-1500", 3)
    assert amounts == ["-500", "-500", "-500"]

    # Invalid case
    with pytest.raises(ValueError, match="not divisible"):
        calculate_equal_amounts("1001", 5)


def test_twap_order_validation_errors(senders):
    """Test TWAP order creation validation errors."""
    base_params = {
        "product_id": 1,
        "sender": senders[0],
        "price_x18": "50000000000000000000000",
        "total_amount_x18": "1000000000000000000",
        "expiration": 1700000000,
        "nonce": 123456,
        "interval_seconds": 300,
        "slippage_frac": 0.01,
    }

    # Invalid times
    with pytest.raises(ValueError, match="must be between 1 and 500"):
        create_twap_order(**base_params, times=0)

    with pytest.raises(ValueError, match="must be between 1 and 500"):
        create_twap_order(**base_params, times=501)

    # Invalid slippage
    invalid_slippage_params = base_params.copy()
    invalid_slippage_params["slippage_frac"] = -0.1
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        create_twap_order(**invalid_slippage_params, times=5)

    invalid_slippage_params["slippage_frac"] = 1.1
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        create_twap_order(**invalid_slippage_params, times=5)

    # Invalid interval
    invalid_interval_params = base_params.copy()
    invalid_interval_params["interval_seconds"] = 0
    with pytest.raises(ValueError, match="must be positive"):
        create_twap_order(**invalid_interval_params, times=5)


def test_twap_with_reduce_only(senders):
    """Test creating TWAP order with reduce_only flag."""
    order = create_twap_order(
        product_id=1,
        sender=senders[0],
        price_x18="50000000000000000000000",
        total_amount_x18="-500000000000000000",  # Sell order
        expiration=1700000000,
        nonce=123456,
        times=2,
        slippage_frac=0.01,
        interval_seconds=300,
        reduce_only=True,
    )

    # Check that reduce_only is encoded in appendix
    appendix = int(order.order.appendix)
    assert order_reduce_only(appendix) is True


def test_twap_edge_cases(senders):
    """Test TWAP creation with edge case values."""
    # Maximum times
    order = create_twap_order(
        product_id=1,
        sender=senders[0],
        price_x18="1000000000000000000000",
        total_amount_x18="50000000000000000000000",  # Large amount
        expiration=1700000000,
        nonce=123456,
        times=500,
        slippage_frac=0.999999,  # Maximum slippage
        interval_seconds=1,  # Minimum interval
    )

    appendix = int(order.order.appendix)
    times, slippage = order_twap_data(appendix)
    assert times == 500
    assert abs(slippage - 0.999999) < 1e-6


def test_negative_amount_twap(senders):
    """Test TWAP order with negative amount (sell order)."""
    order = create_twap_order(
        product_id=1,
        sender=senders[0],
        price_x18="50000000000000000000000",
        total_amount_x18="-2000000000000000000",  # -2 BTC
        expiration=1700000000,
        nonce=123456,
        times=4,
        slippage_frac=0.01,
        interval_seconds=900,
    )

    assert order.order.amount == -2000000000000000000
    assert order.trigger.time_trigger.interval == 900
