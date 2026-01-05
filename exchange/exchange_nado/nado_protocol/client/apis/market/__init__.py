from nado_protocol.client.apis.market.execute import MarketExecuteAPI
from nado_protocol.client.apis.market.query import MarketQueryAPI


class MarketAPI(MarketExecuteAPI, MarketQueryAPI):
    """
    A unified interface for market operations in the Nado Protocol.

    This class combines functionalities from both MarketExecuteAPI and MarketQueryAPI
    into a single interface, providing a simpler and more consistent way to perform market operations.
    It allows for both query (data retrieval) and execution (transaction) operations for market.

    Inheritance:
        MarketExecuteAPI: This provides functionalities to execute various operations related to market.
        These include actions like placing an order, canceling an order, minting and burning LP tokens.

        MarketQueryAPI: This provides functionalities to retrieve various kinds of information related to market.
        These include operations like retrieving order books, historical orders, market matches, and others.

    Attributes and Methods: Inherited from MarketExecuteAPI and MarketQueryAPI.
    """

    pass
