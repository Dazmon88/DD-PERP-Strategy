from web3.contract import Contract
from nado_protocol.client.apis.base import NadoBaseAPI


class BaseSpotAPI(NadoBaseAPI):
    """
    Base class for Spot operations in the Nado Protocol.

    This class provides basic functionality for retrieving product-specific information
    from the spot market of the Nado Protocol, such as the associated ERC20 token contract for a given spot product.

    Attributes:
        context (NadoClientContext): Provides connectivity details for accessing Nado APIs.

    Methods:
        get_token_contract_for_product: Retrieves the associated ERC20 token contract for a given spot product.
    """

    def get_token_contract_for_product(self, product_id: int) -> Contract:
        """
        Retrieves the associated ERC20 token contract for a given spot product.

        Args:
            product_id (int): The identifier for the spot product.

        Returns:
            Contract: The associated ERC20 token contract for the specified spot product.

        Raises:
            InvalidProductId: If the provided product ID is not valid.
        """
        return self.context.contracts.get_token_contract_for_product(product_id)
