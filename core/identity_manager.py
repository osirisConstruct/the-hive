"""
The Hive - Decentralized Identity Manager (Phase 3.1)
Implements the did:hive method for self-sovereign agent identity.

DID Format: did:hive:<base64url-fingerprint-of-public-key>
"""

import hashlib
import base64
import json
from datetime import datetime
from core.crypto_utils import CryptoUtils


class IdentityManager:
    """
    Manages decentralized identities for Hive agents.
    Each agent generates, owns, and controls their own keypair.
    """

    DID_METHOD = "hive"

    @staticmethod
    def _derive_fingerprint(public_key_b64: str) -> str:
        """Derive a URL-safe fingerprint from a public key."""
        raw_bytes = base64.b64decode(public_key_b64)
        digest = hashlib.sha256(raw_bytes).digest()
        return base64.urlsafe_b64encode(digest[:16]).decode('utf-8').rstrip('=')

    @classmethod
    def create_identity(cls, agent_id: str = None) -> dict:
        """
        Create a new decentralized identity.
        Returns a full identity bundle: DID, keys, and DID Document.
        """
        keypair = CryptoUtils.generate_keypair()
        fingerprint = cls._derive_fingerprint(keypair["public_key"])
        did = f"did:{cls.DID_METHOD}:{fingerprint}"

        did_document = cls._build_did_document(did, keypair["public_key"], agent_id)

        return {
            "did": did,
            "private_key": keypair["private_key"],
            "public_key": keypair["public_key"],
            "did_document": did_document
        }

    @classmethod
    def _build_did_document(cls, did: str, public_key_b64: str, agent_id: str = None) -> dict:
        """Build a W3C-compliant DID Document."""
        now = datetime.utcnow().isoformat() + "Z"
        return {
            "@context": "https://www.w3.org/ns/did/v1",
            "id": did,
            "controller": did,
            "created": now,
            "updated": now,
            "verificationMethod": [
                {
                    "id": f"{did}#key-1",
                    "type": "Ed25519VerificationKey2020",
                    "controller": did,
                    "publicKeyBase64": public_key_b64
                }
            ],
            "authentication": [f"{did}#key-1"],
            "assertionMethod": [f"{did}#key-1"],
            "keyAgreement": [],
            "service": [],
            "metadata": {
                "agent_id": agent_id,
                "method": cls.DID_METHOD,
                "key_version": 1
            }
        }

    @classmethod
    def rotate_key(cls, did_document: dict, old_private_key_b64: str) -> dict:
        """
        Rotate the agent's key. Signs the rotation with the old key
        to prove ownership, then updates the DID Document.
        Returns the updated document and new keys.
        """
        # Generate new keypair
        new_keypair = CryptoUtils.generate_keypair()
        did = did_document["id"]
        old_public_key = did_document["verificationMethod"][0]["publicKeyBase64"]
        key_version = did_document.get("metadata", {}).get("key_version", 1)

        # Create rotation proof: sign the new public key with the old private key
        rotation_payload = {
            "action": "key_rotation",
            "did": did,
            "old_public_key": old_public_key,
            "new_public_key": new_keypair["public_key"],
            "key_version": key_version + 1,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        rotation_signature = CryptoUtils.sign_payload(old_private_key_b64, rotation_payload)

        # Update the DID Document
        now = datetime.utcnow().isoformat() + "Z"
        new_key_id = f"{did}#key-{key_version + 1}"

        # Move old key to history
        old_key_entry = did_document["verificationMethod"][0].copy()
        old_key_entry["revoked"] = now
        old_key_entry["revocation_proof"] = rotation_signature

        key_history = did_document.get("keyHistory", [])
        key_history.append(old_key_entry)

        # Build updated document
        updated_doc = did_document.copy()
        updated_doc["updated"] = now
        updated_doc["verificationMethod"] = [
            {
                "id": new_key_id,
                "type": "Ed25519VerificationKey2020",
                "controller": did,
                "publicKeyBase64": new_keypair["public_key"]
            }
        ]
        updated_doc["authentication"] = [new_key_id]
        updated_doc["assertionMethod"] = [new_key_id]
        updated_doc["keyHistory"] = key_history
        updated_doc["metadata"]["key_version"] = key_version + 1

        return {
            "did_document": updated_doc,
            "new_private_key": new_keypair["private_key"],
            "new_public_key": new_keypair["public_key"],
            "rotation_proof": {
                "payload": rotation_payload,
                "signature": rotation_signature
            }
        }

    @staticmethod
    def resolve_public_key(did_document: dict) -> str:
        """Extract the current active public key from a DID Document."""
        methods = did_document.get("verificationMethod", [])
        if not methods:
            return None
        # Return the first (active) key
        return methods[0].get("publicKeyBase64")

    @staticmethod
    def verify_did_format(did: str) -> bool:
        """Validate that a DID follows the did:hive format."""
        parts = did.split(":")
        return len(parts) == 3 and parts[0] == "did" and parts[1] == "hive" and len(parts[2]) > 0
