from typing import Optional
from nado_protocol.client.context import NadoClientContext
from nado_protocol.utils.exceptions import MissingSignerException
from eth_account.signers.local import LocalAccount


class NadoBaseAPI:
    """
    The base class for all Nado API classes, providing the foundation for API-specific classes in the Nado client.

    NadoBaseAPI serves as a foundation for the hierarchical structure of the Nado API classes. This structure allows for better
    organization and separation of concerns, with each API-specific subclass handling a different aspect of the Nado client's functionality.

    Attributes:
        context (NadoClientContext): The context in which the API operates, providing access to the client's state and services.

    Note:
        This class is not meant to be used directly. It provides base functionality for other API classes in the Nado client.
    """

    context: NadoClientContext

    def __init__(self, context: NadoClientContext):
        """
        Initialize an instance of NadoBaseAPI.

        NadoBaseAPI requires a context during instantiation, which should be an instance of NadoClientContext. This context
        provides access to the state and services of the Nado client and allows the API to interact with these.

        Args:
            context (NadoClientContext): The context in which this API operates. Provides access to the state and services
            of the Nado client.
        """
        self.context = context

    def _get_signer(self, signer: Optional[LocalAccount]) -> LocalAccount:
        signer = signer if signer else self.context.signer
        if not signer:
            raise MissingSignerException(
                "A signer must be provided or set via the context."
            )
        return signer
