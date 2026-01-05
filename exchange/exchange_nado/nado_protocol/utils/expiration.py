from enum import IntEnum
import time


class OrderType(IntEnum):
    DEFAULT = 0
    IOC = 1
    FOK = 2
    POST_ONLY = 3


def get_expiration_timestamp(seconds_from_now: int) -> int:
    """
    Returns a timestamp that is seconds_from_now in the future.

    Order types and reduce-only flags should now be set using build_appendix().

    Args:
        seconds_from_now (int): Number of seconds from now for expiration.

    Returns:
        int: The expiration timestamp.
    """
    return int(time.time()) + seconds_from_now
