from nado_protocol.engine_client.types.execute import SignatureParams


class StreamAuthenticationParams(SignatureParams):
    sender: str
    expiration: int
