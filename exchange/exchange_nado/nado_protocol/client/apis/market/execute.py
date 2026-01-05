from typing import Optional, List
from nado_protocol.engine_client.types.execute import (
    BurnNlpParams,
    CancelAndPlaceParams,
    CancelOrdersParams,
    CancelProductOrdersParams,
    ExecuteResponse,
    MintNlpParams,
    PlaceMarketOrderParams,
    PlaceOrderParams,
)
from nado_protocol.client.apis.base import NadoBaseAPI
from nado_protocol.trigger_client.types.execute import (
    PlaceTriggerOrderParams,
    CancelTriggerOrdersParams,
    CancelProductTriggerOrdersParams,
)
from nado_protocol.utils.exceptions import MissingTriggerClient
from nado_protocol.utils.subaccount import Subaccount
from nado_protocol.utils.expiration import OrderType


class MarketExecuteAPI(NadoBaseAPI):
    """
    Provides functionality to interact with the Nado's market execution APIs.
    This class contains methods that allow clients to execute operations such as minting LP tokens, burning LP tokens,
    placing and cancelling orders on the Nado market.

    Attributes:
        context (NadoClientContext): The context that provides connectivity configuration for NadoClient.

    Note:
        This class should not be instantiated directly, it is designed to be used through a NadoClient instance.
    """

    def mint_nlp(self, params: MintNlpParams) -> ExecuteResponse:
        """
        Mint NLP tokens through the engine.

        Args:
            params (MintNlpParams): Parameters required to mint NLP tokens.

        Returns:
            ExecuteResponse: The response from the engine execution.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.mint_nlp(params)

    def burn_nlp(self, params: BurnNlpParams) -> ExecuteResponse:
        """
        Burn NLP tokens through the engine.

        Args:
            params (BurnNlpParams): Parameters required to burn NLP tokens.

        Returns:
            ExecuteResponse: The response from the engine execution.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.burn_nlp(params)

    def place_order(self, params: PlaceOrderParams) -> ExecuteResponse:
        """
        Places an order through the engine.

        Args:
            params (PlaceOrderParams): Parameters required to place an order.

        Returns:
            ExecuteResponse: The response from the engine execution.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.place_order(params)

    def place_market_order(self, params: PlaceMarketOrderParams) -> ExecuteResponse:
        """
        Places a market order through the engine.

        Args:
            params (PlaceMarketOrderParams): Parameters required to place a market order.

        Returns:
            ExecuteResponse: The response from the engine execution.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.place_market_order(params)

    def cancel_orders(self, params: CancelOrdersParams) -> ExecuteResponse:
        """
        Cancels orders through the engine.

        Args:
            params (CancelOrdersParams): Parameters required to cancel orders.

        Returns:
            ExecuteResponse: The response from the engine execution containing information about the canceled product orders.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.cancel_orders(params)

    def cancel_product_orders(
        self, params: CancelProductOrdersParams
    ) -> ExecuteResponse:
        """
        Cancels all orders for provided products through the engine.

        Args:
            params (CancelProductOrdersParams): Parameters required to cancel product orders.

        Returns:
            ExecuteResponse: The response from the engine execution containing information about the canceled product orders.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.cancel_product_orders(params)

    def cancel_and_place(self, params: CancelAndPlaceParams) -> ExecuteResponse:
        """
        Cancels orders and places a new one through the engine on the same request.

        Args:
            params (CancelAndPlaceParams): Parameters required to cancel orders and place a new one.

        Returns:
            ExecuteResponse: The response from the engine execution.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.cancel_and_place(params)

    def close_position(
        self, subaccount: Subaccount, product_id: int
    ) -> ExecuteResponse:
        """
        Places an order through the engine to close a position for the provided `product_id`.

        Attributes:
            subaccount (Subaccount): The subaccount to close position for.
            product_id (int): The ID of the product to close position for.

         Returns:
            ExecuteResponse: The response from the engine execution.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.close_position(subaccount, product_id)

    def place_trigger_order(self, params: PlaceTriggerOrderParams) -> ExecuteResponse:
        if self.context.trigger_client is None:
            raise MissingTriggerClient()
        return self.context.trigger_client.place_trigger_order(params)

    def cancel_trigger_orders(
        self, params: CancelTriggerOrdersParams
    ) -> ExecuteResponse:
        if self.context.trigger_client is None:
            raise MissingTriggerClient()
        return self.context.trigger_client.cancel_trigger_orders(params)

    def cancel_trigger_product_orders(
        self, params: CancelProductTriggerOrdersParams
    ) -> ExecuteResponse:
        if self.context.trigger_client is None:
            raise MissingTriggerClient()
        return self.context.trigger_client.cancel_product_trigger_orders(params)

    def place_twap_order(
        self,
        product_id: int,
        price_x18: str,
        total_amount_x18: str,
        times: int,
        slippage_frac: float,
        interval_seconds: int,
        sender: Optional[str] = None,
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

        Raises:
            MissingTriggerClient: If trigger client is not configured.
        """
        if self.context.trigger_client is None:
            raise MissingTriggerClient()
        return self.context.trigger_client.place_twap_order(
            product_id=product_id,
            price_x18=price_x18,
            total_amount_x18=total_amount_x18,
            times=times,
            slippage_frac=slippage_frac,
            interval_seconds=interval_seconds,
            sender=sender,
            subaccount_owner=subaccount_owner,
            subaccount_name=subaccount_name,
            expiration=expiration,
            nonce=nonce,
            custom_amounts_x18=custom_amounts_x18,
            reduce_only=reduce_only,
            spot_leverage=spot_leverage,
            id=id,
        )

    def place_price_trigger_order(
        self,
        product_id: int,
        price_x18: str,
        amount_x18: str,
        trigger_price_x18: str,
        trigger_type: str,
        sender: Optional[str] = None,
        subaccount_owner: Optional[str] = None,
        subaccount_name: str = "default",
        expiration: Optional[int] = None,
        nonce: Optional[int] = None,
        reduce_only: bool = False,
        order_type: OrderType = OrderType.DEFAULT,
        spot_leverage: Optional[bool] = None,
        id: Optional[int] = None,
        dependency: Optional[dict] = None,
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
            dependency (Optional[dict]): Optional dependency trigger dict with 'digest' and 'on_partial_fill' keys.

        Returns:
            ExecuteResponse: The response from placing the price trigger order.

        Raises:
            MissingTriggerClient: If trigger client is not configured.
            ValueError: If trigger_type is not supported.
        """
        if self.context.trigger_client is None:
            raise MissingTriggerClient()

        # Convert dict to Dependency if provided
        dependency_obj = None
        if dependency is not None:
            from nado_protocol.trigger_client.types.models import Dependency

            dependency_obj = Dependency.parse_obj(dependency)

        return self.context.trigger_client.place_price_trigger_order(
            product_id=product_id,
            price_x18=price_x18,
            amount_x18=amount_x18,
            trigger_price_x18=trigger_price_x18,
            trigger_type=trigger_type,
            sender=sender,
            subaccount_owner=subaccount_owner,
            subaccount_name=subaccount_name,
            expiration=expiration,
            nonce=nonce,
            reduce_only=reduce_only,
            order_type=order_type,
            spot_leverage=spot_leverage,
            id=id,
            dependency=dependency_obj,
        )
