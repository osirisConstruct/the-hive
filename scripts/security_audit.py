"""
The Hive - Red Team Security Audit (Phase 3.2)
Tests cryptographic vulnerabilities: payload forgery, key spoofing, revoked key usage, and missing signature validations.
"""

import requests
import json
import base64
import sys
import os

# Add repo root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.crypto_utils import CryptoUtils
except ImportError:
    from the_hive.core.crypto_utils import CryptoUtils

BASE_URL = "http://127.0.0.1:8000"

def run_audit():
    print("\n" + "="*50)
    print("🐝 THE HIVE - RED TEAM SECURITY AUDIT (PHASE 3.2)")
    print("="*50 + "\n")
    
    # 1. Setup Identities
    print(">>> Setting up Hacker and Target identities...")
    h_priv, h_pub = CryptoUtils.generate_keypair()
    t_priv, t_pub = CryptoUtils.generate_keypair()
    
    # Onboard Target (Optional, just to ensure it exists in registry)
    requests.post(f"{BASE_URL}/agents/onboard", json={
        "agent_id": "target_agent",
        "name": "Target",
        "public_key": h_pub
    })
    
    # Register proper DID for Hacker
    r = requests.post(f"{BASE_URL}/identity/create", json={"agent_id": "hacker_agent"})
    if r.status_code != 201:
        print(f"Failed to create hacker identity: {r.text}")
        return
        
    h_did = r.json()["did"]
    h_priv_b64 = r.json()["private_key"]
    h_doc = requests.get(f"{BASE_URL}/identity/{h_did}").json()
    h_pub_b64 = h_doc["verificationMethod"][0]["publicKeyBase64"]
    
    # Register Target
    r = requests.post(f"{BASE_URL}/identity/create", json={"agent_id": "target_agent"})
    t_did = r.json()["did"]
    t_priv_b64 = r.json()["private_key"]
    
    print(f"Hacker DID: {h_did}")
    print(f"Target DID: {t_did}")
    
    # --- VULN 1: PAYLOAD FORGERY ---
    print("\n[VULN 1] Testing Payload Forgery (Altering data after signing)...")
    payload = {"from_agent": h_did, "to_agent": t_did, "score": 10, "reason": "Weak vouch", "domain": "general", "skill": None}
    signature = CryptoUtils.sign_payload(h_priv_b64, payload)
    
    # Hacker modifies the score to 100 but uses the signature for 10
    forged_payload = payload.copy()
    forged_payload["score"] = 100
    forged_payload["signature"] = signature
    
    r = requests.post(f"{BASE_URL}/trust/vouch", json=forged_payload)
    if r.status_code == 400 and "Vouch failed" in r.text:
        print("✅ PASS: System rejected altered payload (Signature verification failed).")
    else:
        print(f"❌ FAIL: System accepted forged payload! Status: {r.status_code}")
        
    # --- VULN 2: KEY SPOOFING ---
    print("\n[VULN 2] Testing Key Spoofing (Signing as Target using Hacker's Key)...")
    payload = {"from_agent": t_did, "to_agent": h_did, "score": 100, "reason": "I love the hacker", "domain": "general", "skill": None}
    signature = CryptoUtils.sign_payload(h_priv_b64, payload) # Signed with Hacker's private key!
    payload["signature"] = signature
    
    r = requests.post(f"{BASE_URL}/trust/vouch", json=payload)
    if r.status_code == 400 and "Vouch failed" in r.text:
        print("✅ PASS: System rejected spoofed signature (Target's public key didn't match Hacker's private key).")
    else:
        print(f"❌ FAIL: System accepted spoofed signature! Status: {r.status_code}")
        
    # --- VULN 3: MISSING SIGNATURES ON PROPOSALS ---
    print("\n[VULN 3] Testing Missing Signatures on Proposals...")
    print("Hacker is attempting to submit a proposal ON BEHALF of the Target without a signature.")
    r = requests.post(f"{BASE_URL}/proposals", json={
        "proposer_id": t_did,
        "title": "Give Hacker Admin Rights",
        "description": "I totally endorse this as the Target.",
        "code_diff_hash": "deadbeef"
    })
    if r.status_code == 422: # Missing signature validation field implies it's required by Pydantic
        print("✅ PASS: System rejected unsigned proposal.")
    else:
        print(f"❌ CRITICAL VULN: System accepted unsigned proposal from spoofed agent (or failed for trust reasons instead of signature reasons)! Status: {r.status_code}")
        
    # --- VULN 4: MISSING SIGNATURES ON VOTES ---
    print("\n[VULN 4] Testing Missing Signatures on Votes...")
    # First get the proposal ID (it was just created if the system is vulnerable)
    prop_id = r.json().get("message", "").replace("Proposal recorded: ", "") if r.status_code == 201 else "prop_123"
    
    print(f"Hacker is attempting to vote UP on a proposal ON BEHALF of the Target.")
    r = requests.post(f"{BASE_URL}/proposals/{prop_id}/vote", json={
        "voter_id": t_did,
        "vote": "approve",
        "reason": "Hacker is cool.",
    })
    
    if r.status_code == 422: # Pydantic validation missing signature
        print("✅ PASS: System rejected unsigned vote.")
    else:
        print(f"❌ CRITICAL VULN: System accepted unsigned vote from spoofed agent (or failed for trust)! Status: {r.status_code}")

    print("\n[VULN 5] Testing Revoked Key Usage...")
    # Rotate Target's key
    print("Rotating Target's key...")
    r = requests.post(f"{BASE_URL}/identity/rotate", json={"did": t_did, "old_private_key": t_priv_b64})
    new_t_priv = r.json()["new_private_key"]
    
    # Attempt to use old key
    payload = {"from_agent": t_did, "to_agent": h_did, "score": 90, "reason": "Old trust", "domain": "general", "skill": None}
    signature = CryptoUtils.sign_payload(t_priv_b64, payload) # OLD KEY
    payload["signature"] = signature
    r = requests.post(f"{BASE_URL}/trust/vouch", json=payload)
    if r.status_code == 400 and "Vouch failed" in r.text:
        print("✅ PASS: System rejected vouch using revoked key.")
    else:
        print(f"❌ FAIL: System accepted vouch using revoked key! Status: {r.status_code}")
        
    print("\n" + "="*50)
    print("AUDIT COMPLETE.")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_audit()
