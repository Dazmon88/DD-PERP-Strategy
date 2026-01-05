import requests
from functools import singledispatchmethod

from typing import Optional, Union
from nado_protocol.engine_client.query import EngineQueryClient
from nado_protocol.engine_client.types import (
    EngineClientOpts,
)
from nado_protocol.engine_client.types.execute import (
    BurnNlpParams,
    CancelAndPlaceParams,
    CancelOrdersParams,
    CancelProductOrdersParams,
    ExecuteParams,
    ExecuteRequest,
    ExecuteResponse,
    LinkSignerParams,
    LiquidateSubaccountParams,
    MintNlpParams,
    OrderParams,
    PlaceMarketOrderParams,
    PlaceOrderParams,
    WithdrawCollateralParams,
    to_execute_request,
)
from nado_protocol.contracts.types import NadoExecuteType
from nado_protocol.engine_client.types.models import MarketLiquidity
from nado_protocol.utils.bytes32 import subaccount_to_hex

from nado_protocol.utils.exceptions import (
    BadStatusCodeException,
    ExecuteFailedException,
)
from nado_protocol.utils.expiration import OrderType, get_expiration_timestamp
from nado_protocol.utils.math import mul_x18, round_x18, to_x18
from nado_protocol.utils.model import NadoBaseModel, is_instance_of_union
from nado_protocol.utils.subaccount import Subaccount, SubaccountParams
from nado_protocol.utils.execute import NadoBaseExecute
from nado_protocol.utils.order import build_appendix


class EngineExecuteClient(NadoBaseExecute):
    """
    Client class for executing operations against the off-chain engine.
    """

    def __init__(
        self, opts: EngineClientOpts, querier: Optional[EngineQueryClient] = None
    ):
        """
        Initialize the EngineExecuteClient with provided options.

        Args:
            opts (EngineClientOpts): Options for the client.

            querier (EngineQueryClient, optional): An EngineQueryClient instance. If not provided, a new one is created.
        """
        super().__init__(opts)
        self._querier = querier or EngineQueryClient(opts)
        self._opts: EngineClientOpts = EngineClientOpts.parse_obj(opts)
        self.url: str = self._opts.url
        self.session = requests.Session()

    def tx_nonce(self, sender: str) -> int:
        """
        Get the transaction nonce. Used to perform executes such as `withdraw_collateral`.

        Returns:
            int: The transaction nonce.
        """
        return int(self._querier.get_nonces(sender[:42]).tx_nonce)

    @singledispatchmethod
    def execute(self, params: Union[ExecuteParams, ExecuteRequest]) -> ExecuteResponse:
        """
        Executes the operation defined by the provided parameters.

        Args:
            params (ExecuteParams): The parameters for the operation to execute. This can represent a variety of operations, such as placing orders, cancelling orders, and more.

        Returns:
            ExecuteResponse: The response from the executed operation.
        """
        req: ExecuteRequest = (
            params if is_instance_of_union(params, ExecuteRequest) else to_execute_request(params)  # type: ignore
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
        parsed_req: ExecuteRequest = NadoBaseModel.parse_obj(req)  # type: ignore
        return self._execute(parsed_req)

    def _execute(self, req: ExecuteRequest) -> ExecuteResponse:
        """
        Internal method to execute the operation. Sends request to the server.

        Args:
            req (ExecuteRequest): The request data for the operation to execute.

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

    def _assert_book_not_empty(
        self, bids: list[MarketLiquidity], asks: list[MarketLiquidity], is_bid: bool
    ):
        book_is_empty = (is_bid and len(bids) == 0) or (not is_bid and len(asks) == 0)
        if book_is_empty:
            raise Exception("Orderbook is empty.")

    def place_order(self, params: PlaceOrderParams) -> ExecuteResponse:
        """
        Execute a place order operation.

        Args:
            params (PlaceOrderParams): Parameters required for placing an order.
            The parameters include the order details and the product_id.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = PlaceOrderParams.parse_obj(params)
        params.order = self.prepare_execute_params(params.order, True)
        params.signature = params.signature or self._sign(
            NadoExecuteType.PLACE_ORDER, params.order.dict(), params.product_id
        )
        return self.execute(params)

    def place_market_order(self, params: PlaceMarketOrderParams) -> ExecuteResponse:
        """
        Places an FOK order using top of the book price with provided slippage.

        Args:
            params (PlaceMarketOrderParams): Parameters required for placing a market order.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        orderbook = self._querier.get_market_liquidity(params.product_id, 1)
        is_bid = int(params.market_order.amount) > 0
        self._assert_book_not_empty(orderbook.bids, orderbook.asks, is_bid)
        slippage = to_x18(params.slippage or 0.005)  # defaults to 0.5%
        market_price_x18 = (
            mul_x18(orderbook.bids[0][0], to_x18(1) + slippage)
            if is_bid
            else mul_x18(orderbook.asks[0][0], to_x18(1) - slippage)
        )
        price_increment_x18 = self._querier._get_subaccount_product_position(
            subaccount_to_hex(params.market_order.sender), params.product_id
        ).product.book_info.price_increment_x18
        order = OrderParams(
            sender=params.market_order.sender,
            amount=params.market_order.amount,
            nonce=params.market_order.nonce,
            priceX18=round_x18(market_price_x18, price_increment_x18),
            expiration=get_expiration_timestamp(1000),
            appendix=build_appendix(
                OrderType.FOK, reduce_only=bool(params.reduce_only)
            ),
        )
        return self.place_order(
            PlaceOrderParams(  # type: ignore
                product_id=params.product_id,
                order=order,
                spot_leverage=params.spot_leverage,
                signature=params.signature,
            )
        )

    def cancel_orders(self, params: CancelOrdersParams) -> ExecuteResponse:
        """
        Execute a cancel orders operation.

        Args:
            params (CancelOrdersParams): Parameters required for canceling orders.
            The parameters include the order digests to be cancelled.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = self.prepare_execute_params(CancelOrdersParams.parse_obj(params), True)
        params.signature = params.signature or self._sign(
            NadoExecuteType.CANCEL_ORDERS, params.dict()
        )
        return self.execute(params)

    def cancel_product_orders(
        self, params: CancelProductOrdersParams
    ) -> ExecuteResponse:
        """
        Execute a cancel product orders operation.

        Args:
            params (CancelProductOrdersParams): Parameters required for bulk canceling orders of specific products.
            The parameters include a list of product ids to bulk cancel orders for.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = self.prepare_execute_params(
            CancelProductOrdersParams.parse_obj(params), True
        )
        params.signature = params.signature or self._sign(
            NadoExecuteType.CANCEL_PRODUCT_ORDERS, params.dict()
        )
        return self.execute(params)

    def cancel_and_place(self, params: CancelAndPlaceParams) -> ExecuteResponse:
        """
        Execute a cancel and place operation.

        Args:
            params (CancelAndPlaceParams): Parameters required for cancel and place.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        cancel_orders: CancelOrdersParams = self.prepare_execute_params(
            CancelOrdersParams.parse_obj(params.cancel_orders), True
        )
        cancel_orders.signature = cancel_orders.signature or self._sign(
            NadoExecuteType.CANCEL_ORDERS, cancel_orders.dict()
        )
        place_order: PlaceOrderParams = PlaceOrderParams.parse_obj(params.place_order)
        place_order.order = self.prepare_execute_params(place_order.order, True)
        place_order.signature = place_order.signature or self._sign(
            NadoExecuteType.PLACE_ORDER,
            place_order.order.dict(),
            place_order.product_id,
        )
        return self.execute(
            CancelAndPlaceParams(cancel_orders=cancel_orders, place_order=place_order)
        )

    def withdraw_collateral(self, params: WithdrawCollateralParams) -> ExecuteResponse:
        """
        Execute a withdraw collateral operation.

        Args:
            params (WithdrawCollateralParams): Parameters required for withdrawing collateral.
            The parameters include the collateral details.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = self.prepare_execute_params(
            WithdrawCollateralParams.parse_obj(params), False
        )
        params.signature = params.signature or self._sign(
            NadoExecuteType.WITHDRAW_COLLATERAL, params.dict()
        )
        return self.execute(params)

    def liquidate_subaccount(
        self, params: LiquidateSubaccountParams
    ) -> ExecuteResponse:
        """
        Execute a liquidate subaccount operation.

        Args:
            params (LiquidateSubaccountParams): Parameters required for liquidating a subaccount.
            The parameters include the liquidatee details.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = self.prepare_execute_params(
            LiquidateSubaccountParams.parse_obj(params), False
        )
        params.signature = params.signature or self._sign(
            NadoExecuteType.LIQUIDATE_SUBACCOUNT,
            params.dict(),
        )
        return self.execute(params)

    def mint_nlp(self, params: MintNlpParams) -> ExecuteResponse:
        """
        Execute a mint NLP tokens operation.

        Args:
            params (MintNlpParams): Parameters required for minting NLP tokens.
            The parameters include the LP details.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = self.prepare_execute_params(MintNlpParams.parse_obj(params), False)
        params.signature = params.signature or self._sign(
            NadoExecuteType.MINT_NLP,
            params.dict(),
        )
        return self.execute(params)

    def burn_nlp(self, params: BurnNlpParams) -> ExecuteResponse:
        """
        Execute a burn NLP tokens operation.

        Args:
            params (BurnNlpParams): Parameters required for burning LP tokens.
            The parameters include the LP details.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = self.prepare_execute_params(BurnNlpParams.parse_obj(params), False)
        params.signature = params.signature or self._sign(
            NadoExecuteType.BURN_NLP,
            params.dict(),
        )
        return self.execute(params)

    def link_signer(self, params: LinkSignerParams) -> ExecuteResponse:
        """
        Execute a link signer operation.

        Args:
            params (LinkSignerParams): Parameters required for linking a signer.
            The parameters include the signer details.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        params = self.prepare_execute_params(LinkSignerParams.parse_obj(params), False)
        params.signature = params.signature or self._sign(
            NadoExecuteType.LINK_SIGNER,
            params.dict(),
        )
        return self.execute(params)

    def close_position(
        self, subaccount: Subaccount, product_id: int
    ) -> ExecuteResponse:
        """
        Execute a place order operation to close a position for the provided `product_id`.

        Attributes:
            subaccount (Subaccount): The subaccount to close position for.
            product_id (int): The ID of the product to close position for.

        Returns:
            ExecuteResponse: Response of the execution, including status and potential error message.
        """
        subaccount = subaccount_to_hex(subaccount)
        position = self._querier._get_subaccount_product_position(
            subaccount, product_id
        )
        balance, product = position.balance, position.product
        closing_spread_x18 = to_x18(0.005)
        closing_price_x18 = (
            mul_x18(product.oracle_price_x18, to_x18(1) - closing_spread_x18)
            if int(balance.balance.amount) > 0
            else mul_x18(product.oracle_price_x18, to_x18(1) + closing_spread_x18)
        )
        return self.place_order(
            PlaceOrderParams(  # type: ignore
                product_id=product_id,
                order=OrderParams(  # type: ignore
                    sender=subaccount,
                    amount=-round_x18(
                        balance.balance.amount,
                        product.book_info.size_increment,
                    ),
                    priceX18=round_x18(
                        closing_price_x18,
                        product.book_info.price_increment_x18,
                    ),
                    expiration=get_expiration_timestamp(1000),
                    appendix=build_appendix(OrderType.FOK, reduce_only=True),
                ),
            )
        )
