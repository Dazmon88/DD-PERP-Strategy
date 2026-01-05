from typing import Union, Sequence
from pydantic import validator
from nado_protocol.contracts.types import NadoExecuteType
from nado_protocol.utils.bytes32 import bytes32_to_hex
from nado_protocol.utils.model import NadoBaseModel
from nado_protocol.engine_client.types.execute import (
    PlaceOrderParams,
    PlaceOrdersParams,
    CancelOrdersParams,
    CancelProductOrdersParams,
    CancelOrdersRequest,
    CancelProductOrdersRequest,
)
from nado_protocol.trigger_client.types.models import TriggerCriteria


class PlaceTriggerOrderParams(PlaceOrderParams):
    trigger: TriggerCriteria


class PlaceTriggerOrdersParams(PlaceOrdersParams):
    """
    Class for defining the parameters needed to place multiple trigger orders in a single request.

    Attributes:
        orders (list[PlaceTriggerOrderParams]): Array of trigger orders to place.

        stop_on_failure (Optional[bool]): If true, stops processing remaining orders when the first order fails.
        Already successfully placed orders are NOT cancelled. Defaults to false.
    """

    orders: Sequence[PlaceTriggerOrderParams]


CancelTriggerOrdersParams = CancelOrdersParams
CancelProductTriggerOrdersParams = CancelProductOrdersParams

TriggerExecuteParams = Union[
    PlaceTriggerOrderParams,
    PlaceTriggerOrdersParams,
    CancelTriggerOrdersParams,
    CancelProductTriggerOrdersParams,
]


class PlaceTriggerOrderRequest(NadoBaseModel):
    """
    Parameters for a request to place an order.

    Attributes:
        place_order (PlaceOrderParams): The parameters for the order to be placed.

    Methods:
        serialize: Validates and serializes the order parameters.
    """

    place_order: PlaceTriggerOrderParams

    @validator("place_order")
    def serialize(cls, v: PlaceTriggerOrderParams) -> PlaceTriggerOrderParams:
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


class PlaceTriggerOrdersRequest(NadoBaseModel):
    """
    Parameters for a request to place multiple trigger orders.

    Attributes:
        place_orders (PlaceTriggerOrdersParams): The parameters for the trigger orders to be placed.

    Methods:
        serialize: Validates and serializes the order parameters.
    """

    place_orders: PlaceTriggerOrdersParams

    @validator("place_orders")
    def serialize(cls, v: PlaceTriggerOrdersParams) -> PlaceTriggerOrdersParams:
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


CancelTriggerOrdersRequest = CancelOrdersRequest
CancelProductTriggerOrdersRequest = CancelProductOrdersRequest

TriggerExecuteRequest = Union[
    PlaceTriggerOrderRequest,
    PlaceTriggerOrdersRequest,
    CancelTriggerOrdersRequest,
    CancelProductTriggerOrdersRequest,
]


def to_trigger_execute_request(params: TriggerExecuteParams) -> TriggerExecuteRequest:
    """
    Maps `TriggerExecuteParams` to its corresponding `TriggerExecuteRequest` object based on the parameter type.

    Args:
        params (TriggerExecuteParams): The parameters to be executed.

    Returns:
        TriggerExecuteRequest: The corresponding `TriggerExecuteRequest` object.
    """
    execute_request_mapping = {
        PlaceTriggerOrderParams: (
            PlaceTriggerOrderRequest,
            NadoExecuteType.PLACE_ORDER.value,
        ),
        PlaceTriggerOrdersParams: (
            PlaceTriggerOrdersRequest,
            NadoExecuteType.PLACE_ORDERS.value,
        ),
        CancelTriggerOrdersParams: (
            CancelTriggerOrdersRequest,
            NadoExecuteType.CANCEL_ORDERS.value,
        ),
        CancelProductTriggerOrdersParams: (
            CancelProductTriggerOrdersRequest,
            NadoExecuteType.CANCEL_PRODUCT_ORDERS.value,
        ),
    }

    RequestClass, field_name = execute_request_mapping[type(params)]
    return RequestClass(**{field_name: params})  # type: ignore
