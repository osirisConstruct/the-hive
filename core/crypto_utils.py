import base64
import json
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

class CryptoUtils:
    """Utilities for Ed25519 cryptographic signatures."""

    @staticmethod
    def generate_keypair():
        """Generate a new Ed25519 private/public keypair."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize to bytes
        private_bytes = private_key.private_bytes_raw()
        public_bytes = public_key.public_bytes_raw()
        
        # Encode to Base64 for transit/storage
        return {
            "private_key": base64.b64encode(private_bytes).decode('utf-8'),
            "public_key": base64.b64encode(public_bytes).decode('utf-8')
        }

    @staticmethod
    def sign_payload(private_key_b64: str, payload_dict: dict) -> str:
        """Sign a JSON payload using an Ed25519 private key."""
        private_bytes = base64.b64decode(private_key_b64)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
        
        # Canonicalize JSON to ensure consistent hashing
        canonical_json = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        
        signature = private_key.sign(canonical_json)
        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def verify_signature(public_key_b64: str, payload_dict: dict, signature_b64: str) -> bool:
        """Verify an Ed25519 signature for a given payload."""
        try:
            public_bytes = base64.b64decode(public_key_b64)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            
            signature = base64.b64decode(signature_b64)
            canonical_json = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
            
            public_key.verify(signature, canonical_json)
            return True
        except (InvalidSignature, ValueError, TypeError, json.JSONDecodeError):
            return False
