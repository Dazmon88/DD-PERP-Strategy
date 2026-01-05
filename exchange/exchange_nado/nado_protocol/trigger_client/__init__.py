from nado_protocol.trigger_client.types import TriggerClientOpts
from nado_protocol.trigger_client.execute import TriggerExecuteClient
from nado_protocol.trigger_client.query import TriggerQueryClient


class TriggerClient(TriggerQueryClient, TriggerExecuteClient):  # type: ignore
    def __init__(self, opts: TriggerClientOpts):
        TriggerQueryClient.__init__(self, opts)
        TriggerExecuteClient.__init__(self, opts)


__all__ = [
    "TriggerClient",
    "TriggerClientOpts",
    "TriggerExecuteClient",
    "TriggerQueryClient",
]
