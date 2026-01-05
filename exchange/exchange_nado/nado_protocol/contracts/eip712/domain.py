from nado_protocol.contracts.eip712.types import EIP712Domain


def get_nado_eip712_domain(verifying_contract: str, chain_id: int) -> EIP712Domain:
    """
    Util to create an EIP712Domain instance specific to Nado.

    Args:
        verifying_contract (str): The address of the contract that will verify the EIP-712 signature.

        chain_id (int): The chain ID of the originating network.

    Returns:
        EIP712Domain: An instance of EIP712Domain with name set to "Nado", version "0.0.1", and the provided verifying contract and chain ID.
    """
    return EIP712Domain(
        name="Nado",
        version="0.0.1",
        verifyingContract=verifying_contract,
        chainId=chain_id,
    )


def get_eip712_domain_type() -> list[dict[str, str]]:
    """
    Util to return the structure of an EIP712Domain as per EIP-712.

    Returns:
        dict: A list of dictionaries each containing the name and type of a field in EIP712Domain.
    """
    return [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ]
