import os
from dotenv import load_dotenv
from nado_protocol.client import NadoClientMode, client_mode_to_setup

load_dotenv()

CLIENT_MODE: NadoClientMode = os.getenv("CLIENT_MODE")
SIGNER_PRIVATE_KEY = os.getenv("SIGNER_PRIVATE_KEY")
LINKED_SIGNER_PRIVATE_KEY = os.getenv("LINKED_SIGNER_PRIVATE_KEY")

assert CLIENT_MODE, "CLIENT_MODE not set! set via .env file"
assert SIGNER_PRIVATE_KEY, "SIGNER_PRIVATE_KEY not set! set via .env file"

(
    ENGINE_BACKEND_URL,
    INDEXER_BACKEND_URL,
    TRIGGER_BACKEND_URL,
    NETWORK,
) = client_mode_to_setup(CLIENT_MODE)
