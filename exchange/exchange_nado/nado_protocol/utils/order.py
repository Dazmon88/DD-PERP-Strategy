from typing import Optional
from enum import IntEnum
from nado_protocol.utils.expiration import OrderType


# Order appendix version
APPENDIX_VERSION = 1


class AppendixBitFields:
    # | value   | reserved | trigger | reduce only | order type| isolated | version |
    # | 64 bits | 50 bits  | 2 bits  | 1 bit       | 2 bits    | 1 bit    | 8 bits  |
    # | 127..64 | 63..14   | 13..12  | 11          | 10..9     | 8        | 7..0    |

    # Bit positions (from LSB to MSB)
    VERSION_BITS = 8  # bits 7..0
    ISOLATED_BITS = 1  # bit 8
    ORDER_TYPE_BITS = 2  # bits 10..9
    REDUCE_ONLY_BITS = 1  # bit 11
    TRIGGER_TYPE_BITS = 2  # bits 13..12
    RESERVED_BITS = 50  # bits 63..14
    VALUE_BITS = 64  # bits 127..64 (for isolated margin or TWAP data)

    # Bit masks
    VERSION_MASK = (1 << VERSION_BITS) - 1
    ISOLATED_MASK = (1 << ISOLATED_BITS) - 1
    ORDER_TYPE_MASK = (1 << ORDER_TYPE_BITS) - 1
    REDUCE_ONLY_MASK = (1 << REDUCE_ONLY_BITS) - 1
    TRIGGER_TYPE_MASK = (1 << TRIGGER_TYPE_BITS) - 1
    RESERVED_MASK = (1 << RESERVED_BITS) - 1
    VALUE_MASK = (1 << VALUE_BITS) - 1

    # Bit shift positions
    VERSION_SHIFT = 0
    ISOLATED_SHIFT = 8
    ORDER_TYPE_SHIFT = 9
    REDUCE_ONLY_SHIFT = 11
    TRIGGER_TYPE_SHIFT = 12
    RESERVED_SHIFT = 14
    VALUE_SHIFT = 64


class OrderAppendixTriggerType(IntEnum):
    """
    Enumeration for trigger order types encoded in the appendix.
    """

    PRICE = 1
    TWAP = 2
    TWAP_CUSTOM_AMOUNTS = 3


class TWAPBitFields:
    """Bit field definitions for TWAP value packing within the 64-bit value field."""

    # Bit layout (MSB → LSB): | times (32 bits) | slippage_x6 (32 bits) |
    TIMES_BITS = 32
    SLIPPAGE_BITS = 32

    # Bit masks
    TIMES_MASK = (1 << TIMES_BITS) - 1
    SLIPPAGE_MASK = (1 << SLIPPAGE_BITS) - 1

    # Bit shift positions (within the 64-bit value field)
    SLIPPAGE_SHIFT = 0
    TIMES_SHIFT = 32

    # Slippage scaling factor (6 decimal places)
    SLIPPAGE_SCALE = 1_000_000


def pack_twap_appendix_value(times: int, slippage_frac: float) -> int:
    """
    Packs TWAP order fields into a 64-bit integer for the appendix.

    Bit layout (MSB → LSB):
    |   times   | slippage_x6 |
    |-----------|-------------|
    | 63..32    | 31..0       |
    | 32 bits   | 32 bits     |
    """
    slippage_x6 = int(slippage_frac * TWAPBitFields.SLIPPAGE_SCALE)

    return ((times & TWAPBitFields.TIMES_MASK) << TWAPBitFields.TIMES_SHIFT) | (
        (slippage_x6 & TWAPBitFields.SLIPPAGE_MASK) << TWAPBitFields.SLIPPAGE_SHIFT
    )


def unpack_twap_appendix_value(value: int) -> tuple[int, float]:
    """
    Unpacks a 64-bit integer into TWAP order fields.

    Args:
        value (int): The 64-bit value to unpack.

    Returns:
        tuple[int, float]: Number of TWAP executions and slippage fraction.
    """
    times = (value >> TWAPBitFields.TIMES_SHIFT) & TWAPBitFields.TIMES_MASK
    slippage_x6 = (value >> TWAPBitFields.SLIPPAGE_SHIFT) & TWAPBitFields.SLIPPAGE_MASK
    slippage_frac = slippage_x6 / TWAPBitFields.SLIPPAGE_SCALE

    return int(times), slippage_frac


def build_appendix(
    order_type: OrderType,
    isolated: bool = False,
    reduce_only: bool = False,
    trigger_type: Optional[OrderAppendixTriggerType] = None,
    isolated_margin: Optional[int] = None,
    twap_times: Optional[int] = None,
    twap_slippage_frac: Optional[float] = None,
    _version: Optional[int] = APPENDIX_VERSION,
) -> int:
    """
    Builds an appendix value with the specified parameters.

    Args:
        order_type (OrderType): The order execution type. Required.
        isolated (bool): Whether this order is for an isolated position. Defaults to False.
        reduce_only (bool): Whether this is a reduce-only order. Defaults to False.
        trigger_type (Optional[OrderAppendixTriggerType]): Trigger type. Defaults to None (no trigger).
        isolated_margin (Optional[int]): Margin amount for isolated position if isolated is True.
        twap_times (Optional[int]): Number of TWAP executions (required for TWAP trigger type).
        twap_slippage_frac (Optional[float]): TWAP slippage fraction (required for TWAP trigger type).

    Returns:
        int: The built appendix value with version set to APPENDIX_VERSION.

    Raises:
        ValueError: If parameters are invalid or incompatible.
    """
    if isolated_margin is not None and not isolated:
        raise ValueError("isolated_margin can only be set when isolated=True")

    if (
        isolated
        and trigger_type is not None
        and trigger_type
        in [OrderAppendixTriggerType.TWAP, OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS]
    ):
        raise ValueError("An order cannot be both isolated and a TWAP order")

    if trigger_type is not None and trigger_type in [
        OrderAppendixTriggerType.TWAP,
        OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
    ]:
        if twap_times is None or twap_slippage_frac is None:
            raise ValueError(
                "twap_times and twap_slippage_frac are required for TWAP orders"
            )

    appendix = 0

    version = _version if _version is not None else APPENDIX_VERSION

    # Version (bits 7..0)
    appendix |= (
        version & AppendixBitFields.VERSION_MASK
    ) << AppendixBitFields.VERSION_SHIFT

    # Isolated bit (bit 8)
    if isolated:
        appendix |= 1 << AppendixBitFields.ISOLATED_SHIFT

    # Order type (bits 10..9) - 2 bits only
    appendix |= (
        int(order_type) & AppendixBitFields.ORDER_TYPE_MASK
    ) << AppendixBitFields.ORDER_TYPE_SHIFT

    # Reduce only bit (bit 11)
    if reduce_only:
        appendix |= 1 << AppendixBitFields.REDUCE_ONLY_SHIFT

    # Trigger type (bits 13..12) - default to 0 if None
    trigger_value = 0 if trigger_type is None else int(trigger_type)
    appendix |= (
        trigger_value & AppendixBitFields.TRIGGER_TYPE_MASK
    ) << AppendixBitFields.TRIGGER_TYPE_SHIFT

    # Handle upper bits (127..64) based on order type
    if isolated and isolated_margin is not None:
        # Isolated margin (bits 127..64)
        appendix |= (
            isolated_margin & AppendixBitFields.VALUE_MASK
        ) << AppendixBitFields.VALUE_SHIFT
    elif trigger_type is not None and trigger_type in [
        OrderAppendixTriggerType.TWAP,
        OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
    ]:
        # TWAP value (bits 127..64) - 64 bits
        # These are guaranteed to be non-None due to validation above
        assert twap_times is not None
        assert twap_slippage_frac is not None
        twap_value = pack_twap_appendix_value(twap_times, twap_slippage_frac)
        appendix |= (
            twap_value & AppendixBitFields.VALUE_MASK
        ) << AppendixBitFields.VALUE_SHIFT

    return appendix


def gen_order_verifying_contract(product_id: int) -> str:
    """
    Generates the order verifying contract address based on the product ID.

    Args:
        product_id (int): The product ID for which to generate the verifying contract address.

    Returns:
        str: The generated order verifying contract address in hexadecimal format.
    """
    be_bytes = product_id.to_bytes(20, byteorder="big", signed=False)
    return "0x" + be_bytes.hex()


def order_reduce_only(appendix: int) -> bool:
    """
    Checks if the order is reduce-only based on the appendix value.

    Args:
        appendix (int): The order appendix value.

    Returns:
        bool: True if the order is reduce-only, False otherwise.
    """
    return (
        appendix >> AppendixBitFields.REDUCE_ONLY_SHIFT
        & AppendixBitFields.REDUCE_ONLY_MASK
    ) == 1


def order_is_trigger_order(appendix: int) -> bool:
    """
    Checks if the order is a trigger order based on the appendix value.

    Args:
        appendix (int): The order appendix value.

    Returns:
        bool: True if the order is a trigger order, False otherwise.
    """
    return (
        appendix >> AppendixBitFields.TRIGGER_TYPE_SHIFT
        & AppendixBitFields.TRIGGER_TYPE_MASK
    ) > 0


def order_is_isolated(appendix: int) -> bool:
    """
    Checks if the order is for an isolated position based on the appendix value.

    Args:
        appendix (int): The order appendix value.

    Returns:
        bool: True if the order is for an isolated position, False otherwise.
    """
    return (
        appendix >> AppendixBitFields.ISOLATED_SHIFT & AppendixBitFields.ISOLATED_MASK
    ) == 1


def order_isolated_margin(appendix: int) -> Optional[int]:
    """
    Extracts the isolated margin amount from the appendix value.

    Args:
        appendix (int): The order appendix value.

    Returns:
        Optional[int]: The isolated margin amount if the order is isolated, None otherwise.
    """
    if order_is_isolated(appendix):
        return (
            appendix >> AppendixBitFields.VALUE_SHIFT
        ) & AppendixBitFields.VALUE_MASK
    return None


def order_version(appendix: int) -> int:
    """
    Extracts the version from the appendix value.

    Args:
        appendix (int): The order appendix value.

    Returns:
        int: The version number (bits 7..0).
    """
    return (
        appendix >> AppendixBitFields.VERSION_SHIFT
    ) & AppendixBitFields.VERSION_MASK


def order_trigger_type(appendix: int) -> Optional[OrderAppendixTriggerType]:
    """
    Extracts the trigger type from the appendix value.

    Args:
        appendix (int): The order appendix value.

    Returns:
        Optional[OrderAppendixTriggerType]: The trigger type, or None if no trigger is set.
    """
    trigger_bits = (
        appendix >> AppendixBitFields.TRIGGER_TYPE_SHIFT
    ) & AppendixBitFields.TRIGGER_TYPE_MASK
    if trigger_bits == 0:
        return None
    return OrderAppendixTriggerType(trigger_bits)


def order_twap_data(appendix: int) -> Optional[tuple[int, float]]:
    """
    Extracts TWAP data from the appendix value if it's a TWAP order.

    Args:
        appendix (int): The order appendix value.

    Returns:
        Optional[tuple[int, float]]: Tuple of (times, slippage_frac) if TWAP, None otherwise.
    """
    trigger_type = order_trigger_type(appendix)
    if trigger_type is not None and trigger_type in [
        OrderAppendixTriggerType.TWAP,
        OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS,
    ]:
        twap_value = (
            appendix >> AppendixBitFields.VALUE_SHIFT
        ) & AppendixBitFields.VALUE_MASK
        return unpack_twap_appendix_value(twap_value)
    return None


def order_execution_type(appendix: int) -> OrderType:
    """
    Extracts the order execution type from the appendix value.

    Args:
        appendix (int): The order appendix value.

    Returns:
        OrderType: The order execution type.
    """
    order_type_bits = (
        appendix >> AppendixBitFields.ORDER_TYPE_SHIFT
    ) & AppendixBitFields.ORDER_TYPE_MASK
    return OrderType(order_type_bits)
