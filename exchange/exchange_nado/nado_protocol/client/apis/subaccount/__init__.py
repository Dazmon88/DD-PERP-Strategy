from nado_protocol.client.apis.subaccount.execute import SubaccountExecuteAPI
from nado_protocol.client.apis.subaccount.query import SubaccountQueryAPI


class SubaccountAPI(SubaccountExecuteAPI, SubaccountQueryAPI):
    """
    A unified interface for subaccount operations in the Nado Protocol.

    This class combines functionalities from both SubaccountExecuteAPI and SubaccountQueryAPI
    into a single interface, providing a simpler and more consistent way to perform subaccount operations.
    It allows for both query (data retrieval) and execution (transaction) operations for subaccounts.

    Inheritance:
        SubaccountExecuteAPI: This provides functionalities to execute various operations related to subaccounts.
        These include actions like liquidating a subaccount or linking a signer to a subaccount.

        SubaccountQueryAPI: This provides functionalities to retrieve various kinds of information related to subaccounts.
        These include operations like retrieving a summary of a subaccount's state, retrieving the fee rates associated with a
        subaccount, querying token rewards for a wallet, and getting linked signer rate limits for a subaccount.

    Attributes and Methods: Inherited from SubaccountExecuteAPI and SubaccountQueryAPI.
    """

    pass
