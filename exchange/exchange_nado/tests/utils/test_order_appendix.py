import pytest
from nado_protocol.utils.order import (
    APPENDIX_VERSION,
    AppendixBitFields,
    OrderAppendixTriggerType,
    TWAPBitFields,
    build_appendix,
    order_execution_type,
    order_is_isolated,
    order_is_trigger_order,
    order_isolated_margin,
    order_reduce_only,
    order_trigger_type,
    order_twap_data,
    order_version,
    pack_twap_appendix_value,
    unpack_twap_appendix_value,
)
from nado_protocol.utils.expiration import OrderType
from nado_protocol.utils.math import to_x6


def order_type_appendix_bit(order_type: OrderType) -> int:
    """
    Gets the appendix bits for a given order type.

    Args:
        order_type (OrderType): The order type.

    Returns:
        int: The appendix bits for the order type.
    """
    return int(order_type) << AppendixBitFields.ORDER_TYPE_SHIFT


def test_appendix_bit_field_sizes():
    """Test that bit field sizes are correct."""
    assert AppendixBitFields.VERSION_BITS == 8
    assert AppendixBitFields.ISOLATED_BITS == 1
    assert AppendixBitFields.ORDER_TYPE_BITS == 2
    assert AppendixBitFields.REDUCE_ONLY_BITS == 1
    assert AppendixBitFields.TRIGGER_TYPE_BITS == 2
    assert AppendixBitFields.RESERVED_BITS == 50
    assert AppendixBitFields.VALUE_BITS == 64


def test_appendix_bit_masks():
    """Test that bit masks match expected values."""
    assert AppendixBitFields.VERSION_MASK == 255
    assert AppendixBitFields.ISOLATED_MASK == 1
    assert AppendixBitFields.ORDER_TYPE_MASK == 3
    assert AppendixBitFields.REDUCE_ONLY_MASK == 1
    assert AppendixBitFields.TRIGGER_TYPE_MASK == 3
    assert AppendixBitFields.RESERVED_MASK == (1 << 50) - 1
    assert AppendixBitFields.VALUE_MASK == (1 << 64) - 1


def test_appendix_bit_shift_positions():
    """Test that bit shift positions are correct."""
    assert AppendixBitFields.VERSION_SHIFT == 0
    assert AppendixBitFields.ISOLATED_SHIFT == 8
    assert AppendixBitFields.ORDER_TYPE_SHIFT == 9
    assert AppendixBitFields.REDUCE_ONLY_SHIFT == 11
    assert AppendixBitFields.TRIGGER_TYPE_SHIFT == 12
    assert AppendixBitFields.RESERVED_SHIFT == 14
    assert AppendixBitFields.VALUE_SHIFT == 64


def test_order_type_appendix_bits():
    """Test that order types are encoded correctly."""
    assert (
        order_type_appendix_bit(OrderType.DEFAULT)
        == 0 << AppendixBitFields.ORDER_TYPE_SHIFT
    )
    assert (
        order_type_appendix_bit(OrderType.IOC)
        == 1 << AppendixBitFields.ORDER_TYPE_SHIFT
    )
    assert (
        order_type_appendix_bit(OrderType.FOK)
        == 2 << AppendixBitFields.ORDER_TYPE_SHIFT
    )
    assert (
        order_type_appendix_bit(OrderType.POST_ONLY)
        == 3 << AppendixBitFields.ORDER_TYPE_SHIFT
    )


def test_order_type_bit_positions():
    """Test that order type bits are in correct positions."""
    assert order_type_appendix_bit(OrderType.IOC) == 512  # 2^9
    assert order_type_appendix_bit(OrderType.FOK) == 1024  # 2^10
    assert order_type_appendix_bit(OrderType.POST_ONLY) == 1536  # 2^9 + 2^10


def test_twap_basic_packing():
    """Test basic TWAP packing functionality."""
    times = 5
    slippage_frac = 0.01

    packed = pack_twap_appendix_value(times, slippage_frac)
    unpacked_orders, unpacked_slippage = unpack_twap_appendix_value(packed)

    assert unpacked_orders == times
    assert unpacked_slippage == slippage_frac


def test_twap_edge_values():
    """Test TWAP packing with edge values."""
    # Test minimum values
    packed = pack_twap_appendix_value(1, 0.000001)
    orders, slippage = unpack_twap_appendix_value(packed)
    assert orders == 1
    assert slippage == 0.000001

    # Test maximum 32-bit values
    max_orders = (1 << 32) - 1  # 2^32 - 1
    max_slippage = 4.294967295

    packed = pack_twap_appendix_value(max_orders, max_slippage)
    orders, slippage = unpack_twap_appendix_value(packed)
    assert orders == max_orders


def test_twap_bit_layout():
    """Test that TWAP packing follows the correct bit layout."""
    times = 10
    slippage_frac = 0.005

    packed = pack_twap_appendix_value(times, slippage_frac)

    # Check bit positions
    extracted_orders = (packed >> TWAPBitFields.TIMES_SHIFT) & TWAPBitFields.TIMES_MASK
    assert extracted_orders == times

    extracted_slippage_x6 = (
        packed >> TWAPBitFields.SLIPPAGE_SHIFT
    ) & TWAPBitFields.SLIPPAGE_MASK
    assert extracted_slippage_x6 == int(slippage_frac * TWAPBitFields.SLIPPAGE_SCALE)


def test_basic_appendix_construction():
    """Test building basic appendix with order type."""
    appendix = build_appendix(OrderType.IOC)

    assert order_version(appendix) == APPENDIX_VERSION
    assert order_execution_type(appendix) == OrderType.IOC
    assert not order_reduce_only(appendix)
    assert not order_is_isolated(appendix)
    assert not order_is_trigger_order(appendix)


def test_reduce_only_flag():
    """Test reduce-only flag functionality."""
    appendix = build_appendix(OrderType.DEFAULT, reduce_only=True)
    assert order_reduce_only(appendix)

    appendix = build_appendix(OrderType.DEFAULT, reduce_only=False)
    assert not order_reduce_only(appendix)


def test_all_order_types():
    """Test all order execution types."""
    for order_type in [
        OrderType.DEFAULT,
        OrderType.IOC,
        OrderType.FOK,
        OrderType.POST_ONLY,
    ]:
        appendix = build_appendix(order_type)
        assert order_execution_type(appendix) == order_type


def test_combination_flags():
    """Test combinations of flags."""
    appendix = build_appendix(OrderType.FOK, reduce_only=True)

    assert order_version(appendix) == APPENDIX_VERSION
    assert order_execution_type(appendix) == OrderType.FOK
    assert order_reduce_only(appendix)
    assert not order_is_isolated(appendix)
    assert not order_is_trigger_order(appendix)


def test_trigger_order_types():
    """Test all trigger order types."""
    for trigger_type in OrderAppendixTriggerType:
        if trigger_type in [
            OrderAppendixTriggerType.TWAP,
            OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
        ]:
            appendix = build_appendix(
                OrderType.DEFAULT,
                trigger_type=trigger_type,
                twap_times=5,
                twap_slippage_frac=0.01,
            )
        else:
            appendix = build_appendix(OrderType.DEFAULT, trigger_type=trigger_type)

        extracted_trigger_type = order_trigger_type(appendix)
        assert extracted_trigger_type == trigger_type

        assert order_is_trigger_order(appendix) == True


def test_twap_order_data_extraction():
    """Test TWAP order data extraction."""
    times = 10
    slippage_frac = 0.005

    appendix = build_appendix(
        OrderType.DEFAULT,
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=times,
        twap_slippage_frac=slippage_frac,
    )

    twap_data = order_twap_data(appendix)
    assert twap_data is not None
    extracted_orders, extracted_slippage = twap_data
    assert extracted_orders == times
    assert extracted_slippage == slippage_frac


def test_non_twap_order_data_extraction():
    """Test that non-TWAP orders return None for TWAP data."""
    appendix = build_appendix(
        OrderType.DEFAULT, trigger_type=OrderAppendixTriggerType.PRICE
    )
    twap_data = order_twap_data(appendix)
    assert twap_data is None

    appendix = build_appendix(OrderType.DEFAULT)
    twap_data = order_twap_data(appendix)
    assert twap_data is None


def test_isolated_order_basic():
    """Test basic isolated order functionality."""
    margin = to_x6(10)
    appendix = build_appendix(OrderType.DEFAULT, isolated=True, isolated_margin=margin)

    assert order_is_isolated(appendix)
    assert order_isolated_margin(appendix) == margin


def test_isolated_order_with_other_flags():
    """Test isolated order with other flags."""
    margin = to_x6(5)
    appendix = build_appendix(
        OrderType.POST_ONLY, isolated=True, reduce_only=True, isolated_margin=margin
    )

    assert order_is_isolated(appendix)
    assert order_isolated_margin(appendix) == margin
    assert order_execution_type(appendix) == OrderType.POST_ONLY
    assert order_reduce_only(appendix)
    assert order_version(appendix) == APPENDIX_VERSION


def test_non_isolated_order():
    """Test non-isolated orders."""
    appendix = build_appendix(OrderType.DEFAULT, isolated=False)

    assert not order_is_isolated(appendix)
    assert order_isolated_margin(appendix) is None


def test_isolated_margin_max_value():
    """Test isolated margin with maximum value."""
    max_margin = AppendixBitFields.VALUE_MASK
    appendix = build_appendix(
        OrderType.DEFAULT, isolated=True, isolated_margin=max_margin
    )

    assert order_is_isolated(appendix)
    assert order_isolated_margin(appendix) == max_margin


def test_version_bits():
    """Test version bit positions."""
    appendix = build_appendix(OrderType.DEFAULT)
    assert order_version(appendix) == APPENDIX_VERSION


def test_custom_version():
    """Test that custom version parameter works correctly."""
    custom_version = 5
    appendix = build_appendix(OrderType.DEFAULT, _version=custom_version)
    assert order_version(appendix) == custom_version

    # Test that other functionality works with custom version
    appendix = build_appendix(OrderType.IOC, reduce_only=True, _version=custom_version)
    assert order_version(appendix) == custom_version
    assert order_execution_type(appendix) == OrderType.IOC
    assert order_reduce_only(appendix)


def test_reserved_bits_extraction():
    """Test reserved bits extraction."""
    appendix = build_appendix(OrderType.DEFAULT)

    def order_reserved_bits(appendix: int) -> int:
        """
        Extracts the reserved bits from the appendix value.

        Args:
            appendix (int): The order appendix value.

        Returns:
            int: The reserved bits (bits 31..14).
        """
        return (
            appendix >> AppendixBitFields.RESERVED_SHIFT
        ) & AppendixBitFields.RESERVED_MASK

    reserved = order_reserved_bits(appendix)
    assert reserved == 0


def test_isolated_margin_without_isolated_flag():
    """Test that providing isolated_margin without isolated=True raises error."""
    with pytest.raises(
        ValueError, match="isolated_margin can only be set when isolated=True"
    ):
        build_appendix(OrderType.DEFAULT, isolated=False, isolated_margin=to_x6(1000))


def test_twap_parameters_without_twap_trigger():
    """Test that TWAP parameters are required for TWAP orders."""
    with pytest.raises(
        ValueError,
        match="twap_times and twap_slippage_frac are required for TWAP orders",
    ):
        build_appendix(OrderType.DEFAULT, trigger_type=OrderAppendixTriggerType.TWAP)


def test_isolated_and_twap_mutual_exclusion():
    """Test that isolated and TWAP orders are mutually exclusive."""
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


def test_typescript_basic_appendix_compatibility():
    """Test that our values match TypeScript SDK for basic appendix."""
    appendix = build_appendix(
        OrderType.DEFAULT, trigger_type=OrderAppendixTriggerType.PRICE
    )
    assert appendix == 4097


def test_typescript_reduce_only_compatibility():
    """Test reduce-only compatibility with TypeScript SDK."""
    appendix = build_appendix(
        OrderType.DEFAULT, reduce_only=True, trigger_type=OrderAppendixTriggerType.PRICE
    )
    assert appendix == 6145


def test_typescript_twap_compatibility():
    """Test TWAP compatibility with TypeScript SDK."""
    appendix = build_appendix(
        OrderType.DEFAULT,
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=10,
        twap_slippage_frac=0.005,
    )
    assert appendix == 792281717376363744483197591553


def test_basic_round_trip():
    """Test basic round-trip conversion."""
    original_appendix = build_appendix(OrderType.FOK, reduce_only=True)

    version = order_version(original_appendix)
    order_type = order_execution_type(original_appendix)
    reduce_only = order_reduce_only(original_appendix)

    rebuilt_appendix = build_appendix(order_type, reduce_only=reduce_only)

    assert original_appendix == rebuilt_appendix


def test_isolated_round_trip():
    """Test isolated order round-trip conversion."""
    original_margin = to_x6(12)
    original_appendix = build_appendix(
        OrderType.POST_ONLY, isolated=True, isolated_margin=original_margin
    )

    version = order_version(original_appendix)
    is_isolated = order_is_isolated(original_appendix)
    margin = order_isolated_margin(original_appendix)
    order_type = order_execution_type(original_appendix)

    rebuilt_appendix = build_appendix(
        order_type, isolated=is_isolated, isolated_margin=margin
    )

    assert original_appendix == rebuilt_appendix


def test_twap_round_trip():
    """Test TWAP order round-trip conversion."""
    original_orders = 7
    original_slippage = 0.0075

    original_appendix = build_appendix(
        OrderType.DEFAULT,
        reduce_only=True,
        trigger_type=OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
        twap_times=original_orders,
        twap_slippage_frac=original_slippage,
    )

    version = order_version(original_appendix)
    trigger_type = order_trigger_type(original_appendix)
    reduce_only = order_reduce_only(original_appendix)
    twap_data = order_twap_data(original_appendix)

    assert twap_data is not None
    extracted_orders, extracted_slippage = twap_data

    rebuilt_appendix = build_appendix(
        OrderType.DEFAULT,
        reduce_only=reduce_only,
        trigger_type=trigger_type,
        twap_times=extracted_orders,
        twap_slippage_frac=extracted_slippage,
    )

    assert original_appendix == rebuilt_appendix


def test_bit_field_isolation():
    """Test that bit fields are properly isolated."""
    base_appendix = build_appendix(OrderType.DEFAULT)

    isolated_appendix = build_appendix(
        OrderType.DEFAULT, isolated=True, isolated_margin=to_x6(1)
    )
    assert order_is_isolated(isolated_appendix)
    assert not order_is_isolated(base_appendix)

    fok_appendix = build_appendix(OrderType.FOK)
    assert order_execution_type(fok_appendix) == OrderType.FOK
    assert order_execution_type(base_appendix) == OrderType.DEFAULT


def test_all_combinations_work():
    """Test various valid combinations of flags."""
    # Compatible combinations
    appendix = build_appendix(
        OrderType.POST_ONLY,
        isolated=True,
        reduce_only=True,
        isolated_margin=to_x6(10),
    )

    assert order_version(appendix) == APPENDIX_VERSION
    assert order_is_isolated(appendix)
    assert order_isolated_margin(appendix) == to_x6(10)
    assert order_execution_type(appendix) == OrderType.POST_ONLY
    assert order_reduce_only(appendix)
    assert not order_is_trigger_order(appendix)


def test_twap_ioc_requirement():
    """Test that TWAP orders must use IOC execution type."""
    # TWAP orders should work with IOC
    appendix = build_appendix(
        OrderType.IOC,
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=5,
        twap_slippage_frac=0.01,
    )

    assert order_execution_type(appendix) == OrderType.IOC
    assert order_trigger_type(appendix) == OrderAppendixTriggerType.TWAP
    twap_data = order_twap_data(appendix)
    assert twap_data == (5, 0.01)


def test_twap_custom_amounts_trigger():
    """Test TWAP_CUSTOM_AMOUNTS trigger type."""
    times = 3
    slippage = 0.02

    appendix = build_appendix(
        OrderType.IOC,
        trigger_type=OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
        twap_times=times,
        twap_slippage_frac=slippage,
    )

    assert order_trigger_type(appendix) == OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS
    assert order_execution_type(appendix) == OrderType.IOC
    assert order_is_trigger_order(appendix)

    twap_data = order_twap_data(appendix)
    assert twap_data is not None
    extracted_times, extracted_slippage = twap_data
    assert extracted_times == times
    assert abs(extracted_slippage - slippage) < 1e-6


def test_twap_reduce_only_combination():
    """Test TWAP orders with reduce_only flag."""
    appendix = build_appendix(
        OrderType.IOC,
        reduce_only=True,
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=10,
        twap_slippage_frac=0.005,
    )

    assert order_reduce_only(appendix)
    assert order_trigger_type(appendix) == OrderAppendixTriggerType.TWAP
    assert order_execution_type(appendix) == OrderType.IOC


def test_twap_large_values():
    """Test TWAP with large times and precise slippage."""
    times = 500  # Maximum allowed
    slippage = 0.123456  # Precise slippage

    appendix = build_appendix(
        OrderType.IOC,
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=times,
        twap_slippage_frac=slippage,
    )

    twap_data = order_twap_data(appendix)
    assert twap_data is not None
    extracted_times, extracted_slippage = twap_data
    assert extracted_times == times
    assert abs(extracted_slippage - slippage) < 1e-6


def test_twap_minimum_values():
    """Test TWAP with minimum valid values."""
    times = 1
    slippage = 0.000001

    appendix = build_appendix(
        OrderType.IOC,
        trigger_type=OrderAppendixTriggerType.TWAP,
        twap_times=times,
        twap_slippage_frac=slippage,
    )

    twap_data = order_twap_data(appendix)
    assert twap_data is not None
    extracted_times, extracted_slippage = twap_data
    assert extracted_times == times
    assert abs(extracted_slippage - slippage) < 1e-6
