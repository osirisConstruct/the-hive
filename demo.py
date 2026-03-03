#!/usr/bin/env python3
"""
The Hive - Demo Script
Run this to test the swarm governance system
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.swarm_governance import create_swarm

def main():
    print("=" * 50)
    print("THE HIVE - Swarm Governance Demo")
    print("=" * 50)
    
    # Create swarm
    swarm = create_swarm("./state")
    
    # Onboard agents
    print("\n[1] Onboarding agents...")
    swarm.onboard_agent("osiris_alpha", "Osiris Alpha", "First agent of the hive")
    swarm.onboard_agent("osiris_beta", "Osiris Beta", "Second agent") 
    swarm.onboard_agent("osiris_gamma", "Osiris Gamma", "Third agent")
    print("   3 agents onboarded")
    
    # Create trust - alpha needs some initial trust to propose
    # In real swarm, founder gets bootstrap trust
    print("\n[2] Creating trust vouches...")
    swarm.vouch("osiris_beta", "osiris_alpha", 80, "Founder of the hive")
    swarm.vouch("osiris_alpha", "osiris_beta", 85, "Reliable worker, great code")
    swarm.vouch("osiris_alpha", "osiris_gamma", 70, "Good potential")
    swarm.vouch("osiris_beta", "osiris_gamma", 75, "Solid contributions")
    print("   4 vouches created")
    
    # Check trust scores
    print("\n[3] Trust scores:")
    for agent_id in ["osiris_alpha", "osiris_beta", "osiris_gamma"]:
        score = swarm.get_trust_score(agent_id)
        print(f"   {agent_id}: {score}")
    
    # Propose evolution
    print("\n[4] Creating evolution proposal...")
    result = swarm.propose_evolution(
        "osiris_alpha",
        "Add vector memory module",
        "Update memory.py to use vector embeddings for better retrieval",
        "abc123def456"
    )
    print(f"   {result}")
    
    # Get active proposals
    proposals = swarm.get_active_proposals()
    if proposals:
        proposal_id = proposals[0]["id"]
        
        # Vote
        print(f"\n[5] Voting on proposal {proposal_id[:8]}...")
        swarm.vote(proposal_id, "osiris_beta", "approve", "Good idea, should help")
        swarm.vote(proposal_id, "osiris_gamma", "approve", "Agree")
        
        # Check status
        status = swarm.get_proposal_status(proposal_id)
        print(f"\n[6] Proposal status:")
        print(f"   Title: {status['proposal']['title']}")
        print(f"   Votes: {status['quorum']['total_votes']}")
        print(f"   Approval: {status['quorum']['approval_rate']}%")
        print(f"   Can execute: {status['quorum']['can_execute']}")
    
    # Swarm health
    print("\n[7] Swarm health:")
    health = swarm.get_swarm_health()
    print(f"   Total agents: {health['total_agents']}")
    print(f"   Average trust: {health['average_trust']}")
    print(f"   Active proposals: {health['active_proposals']}")
    print(f"   Governance: {health['governance_health']}")
    
    print("\n" + "=" * 50)
    print("Demo complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()
