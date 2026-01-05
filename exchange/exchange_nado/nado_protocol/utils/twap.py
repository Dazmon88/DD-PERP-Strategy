from typing import List, Optional
from nado_protocol.utils.order import (
    build_appendix,
    OrderAppendixTriggerType,
)
from nado_protocol.utils.expiration import OrderType
from nado_protocol.utils.execute import OrderParams


def create_twap_order(
    product_id: int,
    sender: str,
    price_x18: str,
    total_amount_x18: str,
    expiration: int,
    nonce: int,
    times: int,
    slippage_frac: float,
    interval_seconds: int,
    custom_amounts_x18: Optional[List[str]] = None,
    reduce_only: bool = False,
    spot_leverage: Optional[bool] = None,
    id: Optional[int] = None,
):
    """
    Create a TWAP (Time-Weighted Average Price) order.

    Args:
        product_id (int): The product ID for the order.
        sender (str): The sender address (32 bytes hex).
        price_x18 (str): The limit price multiplied by 1e18.
        total_amount_x18 (str): The total amount to trade multiplied by 1e18 (signed, negative for sell).
        expiration (int): Order expiration timestamp.
        nonce (int): Order nonce.
        times (int): Number of TWAP executions (1-500).
        slippage_frac (float): Slippage tolerance as a fraction (e.g., 0.01 for 1%).
        interval_seconds (int): Time interval between executions in seconds.
        custom_amounts_x18 (Optional[List[str]]): Custom amounts for each execution multiplied by 1e18.
                                                If provided, uses TWAP_CUSTOM_AMOUNTS trigger type.
        reduce_only (bool): Whether this is a reduce-only order.
        spot_leverage (Optional[bool]): Whether to use spot leverage.
        id (Optional[int]): Optional order ID.

    Returns:
        PlaceTriggerOrderParams: Parameters for placing the TWAP order.

    Raises:
        ValueError: If parameters are invalid.
    """
    # Import here to avoid circular imports
    from nado_protocol.trigger_client.types.models import TimeTrigger
    from nado_protocol.trigger_client.types.execute import PlaceTriggerOrderParams

    if times < 1 or times > 500:
        raise ValueError(f"TWAP times must be between 1 and 500, got {times}")

    if slippage_frac < 0 or slippage_frac > 1:
        raise ValueError(
            f"Slippage fraction must be between 0 and 1, got {slippage_frac}"
        )

    if interval_seconds <= 0:
        raise ValueError(f"Interval must be positive, got {interval_seconds}")

    # Determine trigger type
    trigger_type = (
        OrderAppendixTriggerType.TWAP_CUSTOM_AMOUNTS
        if custom_amounts_x18 is not None
        else OrderAppendixTriggerType.TWAP
    )

    # Build appendix - TWAP orders must use IOC execution type
    appendix = build_appendix(
        order_type=OrderType.IOC,
        reduce_only=reduce_only,
        trigger_type=trigger_type,
        twap_times=times,
        twap_slippage_frac=slippage_frac,
    )

    # Create the base order
    order_params = OrderParams(
        sender=sender,
        priceX18=int(price_x18),
        amount=int(total_amount_x18),
        expiration=expiration,
        nonce=nonce,
        appendix=appendix,
    )

    # Create trigger criteria
    from nado_protocol.trigger_client.types.models import TimeTriggerData

    trigger = TimeTrigger(
        time_trigger=TimeTriggerData(
            interval=interval_seconds,
            amounts=custom_amounts_x18,
        )
    )

    return PlaceTriggerOrderParams(
        product_id=product_id,
        order=order_params,
        trigger=trigger,
        signature=None,  # Will be filled by client
        digest=None,  # Will be filled by client
        spot_leverage=spot_leverage,
        id=id,
    )


def validate_twap_order(
    total_amount_x18: str,
    times: int,
    custom_amounts_x18: Optional[List[str]] = None,
) -> None:
    """
    Validate TWAP order parameters.

    Args:
        total_amount_x18 (str): The total amount to trade multiplied by 1e18.
        times (int): Number of TWAP executions.
        custom_amounts_x18 (Optional[List[str]]): Custom amounts for each execution multiplied by 1e18.

    Raises:
        ValueError: If validation fails.
    """
    total_amount_int = int(total_amount_x18)

    if custom_amounts_x18 is None:
        # For equal distribution, total amount must be divisible by times
        if total_amount_int % times != 0:
            raise ValueError(
                f"Total amount {total_amount_x18} must be divisible by times {times} "
                f"for equal distribution TWAP orders"
            )
    else:
        # For custom amounts, verify the list length and sum
        if len(custom_amounts_x18) != times:
            raise ValueError(
                f"Custom amounts list length ({len(custom_amounts_x18)}) must equal "
                f"times ({times})"
            )

        custom_sum = sum(int(amount) for amount in custom_amounts_x18)
        if custom_sum != total_amount_int:
            raise ValueError(
                f"Sum of custom amounts ({custom_sum}) must equal "
                f"total amount ({total_amount_int})"
            )


def estimate_twap_completion_time(times: int, interval_seconds: int) -> int:
    """
    Estimate the total time for TWAP order completion.

    Args:
        times (int): Number of TWAP executions.
        interval_seconds (int): Time interval between executions.

    Returns:
        int: Estimated completion time in seconds.
    """
    return (times - 1) * interval_seconds


def calculate_equal_amounts(total_amount_x18: str, times: int) -> List[str]:
    """
    Calculate equal amounts for TWAP executions.

    Args:
        total_amount_x18 (str): The total amount to distribute multiplied by 1e18.
        times (int): Number of executions.

    Returns:
        List[str]: List of equal amounts for each execution multiplied by 1e18.

    Raises:
        ValueError: If total amount is not divisible by times.
    """
    total_amount_int = int(total_amount_x18)

    if total_amount_int % times != 0:
        raise ValueError(
            f"Total amount {total_amount_x18} is not divisible by times {times}"
        )

    amount_per_execution = total_amount_int // times
    return [str(amount_per_execution)] * times
