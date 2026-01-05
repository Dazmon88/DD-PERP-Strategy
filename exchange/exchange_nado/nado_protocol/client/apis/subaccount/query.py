from typing import Optional
from nado_protocol.client.apis.base import NadoBaseAPI
from nado_protocol.engine_client.types.query import (
    FeeRatesData,
    QuerySubaccountInfoTx,
    SubaccountInfoData,
)
from nado_protocol.indexer_client.types.query import (
    IndexerLinkedSignerRateLimitData,
    IndexerSubaccountsData,
    IndexerSubaccountsParams,
    IndexerInterestAndFundingParams,
    IndexerInterestAndFundingData,
)


class SubaccountQueryAPI(NadoBaseAPI):
    """
    Provides functionalities for querying data related to subaccounts in the Nado Protocol.

    Inherits from NadoBaseAPI, which provides a basic context setup for accessing Nado Clearinghouse.
    This class extends the base class to provide specific functionalities for querying data related to subaccounts.

    Attributes:
        context (NadoClientContext): Provides connectivity details for accessing Nado APIs.
    """

    def get_engine_subaccount_summary(
        self, subaccount: str, txs: Optional[list[QuerySubaccountInfoTx]] = None
    ) -> SubaccountInfoData:
        """
        Retrieve a comprehensive summary of the specified subaccount's state as per the off-chain engine.

        You can optionally provide a list of txs to get an estimated view of your subaccount.

        Args:
            subaccount (str): Unique identifier for the subaccount.

            txs (list[QuerySubaccountInfoTx], optional): Optional list of transactions for the subaccount.

        Returns:
            SubaccountInfoData: A data class object containing detailed state information about the queried subaccount.
        """
        return self.context.engine_client.get_subaccount_info(subaccount, txs)

    def get_subaccount_fee_rates(self, subaccount: str) -> FeeRatesData:
        """
        Retrieve the fee rates associated with a specific subaccount from the off-chain engine.

        Args:
            subaccount (str): Unique identifier for the subaccount.

        Returns:
            FeeRatesData: A data class object containing detailed fee rates data for the specified subaccount.
        """
        return self.context.engine_client.get_fee_rates(subaccount)

    def get_subaccount_linked_signer_rate_limits(
        self, subaccount: str
    ) -> IndexerLinkedSignerRateLimitData:
        """
        Retrieve the current linked signer and their rate limit for a specified subaccount from the indexer.

        Args:
            subaccount (str): Unique identifier for the subaccount.

        Returns:
            IndexerLinkedSignerRateLimitData: A data class object containing information about the current linked signer and their rate limits for the queried subaccount.
        """
        return self.context.indexer_client.get_linked_signer_rate_limits(subaccount)

    def get_subaccounts(
        self,
        address: Optional[str] = None,
        start_idx: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> IndexerSubaccountsData:
        """
        List nado subaccounts via the indexer.

        Args:
            address (Optional[str]): An optional wallet address to find all subaccounts associated to it.
            start_idx (Optional[int]): Optional subaccount id to start from. Used for pagination. Defaults to 0.
            limit (Optional[int]): Maximum number of subaccounts to return. Defaults to 100. Max of 500.

        Returns:
            IndexerSubaccountsData: A data class object containing the list of subaccounts found.
        """
        return self.context.indexer_client.get_subaccounts(
            IndexerSubaccountsParams(address=address, start=start_idx, limit=limit)
        )

    def get_interest_and_funding_payments(
        self,
        subaccount: str,
        product_ids: list[int],
        limit: int,
        max_idx: Optional[int] = None,
    ) -> IndexerInterestAndFundingData:
        """
        List interests and funding payments for a subaccount and provided products from the indexer.

        Args:
            subaccount (str): Subaccount to fetch interest / funding payments for.
            product_ids (list[int]): List of product IDs to fetch interest / funding payments for.
            limit (int): Max number of records to return. Max possible of 100.
            max_idx (Optional[int]): When provided, only return records with idx <= max_idx. Used for pagination.

        Returns:
            IndexerInterestAndFundingData: A data class object containing the list of interest / funding payments found.
        """
        return self.context.indexer_client.get_interest_and_funding_payments(
            IndexerInterestAndFundingParams(
                subaccount=subaccount,
                product_ids=product_ids,
                limit=limit,
                max_idx=max_idx,
            )
        )
