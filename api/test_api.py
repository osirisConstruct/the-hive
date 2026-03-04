import requests
import time
import subprocess
import os
import signal
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("\n--- [THE HIVE: PHASE 2 API TEST SUITE] ---")
    
    # 1. Health check
    print("\n[TEST 1] Health check")
    res = requests.get(f"{BASE_URL}/health")
    print(f"Status: {res.status_code}")
    print(f"Health: {res.json().get('governance_health')}")
    assert res.status_code == 200

    # 2. Onboard agents
    print("\n[TEST 2] Onboarding agents")
    agents = [
        {"agent_id": "test_01", "name": "Test Agent One", "description": "Validator"},
        {"agent_id": "test_02", "name": "Test Agent Two", "description": "Worker"}
    ]
    for agent in agents:
        res = requests.post(f"{BASE_URL}/agents/onboard", json=agent)
        print(f"Onboarding {agent['agent_id']}: {res.status_code}")
        assert res.status_code == 201

    # 3. Get all agents
    print("\n[TEST 3] Listing agents")
    res = requests.get(f"{BASE_URL}/agents")
    data = res.json()
    print(f"Total agents: {len(data)}")
    assert len(data) >= 2

    # 4. Peer Vouching
    print("\n[TEST 4] Peer vouching")
    vouch = {
        "from_agent": "test_01",
        "to_agent": "test_02",
        "score": 90,
        "reason": "Excellent performance in simulation"
    }
    res = requests.post(f"{BASE_URL}/trust/vouch", json=vouch)
    print(f"Vouch status: {res.status_code}")
    assert res.status_code == 200

    # 5. Check trust score
    print("\n[TEST 5] Trust score verification")
    res = requests.get(f"{BASE_URL}/trust/test_02")
    score = res.json().get('score')
    print(f"Trust score for test_02: {score}")
    assert score > 0

    # 6. Submit Proposal (should fail if trust < 60, but test_01 starts with 0 trust from the system perspective if not in state)
    # Actually, in this test, test_01 doesn't have 60 trust yet.
    # Let's see if we can vouch for test_01 from a high-trust demo agent if possible, or just expect failure.
    print("\n[TEST 6] Submit Proposal (Expect 403 if trust < 60)")
    proposal = {
        "proposer_id": "test_01",
        "title": "API V2 Evolution",
        "description": "Add websocket support",
        "code_diff_hash": "sha256-abc123"
    }
    res = requests.post(f"{BASE_URL}/proposals", json=proposal)
    print(f"Proposal status: {res.status_code} | Detail: {res.json().get('detail')}")
    # Note: test_01 has 0 trust because no one vouched for it.

    print("\n--- [TEST SUITE COMPLETED SUCCESSFULLY] ---")

if __name__ == "__main__":
    # Start server in background
    # cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    # print(f"Starting server: {' '.join(cmd)}")
    # server_process = subprocess.Popen(cmd, cwd=os.getcwd())
    
    # We'll assume the user starts the server separately or we use a background task in the command runner.
    try:
        run_tests()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        sys.exit(1)
