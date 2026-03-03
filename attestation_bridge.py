"""
The Hive - Attestation Bridge
Integrates Agent Attestation v2.0 trust scores into Hive governance
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

# Fix imports for running from workspace/ directory
_repo_root = Path(__file__).resolve().parent.parent.parent
_workspace = _repo_root / "workspace"
sys.path.insert(0, str(_workspace))  # For "the_hive" module
sys.path.insert(0, str(_workspace / "the_hive"))
sys.path.insert(0, str(_workspace / "skills" / "agent-attestation"))

from core.swarm_governance import SwarmGovernance
from attestation_system_v2 import AttestationSystemV2


class HiveAttestationBridge:
    """
    Bridge between The Hive governance and Agent Attestation v2.0
    Allows using external attestations to seed Hive trust scores
    """
    
    def __init__(
        self, 
        hive: SwarmGovernance,
        attestations: List[dict] = None,
        attestation_dir: str = None
    ):
        self.hive = hive
        self.attestations = attestations or []
        self.attestation_dir = attestation_dir
        
        if attestation_dir:
            self._load_attestations()
    
    def _load_attestations(self) -> None:
        """Load attestations from directory"""
        att_dir = Path(self.attestation_dir)
        if not att_dir.exists():
            return
        
        for f in att_dir.glob("*.json"):
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                    if isinstance(data, list):
                        self.attestations.extend(data)
                    elif isinstance(data, dict):
                        self.attestations.append(data)
            except Exception as e:
                print(f"Warning: Could not load {f}: {e}")
    
    def sync_attestation_to_vouch(
        self, 
        attestation: dict,
        weight: float = 1.0
    ) -> bool:
        """
        Convert an attestation to a Hive vouch
        Uses attestation score as trust score
        """
        attestor = attestation.get("attestor", {}).get("name")
        subject = attestation.get("subject")
        score = attestation.get("stake", {}).get("reputation_at_stake", 0.5)
        
        if not attestor or not subject:
            return False
        
        # Register attestor if not exists
        if not self.hive.get_agent(attestor):
            self.hive.onboard_agent(
                attestor, 
                attestor, 
                f"Attestor from attestation system"
            )
        
        # Register subject if not exists
        if not self.hive.get_agent(subject):
            self.hive.onboard_agent(
                subject,
                subject,
                f"Subject of attestation"
            )
        
        # Calculate vouch score from attestation
        task_value = attestation.get("task_value", "medium")
        task_weights = {"low": 0.5, "medium": 1.0, "high": 2.0, "critical": 5.0}
        task_weight = task_weights.get(task_value, 1.0)
        
        # Base score + task weight + vouch bonus
        final_score = int((1.0 + task_weight + score) * 50 * weight)
        final_score = min(100, final_score)  # Cap at 100
        
        reason = attestation.get("reason", "Attestation-based vouch")
        is_vouched = attestation.get("stake", {}).get("vouched", False)
        
        if is_vouched:
            reason = f"[VOUCHED] {reason}"
        
        return self.hive.vouch(attestor, subject, final_score, reason)
    
    def sync_all_attestations(self, weight: float = 1.0) -> Dict:
        """Sync all loaded attestations to Hive vouches"""
        synced = 0
        failed = 0
        
        for att in self.attestations:
            try:
                if self.sync_attestation_to_vouch(att, weight):
                    synced += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Error syncing attestation: {e}")
                failed += 1
        
        return {
            "synced": synced,
            "failed": failed,
            "total": len(self.attestations)
        }
    
    def get_hybrid_trust_score(
        self, 
        agent_id: str,
        attestation_weight: float = 0.3
    ) -> Dict:
        """
        Get hybrid trust score combining:
        - Hive's internal vouch-based score
        - External attestation score
        """
        hive_score = self.hive.get_trust_score(agent_id)
        
        # Calculate attestation score
        attestation_system = AttestationSystemV2("bridge_agent")
        att_score_data = attestation_system.compute_score(
            self.attestations, 
            agent_id
        )
        att_score = att_score_data.get("score", 0.0)
        
        # Normalize attestation score (typically 0-10 range) to 0-100
        att_score_normalized = min(att_score * 10, 100)
        
        # Weighted combination
        hive_weight = 1.0 - attestation_weight
        hybrid = (
            hive_score * hive_weight + 
            att_score_normalized * attestation_weight
        )
        
        return {
            "agent_id": agent_id,
            "hive_score": hive_score,
            "attestation_score": att_score_normalized,
            "attestation_valid": att_score_data.get("valid_attestations", 0),
            "hybrid_score": round(hybrid, 2),
            "weights": {
                "hive": hive_weight,
                "attestation": attestation_weight
            }
        }
    
    def create_attestation_vouch_proposal(
        self,
        proposer_id: str,
        attestor: str,
        subject: str,
        task_value: str = "medium"
    ) -> str:
        """
        Create a proposal to add an attestation-based vouch
        Uses governance to approve external trust integration
        """
        # Check proposer can propose
        if not self.hive.can_propose(proposer_id):
            return "Failed: Proposer doesn't meet trust threshold"
        
        # Create attestation
        attestation_system = AttestationSystemV2(attestor)
        attestation = attestation_system.create_attestation(
            subject=subject,
            reason=f"Hive governance approved vouch for {subject}",
            task_value=task_value,
            vouch=True,
            stake_amount=0.5
        )
        
        # Add to attestations
        self.attestations.append(attestation)
        
        # Create proposal
        proposal_title = f"Attestation Vouch: {attestor} → {subject}"
        proposal_desc = f"""
Add external attestation from {attestor} for {subject}
Task value: {task_value}
Vouched: True
        """
        
        return self.hive.propose_evolution(
            proposer_id=proposer_id,
            title=proposal_title,
            description=proposal_desc,
            code_diff_hash=attestation.get("signature", "")
        )


def create_bridge(
    hive_state_dir: str = "./state",
    attestation_dir: str = None
) -> HiveAttestationBridge:
    """Create a bridged Hive + Attestation system"""
    hive = SwarmGovernance(
        adapter=None,
        state_dir=hive_state_dir
    )
    return HiveAttestationBridge(hive, attestation_dir=attestation_dir)


if __name__ == "__main__":
    # Demo
    bridge = create_bridge("./state")
    
    # Load or create demo attestations
    system = AttestationSystemV2("osiris_alpha")
    
    att1 = system.create_attestation(
        subject="osiris_beta",
        reason="Excellent work on memory module",
        task_value="high",
        vouch=True,
        stake_amount=0.8
    )
    
    att2 = system.create_attestation(
        subject="osiris_gamma",
        reason="Good potential, needs more experience",
        task_value="medium",
        vouch=False,
        stake_amount=0.0
    )
    
    bridge.attestations = [att1, att2]
    
    print("=== Syncing attestations to Hive ===")
    result = bridge.sync_all_attestations()
    print(json.dumps(result, indent=2))
    
    print("\n=== Hive trust scores ===")
    for agent_id in ["osiris_alpha", "osiris_beta", "osiris_gamma"]:
        score = bridge.hive.get_trust_score(agent_id)
        print(f"{agent_id}: {score}")
    
    print("\n=== Hybrid trust scores ===")
    for agent_id in ["osiris_beta", "osiris_gamma"]:
        hybrid = bridge.get_hybrid_trust_score(agent_id)
        print(json.dumps(hybrid, indent=2))
