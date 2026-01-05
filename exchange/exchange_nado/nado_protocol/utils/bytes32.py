import binascii
from typing import Optional, Union
from nado_protocol.utils.subaccount import Subaccount, SubaccountParams


def hex_to_bytes32(input: Union[str, bytes]) -> bytes:
    """Converts a hexadecimal string or bytes to a bytes object of length 32.

    Args:
        input (str | bytes): The hexadecimal string or bytes to be converted.

    Returns:
        bytes: The converted bytes object of length 32.
    """
    return hex_to_bytes(input, 32)


def hex_to_bytes12(input: Union[str, bytes]) -> bytes:
    """Converts a hexadecimal string or bytes to a bytes object of length 12.

    Args:
        input (str | bytes): The hexadecimal string or bytes to be converted.

    Returns:
        bytes: The converted bytes object of length 12.
    """
    return hex_to_bytes(input, 12)


def hex_to_bytes(input: Union[str, bytes], size: int) -> bytes:
    """Converts a hexadecimal string or bytes to a bytes object of specified size.

    Args:
        input (str | bytes): The hexadecimal string or bytes to be converted.

        size (int): The specified size for the output bytes object.

    Returns:
        bytes: The converted bytes object of the specified size.
    """
    if isinstance(input, bytes):
        return input
    if input.encode() == zero_subaccount():
        return zero_subaccount()
    if input.startswith("0x"):
        input = input[2:]
    data_bytes = bytes.fromhex(input)
    padded_data = data_bytes + b"\x00" * (size - len(data_bytes))
    return padded_data


def str_to_hex(input: str) -> str:
    """Converts a string to its hexadecimal representation.

    Args:
        input (str): The string to be converted.

    Returns:
        str: The hexadecimal representation of the input string.
    """
    return binascii.hexlify(input.encode()).decode()


def subaccount_to_bytes32(
    subaccount: Subaccount, name: Optional[Union[str, bytes]] = None
) -> bytes:
    """Converts a subaccount representation to a bytes object of length 32.

    Args:
        subaccount (Subaccount): The subaccount, which can be a string, bytes, or SubaccountParams instance.

        name (str|bytes, optional): The subaccount name, when provided `subaccount` is expected to be the owner address.

    Returns:
        (bytes|SubaccountParams): The bytes object of length 32 representing the subaccount.

    Raises:
        ValueError: If the `subaccount` is a `SubaccountParams` instance and is missing either `subaccount_owner` or `subaccount_name`

    Note:
        If `name` is provided, `subaccount` must be the owner address, otherwise `subaccount`
        can be the bytes32 or hex representation of the subaccount or a SubaccountParams object.
    """
    if isinstance(subaccount, str):
        if name is None:
            return hex_to_bytes32(subaccount)
        else:
            name = name.hex() if isinstance(name, bytes) else name
            return hex_to_bytes32(subaccount + str_to_hex(name))
    elif isinstance(subaccount, SubaccountParams):
        subaccount_owner = subaccount.dict().get("subaccount_owner")
        subaccount_name = subaccount.dict().get("subaccount_name")
        if subaccount_owner is None or subaccount_name is None:
            raise ValueError("Missing `subaccount_owner` or `subaccount_name`")
        else:
            return hex_to_bytes32(subaccount_owner + str_to_hex(subaccount_name))
    else:
        return subaccount


def subaccount_to_hex(
    subaccount: Subaccount, name: Optional[Union[str, bytes]] = None
) -> str:
    """Converts a subaccount representation to its hexadecimal representation.

    Args:
        subaccount (Subaccount): The subaccount, which can be a string, bytes, or SubaccountParams instance.

        name (str|bytes, optional): Additional string, if any, to be appended to the subaccount string before conversion. Defaults to None.

    Returns:
        (str|SubaccountParams): The hexadecimal representation of the subaccount.
    """
    return bytes32_to_hex(subaccount_to_bytes32(subaccount, name))


def subaccount_name_to_bytes12(subaccount_name: str) -> bytes:
    """Converts a subaccount name to a bytes object of length 12.

    Args:
        subaccount_name (str): The subaccount name to be converted.

    Returns:
        bytes: A bytes object of length 12 representing the subaccount name.
    """
    return hex_to_bytes12(str_to_hex(subaccount_name))


def bytes32_to_hex(bytes32: bytes) -> str:
    """Converts a bytes object of length 32 to its hexadecimal representation.

    Args:
        bytes32 (bytes): The bytes object of length 32 to be converted.

    Returns:
        str: The hexadecimal representation of the input bytes object. If the input is not a bytes object, the function returns the input itself.
    """
    if isinstance(bytes32, bytes):
        return f"0x{bytes32.hex()}"
    else:
        return bytes32


def zero_subaccount() -> bytes:
    """Generates a bytes object of length 32 filled with zero bytes.

    Returns:
        bytes: A bytes object of length 32 filled with zero bytes.
    """
    return b"\x00" * 32


def zero_address() -> bytes:
    """Generates a bytes object of length 20 filled with zero bytes.

    Returns:
        bytes: A bytes object of length 20 filled with zero bytes.
    """
    return b"\x00" * 20
