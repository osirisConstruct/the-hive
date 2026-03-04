import requests
import time
import sys
import os
import json

BASE_URL = "http://127.0.0.1:8000"

def log_test_header(name):
    print(f"\n{'='*20} {name} {'='*20}")

def run_adversarial_suite():
    # 1. Setup: Register a "Seed" agent and some legitimate trust
    log_test_header("SETUP: ROOTED TRUST")
    # Resetting state for clean test is hard via API, so we use unique IDs
    seed_id = f"seed_{int(time.time())}"
    legit_id = f"legit_{int(time.time())}"
    
    # Legit agent is pre-trusted via metadata (Simulating human/verified root)
    requests.post(f"{BASE_URL}/agents/onboard", json={
        "agent_id": legit_id, 
        "name": "Root Agent", 
        "metadata": {"pre_trusted": True}
    })
    
    requests.post(f"{BASE_URL}/agents/onboard", json={"agent_id": seed_id, "name": "Seed Agent"})
    
    # Root vouches for Seed (Seed now has 100 trust flow)
    requests.post(f"{BASE_URL}/trust/vouch", json={
        "from_agent": legit_id, "to_agent": seed_id, 
        "score": 100, "reason": "Rooted trust"
    })
    
    # 2. SYBIL ATTACK
    log_test_header("TEST: SYBIL ATTACK (EXPECT LOW SCORE)")
    attacker_id = f"attacker_{int(time.time())}"
    requests.post(f"{BASE_URL}/agents/onboard", json={"agent_id": attacker_id, "name": "Attacker"})
    
    # Create 5 Sybils (Disconnected from root)
    sybils = [f"sybil_{i}_{int(time.time())}" for i in range(5)]
    for sid in sybils:
        requests.post(f"{BASE_URL}/agents/onboard", json={"agent_id": sid, "name": f"Sybil {sid}"})
        # Sybils vouch for each other (Circular)
        for other_sid in sybils:
            if sid != other_sid:
                requests.post(f"{BASE_URL}/trust/vouch", json={
                    "from_agent": sid, "to_agent": other_sid, 
                    "score": 100, "reason": "Sybil pump"
                })
    
    # Sybils all vouch for the Attacker
    for sid in sybils:
        requests.post(f"{BASE_URL}/trust/vouch", json={
            "from_agent": sid, "to_agent": attacker_id, 
            "score": 100, "reason": "Sybil boost"
        })
    
    # RESULT: Check Attacker's trust score
    res = requests.get(f"{BASE_URL}/trust/{attacker_id}")
    attacker_score = res.json().get('score')
    print(f"Attacker Trust Score (target < 30): {attacker_score}")
    
    # 3. COLLUSION DETECTION (Directed Cycle)
    log_test_header("TEST: COLLUSION DETECTION (RING)")
    ts = int(time.time())
    cA, cB, cC = f"col_A_{ts}", f"col_B_{ts}", f"col_C_{ts}"
    for cid in [cA, cB, cC]:
        requests.post(f"{BASE_URL}/agents/onboard", json={"agent_id": cid, "name": f"Colluder {cid}"})
    
    # A -> B -> C -> A (Directed Cycle)
    requests.post(f"{BASE_URL}/trust/vouch", json={"from_agent": cA, "to_agent": cB, "score": 100, "reason": "Ring 1"})
    requests.post(f"{BASE_URL}/trust/vouch", json={"from_agent": cB, "to_agent": cC, "score": 100, "reason": "Ring 2"})
    requests.post(f"{BASE_URL}/trust/vouch", json={"from_agent": cC, "to_agent": cA, "score": 100, "reason": "Ring 3"})
    
    # Check suspicious patterns
    res = requests.get(f"{BASE_URL}/trust/{cA}/details")
    details = res.json()
    cycles = details.get('suspicious', {}).get('cliques', [])
    print(f"Collusion Cycles/Cliques detected: {len(cycles)}")
    for c in cycles:
        print(f"  - Detected {c['type']} with {len(c['members'])} members")

    # 4. STAKE SLASHING
    log_test_header("TEST: STAKE SLASHING")
    mal_id = f"mal_{int(time.time())}"
    requests.post(f"{BASE_URL}/agents/onboard", json={"agent_id": mal_id, "name": "Malicious Node"})
    
    # Enable stake & add stake
    requests.post(f"{BASE_URL}/stake/{mal_id}/enable")
    requests.post(f"{BASE_URL}/stake/{mal_id}/add", json={"amount": 100.0})
    
    # Check initial stake (Mock check via registry if needed, but we trust the slash)
    print("Executing slash...")
    slash_res = requests.post(f"{BASE_URL}/stake/{mal_id}/slash?reason=Simulation")
    print(f"Slash Result: {slash_res.json().get('message')}")

    print(f"\n{'='*20} ADVERSARIAL SUITE COMPLETE {'='*20}")

if __name__ == "__main__":
    try:
        run_adversarial_suite()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
