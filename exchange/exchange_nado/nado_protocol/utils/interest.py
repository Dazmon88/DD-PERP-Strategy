from nado_protocol.engine_client.types.models import SpotProduct
from nado_protocol.utils.time import TimeInSeconds
from nado_protocol.utils.math import from_x18, mul_x18


def calc_deposits_and_borrows(product: SpotProduct) -> tuple[float, float]:
    total_deposited = from_x18(
        mul_x18(
            int(product.state.total_deposits_normalized),
            int(product.state.cumulative_deposits_multiplier_x18),
        )
    )
    total_borrowed = from_x18(
        mul_x18(
            int(product.state.total_borrows_normalized),
            int(product.state.cumulative_borrows_multiplier_x18),
        )
    )
    return (total_deposited, total_borrowed)


def calc_utilization_ratio(product: SpotProduct) -> float:
    total_deposited, total_borrowed = calc_deposits_and_borrows(product)

    if total_deposited == 0 or total_borrowed == 0:
        return 0

    return abs(total_borrowed) / total_deposited


def calc_borrow_rate_per_second(product: SpotProduct) -> float:
    utilization = calc_utilization_ratio(product)
    if utilization == 0:
        return 0
    interest_floor = from_x18(int(product.config.interest_floor_x18))
    interest_inflection_util = from_x18(
        int(product.config.interest_inflection_util_x18)
    )
    interest_small_cap = from_x18(int(product.config.interest_small_cap_x18))
    interest_large_cap = from_x18(int(product.config.interest_large_cap_x18))

    annual_rate = 0.0
    if utilization > interest_inflection_util:
        utilization_term = interest_large_cap * (
            (utilization - interest_inflection_util) / (1 - interest_inflection_util)
        )
        annual_rate = interest_floor + interest_small_cap + utilization_term
    else:
        utilization_term = (utilization / interest_inflection_util) * interest_small_cap
        annual_rate = interest_floor + utilization_term
    return annual_rate / TimeInSeconds.YEAR


def calc_borrow_rate_in_period(product: SpotProduct, period_in_seconds) -> float:
    borrow_rate_per_second = calc_borrow_rate_per_second(product)
    return (borrow_rate_per_second + 1) ** period_in_seconds - 1


def calc_deposit_rate_in_period(
    product: SpotProduct, period_in_seconds: int, interest_fee_fraction: float
) -> float:
    utilization = calc_utilization_ratio(product)
    if utilization == 0:
        return 0
    borrow_rate_in_period = calc_borrow_rate_in_period(product, period_in_seconds)
    return utilization * borrow_rate_in_period * (1 - interest_fee_fraction)
