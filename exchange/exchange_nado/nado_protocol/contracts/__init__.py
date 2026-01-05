import os
from typing import Optional
from pydantic import BaseModel
from web3 import Web3
from web3.types import TxParams
from web3.contract import Contract
from web3.contract.contract import ContractFunction
from eth_account.signers.local import LocalAccount
from nado_protocol.contracts.loader import load_abi
from nado_protocol.contracts.types import DepositCollateralParams, NadoAbiName
from nado_protocol.utils.bytes32 import (
    hex_to_bytes32,
    str_to_hex,
    subaccount_name_to_bytes12,
    zero_address,
)
from nado_protocol.utils.exceptions import InvalidProductId
from nado_protocol.contracts.types import *


class NadoContractsContext(BaseModel):
    """
    Holds the context for various Nado contracts.

    Attributes:
        endpoint_addr (str): The endpoint address.

        querier_addr (str): The querier address.

        spot_engine_addr (Optional[str]): The spot engine address. This may be None.

        perp_engine_addr (Optional[str]): The perp engine address. This may be None.

        clearinghouse_addr (Optional[str]): The clearinghouse address. This may be None.

        airdrop_addr (Optional[str]): The airdrop address. This may be None.

        staking_addr (Optional[str]): The staking address. This may be None.

        foundation_rewards_airdrop_addr (Optional[str]): The Foundation Rewards airdrop address of the corresponding chain (e.g: Ink airdrop for Ink). This may be None.
    """

    network: Optional[NadoNetwork]
    endpoint_addr: str
    querier_addr: str
    spot_engine_addr: Optional[str]
    perp_engine_addr: Optional[str]
    clearinghouse_addr: Optional[str]
    airdrop_addr: Optional[str]
    staking_addr: Optional[str]
    foundation_rewards_airdrop_addr: Optional[str]


class NadoContracts:
    """
    Encapsulates the set of Nado contracts required for querying and executing.
    """

    w3: Web3
    network: Optional[NadoNetwork]
    contracts_context: NadoContractsContext
    querier: Contract
    endpoint: Contract
    clearinghouse: Optional[Contract]
    spot_engine: Optional[Contract]
    perp_engine: Optional[Contract]
    airdrop: Optional[Contract]
    staking: Optional[Contract]
    foundation_rewards_airdrop: Optional[Contract]

    def __init__(self, node_url: str, contracts_context: NadoContractsContext):
        """
        Initialize a NadoContracts instance.

        This will set up the Web3 instance and contract addresses for querying and executing the Nado contracts.
        It will also load and parse the ABI for the given contracts.

        Args:
            node_url (str): The Ethereum node URL.

            contracts_context (NadoContractsContext): The Nado contracts context, holding the relevant addresses.
        """
        self.network = contracts_context.network
        self.w3 = Web3(Web3.HTTPProvider(node_url))

        self.contracts_context = NadoContractsContext.parse_obj(contracts_context)
        self.querier: Contract = self.w3.eth.contract(
            address=contracts_context.querier_addr, abi=load_abi(NadoAbiName.FQUERIER)  # type: ignore
        )
        self.endpoint: Contract = self.w3.eth.contract(
            address=self.contracts_context.endpoint_addr,
            abi=load_abi(NadoAbiName.ENDPOINT),  # type: ignore
        )
        self.clearinghouse = None
        self.spot_engine = None
        self.perp_engine = None

        if self.contracts_context.clearinghouse_addr:
            self.clearinghouse: Contract = self.w3.eth.contract(
                address=self.contracts_context.clearinghouse_addr,
                abi=load_abi(NadoAbiName.ICLEARINGHOUSE),  # type: ignore
            )

        if self.contracts_context.spot_engine_addr:
            self.spot_engine: Contract = self.w3.eth.contract(
                address=self.contracts_context.spot_engine_addr,
                abi=load_abi(NadoAbiName.ISPOT_ENGINE),  # type: ignore
            )

        if self.contracts_context.perp_engine_addr:
            self.perp_engine: Contract = self.w3.eth.contract(
                address=self.contracts_context.perp_engine_addr,
                abi=load_abi(NadoAbiName.IPERP_ENGINE),  # type: ignore
            )

        if self.contracts_context.staking_addr:
            self.staking: Contract = self.w3.eth.contract(
                address=self.contracts_context.staking_addr,
                abi=load_abi(NadoAbiName.ISTAKING),  # type: ignore
            )

        if self.contracts_context.airdrop_addr:
            self.airdrop: Contract = self.w3.eth.contract(
                address=self.contracts_context.airdrop_addr,
                abi=load_abi(NadoAbiName.IAIRDROP),  # type: ignore
            )

        if self.contracts_context.foundation_rewards_airdrop_addr:
            self.foundation_rewards_airdrop: Contract = self.w3.eth.contract(
                address=self.contracts_context.foundation_rewards_airdrop_addr,
                abi=load_abi(NadoAbiName.IFOUNDATION_REWARDS_AIRDROP),  # type: ignore
            )

    def deposit_collateral(
        self, params: DepositCollateralParams, signer: LocalAccount
    ) -> str:
        """
        Deposits a specified amount of collateral into a spot product.

        Args:
            params (DepositCollateralParams): The parameters for depositing collateral.

            signer (LocalAccount): The account that will sign the deposit transaction.

        Returns:
            str: The transaction hash of the deposit operation.
        """
        params = DepositCollateralParams.parse_obj(params)
        if params.referral_code is not None and params.referral_code.strip():
            return self.execute(
                self.endpoint.functions.depositCollateralWithReferral(
                    subaccount_name_to_bytes12(params.subaccount_name),
                    params.product_id,
                    params.amount,
                    params.referral_code,
                ),
                signer,
            )
        else:
            return self.execute(
                self.endpoint.functions.depositCollateral(
                    subaccount_name_to_bytes12(params.subaccount_name),
                    params.product_id,
                    params.amount,
                ),
                signer,
            )

    def approve_allowance(
        self,
        erc20: Contract,
        amount: int,
        signer: LocalAccount,
        to: Optional[str] = None,
    ):
        """
        Approves a specified amount of allowance for the ERC20 token contract.

        Args:
            erc20 (Contract): The ERC20 token contract.

            amount (int): The amount of the ERC20 token to be approved.

            signer (LocalAccount): The account that will sign the approval transaction.

            to (Optional[str]): When specified, approves allowance to the provided contract address, otherwise it approves it to Nado's Endpoint.

        Returns:
            str: The transaction hash of the approval operation.
        """
        to = to or self.endpoint.address
        return self.execute(erc20.functions.approve(to, amount), signer)

    # TODO: revise once airdrop contract is deployed
    def claim(
        self,
        epoch: int,
        amount_to_claim: int,
        total_claimable_amount: int,
        merkle_proof: list[str],
        signer: LocalAccount,
    ) -> str:
        assert self.airdrop is not None
        return self.execute(
            self.airdrop.functions.claim(
                epoch, amount_to_claim, total_claimable_amount, merkle_proof
            ),
            signer,
        )

    # TODO: revise once airdrop contract is deployed
    def claim_and_stake(
        self,
        epoch: int,
        amount_to_claim: int,
        total_claimable_amount: int,
        merkle_proof: list[str],
        signer: LocalAccount,
    ) -> str:
        assert self.airdrop is not None
        return self.execute(
            self.airdrop.functions.claimAndStake(
                epoch, amount_to_claim, total_claimable_amount, merkle_proof
            ),
            signer,
        )

    # TODO: revise once staking contract is deployed
    def stake(
        self,
        amount: int,
        signer: LocalAccount,
    ) -> str:
        assert self.staking is not None
        return self.execute(
            self.staking.functions.stake(amount),
            signer,
        )

    # TODO: revise once staking contract is deployed
    def unstake(
        self,
        amount: int,
        signer: LocalAccount,
    ) -> str:
        assert self.staking is not None
        return self.execute(
            self.staking.functions.withdraw(amount),
            signer,
        )

    # TODO: revise once staking contract is deployed
    def withdraw_unstaked(
        self,
        signer: LocalAccount,
    ) -> str:
        assert self.staking is not None
        return self.execute(
            self.staking.functions.claim(),
            signer,
        )

    # TODO: revise once staking contract is deployed
    def claim_usdc_rewards(
        self,
        signer: LocalAccount,
    ) -> str:
        assert self.staking is not None
        return self.execute(
            self.staking.functions.claimUsdc(),
            signer,
        )

    # TODO: revise once staking contract is deployed
    def claim_and_stake_usdc_rewards(
        self,
        signer: LocalAccount,
    ) -> str:
        assert self.staking is not None
        return self.execute(
            self.staking.functions.claimUsdcAndStake(),
            signer,
        )

    # TODO: revise once foundation rewards contract is deployed
    def claim_foundation_rewards(
        self,
        claim_proofs: list[ClaimFoundationRewardsProofStruct],
        signer: LocalAccount,
    ) -> str:
        assert self.foundation_rewards_airdrop is not None
        proofs = [proof.dict() for proof in claim_proofs]
        return self.execute(
            self.foundation_rewards_airdrop.functions.claim(proofs), signer
        )

    def _mint_mock_erc20(
        self, erc20: Contract, amount: int, signer: LocalAccount
    ) -> str:
        """
        Mints a specified amount of mock ERC20 tokens for testing purposes.

        Args:
            erc20 (Contract): The contract instance of the ERC20 token to be minted.

            amount (int): The amount of tokens to mint.

            signer (LocalAccount): The account that will sign the minting transaction.

        Returns:
            str: The transaction hash of the mint operation.
        """
        return self.execute(erc20.functions.mint(signer.address, amount), signer)

    def get_token_contract_for_product(self, product_id: int) -> Contract:
        """
        Returns the ERC20 token contract for a given product.

        Args:
            product_id (int): The ID of the product for which to get the ERC20 token contract.

        Returns:
            Contract: The ERC20 token contract for the specified product.

        Raises:
            InvalidProductId: If the provided product ID is not valid.
        """
        if self.spot_engine is None:
            raise Exception("SpotEngine contract not initialized")
        product_config = self.spot_engine.functions.getConfig(product_id).call()
        token = product_config[0]
        if token == f"0x{zero_address().hex()}":
            raise InvalidProductId(f"Invalid product id provided: {product_id}")
        return self.w3.eth.contract(
            address=token,
            abi=load_abi(NadoAbiName.MOCK_ERC20),
        )

    def execute(self, func: ContractFunction, signer: LocalAccount) -> str:
        """
        Executes a smart contract function.

        This method builds a transaction for a given contract function, signs the transaction with the provided signer's private key,
        sends the raw signed transaction to the network, and waits for the transaction to be mined.

        Args:
            func (ContractFunction): The contract function to be executed.

            signer (LocalAccount): The local account object that will sign the transaction. It should contain the private key.

        Returns:
            str: The hexadecimal representation of the transaction hash.

        Raises:
            ValueError: If the transaction is invalid, the method will not catch the error.
            TimeExhausted: If the transaction receipt isn't available within the timeout limit set by the Web3 provider.
        """
        tx = func.build_transaction(self._build_tx_params(signer))
        signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=signer.key)
        signed_tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        self.w3.eth.wait_for_transaction_receipt(signed_tx_hash)
        return signed_tx_hash.hex()

    def _build_tx_params(self, signer: LocalAccount) -> TxParams:
        tx_params: TxParams = {
            "from": signer.address,
            "nonce": self.w3.eth.get_transaction_count(signer.address),
        }
        needs_gas_price = self.network is not None and self.network.value in [
            NadoNetwork.HARDHAT.value
        ]
        if needs_gas_price or os.getenv("CLIENT_MODE") in ["devnet"]:
            tx_params["gasPrice"] = self.w3.eth.gas_price
        return tx_params


__all__ = [
    "NadoContractsContext",
    "NadoContracts",
    "DepositCollateralParams",
    "NadoExecuteType",
    "NadoNetwork",
    "NadoAbiName",
    "NadoDeployment",
]
