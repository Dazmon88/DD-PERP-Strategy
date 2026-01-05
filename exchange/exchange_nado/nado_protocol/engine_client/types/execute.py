from typing import Optional, Type, Union, Sequence
from pydantic import validator
from nado_protocol.contracts.types import NadoExecuteType
from nado_protocol.engine_client.types.models import ResponseStatus
from nado_protocol.utils.execute import (
    BaseParamsSigned,
    MarketOrderParams,
    OrderParams,
    SignatureParams,
)
from nado_protocol.utils.model import NadoBaseModel
from nado_protocol.utils.bytes32 import (
    bytes32_to_hex,
    hex_to_bytes32,
    subaccount_to_bytes32,
)
from nado_protocol.utils.subaccount import Subaccount
from nado_protocol.engine_client.types.query import OrderData


Digest = Union[str, bytes]


class PlaceOrderParams(SignatureParams):
    """
    Class for defining the parameters needed to place an order.

    Attributes:
        id (Optional[int]): An optional custom order id that is echoed back in subscription events e.g: fill orders, etc.

        product_id (int): The id of the product for which the order is being placed.

        order (OrderParams): The parameters of the order.

        digest (Optional[str]): An optional hash of the order data.

        spot_leverage (Optional[bool]): An optional flag indicating whether leverage should be used for the order. By default, leverage is assumed.
    """

    id: Optional[int]
    product_id: int
    order: OrderParams
    digest: Optional[str]
    spot_leverage: Optional[bool]


class PlaceOrdersParams(NadoBaseModel):
    """
    Class for defining the parameters needed to place multiple orders in a single request.

    Attributes:
        orders (list[PlaceOrderParams]): Array of orders to place.

        stop_on_failure (Optional[bool]): If true, stops processing remaining orders when the first order fails.
        Already successfully placed orders are NOT cancelled. Defaults to false.
    """

    orders: Sequence[PlaceOrderParams]
    stop_on_failure: Optional[bool]


class PlaceMarketOrderParams(SignatureParams):
    """
    Class for defining the parameters needed to place a market order.

    Attributes:
        product_id (int): The id of the product for which the order is being placed.

        slippage (Optional[float]): Optional slippage allowed in market price. Defaults to 0.005 (0.5%)

        market_order (MarketOrderParams): The parameters of the market order.

        spot_leverage (Optional[bool]): An optional flag indicating whether leverage should be used for the order. By default, leverage is assumed.

        reduce_only (Optional[bool]): When True, the order can only reduce the size of an existing position. Works only with IOC & FOK.
    """

    product_id: int
    market_order: MarketOrderParams
    slippage: Optional[float]
    spot_leverage: Optional[bool]
    reduce_only: Optional[bool]


class CancelOrdersParams(BaseParamsSigned):
    """
    Parameters to cancel specific orders.

    Args:
        productIds (list[int]): List of product IDs for the orders to be canceled.

        digests (list[Digest]): List of digests of the orders to be canceled.

        nonce (Optional[int]): A unique number used to prevent replay attacks.

    Methods:
        serialize_digests: Validates and converts a list of hex digests to bytes32.
    """

    productIds: list[int]
    digests: list[Digest]
    nonce: Optional[int]

    @validator("digests")
    def serialize_digests(cls, v: list[Digest]) -> list[bytes]:
        return [hex_to_bytes32(digest) for digest in v]


class CancelProductOrdersParams(BaseParamsSigned):
    """
    Parameters to cancel all orders for specific products.

    Args:
        productIds (list[int]): List of product IDs for the orders to be canceled.

        digest (str, optional): Optional EIP-712 digest of the CancelProductOrder request.

        nonce (Optional[int]): A unique number used to prevent replay attacks.
    """

    productIds: list[int]
    digest: Optional[str]
    nonce: Optional[int]


class CancelAndPlaceParams(NadoBaseModel):
    """
    Parameters to perform an order cancellation + order placement in the same request.

    Args:
        cancel_orders (CancelOrdersParams): Order cancellation object.
        place_order (PlaceOrderParams): Order placement object.
    """

    cancel_orders: CancelOrdersParams
    place_order: PlaceOrderParams


class WithdrawCollateralParams(BaseParamsSigned):
    """
    Parameters required to withdraw collateral from a specific product.

    Attributes:
        productId (int): The ID of the product to withdraw collateral from.

        amount (int): The amount of collateral to be withdrawn.

        spot_leverage (Optional[bool]): Indicates whether leverage is to be used. Defaults to True.
        If set to False, the transaction fails if it causes a borrow on the subaccount.
    """

    productId: int
    amount: int
    spot_leverage: Optional[bool]


class LiquidateSubaccountParams(BaseParamsSigned):
    """
    Parameters required to liquidate a subaccount.

    Attributes:
        liquidatee (Subaccount): The subaccount that is to be liquidated.

        productId (int): ID of product to liquidate.

        isEncodedSpread (bool): When set to True, productId is expected to encode a perp and spot product Ids as follows: (perp_id << 16) | spot_id

        amount (int): The amount to be liquidated.

    Methods:
        serialize_liquidatee(cls, v: Subaccount) -> bytes: Validates and converts the liquidatee subaccount to bytes32 format.
    """

    liquidatee: Subaccount
    productId: int
    isEncodedSpread: bool
    amount: int

    @validator("liquidatee")
    def serialize_liquidatee(cls, v: Subaccount) -> bytes:
        return subaccount_to_bytes32(v)


class MintNlpParams(BaseParamsSigned):
    """
    Parameters required for minting Nado Liquidity Provider (NLP) tokens for a specific product in a subaccount.

    Attributes:
        quoteAmount (int): The amount of quote to be consumed by minting NLP multiplied by 1e18.

        spot_leverage (Optional[bool]): Indicates whether leverage is to be used. Defaults to True.
        If set to False, the transaction fails if it causes a borrow on the subaccount.
    """

    quoteAmount: int
    spot_leverage: Optional[bool]


class BurnNlpParams(BaseParamsSigned):
    """
    This class represents the parameters required to burn Nado Liquidity Provider (NLP)
    tokens for a specific subaccount.

    Attributes:
        productId (int): The ID of the product.

        nlpAmount (int): Amount of NLP tokens to burn multiplied by 1e18.
    """

    nlpAmount: int


class LinkSignerParams(BaseParamsSigned):
    """
    This class represents the parameters required to link a signer to a subaccount.

    Attributes:
        signer (Subaccount): The subaccount to be linked.

    Methods:
        serialize_signer(cls, v: Subaccount) -> bytes: Validates and converts the subaccount to bytes32 format.
    """

    signer: Subaccount

    @validator("signer")
    def serialize_signer(cls, v: Subaccount) -> bytes:
        return subaccount_to_bytes32(v)


ExecuteParams = Union[
    PlaceOrderParams,
    PlaceOrdersParams,
    CancelOrdersParams,
    CancelProductOrdersParams,
    WithdrawCollateralParams,
    LiquidateSubaccountParams,
    MintNlpParams,
    BurnNlpParams,
    LinkSignerParams,
    CancelAndPlaceParams,
]


class PlaceOrderRequest(NadoBaseModel):
    """
    Parameters for a request to place an order.

    Attributes:
        place_order (PlaceOrderParams): The parameters for the order to be placed.

    Methods:
        serialize: Validates and serializes the order parameters.
    """

    place_order: PlaceOrderParams

    @validator("place_order")
    def serialize(cls, v: PlaceOrderParams) -> PlaceOrderParams:
        if v.order.nonce is None:
            raise ValueError("Missing order `nonce`")
        if v.signature is None:
            raise ValueError("Missing `signature`")
        if isinstance(v.order.sender, bytes):
            v.order.serialize_dict(["sender"], bytes32_to_hex)
        v.order.serialize_dict(
            ["nonce", "priceX18", "amount", "expiration", "appendix"], str
        )
        return v


class PlaceOrdersRequest(NadoBaseModel):
    """
    Parameters for a request to place multiple orders.

    Attributes:
        place_orders (PlaceOrdersParams): The parameters for the orders to be placed.

    Methods:
        serialize: Validates and serializes the order parameters.
    """

    place_orders: PlaceOrdersParams

    @validator("place_orders")
    def serialize(cls, v: PlaceOrdersParams) -> PlaceOrdersParams:
        for order_params in v.orders:
            if order_params.order.nonce is None:
                raise ValueError("Missing order `nonce`")
            if order_params.signature is None:
                raise ValueError("Missing `signature`")
            if isinstance(order_params.order.sender, bytes):
                order_params.order.serialize_dict(["sender"], bytes32_to_hex)
            order_params.order.serialize_dict(
                ["nonce", "priceX18", "amount", "expiration", "appendix"], str
            )
        return v


class TxRequest(NadoBaseModel):
    """
    Parameters for a transaction request.

    Attributes:
        tx (dict): The transaction details.

        signature (str): The signature for the transaction.

        spot_leverage (Optional[bool]): Indicates whether leverage should be used. If set to false,
        it denotes no borrowing. Defaults to true.

        digest (Optional[str]): The digest of the transaction.

    Methods:
        serialize: Validates and serializes the transaction parameters.
    """

    tx: dict
    signature: str
    spot_leverage: Optional[bool]
    digest: Optional[str]

    @validator("tx")
    def serialize(cls, v: dict) -> dict:
        """
        Validates and serializes the transaction parameters.

        Args:
            v (dict): The transaction parameters to be validated and serialized.

        Raises:
            ValueError: If the 'nonce' attribute is missing in the transaction parameters.

        Returns:
            dict: The validated and serialized transaction parameters.
        """
        if v.get("nonce") is None:
            raise ValueError("Missing tx `nonce`")
        v["sender"] = bytes32_to_hex(v["sender"])
        v["nonce"] = str(v["nonce"])
        return v


def to_tx_request(cls: Type[NadoBaseModel], v: BaseParamsSigned) -> TxRequest:
    """
    Converts a BaseParamsSigned object to a TxRequest object.

    Args:
        cls (Type[NadoBaseModel]): The type of the model to convert.

        v (BaseParamsSigned): The signed parameters to be converted.

    Raises:
        ValueError: If the 'signature' attribute is missing in the BaseParamsSigned object.

    Returns:
        TxRequest: The converted transaction request.
    """
    if v.signature is None:
        raise ValueError("Missing `signature`")
    return TxRequest(
        tx=v.dict(exclude={"signature", "digest", "spot_leverage"}),
        signature=v.signature,
        spot_leverage=v.dict().get("spot_leverage"),
        digest=v.dict().get("digest"),
    )


class CancelOrdersRequest(NadoBaseModel):
    """
    Parameters for a cancel orders request.

    Attributes:
        cancel_orders (CancelOrdersParams): The parameters of the orders to be cancelled.

    Methods:
        serialize: Serializes 'digests' in 'cancel_orders' into their hexadecimal representation.

        to_tx_request: Validates and converts 'cancel_orders' into a transaction request.
    """

    cancel_orders: CancelOrdersParams

    @validator("cancel_orders")
    def serialize(cls, v: CancelOrdersParams) -> CancelOrdersParams:
        """
        Serializes 'digests' in 'cancel_orders' into their hexadecimal representation.

        Args:
            v (CancelOrdersParams): The parameters of the orders to be cancelled.

        Returns:
            CancelOrdersParams: The 'cancel_orders' with serialized 'digests'.
        """
        v.serialize_dict(["digests"], lambda l: [bytes32_to_hex(x) for x in l])
        return v

    _validator = validator("cancel_orders", allow_reuse=True)(to_tx_request)


class CancelAndPlaceRequest(NadoBaseModel):
    """
    Parameters for a cancel and place request.

    Attributes:
        cancel_and_place (CancelAndPlaceParams): Request parameters for engine cancel_and_place execution
    """

    cancel_and_place: CancelAndPlaceParams

    @validator("cancel_and_place")
    def serialize(cls, v: CancelAndPlaceParams) -> dict:
        cancel_tx = TxRequest.parse_obj(
            CancelOrdersRequest(cancel_orders=v.cancel_orders).cancel_orders
        )
        return {
            "cancel_tx": cancel_tx.tx,
            "place_order": PlaceOrderRequest(place_order=v.place_order).place_order,
            "cancel_signature": cancel_tx.signature,
        }


class CancelProductOrdersRequest(NadoBaseModel):
    """
    Parameters for a cancel product orders request.

    Attributes:
        cancel_product_orders (CancelProductOrdersParams): The parameters of the product orders to be cancelled.

    Methods:
        to_tx_request: Validates and converts 'cancel_product_orders' into a transaction request.
    """

    cancel_product_orders: CancelProductOrdersParams

    _validator = validator("cancel_product_orders", allow_reuse=True)(to_tx_request)


class WithdrawCollateralRequest(NadoBaseModel):
    """
    Parameters for a withdraw collateral request.

    Attributes:
        withdraw_collateral (WithdrawCollateralParams): The parameters of the collateral to be withdrawn.

    Methods:
        serialize: Validates and converts the 'amount' attribute of 'withdraw_collateral' to string.

        to_tx_request: Validates and converts 'withdraw_collateral' into a transaction request.
    """

    withdraw_collateral: WithdrawCollateralParams

    @validator("withdraw_collateral")
    def serialize(cls, v: WithdrawCollateralParams) -> WithdrawCollateralParams:
        v.serialize_dict(["amount"], str)
        return v

    _validator = validator("withdraw_collateral", allow_reuse=True)(to_tx_request)


class LiquidateSubaccountRequest(NadoBaseModel):
    """
    Parameters for a liquidate subaccount request.

    Attributes:
        liquidate_subaccount (LiquidateSubaccountParams): The parameters for the subaccount to be liquidated.

    Methods:
        serialize: Validates and converts the 'amount' attribute and the 'liquidatee' attribute
        of 'liquidate_subaccount' to their proper serialized forms.

        to_tx_request: Validates and converts 'liquidate_subaccount' into a transaction request.
    """

    liquidate_subaccount: LiquidateSubaccountParams

    @validator("liquidate_subaccount")
    def serialize(cls, v: LiquidateSubaccountParams) -> LiquidateSubaccountParams:
        v.serialize_dict(["amount"], str)
        v.serialize_dict(["liquidatee"], bytes32_to_hex)
        return v

    _validator = validator("liquidate_subaccount", allow_reuse=True)(to_tx_request)


class MintNlpRequest(NadoBaseModel):
    """
    Parameters for a mint NLP request.

    Attributes:
        mint_nlp (MintNlpParams): The parameters for minting liquidity.

    Methods:
        serialize: Validates and converts the 'quoteAmount' attribute of 'mint_nlp' to their proper serialized forms.

        to_tx_request: Validates and converts 'mint_nlp' into a transaction request.
    """

    mint_nlp: MintNlpParams

    @validator("mint_nlp")
    def serialize(cls, v: MintNlpParams) -> MintNlpParams:
        v.serialize_dict(["quoteAmount"], str)
        return v

    _validator = validator("mint_nlp", allow_reuse=True)(to_tx_request)


class BurnNlpRequest(NadoBaseModel):
    """
    Parameters for a burn NLP request.

    Attributes:
        burn_nlp (BurnNlpParams): The parameters for burning liquidity.

    Methods:
        serialize: Validates and converts the 'nlpAmount' attribute of 'burn_nlp' to its proper serialized form.

        to_tx_request: Validates and converts 'burn_nlp' into a transaction request.
    """

    burn_nlp: BurnNlpParams

    @validator("burn_nlp")
    def serialize(cls, v: BurnNlpParams) -> BurnNlpParams:
        v.serialize_dict(["nlpAmount"], str)
        return v

    _validator = validator("burn_nlp", allow_reuse=True)(to_tx_request)


class LinkSignerRequest(NadoBaseModel):
    """
    Parameters for a request to link a signer to a subaccount.

    Attributes:
        link_signer (LinkSignerParams): Parameters including the subaccount to be linked.

    Methods:
        serialize: Validates and converts the 'signer' attribute of 'link_signer' into its hexadecimal representation.

        to_tx_request: Validates and converts 'link_signer' into a transaction request.
    """

    link_signer: LinkSignerParams

    @validator("link_signer")
    def serialize(cls, v: LinkSignerParams) -> LinkSignerParams:
        v.serialize_dict(["signer"], bytes32_to_hex)
        return v

    _validator = validator("link_signer", allow_reuse=True)(to_tx_request)


ExecuteRequest = Union[
    PlaceOrderRequest,
    PlaceOrdersRequest,
    CancelOrdersRequest,
    CancelProductOrdersRequest,
    CancelAndPlaceRequest,
    WithdrawCollateralRequest,
    LiquidateSubaccountRequest,
    MintNlpRequest,
    BurnNlpRequest,
    LinkSignerRequest,
]


class PlaceOrderResponse(NadoBaseModel):
    """
    Data model for place order response.
    """

    digest: str


class PlaceOrdersItemResponse(NadoBaseModel):
    """
    Data model for a single order in place orders response.
    """

    digest: Optional[str]
    error: Optional[str]


class PlaceOrdersResponse(NadoBaseModel):
    """
    Data model for place orders response.
    """

    place_orders: list[PlaceOrdersItemResponse]


class CancelOrdersResponse(NadoBaseModel):
    """
    Data model for cancelled orders response.
    """

    cancelled_orders: list[OrderData]


ExecuteResponseData = Union[
    PlaceOrderResponse, PlaceOrdersResponse, CancelOrdersResponse
]


class ExecuteResponse(NadoBaseModel):
    """
    Represents the response returned from executing a request.

    Attributes:
        status (ResponseStatus): The status of the response.

        signature (Optional[str]): The signature of the response. Only present if the request was successfully executed.

        data (Optional[ExecuteResponseData]): Data returned from execute, not all executes currently return data.

        error_code (Optional[int]): The error code, if any error occurred during the execution of the request.

        error (Optional[str]): The error message, if any error occurred during the execution of the request.

        request_type (Optional[str]): Type of the request.

        req (Optional[dict]): The original request that was executed.

        id (Optional[id]): An optional client id provided when placing an order
    """

    status: ResponseStatus
    signature: Optional[str]
    data: Optional[ExecuteResponseData]
    error_code: Optional[int]
    error: Optional[str]
    request_type: Optional[str]
    req: Optional[dict]
    id: Optional[int]


def to_execute_request(params: ExecuteParams) -> ExecuteRequest:
    """
    Maps `ExecuteParams` to its corresponding `ExecuteRequest` object based on the parameter type.

    Args:
        params (ExecuteParams): The parameters to be executed.

    Returns:
        ExecuteRequest: The corresponding `ExecuteRequest` object.
    """
    execute_request_mapping = {
        PlaceOrderParams: (PlaceOrderRequest, NadoExecuteType.PLACE_ORDER.value),
        PlaceOrdersParams: (PlaceOrdersRequest, NadoExecuteType.PLACE_ORDERS.value),
        CancelOrdersParams: (
            CancelOrdersRequest,
            NadoExecuteType.CANCEL_ORDERS.value,
        ),
        CancelProductOrdersParams: (
            CancelProductOrdersRequest,
            NadoExecuteType.CANCEL_PRODUCT_ORDERS.value,
        ),
        WithdrawCollateralParams: (
            WithdrawCollateralRequest,
            NadoExecuteType.WITHDRAW_COLLATERAL.value,
        ),
        LiquidateSubaccountParams: (
            LiquidateSubaccountRequest,
            NadoExecuteType.LIQUIDATE_SUBACCOUNT.value,
        ),
        MintNlpParams: (MintNlpRequest, NadoExecuteType.MINT_NLP.value),
        BurnNlpParams: (BurnNlpRequest, NadoExecuteType.BURN_NLP.value),
        LinkSignerParams: (LinkSignerRequest, NadoExecuteType.LINK_SIGNER.value),
        CancelAndPlaceParams: (
            CancelAndPlaceRequest,
            NadoExecuteType.CANCEL_AND_PLACE.value,
        ),
    }

    RequestClass, field_name = execute_request_mapping[type(params)]
    return RequestClass(**{field_name: params})  # type: ignore
