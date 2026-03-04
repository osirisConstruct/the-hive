import requests
import sys
import os
import json

# Add core to path to use CryptoUtils in test
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from core.crypto_utils import CryptoUtils

BASE_URL = "http://127.0.0.1:8000"

def test_crypto_flow():
    print("--- [TEST: CRYPTOGRAPHIC API FLOW] ---")
    
    # 1. Generate Keypair for Agent A
    print("\n[STEP 1] Generating keys for Agent A...")
    keys_a = CryptoUtils.generate_keypair()
    agent_a_id = "crypto_agent_a"
    
    # 2. Onboard Agent A with Public Key
    print("[STEP 2] Onboarding Agent A (Rooted)...")
    onboard_res = requests.post(f"{BASE_URL}/agents/onboard", json={
        "agent_id": agent_a_id,
        "name": "Crypto Agent A",
        "public_key": keys_a["public_key"],
        "metadata": {"pre_trusted": True} # Root the trust
    })
    print(f"Onboard Status: {onboard_res.status_code}")
    
    # 3. Onboard Agent B (The target)
    print("[STEP 3] Onboarding Agent B...")
    agent_b_id = "target_agent_b"
    requests.post(f"{BASE_URL}/agents/onboard", json={
        "agent_id": agent_b_id,
        "name": "Target B",
        "public_key": CryptoUtils.generate_keypair()["public_key"] # Random key for B
    })
    
    # 4. Agent A signs a vouch for Agent B
    print("[STEP 4] Agent A signs vouch for Agent B...")
    vouch_payload = {
        "from_agent": agent_a_id,
        "to_agent": agent_b_id,
        "score": 95,
        "reason": "Cryptographically verified trust",
        "domain": "security",
        "skill": "cryptography"
    }
    signature = CryptoUtils.sign_payload(keys_a["private_key"], vouch_payload)
    
    # 5. Submit Vouch with Signature
    print("[STEP 5] Submitting signed vouch...")
    vouch_data = vouch_payload.copy()
    vouch_data["signature"] = signature
    vouch_res = requests.post(f"{BASE_URL}/trust/vouch", json=vouch_data)
    print(f"Vouch Status: {vouch_res.status_code}")
    
    # 6. Verify Trust Score
    print("[STEP 6] Verifying trust score...")
    score_res = requests.get(f"{BASE_URL}/trust/{agent_b_id}")
    print(f"Score for Agent B: {score_res.json().get('score')}")
    
    # 7. Malicious Test: Wrong Signature
    print("\n[STEP 7] TEST: Malicious submission (invalid signature)...")
    vouch_data["signature"] = "SGVsbG8gV29ybGQ=" # Invalid Base64 signature
    malicious_res = requests.post(f"{BASE_URL}/trust/vouch", json=vouch_data)
    print(f"Expected 403/400 Error: {malicious_res.status_code}")
    
    print("\n--- [CRYPTO TEST COMPLETED] ---")

if __name__ == "__main__":
    test_crypto_flow()
