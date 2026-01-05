from sanity import CLIENT_MODE, SIGNER_PRIVATE_KEY
from nado_protocol.client import NadoClient, create_nado_client
from nado_protocol.utils.math import to_x18
from nado_protocol.contracts.types import ClaimTokensParams


def run():
    print("setting up nado client...")
    client: NadoClient = create_nado_client(CLIENT_MODE, SIGNER_PRIVATE_KEY)
    signer = client.context.signer

    print("network:", client.context.contracts.network)
    print("signer:", signer.address)

    claim_token_contract_params = client.rewards._get_claim_token_contract_params(
        ClaimTokensParams(epoch=10, amount=to_x18(100)), signer
    )

    print("claim params:", claim_token_contract_params)
    token = client.context.contracts.get_token_contract_for_product(41)
    token_balance = token.functions.balanceOf(signer.address).call()

    print("balance (pre-claim):", token_balance)

    print("claiming...")
    tx = client.rewards.claim(ClaimTokensParams(epoch=10, amount=to_x18(100)))
    print("tx:", tx)
    token_balance = token.functions.balanceOf(signer.address).call()
    print("balance (post-claim):", token_balance)

    claim_and_stake_contract_params = client.rewards._get_claim_tokens_contract_params(
        ClaimTokensParams(epoch=10, amount=to_x18(100)), signer
    )

    print("claim and stake params:", claim_and_stake_contract_params)

    print("claiming and staking tokens...")
    tx = client.rewards.claim_and_stake(ClaimTokensParams(epoch=10, amount=to_x18(100)))
    print("tx:", tx)

    token_balance = token.functions.balanceOf(signer.address).call()
    print("balance (post-claim-and-stake):", token_balance)

    print("approving allowance to staking contract...")
    tx = client.context.contracts.approve_allowance(
        token, to_x18(100), signer, to=client.context.contracts.staking.address
    )
    print("tx:", tx)

    print("staking...")
    tx = client.rewards.stake(to_x18(100))

    print("tx:", tx)

    token_balance = token.functions.balanceOf(signer.address).call()
    print("balance (post-stake):", token_balance)

    print("unstaking...")
    tx = client.rewards.unstake(to_x18(100))
    print(tx)

    print("withdrawing unstaked...")
    tx = client.rewards.withdraw_unstaked()
    print(tx)

    print("claiming usdc rewards...")
    tx = client.rewards.claim_usdc_rewards()
    print(tx)

    print("claiming and staking usdc rewards...")
    tx = client.rewards.claim_and_stake_usdc_rewards()
    print(tx)

    print(
        "claim and stake estimated tokens...",
        client.rewards.get_claim_and_stake_estimated_tokens(signer.address),
    )

    claim_foundation_rewards_contract_params = (
        client.rewards._get_claim_foundation_rewards_contract_params(signer)
    )

    print(
        "foundation rewards contract params:",
        claim_foundation_rewards_contract_params.json(indent=2),
    )

    print("claiming foundation rewards...")
    tx = client.rewards.claim_foundation_rewards()
    print(tx)
