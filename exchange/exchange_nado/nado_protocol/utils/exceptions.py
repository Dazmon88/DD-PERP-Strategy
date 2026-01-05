class ExecuteFailedException(Exception):
    """Raised when the execute status is not 'success'"""

    def __init__(self, message="Execute failed"):
        self.message = message
        super().__init__(self.message)


class QueryFailedException(Exception):
    """Raised when the query status is not 'success'"""

    def __init__(self, message="Query failed"):
        self.message = message
        super().__init__(self.message)


class BadStatusCodeException(Exception):
    """Raised when the response status code is not 200"""

    def __init__(self, message="Bad status code"):
        self.message = message
        super().__init__(self.message)


class MissingSignerException(Exception):
    """Raised when the Signer is required to perform an operation but it's not provided."""

    def __init__(self, message="Signer not provided"):
        self.message = message
        super().__init__(self.message)


class InvalidProductId(Exception):
    """Raised when product id is invalid."""

    def __init__(self, message="Invalid product id provided"):
        self.message = message
        super().__init__(self.message)


class InvalidTokenClaimParams(Exception):
    """Raised when providing invalid token claim parameters."""

    def __init__(
        self,
        message="Invalid token params. Either `amount` or `claim_all` must be provided",
    ):
        self.message = message
        super().__init__(self.message)


class MissingTriggerClient(Exception):
    def __init__(
        self,
        message="Trigger client not initialized.",
    ):
        self.message = message
        super().__init__(self.message)
