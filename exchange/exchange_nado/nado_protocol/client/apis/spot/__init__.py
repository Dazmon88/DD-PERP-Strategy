from nado_protocol.client.apis.spot.execute import SpotExecuteAPI
from nado_protocol.client.apis.spot.query import SpotQueryAPI


class SpotAPI(SpotExecuteAPI, SpotQueryAPI):
    """
    A unified interface for spot operations in the Nado Protocol.

    This class combines functionalities from both SpotExecuteAPI and SpotQueryAPI
    into a single interface, providing a simpler and more consistent way to perform spot operations.
    It allows for both query (data retrieval) and execution (transaction) operations for spot products.

    Inheritance:
        SpotExecuteAPI: This provides functionalities to execute various operations related to spot products,
        such as depositing a specified amount into a spot product.

        SpotQueryAPI: This provides functionalities to retrieve various kinds of information related to spot products,
        such as getting the wallet token balance of a given spot product.

    Attributes and Methods: Inherited from SpotExecuteAPI and SpotQueryAPI.
    """

    pass
