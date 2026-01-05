import requests
from nado_protocol.contracts.types import NadoTxType
from nado_protocol.trigger_client.types import TriggerClientOpts
from nado_protocol.trigger_client.types.query import (
    ListTriggerOrdersParams,
    ListTriggerOrdersRequest,
    ListTwapExecutionsParams,
    ListTwapExecutionsRequest,
    TriggerQueryResponse,
    TriggerQueryParams,
    TriggerQueryRequest,
)
from nado_protocol.utils.exceptions import (
    BadStatusCodeException,
    QueryFailedException,
)
from nado_protocol.utils.execute import NadoBaseExecute


class TriggerQueryClient(NadoBaseExecute):
    """
    Client class for querying the trigger service.
    """

    def __init__(self, opts: TriggerClientOpts):
        self._opts: TriggerClientOpts = TriggerClientOpts.parse_obj(opts)
        self.url: str = self._opts.url
        self.session = requests.Session()  # type: ignore

    def tx_nonce(self, _: str) -> int:
        raise NotImplementedError

    def query(self, req: dict) -> TriggerQueryResponse:
        """
        Send a query to the trigger service.

        Args:
            req (QueryRequest): The query request parameters.

        Returns:
            QueryResponse: The response from the engine.

        Raises:
            BadStatusCodeException: If the response status code is not 200.
            QueryFailedException: If the query status is not "success".
        """
        res = self.session.post(f"{self.url}/query", json=req)
        if res.status_code != 200:
            raise BadStatusCodeException(res.text)
        try:
            query_res = TriggerQueryResponse(**res.json())
        except Exception:
            raise QueryFailedException(res.text)
        if query_res.status != "success":
            raise QueryFailedException(res.text)
        return query_res

    def list_trigger_orders(
        self, params: ListTriggerOrdersParams
    ) -> TriggerQueryResponse:
        params = ListTriggerOrdersParams.parse_obj(params)
        params.signature = params.signature or self._sign(
            NadoTxType.LIST_TRIGGER_ORDERS, params.tx.dict()
        )
        return self.query(ListTriggerOrdersRequest.parse_obj(params).dict())

    def list_twap_executions(
        self, params: ListTwapExecutionsParams
    ) -> TriggerQueryResponse:
        """
        List TWAP executions for a specific order digest.

        Args:
            params (ListTwapExecutionsParams): Parameters containing the order digest.

        Returns:
            TriggerQueryResponse: Response containing TWAP execution details.
        """
        params = ListTwapExecutionsParams.parse_obj(params)
        return self.query(ListTwapExecutionsRequest.parse_obj(params).dict())
