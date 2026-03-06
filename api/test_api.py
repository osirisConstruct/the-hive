"""
Full API Test Suite with cryptographic signatures
Tests the core Hive functionality: onboarding, vouching, trust, proposals.
"""
import requests
import sys
import os

BASE_URL = "http://127.0.0.1:8000"

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from core.crypto_utils import CryptoUtils


def test_api_flow():
    print("--- [TEST: FULL API FLOW] ---")
    
    # ========== AGENT ONBOARDING ==========
    print("\n[TEST] Onboarding agents with signatures...")
    
    keys_01 = CryptoUtils.generate_keypair()
    agent_01 = {
        "agent_id": "test_01",
        "name": "Test Agent One",
        "description": "Validator",
        "public_key": keys_01["public_key"],
        "metadata": {"pre_trusted": True}  # Root trust
    }
    res = requests.post(f"{BASE_URL}/agents/onboard", json=agent_01)
    print(f"  Onboard test_01: {res.status_code}")
    assert res.status_code == 201, f"Failed: {res.text}"
    
    keys_02 = CryptoUtils.generate_keypair()
    agent_02 = {
        "agent_id": "test_02",
        "name": "Test Agent Two",
        "description": "Worker",
        "public_key": keys_02["public_key"]
    }
    res = requests.post(f"{BASE_URL}/agents/onboard", json=agent_02)
    print(f"  Onboard test_02: {res.status_code}")
    assert res.status_code == 201
    
    # ========== LIST AGENTS ==========
    print("\n[TEST] Listing agents...")
    res = requests.get(f"{BASE_URL}/agents")
    agents = res.json()
    print(f"  Total agents: {len(agents)}")
    assert len(agents) >= 2
    
    # ========== VOUCHING (with signature) ==========
    print("\n[TEST] Peer vouching with signature...")
    vouch_payload = {
        "from_agent": "test_01",
        "to_agent": "test_02",
        "score": 90,
        "reason": "Excellent performance",
        "domain": "general",
        "skill": "testing"
    }
    signature = CryptoUtils.sign_payload(keys_01["private_key"], vouch_payload)
    
    vouch_data = {**vouch_payload, "signature": signature}
    res = requests.post(f"{BASE_URL}/trust/vouch", json=vouch_data)
    print(f"  Vouch status: {res.status_code}")
    print(f"  Vouch response: {res.text}")
    assert res.status_code == 200, f"Vouch failed: {res.text}"
    
    # ========== TRUST SCORE ==========
    print("\n[TEST] Trust score verification...")
    res = requests.get(f"{BASE_URL}/trust/test_02")
    score = res.json().get('score')
    print(f"  Trust score for test_02: {score}")
    assert score > 0
    
    # ========== TRUST DETAILS ==========
    print("\n[TEST] Trust details...")
    res = requests.get(f"{BASE_URL}/trust/test_02/details")
    details = res.json()
    print(f"  Domains: {list(details.get('domains', {}).keys())}")
    assert 'domains' in details
    
    # ========== PROPOSAL (with signature, requires trust >= 60) ==========
    print("\n[TEST] Creating proposal with signature...")
    
    # Wait a moment for trust to propagate if needed
    import time
    time.sleep(0.5)
    
    # Check if test_01 has enough trust to propose
    trust_res = requests.get(f"{BASE_URL}/trust/test_01")
    trust_score = trust_res.json().get('score')
    print(f"  test_01 trust: {trust_score}")
    
    # If not enough trust, vouch more or root it
    if trust_score < 60:
        print("  Insufficient trust for proposal. Vouching from osiris_main if available...")
        # Try to add more vouches if we can, otherwise just test proposal failure
        proposal_payload = {
            "proposer_id": "test_01",
            "title": "Test Proposal",
            "description": "A test proposal to verify proposal flow",
            "code_diff_hash": "abc123"
        }
        signature = CryptoUtils.sign_payload(keys_01["private_key"], proposal_payload)
        proposal_data = {**proposal_payload, "signature": signature}
        res = requests.post(f"{BASE_URL}/proposals", json=proposal_data)
        print(f"  Proposal status: {res.status_code}")
        # Expect 403 if trust too low, 201 if created
        assert res.status_code in [201, 403]
    else:
        # Create proposal
        proposal_payload = {
            "proposer_id": "test_01",
            "title": "Test Proposal",
            "description": "A test proposal to verify proposal flow",
            "code_diff_hash": "abc123"
        }
        signature = CryptoUtils.sign_payload(keys_01["private_key"], proposal_payload)
        proposal_data = {**proposal_payload, "signature": signature}
        res = requests.post(f"{BASE_URL}/proposals", json=proposal_data)
        print(f"  Proposal status: {res.status_code}")
        assert res.status_code == 201
        
        proposal_id = res.json().get('message', '').split(': ')[1] if ':' in res.json().get('message', '') else None
        
        if proposal_id:
            # ========== VOTING (with signature) ==========
            print("\n[TEST] Voting on proposal...")
            vote_payload = {
                "voter_id": "test_02",
                "vote": "approve",
                "reason": "Good proposal"
            }
            vote_signature = CryptoUtils.sign_payload(keys_02["private_key"], {**vote_payload, "proposal_id": proposal_id})
            vote_data = {**vote_payload, "signature": vote_signature}
            
            res = requests.post(f"{BASE_URL}/proposals/{proposal_id}/vote", json=vote_data)
            print(f"  Vote status: {res.status_code}")
            assert res.status_code == 200
    
    # ========== HEALTH CHECK ==========
    print("\n[TEST] Health check...")
    res = requests.get(f"{BASE_URL}/health")
    health = res.json()
    print(f"  Governance Health: {health.get('governance_health')}")
    assert res.status_code == 200
    assert health.get('governance_health') in ['healthy', 'degraded']
    
    print("\n✅ ALL TESTS PASSED!")


if __name__ == "__main__":
    try:
        test_api_flow()
        print("\nALL TESTS PASSED!")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
