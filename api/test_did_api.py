"""
The Hive - DID Identity API Test Suite (Phase 3.1)
Tests the full lifecycle: create, resolve, onboard, vouch, rotate, verify.
"""

import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.crypto_utils import CryptoUtils

BASE = "http://127.0.0.1:8000"

def test_did_flow():
    print("--- [TEST: DID IDENTITY FLOW (Phase 3.1)] ---\n")
    
    # Step 1: Create Identity for Agent A
    print("[STEP 1] Creating DID Identity for Agent A...")
    res = requests.post(f"{BASE}/identity/create", json={"agent_id": "did_agent_a"})
    assert res.status_code == 201, f"Expected 201, got {res.status_code}"
    identity_a = res.json()
    did_a = identity_a["did"]
    priv_a = identity_a["private_key"]
    pub_a = identity_a["public_key"]
    print(f"  DID: {did_a}")
    print(f"  Public Key: {pub_a[:20]}...")
    assert did_a.startswith("did:hive:"), f"DID format error: {did_a}"
    print("  ✅ DID format valid\n")

    # Step 2: Resolve the DID
    print("[STEP 2] Resolving DID Document...")
    res = requests.get(f"{BASE}/identity/{did_a}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    doc = res.json()
    assert doc["id"] == did_a
    assert doc["verificationMethod"][0]["publicKeyBase64"] == pub_a
    print(f"  Controller: {doc['controller']}")
    print(f"  Key Version: {doc['metadata']['key_version']}")
    print("  ✅ DID Document resolved correctly\n")

    # Step 3: Onboard Agent A with DID-derived public key
    print("[STEP 3] Onboarding Agent A with DID public key...")
    res = requests.post(f"{BASE}/agents/onboard", json={
        "agent_id": "did_agent_a",
        "name": "DID Agent Alpha",
        "description": "Agent with self-sovereign identity",
        "public_key": pub_a,
        "metadata": {"pre_trusted": True}
    })
    print(f"  Onboard Status: {res.status_code}")
    
    # Step 4: Create Identity for Agent B
    print("\n[STEP 4] Creating DID Identity for Agent B...")
    res = requests.post(f"{BASE}/identity/create", json={"agent_id": "did_agent_b"})
    assert res.status_code == 201
    identity_b = res.json()
    did_b = identity_b["did"]
    pub_b = identity_b["public_key"]
    print(f"  DID: {did_b}")

    # Onboard Agent B
    requests.post(f"{BASE}/agents/onboard", json={
        "agent_id": "did_agent_b",
        "name": "DID Agent Beta",
        "description": "Second DID agent",
        "public_key": pub_b
    })
    print("  ✅ Agent B onboarded\n")
    
    # Step 5: Agent A signs a vouch for Agent B using DID private key
    print("[STEP 5] Agent A vouches for Agent B (signed with DID key)...")
    payload = {
        "from_agent": "did_agent_a",
        "to_agent": "did_agent_b",
        "score": 90,
        "reason": "Verified through DID identity chain",
        "domain": "general",
        "skill": None
    }
    signature = CryptoUtils.sign_payload(priv_a, payload)
    payload["signature"] = signature
    res = requests.post(f"{BASE}/trust/vouch", json=payload)
    print(f"  Vouch Status: {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print("  ✅ Vouch accepted\n")

    # Step 6: Verify trust propagated
    print("[STEP 6] Verifying trust score...")
    res = requests.get(f"{BASE}/trust/did_agent_b")
    score = res.json().get("score", 0)
    print(f"  Score for Agent B: {score}")
    assert score > 0, "Expected non-zero trust score"
    print("  ✅ Trust propagated\n")

    # Step 7: Rotate Agent A's key
    print("[STEP 7] Rotating Agent A's key...")
    res = requests.post(f"{BASE}/identity/rotate", json={
        "did": did_a,
        "old_private_key": priv_a
    })
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    rotation_result = res.json()
    new_priv_a = rotation_result["new_private_key"]
    new_pub_a = rotation_result["new_public_key"]
    print(f"  New Public Key: {new_pub_a[:20]}...")
    print(f"  Rotation Proof: present={bool(rotation_result.get('rotation_proof'))}")
    print("  ✅ Key rotated\n")
    
    # Step 8: Verify old key is revoked (vouch with OLD key must fail)
    print("[STEP 8] TEST: Vouch with OLD key (should fail)...")
    payload_old = {
        "from_agent": "did_agent_a",
        "to_agent": "did_agent_b",
        "score": 85,
        "reason": "Testing old key rejection",
        "domain": "general",
        "skill": None
    }
    old_signature = CryptoUtils.sign_payload(priv_a, payload_old)
    payload_old["signature"] = old_signature
    res = requests.post(f"{BASE}/trust/vouch", json=payload_old)
    print(f"  Expected 400 Error: {res.status_code}")
    assert res.status_code == 400, f"OLD KEY ACCEPTED! Expected 400, got {res.status_code}"
    print("  ✅ Old key correctly rejected\n")
    
    # Step 9: Vouch with NEW key (should succeed)
    print("[STEP 9] Vouch with NEW key (should succeed)...")
    payload_new = {
        "from_agent": "did_agent_a",
        "to_agent": "did_agent_b",
        "score": 85,
        "reason": "Post-rotation verification",
        "domain": "general",
        "skill": None
    }
    new_signature = CryptoUtils.sign_payload(new_priv_a, payload_new)
    payload_new["signature"] = new_signature
    res = requests.post(f"{BASE}/trust/vouch", json=payload_new)
    print(f"  Vouch Status: {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    print("  ✅ New key accepted\n")
    
    # Step 10: Resolve DID again to confirm key history
    print("[STEP 10] Verifying DID Document has key history...")
    res = requests.get(f"{BASE}/identity/{did_a}")
    doc = res.json()
    key_history = doc.get("keyHistory", [])
    print(f"  Key History Entries: {len(key_history)}")
    print(f"  Current Key Version: {doc['metadata']['key_version']}")
    assert len(key_history) > 0, "Expected key history after rotation"
    assert doc["metadata"]["key_version"] == 2
    print("  ✅ Key history verified\n")
    
    print("--- [DID TEST COMPLETED: ALL STEPS PASSED] ---")

if __name__ == "__main__":
    test_did_flow()
