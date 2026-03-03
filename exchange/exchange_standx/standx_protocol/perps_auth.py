"""
StandX Perps Authentication Module
"""
import base64
import json
import time
from typing import Literal, Optional, Dict, Any, Callable
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base58
import requests


Chain = Literal["bsc", "solana"]


class SignedData:
    """Signed data structure from prepare-signin response"""
    def __init__(self, data: Dict[str, Any]):
        self.domain = data.get("domain")
        self.uri = data.get("uri")
        self.statement = data.get("statement")
        self.version = data.get("version")
        self.chain_id = data.get("chainId")
        self.nonce = data.get("nonce")
        self.address = data.get("address")
        self.request_id = data.get("requestId")
        self.issued_at = data.get("issuedAt")
        self.message = data.get("message")
        self.exp = data.get("exp")
        self.iat = data.get("iat")


class LoginResponse:
    """Login response structure"""
    def __init__(self, data: Dict[str, Any]):
        self.token = data.get("token")
        self.address = data.get("address")
        self.alias = data.get("alias")
        self.chain = data.get("chain")
        self.perps_alpha = data.get("perpsAlpha", False)


class StandXAuth:
    """StandX Authentication Client"""
    
    def __init__(self, private_key: Optional[bytes] = None):
        """
        Initialize StandXAuth instance.
        
        Args:
            private_key: Optional 32-byte private key. If None, generates a new key pair.
        """
        if private_key:
            if len(private_key) != 32:
                raise ValueError("Private key must be 32 bytes")
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        else:
            self._private_key = ed25519.Ed25519PrivateKey.generate()
        
        self._public_key = self._private_key.public_key()
        self._public_key_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        self.request_id = base58.b58encode(self._public_key_bytes).decode('utf-8')
        self.base_url = "https://api.standx.com"
    
    def authenticate(
        self,
        chain: Chain,
        wallet_address: str,
        sign_message: Callable[[str], str]
    ) -> LoginResponse:
        """
        Authenticate with StandX API.
        
        Args:
            chain: Chain type ("bsc" or "solana")
            wallet_address: Wallet address
            sign_message: Async function that signs a message and returns signature string
            
        Returns:
            LoginResponse object with token and user info
        """
        signed_data_jwt = self.prepare_signin(chain, wallet_address)
        payload = self._parse_jwt(signed_data_jwt)
        signed_data = SignedData(payload)
        
        # Check expiration
        if signed_data.exp and signed_data.exp < time.time():
            raise ValueError("Signed data has expired")
        
        signature = sign_message(signed_data.message)
        return self.login(chain, signature, signed_data_jwt)
    
    def prepare_signin(self, chain: Chain, address: str) -> str:
        """
        Prepare sign-in request.
        
        Args:
            chain: Chain type ("bsc" or "solana")
            address: Wallet address
            
        Returns:
            JWT token string (signedData)
        """
        url = f"{self.base_url}/v1/offchain/prepare-signin?chain={chain}"
        data = {
            "address": address,
            "requestId": self.request_id
        }
        
        response = requests.post(
            url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=2.0
        )
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        result = response.json()
        if not result.get("success"):
            raise ValueError(f"Failed to prepare sign-in: {result.get('message', 'Unknown error')}")
        
        signed_data = result.get("signedData")
        if not signed_data:
            raise ValueError("Missing signedData in response")
        
        return signed_data
    
    def login(
        self,
        chain: Chain,
        signature: str,
        signed_data: str,
        expires_seconds: int = 604800
    ) -> LoginResponse:
        """
        Login with signature.
        
        Args:
            chain: Chain type ("bsc" or "solana")
            signature: Message signature from wallet
            signed_data: JWT token from prepare_signin
            expires_seconds: Token expiration time in seconds (default: 7 days)
            
        Returns:
            LoginResponse object
        """
        url = f"{self.base_url}/v1/offchain/login?chain={chain}"
        data = {
            "signature": signature,
            "signedData": signed_data,
            "expiresSeconds": expires_seconds
        }
        
        response = requests.post(
            url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=2.0
        )
        
        if not response.ok:
            raise ValueError(f"HTTP {response.status_code}: {response.text}")
        
        result = response.json()
        return LoginResponse(result)
    
    def sign_request(
        self,
        payload: str,
        request_id: str,
        timestamp: int
    ) -> Dict[str, str]:
        """
        Sign a request with ed25519 private key.
        
        Args:
            payload: Request payload as JSON string
            request_id: Request ID
            timestamp: Timestamp in seconds
            
        Returns:
            Dictionary with signature headers
        """
        version = "v1"
        message = f"{version},{request_id},{timestamp},{payload}"
        message_bytes = message.encode('utf-8')
        
        signature = self._private_key.sign(message_bytes)
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        return {
            "x-request-sign-version": version,
            "x-request-id": request_id,
            "x-request-timestamp": str(timestamp),
            "x-request-signature": signature_b64
        }
    
    def _parse_jwt(self, token: str) -> Dict[str, Any]:
        """
        Parse JWT token and return payload.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload as dictionary
        """
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        # Decode base64url
        base64_url = parts[1]
        base64_str = base64_url.replace('-', '+').replace('_', '/')
        # Add padding if needed
        padding = len(base64_str) % 4
        if padding:
            base64_str += '=' * (4 - padding)
        
        decoded = base64.b64decode(base64_str)
        return json.loads(decoded.decode('utf-8'))
    
    def export_private_key(self) -> bytes:
        """Export private key as bytes"""
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    @classmethod
    def from_private_key(cls, private_key: bytes) -> 'StandXAuth':
        """Create StandXAuth instance from private key bytes"""
        return cls(private_key=private_key)
