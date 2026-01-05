from typing import Optional
from nado_protocol.contracts.types import DepositCollateralParams
from eth_account.signers.local import LocalAccount
from nado_protocol.client.apis.spot.base import BaseSpotAPI
from nado_protocol.engine_client.types.execute import (
    ExecuteResponse,
    WithdrawCollateralParams,
)
from nado_protocol.utils.exceptions import MissingSignerException


class SpotExecuteAPI(BaseSpotAPI):
    """
    Class providing execution operations for the spot market in the Nado Protocol.

    This class provides functionality for executing transactions related to spot products,
    such as depositing a specified amount into a spot product.

    Inheritance:
        BaseSpotAPI: Base class for Spot operations. Inherits connectivity context and base functionalities.
    """

    def deposit(
        self, params: DepositCollateralParams, signer: Optional[LocalAccount] = None
    ) -> str:
        """
        Executes the operation of depositing a specified amount into a spot product.

        Args:
            params (DepositCollateralParams): Parameters required for depositing collateral.

            signer (LocalAccount, optional):  The account that will sign the deposit transaction. If no signer is provided, the signer set in the client context will be used.

        Raises:
            MissingSignerException: Raised when there is no signer provided and no signer set in the client context.

        Returns:
            str: The deposit collateral transaction hash.
        """
        signer = signer if signer else self.context.signer
        if not signer:
            raise MissingSignerException(
                "A signer must be provided or set via the context."
            )
        return self.context.contracts.deposit_collateral(params, signer)

    def withdraw(self, params: WithdrawCollateralParams) -> ExecuteResponse:
        """
        Executes a withdrawal for the specified spot product via the off-chain engine.

        Args:
            params (WithdrawCollateralParams): Parameters needed to execute the withdrawal.

        Returns:
            ExecuteResponse: The response from the engine execution.

        Raises:
            Exception: If there is an error during the execution or the response status is not "success".
        """
        return self.context.engine_client.withdraw_collateral(params)

    def approve_allowance(
        self, product_id: int, amount: int, signer: Optional[LocalAccount] = None
    ) -> str:
        """
        Approves an allowance for a certain amount of tokens for a spot product.

        Args:
            product_id (int): The identifier of the spot product for which to approve an allowance.

            amount (int): The amount of the tokens to be approved.

            signer (LocalAccount, optional):  The account that will sign the approval transaction. If no signer is provided, the signer set in the client context will be used.

        Returns:
            str: The approve allowance transaction hash.

        Raises:
            MissingSignerException: Raised when there is no signer provided and no signer set in the client context.
            InvalidProductId: If the provided product ID is not valid.
        """
        signer = signer if signer else self.context.signer
        if not signer:
            raise MissingSignerException(
                "A signer must be provided or set via the context."
            )
        token = self.get_token_contract_for_product(product_id)
        return self.context.contracts.approve_allowance(token, amount, signer)

    def _mint_mock_erc20(
        self, product_id: int, amount: int, signer: Optional[LocalAccount] = None
    ):
        """
        Mints a specified amount of mock ERC20 tokens for testing purposes.

        Args:
            product_id (int): The identifier for the spot product.

            amount (int): The amount of mock ERC20 tokens to mint.

            signer (LocalAccount, optional):  The account that will sign the mint transaction.
                If no signer is provided, the signer set in the client context will be used.

        Returns:
            str: The mock ERC20 mint transaction hash.

        Raises:
            MissingSignerException: Raised when there is no signer provided and no signer set in the client context.
            InvalidProductId: If the provided product ID is not valid.
        """
        signer = signer if signer else self.context.signer
        if not signer:
            raise MissingSignerException(
                "A signer must be provided or set via the context."
            )
        token = self.get_token_contract_for_product(product_id)
        return self.context.contracts._mint_mock_erc20(token, amount, signer)
