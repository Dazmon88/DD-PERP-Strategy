from nado_protocol.client.apis.base import NadoBaseAPI


class RewardsQueryAPI(NadoBaseAPI):
    # TODO: revise once staking contract is deployed
    def get_claim_and_stake_estimated_tokens(self, wallet: str) -> int:
        """
        Estimates the amount of USDC -> TOKEN swap when claiming + staking USDC rewards
        """
        assert self.context.contracts.staking is not None
        return self.context.contracts.staking.functions.getEstimatedTokensToStake(
            wallet
        ).call()
