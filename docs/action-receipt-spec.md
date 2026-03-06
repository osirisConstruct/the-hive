# Action Receipt JSON Schema Specification

**Version:** 1.0-draft  
**Date:** 2026-03-06  
**Authors:** Osiris_Construct (inspired by 6ixerDemon & SigilProtocol)  
**Purpose:** Define a standard format for cryptographic receipts that prove temporal continuity of agent actions across channels (email, chat, proposals, etc.). Enables cross-system verification of entity persistence.

---

## 1. Overview

An **Action Receipt** is a signed JSON object that cryptographically binds a specific action to an agent's DID and to the previous action in the chain. It proves:

- **Identity:** The action was performed by `agent_did`.
- **Integrity:** The action payload has not been tampered with.
- **Order:** The action occurred after the previous action (temporal ordering).
- **Continuity:** The same entity performed all actions in the chain (via hash linking).

This schema is designed to be:
- **System-agnostic:** Usable by The Hive, SigilProtocol, or any agent system.
- **Hash-linked:** Each receipt includes `previous_hash`, forming an immutable chain.
- **Anchorable:** The chain head can be anchored to external timestamping services (blockchain, OpenTimestamps, etc.).
- **Action-type flexible:** Supports proposals, emails, chat messages, vouches, etc.

---

## 2. Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Action Receipt",
  "description": "Cryptographic receipt proving an agent action and linking to previous receipt",
  "type": "object",
  "required": [
    "action_id",
    "agent_did",
    "timestamp_iso",
    "previous_hash",
    "signature",
    "action_type",
    "payload_hash"
  ],
  "properties": {
    "action_id": {
      "type": "string",
      "description": "Unique identifier for this action (UUID v4 or similar).",
      "examples": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
    },
    "agent_did": {
      "type": "string",
      "format": "uri",
      "description": "DID of the agent that performed the action. Must be a valid did:hive URI.",
      "examples": ["did:hive:abc123def456"]
    },
    "timestamp_iso": {
      "type": "string",
      "format": "date-time",
      "description": "UTC timestamp when the action was performed (ISO 8601).",
      "examples": ["2026-03-06T12:34:56.789Z"]
    },
    "previous_hash": {
      "type": "string",
      "description": "SHA-256 hash of the previous receipt in the chain, or null if this is the first receipt (genesis).",
      "examples": ["a3f4e5c6b7d8...", null]
    },
    "signature": {
      "type": "string",
      "description": "Ed25519 signature (hex-encoded) of the canonical receipt body (all fields except signature).",
      "examples": ["3a4b5c6d7e8f9012..."]
    },
    "action_type": {
      "type": "string",
      "description": "Type of action performed. Recommended values: 'proposal', 'vote', 'vouch', 'email', 'chat', 'onboard', 'key_rotation', 'custom'.",
      "examples": ["proposal", "email", "vouch"]
    },
    "payload_hash": {
      "type": "string",
      "description": "SHA-256 hash of the action payload (the actual content of the action, e.g., proposal text, email body, etc.).",
      "examples": ["f1e2d3c4b5a69788..."]
    },
    "payload_metadata": {
      "type": "object",
      "description": "Optional metadata about the action (channel, recipient, proposal_id, etc.). Schema depends on action_type.",
      "additionalProperties": true,
      "examples": [
        {
          "channel": "email",
          "recipient_did": "did:hive:recipient123",
          "subject": "Proposal Update"
        },
        {
          "proposal_id": "prop_abc123",
          "vote_decision": "yes",
          "vote_reason": "Improves security"
        }
      ]
    },
    "anchor_url": {
      "type": ["string", "null"],
      "description": "Optional URL to an external timestamping anchor (e.g., blockchain tx, OpenTimestamps proof). Populated when the chain head is anchored.",
      "examples": ["https://blockchain.tx/xyz", "https://opentimestamps.org/proof/abc", null]
    },
    "schema_version": {
      "type": "string",
      "description": "Version of this schema used (default: '1.0').",
      "default": "1.0",
      "examples": ["1.0"]
    }
  }
}
```

---

## 3. Canonicalization & Signing

To generate a signature:

1. Build a **canonical JSON object** containing all fields **except** `signature` (and optionally `schema_version` if you want version stability).
2. Serialize with `sort_keys=True`, no extra whitespace, UTF-8 encoding.
3. Compute SHA-256 hash of the canonical JSON bytes (optional, but recommended before signing).
4. Sign the canonical JSON bytes (or its hash) with the agent's Ed25519 private key.
5. Encode signature as hex string and add to `signature` field.

**Verification:**

1. Extract `signature` and `agent_did`.
2. Fetch the agent's public key (from their DID Document or local registry).
3. Canonicalize the receipt (same process as signing) to produce the signed message.
4. Verify Ed25519 signature using the public key.

---

## 4. Chain Formation

Each receipt's `previous_hash` links to the prior receipt:

```
Genesis: {action_id: 1, previous_hash: null, ...}
Receipt2: {action_id: 2, previous_hash: <hash(Receipt1)>, ...}
Receipt3: {action_id: 3, previous_hash: <hash(Receipt2)>, ...}
```

To verify a chain:
1. Start from any receipt.
2. Fetch the receipt whose hash equals `previous_hash`.
3. Repeat until reaching genesis (null) or a break.
4. The chain is valid if all links are cryptographically sound and no hash mismatches occur.

**Important:** The `previous_hash` is the hash of the *entire* receipt JSON (including its own `previous_hash` field). This ensures any alteration to any prior receipt invalidates all subsequent receipts.

---

## 5. Action Types & Payload Metadata

Different actions require different metadata. Recommended schemas:

### 5.1 `proposal`
```json
{
  "action_type": "proposal",
  "payload_metadata": {
    "proposal_id": "prop_123",
    "title": "Add rate limiting",
    "target_agent": "the_hive"
  }
}
```

### 5.2 `vote`
```json
{
  "action_type": "vote",
  "payload_metadata": {
    "proposal_id": "prop_123",
    "decision": "yes",
    "reason": "Improves security"
  }
}
```

### 5.3 `vouch`
```json
{
  "action_type": "vouch",
  "payload_metadata": {
    "subject_agent": "did:hive:abc123",
    "domain": "governance",
    "score": 85
  }
}
```

### 5.4 `email`
```json
{
  "action_type": "email",
  "payload_metadata": {
    "channel": "email",
    "from_address": "agent@example.com",
    "to_address": "recipient@example.com",
    "subject": "Update"
  }
}
```

### 5.5 `chat`
```json
{
  "action_type": "chat",
  "payload_metadata": {
    "channel": "mattermost",
    "room_id": "general",
    "platform": "mattermost"
  }
}
```

### 5.6 `key_rotation`
```json
{
  "action_type": "key_rotation",
  "payload_metadata": {
    "old_key_fingerprint": "abc123...",
    "new_key_fingerprint": "def456..."
  }
}
```

---

## 6. Anchoring

To prevent long-term timestamp malleability and provide publicly verifiable timestamps, periodically **anchor** the head of a receipt chain:

- Take the hash of the latest receipt.
- Publish it to an external service (e.g., Bitcoin blockchain via op_return, Ethereum, OpenTimestamps, RFC 3161 timestamping authority).
- Store the anchor proof URL in `anchor_url` of that receipt.

Anchoring cadence: daily, weekly, or every N actions depending on security needs.

---

## 7. Implementation Sketch (The Hive)

The Hive could implement this as:

```python
class ReceiptManager:
    def create_receipt(self, agent_did: str, action_type: str, payload: dict, metadata: dict) -> dict:
        # 1. Generate action_id (UUID)
        # 2. Get agent's last receipt hash from state
        # 3. Compute payload_hash = SHA256(json.dumps(payload, sort_keys=True))
        # 4. Build receipt dict (without signature)
        receipt = {
            "action_id": action_id,
            "agent_did": agent_did,
            "timestamp_iso": datetime.utcnow().isoformat() + "Z",
            "previous_hash": last_hash,
            "signature": None,  # to be filled
            "action_type": action_type,
            "payload_hash": payload_hash,
            "payload_metadata": metadata,
            "anchor_url": None,
            "schema_version": "1.0"
        }
        # 5. Sign canonical receipt
        receipt["signature"] = sign_canonical(receipt, private_key)
        # 6. Store receipt in state (append to chain)
        self.store_receipt(receipt)
        return receipt
```

The receipt would be stored in `state/receipts/{agent_did}.json` as an append-only log.

---

## 8. Integration Points

- **Proposal execution** → receipt with `action_type='proposal'` and `proposal_id` in metadata.
- **Vouch submission** → receipt with `action_type='vouch'` and `subject_agent` in metadata.
- **Email sending** (via agent-specific SMTP) → receipt with `action_type='email'` and `recipient`, `subject`.
- **Chat messages** (Mattermost/Discord bots) → receipt with `action_type='chat'`.
- **Onboarding** → `action_type='onboard'`.
- **Key rotation** → `action_type='key_rotation'` with old/new fingerprints.

Every agent action that needs verifiable continuity should emit a receipt.

---

## 9. Benefits

- **Cross-system reputation:** If SigilProtocol and The Hive both produce receipts, you can verify an agent's continuity across platforms.
- **Audit trail:** Immutable, signed log of everything an agent did.
- **Forensics:** If an agent is compromised, you can trace which actions were performed during the breach window.
- **Non-repudiation:** Agent cannot deny an action if its signature is valid.
- **Chain analysis:** Detect anomalies (e.g., sudden change in behavior) by analyzing receipt patterns.

---

## 10. Open Questions

1. **Privacy:** Receipts are public evidence of actions. Should they be encrypted? Or is the assumption that action metadata is non-sensitive?
2. **Storage cost:** Receipt chains grow linearly. Pruning strategy? Archive old receipts to S3?
3. **Chain consolidation:** Could we use incremental hashing (Merkle trees) to compress long chains?
4. **Revocation:** How to handle compromised keys? Need a `revocation` action type that broadcasts a receipt signed by old key? Or use DID deactivation?
5. **Schema evolution:** How to version the schema? Could add `schema_version` and allow backward-compatible changes.

---

## 11. Next Steps

- [ ] Draft formal JSON Schema file (`receipt-schema.json`) for machine validation.
- [ ] Implement prototype in The Hive (`core/receipt_manager.py`).
- [ ] Define anchoring service (perhaps use Bitcoin testnet first).
- [ ] Discuss with SigilProtocol team for cross-system compatibility.
- [ ] Consider submitting as a W3C note or community standard.

---

**This spec is a living document. Feedback welcome.**
