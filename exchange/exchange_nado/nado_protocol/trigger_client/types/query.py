from typing import Optional, List, Union
from enum import Enum

from pydantic import validator

from nado_protocol.engine_client.types.models import ResponseStatus
from nado_protocol.trigger_client.types.models import TriggerOrderData
from nado_protocol.utils.bytes32 import bytes32_to_hex
from nado_protocol.utils.execute import BaseParams, SignatureParams
from nado_protocol.utils.model import NadoBaseModel


class TriggerType(str, Enum):
    PRICE_TRIGGER = "price_trigger"
    TIME_TRIGGER = "time_trigger"


class TriggerOrderStatusType(str, Enum):
    CANCELLED = "cancelled"
    TRIGGERED = "triggered"
    INTERNAL_ERROR = "internal_error"
    TRIGGERING = "triggering"
    WAITING_PRICE = "waiting_price"
    WAITING_DEPENDENCY = "waiting_dependency"
    TWAP_EXECUTING = "twap_executing"
    TWAP_COMPLETED = "twap_completed"


class ListTriggerOrdersTx(BaseParams):
    recvTime: int


class ListTriggerOrdersParams(NadoBaseModel):
    """
    Parameters for listing trigger orders
    """

    type = "list_trigger_orders"
    tx: ListTriggerOrdersTx
    product_ids: Optional[List[int]] = None
    trigger_types: Optional[List[TriggerType]] = None
    status_types: Optional[List[TriggerOrderStatusType]] = None
    max_update_time: Optional[int] = None
    max_digest: Optional[str] = None
    digests: Optional[List[str]] = None
    reduce_only: Optional[bool] = None
    limit: Optional[int] = None
    signature: Optional[str] = None


class ListTwapExecutionsParams(NadoBaseModel):
    """
    Parameters for listing TWAP executions for a specific order
    """

    type = "list_twap_executions"
    digest: str


class ExecutedStatusData(NadoBaseModel):
    """Data for executed TWAP execution"""

    executed_time: int
    execute_response: dict  # ExecuteResponse from engine


class ExecutedStatus(NadoBaseModel):
    """Status when TWAP execution has been executed"""

    executed: ExecutedStatusData


class FailedStatus(NadoBaseModel):
    """Status when TWAP execution failed"""

    failed: str


class CancelledStatus(NadoBaseModel):
    """Status when TWAP execution was cancelled"""

    cancelled: str


class TwapExecutionDetail(NadoBaseModel):
    """Detail of a single TWAP execution"""

    execution_id: int
    scheduled_time: int
    status: Union[
        ExecutedStatus, FailedStatus, CancelledStatus, str
    ]  # str for "pending"
    updated_at: int


class TwapExecutionsData(NadoBaseModel):
    """Data model for TWAP executions"""

    executions: List[TwapExecutionDetail]


class TriggeredStatus(NadoBaseModel):
    """Status when order has been triggered"""

    triggered: dict  # Contains trigger execution details


class TriggerCancelledStatus(NadoBaseModel):
    """Status when order has been cancelled"""

    cancelled: str  # Cancellation reason (e.g., "user_requested")


class TriggerInternalErrorStatus(NadoBaseModel):
    """Status when there was an internal error"""

    internal_error: str  # Error description


class TwapExecutingStatusObject(NadoBaseModel):
    """Status when TWAP order is executing"""

    twap_executing: dict  # Contains execution details


class TwapCompletedStatusObject(NadoBaseModel):
    """Status when TWAP order is completed"""

    twap_completed: dict  # Contains completion details


# Union type for trigger order status
# Order matters: more specific types (with required fields) should come first
TriggerOrderStatus = Union[
    TriggeredStatus,
    TriggerCancelledStatus,
    TriggerInternalErrorStatus,
    TwapExecutingStatusObject,
    TwapCompletedStatusObject,
    str,  # For simple status strings like "waiting_price", "waiting_dependency", etc.
]


class TriggerOrder(NadoBaseModel):
    order: TriggerOrderData
    status: TriggerOrderStatus
    placed_at: int
    updated_at: int


class TriggerOrdersData(NadoBaseModel):
    """
    Data model for trigger orders
    """

    orders: List[TriggerOrder]


class ListTriggerOrdersRequest(ListTriggerOrdersParams):
    tx: ListTriggerOrdersTx

    @validator("tx")
    def serialize(cls, v: ListTriggerOrdersTx) -> ListTriggerOrdersTx:
        if isinstance(v.sender, bytes):
            v.serialize_dict(["sender"], bytes32_to_hex)
        v.serialize_dict(["recvTime"], str)
        return v


class ListTwapExecutionsRequest(ListTwapExecutionsParams):
    pass


TriggerQueryParams = Union[ListTriggerOrdersParams, ListTwapExecutionsParams]
TriggerQueryRequest = Union[ListTriggerOrdersRequest, ListTwapExecutionsRequest]
TriggerQueryData = Union[TriggerOrdersData, TwapExecutionsData]


class TriggerQueryResponse(NadoBaseModel):
    """
    Represents a response to a query request.

    Attributes:
        status (ResponseStatus): The status of the query response.

        data (Optional[TriggerQueryData]): The data returned from the query, or an error message if the query failed.

        error (Optional[str]): The error message, if any error occurred during the query.

        error_code (Optional[int]): The error code, if any error occurred during the query.

        request_type (Optional[str]): Type of the request.
    """

    status: ResponseStatus
    data: Optional[TriggerQueryData] = None
    error: Optional[str] = None
    error_code: Optional[int] = None
    request_type: Optional[str] = None
