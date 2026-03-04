"""
The Hive - Swarm Governance Core
Governance logic for the swarm
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage_adapters.json_adapter import JSONAdapter
from storage_adapters.base_adapter import BaseAdapter


class SwarmGovernance:
    """
    Core governance logic for The Hive swarm.
    Uses adapter pattern to support different storage backends.
    """
    
    def __init__(self, adapter: BaseAdapter = None, state_dir: str = "./state"):
        self.adapter = adapter or JSONAdapter(state_dir)
    
    # ========== AGENT MANAGEMENT ==========
    
    def onboard_agent(self, agent_id: str, name: str, description: str = "", metadata: dict = None, public_key: str = None) -> bool:
        """Onboard a new agent to the swarm."""
        agent_info = {
            "agent_id": agent_id,
            "name": name,
            "description": description,
            "public_key": public_key,
            "metadata": metadata or {},
            "status": "active"
        }
        return self.adapter.register_agent(agent_id, agent_info)
    
    def get_agent(self, agent_id: str) -> dict:
        """Get agent info."""
        return self.adapter.get_agent(agent_id)
    
    def get_all_agents(self) -> list:
        """Get all swarm agents."""
        return self.adapter.get_all_agents()
    
    # ========== TRUST & REPUTATION ==========
    
    def vouch(self, from_agent: str, to_agent: str, score: int, reason: str, 
              domain: str = "general", skill: str = None, signature: str = None) -> bool:
        """Vouch for an agent with optional domain/skill and cryptographic signature."""
        return self.adapter.add_vouch(from_agent, to_agent, score, reason, domain, skill, signature)
    
    def get_trust_score(self, agent_id: str) -> float:
        """Agent's overall trust score."""
        return self.adapter.get_trust_score(agent_id)
    
    def get_trust_by_domain(self, agent_id: str) -> dict:
        """Agent's trust score by domain."""
        return self.adapter.get_trust_by_domain(agent_id)
    
    def get_graph_properties(self, agent_id: str) -> dict:
        """Agent's graph properties (connections, diversity, reciprocity)."""
        return self.adapter.get_graph_properties(agent_id)
    
    def detect_cliques(self) -> list:
        """Detect cliques (mutual vouching rings) in the swarm."""
        return self.adapter.detect_cliques()
    
    def check_suspicious_patterns(self, agent_id: str = None) -> dict:
        """Check for suspicious patterns (high reciprocity, cliques, isolation)."""
        return self.adapter.check_suspicious_patterns(agent_id)
    
    def get_vouches_received(self, agent_id: str) -> list:
        """Get vouches received by an agent."""
        return self.adapter.get_vouches(agent_id)
    
    def get_vouches_given(self, agent_id: str) -> list:
        """Get vouches given by an agent."""
        return self.adapter.get_vouches_given(agent_id)
    
    # ========== PROPOSALS & EVOLUTION ==========
    
    def propose_evolution(
        self,
        proposer_id: str,
        title: str,
        description: str,
        code_diff_hash: str
    ) -> str:
        """Submit an evolution proposal."""
        proposal_id = self.adapter.create_proposal(
            proposer_id=proposer_id,
            title=title,
            description=description,
            code_diff_hash=code_diff_hash
        )
        
        if proposal_id:
            return f"Proposal created: {proposal_id}"
        return "Failed: Minimum trust score (60) required to propose"
    
    def vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote: str,
        reason: str = None
    ) -> bool:
        """Vote on a proposal."""
        return self.adapter.vote_proposal(proposal_id, voter_id, vote, reason)
    
    def get_proposal(self, proposal_id: str) -> dict:
        """Get proposal details."""
        return self.adapter.get_proposal(proposal_id)
    
    def get_active_proposals(self) -> list:
        """Get all active proposals."""
        return self.adapter.get_active_proposals()
    
    def get_proposal_status(self, proposal_id: str) -> dict:
        """Get detailed status of a proposal."""
        proposal = self.adapter.get_proposal(proposal_id)
        if not proposal:
            return {"error": "Proposal not found"}
        
        quorum = self.adapter.calculate_quorum(proposal_id)
        
        return {
            "proposal": proposal,
            "quorum": quorum
        }
    
    # ========== GOVERNANCE ==========
    
    def can_propose(self, agent_id: str) -> bool:
        """Check if agent can propose."""
        trust = self.adapter.get_trust_score(agent_id)
        return trust >= self.adapter.MIN_TRUST_TO_PROPOSE
    
    def get_swarm_health(self) -> dict:
        """Get swarm health metrics."""
        status = self.adapter.get_swarm_status()
        
        # Add proposal health
        active = status["active_proposals"]
        approved = len(self.adapter.get_proposals_by_status("approved"))
        rejected = len(self.adapter.get_proposals_by_status("rejected"))
        
        return {
            **status,
            "approved_proposals": approved,
            "rejected_proposals": rejected,
            "governance_health": "healthy" if active <= 5 else "needs attention"
        }
    
    # ========== STAKE MANAGEMENT ==========
    
    def add_stake(self, agent_id: str, amount: float) -> bool:
        """Add stake to agent's account."""
        return self.adapter.add_stake(agent_id, amount)
    
    def get_stake(self, agent_id: str) -> float:
        """Get agent's stake amount."""
        return self.adapter.get_stake(agent_id)
    
    def get_stake_info(self, agent_id: str) -> dict:
        """Get detailed stake info."""
        return self.adapter.get_stake_info(agent_id)
    
    def stake_vouch(self, from_agent: str, to_agent: str, score: int, reason: str,
                    domain: str = "general", skill: str = None) -> tuple:
        """Vouch with stake commitment."""
        return self.adapter.stake_vouch(from_agent, to_agent, score, reason, domain, skill)
    
    def can_vouch_with_stake(self, from_agent: str, vouch_score: int) -> tuple:
        """Check if agent can vouch with stake."""
        return self.adapter.can_vouch_with_stake(from_agent, vouch_score)
    
    def slash_stake(self, agent_id: str, reason: str) -> float:
        """Slash agent's stake for malicious behavior."""
        return self.adapter.slash_stake(agent_id, reason)
    
    def enable_stake(self) -> None:
        """Enable stake-based vouching."""
        self.adapter.STAKE_ENABLED = True
    
    def disable_stake(self) -> None:
        """Disable stake-based vouching."""
        self.adapter.STAKE_ENABLED = False
    
    # ========== QUICK ACTIONS ==========
    
    def demo_swarm(self) -> None:
        """Set up a demo swarm for testing."""
        # Register demo agents
        self.onboard_agent("osiris_alpha", "Osiris Alpha", "First agent of the hive")
        self.onboard_agent("osiris_beta", "Osiris Beta", "Second agent of the hive")
        self.onboard_agent("osiris_gamma", "Osiris Gamma", "Third agent of the hive")
        
        # Create some trust
        self.vouch("osiris_alpha", "osiris_beta", 85, "Reliable worker")
        self.vouch("osiris_alpha", "osiris_gamma", 70, "Good potential")
        self.vouch("osiris_beta", "osiris_gamma", 75, "Solid contributions")
        
        # Create a demo proposal
        self.propose_evolution(
            "osiris_alpha",
            "Add memory module v3",
            "Update memory.py to use vector embeddings for better retrieval",
            "abc123def456"
        )
        
        print("Demo swarm initialized!")
        print(f"Swarm status: {self.get_swarm_health()}")


# Convenience function
def create_swarm(state_dir: str = "./state") -> SwarmGovernance:
    """Create a new swarm governance instance."""
    return SwarmGovernance(JSONAdapter(state_dir))


if __name__ == "__main__":
    # Demo
    swarm = create_swarm("./state")
    swarm.demo_swarm()
