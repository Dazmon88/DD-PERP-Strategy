from typing import Optional
from nado_protocol.contracts.types import (
    ClaimFoundationRewardsContractParams,
    ClaimFoundationRewardsProofStruct,
    ClaimTokensContractParams,
    ClaimTokensParams,
)
from nado_protocol.client.apis.base import NadoBaseAPI
from eth_account.signers.local import LocalAccount

from nado_protocol.utils.exceptions import InvalidTokenClaimParams


class RewardsExecuteAPI(NadoBaseAPI):
    def _validate_claim_params(self, params: ClaimTokensParams):
        p = ClaimTokensParams.parse_obj(params)
        if p.amount is None and p.claim_all is None:
            raise InvalidTokenClaimParams()

    def claim(
        self, params: ClaimTokensParams, signer: Optional[LocalAccount] = None
    ) -> str:
        self._validate_claim_params(params)
        signer = self._get_signer(signer)
        claim_params = self._get_claim_tokens_contract_params(params, signer)
        return self.context.contracts.claim(
            claim_params.epoch,
            claim_params.amount_to_claim,
            claim_params.total_claimable_amount,
            claim_params.merkle_proof,
            signer,
        )

    def claim_and_stake(
        self, params: ClaimTokensParams, signer: Optional[LocalAccount] = None
    ) -> str:
        self._validate_claim_params(params)
        signer = self._get_signer(signer)
        claim_params = self._get_claim_tokens_contract_params(params, signer)
        return self.context.contracts.claim_and_stake(
            claim_params.epoch,
            claim_params.amount_to_claim,
            claim_params.total_claimable_amount,
            claim_params.merkle_proof,
            signer,
        )

    def stake(self, amount: int, signer: Optional[LocalAccount] = None) -> str:
        signer = self._get_signer(signer)
        return self.context.contracts.stake(amount, signer)

    def unstake(self, amount: int, signer: Optional[LocalAccount] = None) -> str:
        signer = self._get_signer(signer)
        return self.context.contracts.unstake(amount, signer)

    def withdraw_unstaked(self, signer: Optional[LocalAccount] = None):
        signer = self._get_signer(signer)
        return self.context.contracts.withdraw_unstaked(signer)

    def claim_usdc_rewards(self, signer: Optional[LocalAccount] = None):
        signer = self._get_signer(signer)
        return self.context.contracts.claim_usdc_rewards(signer)

    def claim_and_stake_usdc_rewards(self, signer: Optional[LocalAccount] = None):
        signer = self._get_signer(signer)
        return self.context.contracts.claim_and_stake_usdc_rewards(signer)

    def claim_foundation_rewards(self, signer: Optional[LocalAccount] = None):
        """
        Claims all available foundation rewards. Foundation rewards are tokens associated with the chain. For example, ARB on Arbitrum.
        """
        signer = self._get_signer(signer)
        claim_params = self._get_claim_foundation_rewards_contract_params(signer)
        return self.context.contracts.claim_foundation_rewards(
            claim_params.claim_proofs, signer
        )

    def _get_claim_tokens_contract_params(
        self, params: ClaimTokensParams, signer: LocalAccount
    ) -> ClaimTokensContractParams:
        raise NotImplementedError(
            "Token merkle proofs endpoint has been removed from the indexer. "
            "This functionality is no longer available."
        )

    def _get_claim_foundation_rewards_contract_params(
        self, signer: LocalAccount
    ) -> ClaimFoundationRewardsContractParams:
        raise NotImplementedError(
            "Foundation rewards merkle proofs endpoint has been removed from the indexer. "
            "This functionality is no longer available."
        )
