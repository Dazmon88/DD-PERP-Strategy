import requests
from functools import singledispatchmethod
from typing import Union, Optional, List, cast
from nado_protocol.contracts.types import NadoExecuteType
from nado_protocol.trigger_client.types.execute import (
    TriggerExecuteParams,
    TriggerExecuteRequest,
    PlaceTriggerOrderParams,
    CancelTriggerOrdersParams,
    CancelProductTriggerOrdersParams,
    to_trigger_execute_request,
)
from nado_protocol.engine_client.types.execute import ExecuteResponse
from nado_protocol.trigger_client.types import TriggerClientOpts
from nado_protocol.utils.exceptions import (
    BadStatusCodeException,
    ExecuteFailedException,
)
from nado_protocol.utils.execute import NadoBaseExecute, OrderParams
from nado_protocol.utils.model import NadoBaseModel, is_instance_of_union
from nado_protocol.utils.twap import create_twap_order
from nado_protocol.utils.order import build_appendix, OrderAppendixTriggerType
from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
from nado_protocol.utils.nonce import gen_order_nonce
from nado_protocol.utils.subaccount import SubaccountParams
from nado_protocol.utils.bytes32 import subaccount_to_hex
from nado_protocol.trigger_client.types.models import (
    PriceTrigger,
    PriceTriggerData,
    LastPriceAbove,
    LastPriceBelow,
    OraclePriceAbove,
    OraclePriceBelow,
    MidPriceAbove,
    MidPriceBelow,
    PriceRequirement,
    Dependency,
)


class TriggerExecuteClient(NadoBaseExecute):
    def __init__(self, opts: TriggerClientOpts):
        super().__init__(opts)
        self._opts: TriggerClientOpts = TriggerClientOpts.parse_obj(opts)
        self.url: str = self._opts.url
        self.session = requests.Session()

    def tx_nonce(self, _: str) -> int:
        raise NotImplementedError

    @singledispatchmethod
    def execute(
        self, params: Union[TriggerExecuteParams, TriggerExecuteRequest]
    ) -> ExecuteResponse:
        """
        Executes the operation defined by the provided parameters.

        Args:
            params (ExecuteParams): The parameters for the operation to execute. This can represent a variety of operations, such as placing orders, cancelling orders, and more.

        Returns:
            ExecuteResponse: The response from the executed operation.
        """
        req: TriggerExecuteRequest = (
            params if is_instance_of_union(params, TriggerExecuteRequest) else to_trigger_execute_request(params)  # type: ignore
        )
        return self._execute(req)

    @execute.register
    def _(self, req: dict) -> ExecuteResponse:
        """
        Overloaded method to execute the operation defined by the provided request.

        Args:
            req (dict): The request data for the operation to execute. Can be a dictionary or an instance of ExecuteRequest.

        Returns:
            ExecuteResponse: The response from the executed operation.
        """
        parsed_req: TriggerExecuteRequest = NadoBaseModel.parse_obj(req)  # type: ignore
        return self._execute(parsed_req)

    def _execute(self, req: TriggerExecuteRequest) -> ExecuteResponse:
        """
        Internal method to execute the operation. Sends request to the server.

        Args:
            req (TriggerExecuteRequest): The request data for the operation to execute.

        Returns:
            ExecuteResponse: The response from the executed operation.

        Raises:
            BadStatusCodeException: If the server response status code is not 200.
            ExecuteFailedException: If there's an error in the execution or the response status is not "success".
        """
        res = self.session.post(f"{self.url}/execute", json=req.dict())
        if res.status_code != 200:
            raise BadStatusCodeException(res.text)
        try:
            execute_res = ExecuteResponse(**res.json(), req=req.dict())
        except Exception:
            raise ExecuteFailedException(res.text)
        if execute_res.status != "success":
            raise ExecuteFailedException(res.text)
        return execute_res

    def place_trigger_order(self, params: PlaceTriggerOrderParams) -> ExecuteResponse:
        params = PlaceTriggerOrderParams.parse_obj(params)
        params.order = self.prepare_execute_params(params.order, True)
        params.signature = params.signature or self._sign(
            NadoExecuteType.PLACE_ORDER, params.order.dict(), params.product_id
        )
        return self.execute(params)

    def place_twap_order(
        self,
        product_id: int,
        price_x18: str,
        total_amount_x18: str,
        times: int,
        slippage_frac: float,
        interval_seconds: int,
        sender: Optional[Union[str, SubaccountParams]] = None,
        subaccount_owner: Optional[str] = None,
        subaccount_name: str = "default",
        expiration: Optional[int] = None,
        nonce: Optional[int] = None,
        custom_amounts_x18: Optional[List[str]] = None,
        reduce_only: bool = False,
        spot_leverage: Optional[bool] = None,
        id: Optional[int] = None,
    ) -> ExecuteResponse:
        """
        Place a TWAP (Time-Weighted Average Price) order.

        This is a convenience method that creates a TWAP trigger order with the specified parameters.

        Args:
            product_id (int): The product ID for the order.
            price_x18 (str): The limit price multiplied by 1e18.
            total_amount_x18 (str): The total amount to trade multiplied by 1e18 (signed, negative for sell).
            times (int): Number of TWAP executions (1-500).
            slippage_frac (float): Slippage tolerance as a fraction (e.g., 0.01 for 1%).
            interval_seconds (int): Time interval between executions in seconds.
            sender (Optional[str]): The sender address (32 bytes hex or SubaccountParams). If provided, takes precedence over subaccount_owner/subaccount_name.
            subaccount_owner (Optional[str]): The subaccount owner address. If not provided, uses client's signer address. Ignored if sender is provided.
            subaccount_name (str): The subaccount name. Defaults to "default". Ignored if sender is provided.
            expiration (Optional[int]): Order expiration timestamp. If not provided, calculated as min(((times - 1) * interval_seconds) + 1 hour, 25 hours) from now.
            nonce (Optional[int]): Order nonce. If not provided, will be auto-generated.
            custom_amounts_x18 (Optional[List[str]]): Custom amounts for each execution multiplied by 1e18.
            reduce_only (bool): Whether this is a reduce-only order. Defaults to False.
            spot_leverage (Optional[bool]): Whether to use spot leverage.
            id (Optional[int]): Optional order ID.

        Returns:
            ExecuteResponse: The response from placing the TWAP order.
        """
        # Calculate default expiration if not provided
        # Backend requires: min_expiration <= expiration <= timestamp + 25 hours
        # Where min_expiration = ((times - 1) * interval) + now
        if expiration is None:
            min_duration = (times - 1) * interval_seconds
            max_duration = 60 * 60 * 25  # 25 hours in seconds
            # Set expiration to minimum duration + 1 hour buffer, capped at 25 hours
            buffer_duration = min(min_duration + 60 * 60, max_duration)
            expiration = get_expiration_timestamp(buffer_duration)

        # Build sender from subaccount parameters if not directly provided
        sender_value: Union[str, SubaccountParams]
        if sender is None:
            sender_value = SubaccountParams(
                subaccount_owner=subaccount_owner or self.signer.address,
                subaccount_name=subaccount_name,
            )
        else:
            sender_value = sender

        # Convert sender to hex string if it's SubaccountParams
        sender_hex: str
        if isinstance(sender_value, SubaccountParams):
            sender_hex = subaccount_to_hex(sender_value)
        else:
            sender_hex = sender_value

        params = create_twap_order(
            product_id=product_id,
            sender=sender_hex,
            price_x18=price_x18,
            total_amount_x18=total_amount_x18,
            expiration=expiration,
            nonce=nonce if nonce is not None else gen_order_nonce(),
            times=times,
            slippage_frac=slippage_frac,
            interval_seconds=interval_seconds,
            custom_amounts_x18=custom_amounts_x18,
            reduce_only=reduce_only,
            spot_leverage=spot_leverage,
            id=id,
        )
        return self.place_trigger_order(params)

    def place_price_trigger_order(
        self,
        product_id: int,
        price_x18: str,
        amount_x18: str,
        trigger_price_x18: str,
        trigger_type: str,
        sender: Optional[Union[str, SubaccountParams]] = None,
        subaccount_owner: Optional[str] = None,
        subaccount_name: str = "default",
        expiration: Optional[int] = None,
        nonce: Optional[int] = None,
        reduce_only: bool = False,
        order_type: OrderType = OrderType.DEFAULT,
        spot_leverage: Optional[bool] = None,
        id: Optional[int] = None,
        dependency: Optional[Dependency] = None,
    ) -> ExecuteResponse:
        """
        Place a price trigger order.

        This is a convenience method that creates a price trigger order with the specified parameters.

        Args:
            product_id (int): The product ID for the order.
            price_x18 (str): The limit price multiplied by 1e18.
            amount_x18 (str): The amount to trade multiplied by 1e18 (signed, negative for sell).
            trigger_price_x18 (str): The trigger price multiplied by 1e18.
            trigger_type (str): Type of price trigger - one of:
                "last_price_above", "last_price_below",
                "oracle_price_above", "oracle_price_below",
                "mid_price_above", "mid_price_below".
            sender (Optional[str]): The sender address (32 bytes hex or SubaccountParams). If provided, takes precedence over subaccount_owner/subaccount_name.
            subaccount_owner (Optional[str]): The subaccount owner address. If not provided, uses client's signer address. Ignored if sender is provided.
            subaccount_name (str): The subaccount name. Defaults to "default". Ignored if sender is provided.
            expiration (Optional[int]): Order expiration timestamp. If not provided, defaults to 7 days from now.
            nonce (Optional[int]): Order nonce. If not provided, will be auto-generated.
            reduce_only (bool): Whether this is a reduce-only order. Defaults to False.
            order_type (OrderType): Order execution type (DEFAULT, IOC, FOK, POST_ONLY). Defaults to DEFAULT.
            spot_leverage (Optional[bool]): Whether to use spot leverage.
            id (Optional[int]): Optional order ID.
            dependency (Optional[Dependency]): Optional dependency trigger. If provided, this order will trigger
                when the specified order (by digest) is filled. The dependency includes:
                - digest (str): The digest of the order to depend on
                - on_partial_fill (bool): Whether to trigger on partial fill (True) or only on full fill (False)

        Returns:
            ExecuteResponse: The response from placing the price trigger order.

        Raises:
            ValueError: If trigger_type is not supported.
        """
        # Create the appropriate price requirement based on trigger type
        price_requirement: PriceRequirement
        if trigger_type == "last_price_above":
            price_requirement = LastPriceAbove(last_price_above=trigger_price_x18)
        elif trigger_type == "last_price_below":
            price_requirement = LastPriceBelow(last_price_below=trigger_price_x18)
        elif trigger_type == "oracle_price_above":
            price_requirement = OraclePriceAbove(oracle_price_above=trigger_price_x18)
        elif trigger_type == "oracle_price_below":
            price_requirement = OraclePriceBelow(oracle_price_below=trigger_price_x18)
        elif trigger_type == "mid_price_above":
            price_requirement = MidPriceAbove(mid_price_above=trigger_price_x18)
        elif trigger_type == "mid_price_below":
            price_requirement = MidPriceBelow(mid_price_below=trigger_price_x18)
        else:
            raise ValueError(
                f"Unsupported trigger_type: {trigger_type}. "
                f"Supported types: ['last_price_above', 'last_price_below', 'oracle_price_above', 'oracle_price_below', 'mid_price_above', 'mid_price_below']"
            )

        trigger = PriceTrigger(
            price_trigger=PriceTriggerData(
                price_requirement=price_requirement, dependency=dependency
            )
        )

        # Build appendix with PRICE trigger type
        appendix = build_appendix(
            order_type=order_type,
            reduce_only=reduce_only,
            trigger_type=OrderAppendixTriggerType.PRICE,
        )

        # Default expiration to 7 days if not provided
        if expiration is None:
            expiration = get_expiration_timestamp(60 * 60 * 24 * 7)

        # Build sender from subaccount parameters if not directly provided
        sender_value: Union[str, SubaccountParams]
        if sender is None:
            sender_value = SubaccountParams(
                subaccount_owner=subaccount_owner or self.signer.address,
                subaccount_name=subaccount_name,
            )
        else:
            sender_value = sender

        order_params = OrderParams(
            sender=sender_value,
            priceX18=int(price_x18),
            amount=int(amount_x18),
            expiration=expiration,
            nonce=nonce if nonce is not None else gen_order_nonce(),
            appendix=appendix,
        )

        params = PlaceTriggerOrderParams(
            product_id=product_id,
            order=order_params,
            trigger=trigger,
            signature=None,
            digest=None,
            spot_leverage=spot_leverage,
            id=id,
        )

        return self.place_trigger_order(params)

    def cancel_trigger_orders(
        self, params: CancelTriggerOrdersParams
    ) -> ExecuteResponse:
        params = self.prepare_execute_params(
            CancelTriggerOrdersParams.parse_obj(params), True
        )
        params.signature = params.signature or self._sign(
            NadoExecuteType.CANCEL_ORDERS, params.dict()
        )
        return self.execute(params)

    def cancel_product_trigger_orders(
        self, params: CancelProductTriggerOrdersParams
    ) -> ExecuteResponse:
        params = self.prepare_execute_params(
            CancelProductTriggerOrdersParams.parse_obj(params), True
        )
        params.signature = params.signature or self._sign(
            NadoExecuteType.CANCEL_PRODUCT_ORDERS, params.dict()
        )
        return self.execute(params)
