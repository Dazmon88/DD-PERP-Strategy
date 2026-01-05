from pydantic import BaseModel
from nado_protocol.contracts.types import NadoTxType


class EIP712Domain(BaseModel):
    """
    Model that represents the EIP-712 Domain data structure.

    Attributes:
        name (str): The user-readable name of the signing domain, i.e., the name of the DApp or the protocol.
        version (str): The current major version of the signing domain. Signatures from different versions are not compatible.
        chainId (int): The chain ID of the originating network.
        verifyingContract (str): The address of the contract that will verify the signature.
    """

    name: str
    version: str
    chainId: int
    verifyingContract: str


class EIP712Types(BaseModel):
    """
    Util to encapsulate the EIP-712 type data structure.

    Attributes:
        EIP712Domain (list[dict]): A list of dictionaries representing EIP-712 Domain data.
    """

    EIP712Domain: list[dict]

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"


class EIP712TypedData(BaseModel):
    """
    Util to represent the EIP-712 Typed Data structure.

    Attributes:
        types (EIP712Types): EIP-712 type data.
        primaryType (str): The primary type for EIP-712 message signing.
        domain (EIP712Domain): The domain data of the EIP-712 typed message.
        message (dict): The actual data to sign.
    """

    types: EIP712Types
    primaryType: str
    domain: EIP712Domain
    message: dict


def get_nado_eip712_type(tx: NadoTxType) -> dict:
    """
    Util that provides the EIP712 type information for Nado execute types.

    Args:
        tx (NadoTxType): The Nado transaction type for which to retrieve EIP712 type information.

    Returns:
        dict: A dictionary containing the EIP712 type information for the given execute type.
    """
    return {
        NadoTxType.PLACE_ORDER: {
            "Order": [
                {"name": "sender", "type": "bytes32"},
                {"name": "priceX18", "type": "int128"},
                {"name": "amount", "type": "int128"},
                {"name": "expiration", "type": "uint64"},
                {"name": "nonce", "type": "uint64"},
                {"name": "appendix", "type": "uint128"},
            ]
        },
        NadoTxType.CANCEL_ORDERS: {
            "Cancellation": [
                {"name": "sender", "type": "bytes32"},
                {"name": "productIds", "type": "uint32[]"},
                {"name": "digests", "type": "bytes32[]"},
                {"name": "nonce", "type": "uint64"},
            ]
        },
        NadoTxType.CANCEL_PRODUCT_ORDERS: {
            "CancellationProducts": [
                {"name": "sender", "type": "bytes32"},
                {"name": "productIds", "type": "uint32[]"},
                {"name": "nonce", "type": "uint64"},
            ],
        },
        NadoTxType.WITHDRAW_COLLATERAL: {
            "WithdrawCollateral": [
                {"name": "sender", "type": "bytes32"},
                {"name": "productId", "type": "uint32"},
                {"name": "amount", "type": "uint128"},
                {"name": "nonce", "type": "uint64"},
            ]
        },
        NadoTxType.LIQUIDATE_SUBACCOUNT: {
            "LiquidateSubaccount": [
                {"name": "sender", "type": "bytes32"},
                {"name": "liquidatee", "type": "bytes32"},
                {"name": "productId", "type": "uint32"},
                {"name": "isEncodedSpread", "type": "bool"},
                {"name": "amount", "type": "int128"},
                {"name": "nonce", "type": "uint64"},
            ],
        },
        NadoTxType.MINT_NLP: {
            "MintNlp": [
                {"name": "sender", "type": "bytes32"},
                {"name": "quoteAmount", "type": "uint128"},
                {"name": "nonce", "type": "uint64"},
            ]
        },
        NadoTxType.BURN_NLP: {
            "BurnNlp": [
                {"name": "sender", "type": "bytes32"},
                {"name": "nlpAmount", "type": "uint128"},
                {"name": "nonce", "type": "uint64"},
            ]
        },
        NadoTxType.LINK_SIGNER: {
            "LinkSigner": [
                {"name": "sender", "type": "bytes32"},
                {"name": "signer", "type": "bytes32"},
                {"name": "nonce", "type": "uint64"},
            ]
        },
        NadoTxType.TRANSFER_QUOTE: {
            "TransferQuote": [
                {"name": "sender", "type": "bytes32"},
                {"name": "recipient", "type": "bytes32"},
                {"name": "amount", "type": "uint128"},
                {"name": "nonce", "type": "uint64"},
            ]
        },
        NadoTxType.AUTHENTICATE_STREAM: {
            "StreamAuthentication": [
                {"name": "sender", "type": "bytes32"},
                {"name": "expiration", "type": "uint64"},
            ]
        },
        NadoTxType.LIST_TRIGGER_ORDERS: {
            "ListTriggerOrders": [
                {"name": "sender", "type": "bytes32"},
                {"name": "recvTime", "type": "uint64"},
            ]
        },
    }[tx]
