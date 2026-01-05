from abc import abstractmethod
from copy import deepcopy
from typing import Optional, Type, Union
from eth_account.signers.local import LocalAccount
from pydantic import validator
from nado_protocol.contracts.eip712.sign import (
    build_eip712_typed_data,
    get_eip712_typed_data_digest,
    sign_eip712_typed_data,
)
from nado_protocol.contracts.types import NadoExecuteType
from nado_protocol.utils.backend import NadoClientOpts
from nado_protocol.utils.bytes32 import subaccount_to_bytes32, subaccount_to_hex
from nado_protocol.utils.model import NadoBaseModel
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.order import gen_order_verifying_contract
from nado_protocol.utils.subaccount import Subaccount, SubaccountParams


class BaseParams(NadoBaseModel):
    """
    Base class for defining request parameters to be sent to the Nado API.

    Attributes:
        sender (Subaccount): The sender's subaccount identifier.
        nonce (Optional[int]): An optional nonce for the request.

    Note:
        - The sender attribute is validated and serialized to bytes32 format before sending the request.
    """

    sender: Subaccount
    nonce: Optional[int]

    class Config:
        validate_assignment = True

    @validator("sender")
    def serialize_sender(cls, v: Subaccount) -> Union[bytes, Subaccount]:
        """
        Validates and serializes the sender to bytes32 format.

        Args:
            v (Subaccount): The sender's subaccount identifier.

        Returns:
            (bytes|Subaccount): The serialized sender in bytes32 format or the original Subaccount if it cannot be converted to bytes32.
        """
        try:
            return subaccount_to_bytes32(v)
        except ValueError:
            return v


class SignatureParams(NadoBaseModel):
    """
    Class for defining signature parameters in a request sent to the Nado API.

    Attributes:
        signature (Optional[str]): An optional string representing the signature for the request.
    """

    signature: Optional[str]


class BaseParamsSigned(BaseParams, SignatureParams):
    """
    Class that combines the base parameters and signature parameters for a signed request
    to the Nado API. Inherits attributes from BaseParams and SignatureParams.
    """

    pass


class MarketOrderParams(BaseParams):
    """
    Class for defining the parameters of a market order.

    Attributes:
        amount (int): The amount of the asset to be bought or sold in the order. Positive for a `long` position and negative for a `short`.

        nonce (Optional[int]): A unique number used to prevent replay attacks.
    """

    amount: int


class OrderParams(MarketOrderParams):
    """
    Class for defining the parameters of an order.

    Attributes:
        priceX18 (int): The price of the order with a precision of 18 decimal places.

        expiration (int): The unix timestamp at which the order will expire.

        amount (int): The amount of the asset to be bought or sold in the order. Positive for a `long` position and negative for a `short`.

        nonce (Optional[int]): A unique number used to prevent replay attacks.

        appendix (int): Additional data or instructions related to the order. Use to encode order type and other related data.
    """

    priceX18: int
    expiration: int
    appendix: int


class NadoBaseExecute:
    def __init__(self, opts: NadoClientOpts):
        self._opts = opts

    @abstractmethod
    def tx_nonce(self, _: str) -> int:
        pass

    @property
    def endpoint_addr(self) -> str:
        if self._opts.endpoint_addr is None:
            raise AttributeError("Endpoint address not set.")
        return self._opts.endpoint_addr

    @endpoint_addr.setter
    def endpoint_addr(self, addr: str) -> None:
        self._opts.endpoint_addr = addr

    @property
    def chain_id(self) -> int:
        if self._opts.chain_id is None:
            raise AttributeError("Chain ID is not set.")
        return self._opts.chain_id

    @chain_id.setter
    def chain_id(self, chain_id: Union[int, str]) -> None:
        self._opts.chain_id = int(chain_id)

    @property
    def signer(self) -> LocalAccount:
        if self._opts.signer is None:
            raise AttributeError("Signer is not set.")
        assert isinstance(self._opts.signer, LocalAccount)
        return self._opts.signer

    @signer.setter
    def signer(self, signer: LocalAccount) -> None:
        self._opts.signer = signer

    @property
    def linked_signer(self) -> LocalAccount:
        if self._opts.linked_signer is not None:
            assert isinstance(self._opts.linked_signer, LocalAccount)
            return self._opts.linked_signer
        if self._opts.signer is not None:
            assert isinstance(self._opts.signer, LocalAccount)
            return self.signer
        raise AttributeError("Signer is not set.")

    @linked_signer.setter
    def linked_signer(self, linked_signer: LocalAccount) -> None:
        if self._opts.signer is None:
            raise AttributeError(
                "Must set a `signer` first before setting `linked_signer`."
            )
        self._opts.linked_signer = linked_signer

    def order_verifying_contract(self, product_id: int) -> str:
        """
        Returns the `place_order` verifying contract address for a given product.

        Note:
            Previously, `place_order` verifying contracts were accessed via `book_addrs[product_id]`.
            Virtual books have now been removed, and the verifying contract is derived
            directly from the product id.

            The address is computed as `address(product_id)`, i.e. the 20-byte
            big-endian representation of the product id, zero-padded on the left.

            Example:
                product_id = 18  →  0x0000000000000000000000000000000000000012
        """
        return gen_order_verifying_contract(product_id)

    def order_nonce(self, recv_time_ms: Optional[int] = None) -> int:
        """
        Generate the order nonce. Used for oder placements and cancellations.

        Args:
            recv_time_ms (int, optional): Received time in milliseconds.

        Returns:
            int: The generated order nonce.
        """
        return gen_order_nonce(recv_time_ms)

    def _inject_owner_if_needed(self, params: Type[BaseParams]) -> Type[BaseParams]:
        """
        Inject the owner if needed.

        Args:
            params (Type[BaseParams]): The parameters.

        Returns:
            Type[BaseParams]: The parameters with the owner injected if needed.
        """
        if isinstance(params.sender, SubaccountParams):
            params.sender.subaccount_owner = (
                params.sender.subaccount_owner or self.signer.address
            )
            params.sender = params.serialize_sender(params.sender)
        return params

    def _inject_nonce_if_needed(
        self,
        params: Type[BaseParams],
        use_order_nonce: bool,
    ) -> Type[BaseParams]:
        """
        Inject the nonce if needed.

        Args:
            params (Type[BaseParams]): The parameters.

        Returns:
            Type[BaseParams]: The parameters with the nonce injected if needed.
        """
        if params.nonce is not None:
            return params
        params.nonce = (
            self.order_nonce()
            if use_order_nonce
            else self.tx_nonce(subaccount_to_hex(params.sender))
        )
        return params

    def prepare_execute_params(self, params, use_order_nonce: bool):
        """
        Prepares the parameters for execution by ensuring that both owner and nonce are correctly set.

        Args:
            params (Type[BaseParams]): The original parameters.

        Returns:
            Type[BaseParams]: A copy of the original parameters with owner and nonce injected if needed.
        """
        params = deepcopy(params)
        params = self._inject_owner_if_needed(params)
        params = self._inject_nonce_if_needed(params, use_order_nonce)
        return params

    def _sign(
        self, execute: NadoExecuteType, msg: dict, product_id: Optional[int] = None
    ) -> str:
        """
        Internal method to create an EIP-712 signature for the given operation type and message.

        Args:
            execute (NadoExecuteType): The Nado execute type to sign.

            msg (dict): The message to be signed.

            product_id (int, optional): Required for 'PLACE_ORDER' operation, specifying the product ID.

        Returns:
            str: The generated EIP-712 signature.

        Raises:
            ValueError: If the operation type is 'PLACE_ORDER' and no product_id is provided.

        Notes:
            The contract used for verification varies based on the operation type:
                - For 'PLACE_ORDER', it's derived from the book address associated with the product_id.
                - For other operations, it's the endpoint address.
        """
        is_place_order = execute == NadoExecuteType.PLACE_ORDER
        if is_place_order and product_id is None:
            raise ValueError("Missing `product_id` to sign place_order execute")
        verifying_contract = (
            self.order_verifying_contract(product_id)
            if is_place_order and product_id
            else self.endpoint_addr
        )
        return self.sign(
            execute, msg, verifying_contract, self.chain_id, self.linked_signer
        )

    def build_digest(
        self,
        execute: NadoExecuteType,
        msg: dict,
        verifying_contract: str,
        chain_id: int,
    ) -> str:
        """
        Build an EIP-712 compliant digest from given parameters.

        Must provide the same input to build an EIP-712 typed data as the one provided for signing via `.sign(...)`

        Args:
            execute (NadoExecuteType): The Nado execute type to build digest for.

            msg (dict): The EIP712 message.

            verifying_contract (str): The contract used for verification.

            chain_id (int): The network chain ID.

        Returns:
            str: The digest computed from the provided parameters.
        """
        return get_eip712_typed_data_digest(
            build_eip712_typed_data(execute, msg, verifying_contract, chain_id)
        )

    def sign(
        self,
        execute: NadoExecuteType,
        msg: dict,
        verifying_contract: str,
        chain_id: int,
        signer: LocalAccount,
    ) -> str:
        """
        Signs the EIP-712 typed data using the provided signer account.

        Args:
            execute (NadoExecuteType): The type of operation.

            msg (dict): The message to be signed.

            verifying_contract (str): The contract used for verification.

            chain_id (int): The network chain ID.

            signer (LocalAccount): The account used to sign the data.

        Returns:
            str: The generated EIP-712 signature.
        """
        typed_data = build_eip712_typed_data(execute, msg, verifying_contract, chain_id)
        return sign_eip712_typed_data(
            typed_data=typed_data,
            signer=signer,
        )

    def get_order_digest(self, order: OrderParams, product_id: int) -> str:
        """
        Generates the order digest for a given order and product ID.

        Args:
            order (OrderParams): The order parameters.

            product_id (int): The ID of the product.

        Returns:
            str: The generated order digest.
        """
        return self.build_digest(
            NadoExecuteType.PLACE_ORDER,
            order.dict(),
            self.order_verifying_contract(product_id),
            self.chain_id,
        )
