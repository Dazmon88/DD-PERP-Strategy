from typing import Optional
from nado_protocol.client.apis.spot.base import BaseSpotAPI
from nado_protocol.engine_client.types.query import MaxWithdrawableData
from nado_protocol.utils.math import from_pow_10


class SpotQueryAPI(BaseSpotAPI):
    """
    Class providing querying operations for the spot market in the Nado Protocol.

    This class allows for retrieval of various kinds of information related to spot products,
    such as getting wallet token balance of a given spot product.

    Inheritance:
        BaseSpotAPI: Base class for Spot operations. Inherits connectivity context and base functionalities.
    """

    def get_max_withdrawable(
        self, product_id: int, sender: str, spot_leverage: Optional[bool] = None
    ) -> MaxWithdrawableData:
        """
        Retrieves the estimated maximum withdrawable amount for a provided spot product.

        Args:
            product_id (int): The identifier for the spot product.

            sender (str): The address and subaccount identifier in a bytes32 hex string.

            spot_leverage (Optional[bool]): If False, calculates max amount without considering leverage. Defaults to True.

        Returns:
            MaxWithdrawableData: The maximum withdrawable amount for the spot product.
        """
        return self.context.engine_client.get_max_withdrawable(
            product_id, sender, spot_leverage
        )

    def get_token_wallet_balance(self, product_id: int, address: str) -> float:
        """
        Retrieves the balance of a specific token in the user's wallet (i.e. not in a Nado subaccount)

        Args:
            product_id (int): Identifier for the spot product.

            address (str): User's wallet address.

        Returns:
            float: The balance of the token in the user's wallet in decimal form.

        Raises:
            InvalidProductId: If the provided product ID is not valid.
        """
        token = self.get_token_contract_for_product(product_id)
        decimals = token.functions.decimals().call()
        return from_pow_10(token.functions.balanceOf(address).call(), decimals)

    def get_token_allowance(self, product_id: int, address: str) -> float:
        """
        Retrieves the current token allowance of a specified spot product.

        Args:
            product_id (int): Identifier for the spot product.

            address (str): The user's wallet address.

        Returns:
            float: The current token allowance of the user's wallet address to the associated spot product.

        Raises:
            InvalidProductId: If the provided product ID is not valid.
        """
        token = self.get_token_contract_for_product(product_id)
        decimals = token.functions.decimals().call()
        return from_pow_10(
            token.functions.allowance(
                address, self.context.contracts.endpoint.address
            ).call(),
            decimals,
        )
