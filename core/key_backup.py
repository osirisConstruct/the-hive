"""
The Hive - Key Backup Module
Encrypted export/import for agent identity migration
"""

import base64
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class KeyBackup:
    """
    Handles encrypted backup and restore of agent identities.
    Uses Fernet (AES-128) with PBKDF2 key derivation from password.
    """
    
    SALT = b"the_hive_key_backup_v1"
    ITERATIONS = 480000
    
    @classmethod
    def _derive_key(cls, password: str) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=cls.SALT,
            iterations=cls.ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    @classmethod
    def export_identity(
        cls,
        did: str,
        private_key: str,
        public_key: str,
        did_document: dict,
        password: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Export identity to encrypted JSON string.
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography package required: pip install cryptography")
        
        key = cls._derive_key(password)
        fernet = Fernet(key)
        
        payload = {
            "did": did,
            "private_key": private_key,
            "public_key": public_key,
            "did_document": did_document,
            "metadata": metadata or {},
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "version": 1
        }
        
        json_data = json.dumps(payload, separators=(',', ':'))
        encrypted = fernet.encrypt(json_data.encode())
        
        return base64.b64encode(encrypted).decode()
    
    @classmethod
    def import_identity(cls, backup_string: str, password: str) -> dict:
        """
        Import identity from encrypted backup string.
        Returns the identity bundle.
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography package required: pip install cryptography")
        
        try:
            encrypted = base64.b64decode(backup_string.encode())
            key = cls._derive_key(password)
            fernet = Fernet(key)
            decrypted = fernet.decrypt(encrypted)
            return json.loads(decrypted)
        except Exception as e:
            raise ValueError(f"Failed to decrypt backup. Invalid password or corrupted data: {e}")
    
    @classmethod
    def export_to_file(
        cls,
        did: str,
        private_key: str,
        public_key: str,
        did_document: dict,
        password: str,
        filepath: str,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Export identity to encrypted file.
        """
        backup = cls.export_identity(did, private_key, public_key, did_document, password, metadata)
        Path(filepath).write_text(backup, encoding='utf-8')
        return True
    
    @classmethod
    def import_from_file(cls, filepath: str, password: str) -> dict:
        """
        Import identity from encrypted file.
        """
        backup = Path(filepath).read_text(encoding='utf-8')
        return cls.import_identity(backup, password)
    
    @classmethod
    def verify_backup(cls, backup_string: str, password: str) -> bool:
        """
        Verify if backup can be decrypted with given password.
        """
        try:
            cls.import_identity(backup_string, password)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_fingerprint(public_key: str) -> str:
        """Get fingerprint from public key for filename."""
        raw_bytes = base64.b64decode(public_key)
        digest = hashlib.sha256(raw_bytes).digest()
        return base64.urlsafe_b64encode(digest[:8]).decode('utf-8').rstrip('=')


def create_backup(
    did: str,
    private_key: str,
    public_key: str,
    did_document: dict,
    password: str,
    filepath: Optional[str] = None,
    metadata: Optional[dict] = None
) -> str:
    """
    Convenience function to create a backup.
    Returns backup string. If filepath provided, also saves to file.
    """
    backup = KeyBackup.export_identity(did, private_key, public_key, did_document, password, metadata)
    
    if filepath:
        KeyBackup.export_to_file(did, private_key, public_key, did_document, password, filepath, metadata)
    
    return backup


def restore_backup(backup_string: str = None, filepath: str = None, password: str = None) -> dict:
    """
    Convenience function to restore from backup string or file.
    """
    if filepath and not backup_string:
        return KeyBackup.import_from_file(filepath, password)
    elif backup_string:
        return KeyBackup.import_identity(backup_string, password)
    else:
        raise ValueError("Provide either backup_string or filepath")


if __name__ == "__main__":
    if not CRYPTO_AVAILABLE:
        print("ERROR: cryptography not installed")
        print("Run: pip install cryptography")
        exit(1)
    
    from core.identity_manager import IdentityManager
    
    print("=== Key Backup Demo ===")
    
    identity = IdentityManager.create_identity("test_agent")
    
    print(f"Created DID: {identity['did']}")
    
    password = "super_secure_password_123"
    
    backup = KeyBackup.export_identity(
        identity['did'],
        identity['private_key'],
        identity['public_key'],
        identity['did_document'],
        password,
        metadata={"agent_id": "test_agent", "origin": "demo"}
    )
    
    print(f"\nBackup string (first 80 chars): {backup[:80]}...")
    
    restored = KeyBackup.import_identity(backup, password)
    
    print(f"\nRestored DID: {restored['did']}")
    print(f"Match: {restored['did'] == identity['did']}")
