from nado_protocol.client.apis.rewards.execute import RewardsExecuteAPI
from nado_protocol.client.apis.rewards.query import RewardsQueryAPI


class RewardsAPI(RewardsExecuteAPI, RewardsQueryAPI):
    pass
