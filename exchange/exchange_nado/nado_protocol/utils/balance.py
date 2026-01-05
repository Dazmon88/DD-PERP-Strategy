"""
Balance Value Calculation Utilities
"""

from decimal import Decimal
from typing import Union
from nado_protocol.engine_client.types.models import (
    SpotProduct,
    PerpProduct,
    SpotProductBalance,
    PerpProductBalance,
)
from nado_protocol.utils.math import from_x18


def calculate_spot_balance_value(
    amount: Union[Decimal, float, str], oracle_price: Union[Decimal, float, str]
) -> Decimal:
    """
    Calculate the quote value of a spot balance.

    Formula: amount * oracle_price

    This is used for:
    - Calculating health contributions
    - Determining deposits vs borrows
    - Portfolio value calculations

    Args:
        amount: Token amount (can be negative for borrows)
        oracle_price: Oracle price in quote currency

    Returns:
        Value in quote currency (positive for deposits, negative for borrows)

    Example:
        >>> calculate_spot_balance_value(100, 2000)  # 100 ETH at $2000
        Decimal('200000')
        >>> calculate_spot_balance_value(-50, 2000)  # 50 ETH borrowed
        Decimal('-100000')
    """
    amount_dec = Decimal(str(amount))
    price_dec = Decimal(str(oracle_price))
    return amount_dec * price_dec


def calculate_perp_balance_notional_value(
    amount: Union[Decimal, float, str], oracle_price: Union[Decimal, float, str]
) -> Decimal:
    """
    Calculate the notional value of a perp position.

    Formula: abs(amount * oracle_price)

    This represents the total size of the position in quote currency terms,
    regardless of direction (long or short).

    Args:
        amount: Position size (positive for long, negative for short)
        oracle_price: Oracle price in quote currency

    Returns:
        Absolute notional value in quote currency

    Example:
        >>> calculate_perp_balance_notional_value(10, 50000)  # 10 BTC long
        Decimal('500000')
        >>> calculate_perp_balance_notional_value(-10, 50000)  # 10 BTC short
        Decimal('500000')
    """
    amount_dec = Decimal(str(amount))
    price_dec = Decimal(str(oracle_price))
    return abs(amount_dec * price_dec)


def calculate_perp_balance_value(
    amount: Union[Decimal, float, str],
    oracle_price: Union[Decimal, float, str],
    v_quote_balance: Union[Decimal, float, str],
) -> Decimal:
    """
    Calculate the true quote value of a perp balance (unrealized PnL).

    Formula: (amount * oracle_price) + v_quote_balance

    The v_quote_balance represents:
    - Unrealized PnL from price changes
    - Accumulated funding payments
    - Entry cost adjustments

    This value is what would be added to your balance if the position were closed.

    Args:
        amount: Position size
        oracle_price: Oracle price in quote currency
        v_quote_balance: Virtual quote balance (unsettled PnL)

    Returns:
        Total value in quote currency (can be positive or negative)

    Example:
        >>> # Long 10 BTC at $50k, now at $51k, with funding
        >>> calculate_perp_balance_value(10, 51000, -500000)
        Decimal('10000')  # $10k profit
    """
    amount_dec = Decimal(str(amount))
    price_dec = Decimal(str(oracle_price))
    v_quote_dec = Decimal(str(v_quote_balance))
    return (amount_dec * price_dec) + v_quote_dec


def parse_spot_balance_value(
    balance: SpotProductBalance, product: SpotProduct
) -> Decimal:
    """
    Parse spot balance value from raw SDK types.

    This is a convenience function that extracts values from the SDK types
    and calls calculate_spot_balance_value.

    Args:
        balance: Spot balance from subaccount info
        product: Spot product information

    Returns:
        Balance value in quote currency
    """
    amount = Decimal(from_x18(int(balance.balance.amount)))
    oracle_price = Decimal(from_x18(int(product.oracle_price_x18)))
    return calculate_spot_balance_value(amount, oracle_price)


def parse_perp_balance_notional_value(
    balance: PerpProductBalance, product: PerpProduct
) -> Decimal:
    """
    Parse perp notional value from raw SDK types.

    Args:
        balance: Perp balance from subaccount info
        product: Perp product information

    Returns:
        Notional value in quote currency
    """
    amount = Decimal(from_x18(int(balance.balance.amount)))
    oracle_price = Decimal(from_x18(int(product.oracle_price_x18)))
    return calculate_perp_balance_notional_value(amount, oracle_price)


def parse_perp_balance_value(
    balance: PerpProductBalance, product: PerpProduct
) -> Decimal:
    """
    Parse perp balance value (unrealized PnL) from raw SDK types.

    Args:
        balance: Perp balance from subaccount info
        product: Perp product information

    Returns:
        Balance value in quote currency
    """
    amount = Decimal(from_x18(int(balance.balance.amount)))
    oracle_price = Decimal(from_x18(int(product.oracle_price_x18)))
    v_quote = Decimal(from_x18(int(balance.balance.v_quote_balance)))
    return calculate_perp_balance_value(amount, oracle_price, v_quote)


def calculate_total_spot_deposits_and_borrows(
    balances: list[tuple[SpotProductBalance, SpotProduct]]
) -> tuple[Decimal, Decimal]:
    """
    Calculate total spot deposits and borrows across all balances.

    Args:
        balances: List of (balance, product) tuples

    Returns:
        Tuple of (total_deposits, total_borrows) in quote currency
        Both values are positive (borrows is absolute value)

    Example:
        >>> balances = [(usdt_balance, usdt_product), (eth_balance, eth_product)]
        >>> deposits, borrows = calculate_total_spot_deposits_and_borrows(balances)
        >>> deposits  # Total deposits
        Decimal('10000')
        >>> borrows   # Total borrows (absolute value)
        Decimal('5000')
    """
    total_deposits = Decimal(0)
    total_borrows = Decimal(0)

    for balance, product in balances:
        value = parse_spot_balance_value(balance, product)
        if value > 0:
            total_deposits += value
        else:
            total_borrows += abs(value)

    return total_deposits, total_borrows


def calculate_total_perp_notional(
    balances: list[tuple[PerpProductBalance, PerpProduct]]
) -> Decimal:
    """
    Calculate total notional value across all perp positions.

    Args:
        balances: List of (balance, product) tuples

    Returns:
        Total notional value in quote currency

    Example:
        >>> balances = [(btc_perp_balance, btc_perp_product)]
        >>> total = calculate_total_perp_notional(balances)
        >>> total
        Decimal('500000')  # Total position size
    """
    total = Decimal(0)
    for balance, product in balances:
        total += parse_perp_balance_notional_value(balance, product)
    return total


def calculate_total_perp_value(
    balances: list[tuple[PerpProductBalance, PerpProduct]]
) -> Decimal:
    """
    Calculate total unrealized PnL across all perp positions.

    Args:
        balances: List of (balance, product) tuples

    Returns:
        Total unrealized PnL in quote currency (can be positive or negative)

    Example:
        >>> balances = [(btc_perp_balance, btc_perp_product)]
        >>> total_pnl = calculate_total_perp_value(balances)
        >>> total_pnl
        Decimal('10000')  # $10k unrealized profit
    """
    total = Decimal(0)
    for balance, product in balances:
        total += parse_perp_balance_value(balance, product)
    return total
