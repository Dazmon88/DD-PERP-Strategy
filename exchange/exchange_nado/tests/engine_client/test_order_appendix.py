import time
import pytest
from unittest.mock import MagicMock

from nado_protocol.client import create_nado_client
from nado_protocol.utils.order import (
    APPENDIX_VERSION,
    OrderAppendixTriggerType,
    build_appendix,
    order_execution_type,
    order_is_isolated,
    order_is_trigger_order,
    order_isolated_margin,
    order_reduce_only,
    order_trigger_type,
    order_twap_data,
    order_version,
)
from nado_protocol.utils.expiration import OrderType
from nado_protocol.utils.math import to_x6
from nado_protocol.utils.subaccount import SubaccountParams


def test_basic_appendix_functionality():
    """Test basic appendix building and extraction."""
    # Test default appendix (should be minimal)
    appendix = build_appendix(OrderType.DEFAULT)
    assert order_version(appendix) == APPENDIX_VERSION
    assert order_execution_type(appendix) == OrderType.DEFAULT
    assert not order_reduce_only(appendix)
    assert not order_is_isolated(appendix)
    assert not order_is_trigger_order(appendix)

    # Test with various order types
    for order_type in [
        OrderType.DEFAULT,
        OrderType.IOC,
        OrderType.FOK,
        OrderType.POST_ONLY,
    ]:
        appendix = build_appendix(order_type, reduce_only=True)
        assert order_execution_type(appendix) == order_type
        assert order_reduce_only(appendix)


def test_isolated_position_functionality():
    """Test isolated position appendix functionality."""
    # Test isolated position with various margin amounts (must fit in 64 bits)
    test_margins = [1, 5, 10]  # Different margin sizes that fit in 64-bit x18

    for margin in test_margins:
        margin_x18 = to_x6(margin)
        appendix = build_appendix(
            OrderType.POST_ONLY, isolated=True, isolated_margin=margin_x18
        )

        assert order_is_isolated(appendix)
        assert order_isolated_margin(appendix) == margin_x18
        assert order_execution_type(appendix) == OrderType.POST_ONLY

    # Test isolated position with maximum margin
    max_margin = (1 << 64) - 1  # Maximum 64-bit value
    appendix = build_appendix(
        OrderType.DEFAULT, isolated=True, isolated_margin=max_margin
    )
    assert order_isolated_margin(appendix) == max_margin

    # Test non-isolated orders
    appendix = build_appendix(OrderType.DEFAULT, isolated=False)
    assert not order_is_isolated(appendix)
    assert order_isolated_margin(appendix) is None


def test_twap_functionality():
    """Test TWAP order appendix functionality."""
    # Test various TWAP configurations
    twap_configs = [
        (5, 0.01),  # 5 orders, 1% slippage
        (10, 0.005),  # 10 orders, 0.5% slippage
        (100, 0.001),  # 100 orders, 0.1% slippage
        (1, 0.1),  # 1 order, 10% slippage
    ]

    for trigger_type in [
        OrderAppendixTriggerType.TWAP,
        OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
    ]:
        for times, slippage_frac in twap_configs:
            appendix = build_appendix(
                OrderType.DEFAULT,
                trigger_type=trigger_type,
                twap_times=times,
                twap_slippage_frac=slippage_frac,
            )

            assert order_is_trigger_order(appendix)
            assert order_trigger_type(appendix) == trigger_type

            twap_data = order_twap_data(appendix)
            assert twap_data is not None
            extracted_orders, extracted_slippage = twap_data
            assert extracted_orders == times
            assert (
                abs(extracted_slippage - slippage_frac) < 1e-6
            )  # Allow for floating point precision


def test_trigger_order_functionality():
    """Test trigger order functionality."""
    # Test price-based trigger orders
    appendix = build_appendix(
        OrderType.DEFAULT, trigger_type=OrderAppendixTriggerType.PRICE
    )
    assert order_is_trigger_order(appendix)
    assert order_trigger_type(appendix) == OrderAppendixTriggerType.PRICE
    assert order_twap_data(appendix) is None  # Should be None for price triggers

    # Test non-trigger orders
    appendix = build_appendix(OrderType.DEFAULT)
    assert not order_is_trigger_order(appendix)


def test_validation_and_edge_cases():
    """Test validation rules and edge cases."""
    # Test isolated + TWAP mutual exclusion
    with pytest.raises(
        ValueError, match="An order cannot be both isolated and a TWAP order"
    ):
        build_appendix(
            OrderType.DEFAULT,
            isolated=True,
            trigger_type=OrderAppendixTriggerType.TWAP,
            isolated_margin=to_x6(10),
            twap_times=5,
            twap_slippage_frac=0.01,
        )

    # Test TWAP parameter validation
    with pytest.raises(
        ValueError,
        match="twap_times and twap_slippage_frac are required for TWAP orders",
    ):
        build_appendix(OrderType.DEFAULT, trigger_type=OrderAppendixTriggerType.TWAP)

    # Test isolated margin validation
    with pytest.raises(
        ValueError, match="isolated_margin can only be set when isolated=True"
    ):
        build_appendix(OrderType.DEFAULT, isolated=False, isolated_margin=to_x6(10))


def test_round_trip_conversions():
    """Test that all appendix values can be built and decoded correctly."""
    # Test various combinations
    test_cases = [
        # Basic cases - need to add order_type parameter
        {"order_type": OrderType.DEFAULT},
        {"order_type": OrderType.IOC, "reduce_only": True},
        {"order_type": OrderType.FOK, "reduce_only": False},
        {"order_type": OrderType.POST_ONLY, "reduce_only": True},
        # Trigger cases
        {
            "order_type": OrderType.DEFAULT,
            "trigger_type": OrderAppendixTriggerType.PRICE,
        },
        # TWAP cases
        {
            "order_type": OrderType.DEFAULT,
            "trigger_type": OrderAppendixTriggerType.TWAP,
            "twap_times": 5,
            "twap_slippage_frac": 0.01,
        },
        {
            "order_type": OrderType.DEFAULT,
            "trigger_type": OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
            "twap_times": 10,
            "twap_slippage_frac": 0.005,
        },
        # Isolated cases
        {
            "order_type": OrderType.DEFAULT,
            "isolated": True,
            "isolated_margin": to_x6(1),
        },
        {
            "order_type": OrderType.POST_ONLY,
            "isolated": True,
            "isolated_margin": to_x6(10),
            "reduce_only": True,
        },
    ]

    for case in test_cases:
        # Build appendix - extract order_type as first positional parameter
        order_type = case.pop("order_type", OrderType.DEFAULT)
        appendix = build_appendix(order_type, **case)

        # Extract values
        extracted = {
            "version": order_version(appendix),
            "order_type": order_execution_type(appendix),
            "reduce_only": order_reduce_only(appendix),
            "is_isolated": order_is_isolated(appendix),
            "isolated_margin": order_isolated_margin(appendix),
            "is_trigger": order_is_trigger_order(appendix),
            "trigger_type": order_trigger_type(appendix),
            "twap_data": order_twap_data(appendix),
        }

        # Verify key values match
        assert extracted["version"] == APPENDIX_VERSION

        if "order_type" in case:
            assert extracted["order_type"] == case["order_type"]

        if "reduce_only" in case:
            assert extracted["reduce_only"] == case["reduce_only"]

        if case.get("isolated"):
            assert extracted["is_isolated"]
            assert extracted["isolated_margin"] == case["isolated_margin"]

        if "trigger_type" in case:
            assert extracted["is_trigger"]
            assert extracted["trigger_type"] == case["trigger_type"]

            if case["trigger_type"] in [
                OrderAppendixTriggerType.TWAP,
                OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
            ]:
                assert extracted["twap_data"] is not None
                orders, slippage = extracted["twap_data"]
                assert orders == case["twap_times"]
                assert abs(slippage - case["twap_slippage_frac"]) < 1e-6
