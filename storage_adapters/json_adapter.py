"""
JSON Adapter for The Hive Swarm Governance
Phase 1: Local file-based storage
Phase 3.1: Optimistic locking for concurrency
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import uuid

from .base_adapter import BaseAdapter
from core.crypto_utils import CryptoUtils


class OptimisticLockError(Exception):
    """Raised when optimistic lock fails due to version conflict."""
    pass


class JSONAdapter(BaseAdapter):
    """JSON file-based storage adapter for swarm governance with optimistic locking."""
    
    # Thresholds
    MIN_TRUST_TO_PROPOSE = 60
    APPROVAL_THRESHOLD = 0.75  # 75% approval required
    MIN_VOTES = 2  # Minimum votes to reach quorum
    MAX_RETRIES = 3  # Max retries for optimistic lock conflicts
    
    # Reputation Decay Settings
    DECAY_HALFLIFE_DAYS = 180  # Trust halves every 6 months of inactivity
    DECAY_ENABLED = True
    
    # Configurable Hybrid Scores (domain-specific)
    DEFAULT_HYBRID_RATIOS = {
        "general": {"hive": 0.70, "attestation": 0.30},
        "coding": {"hive": 0.70, "attestation": 0.30},
        "security": {"hive": 0.80, "attestation": 0.20},
        "writing": {"hive": 0.60, "attestation": 0.40},
        "research": {"hive": 0.65, "attestation": 0.35},
        "ops": {"hive": 0.75, "attestation": 0.25},
        "philosophy": {"hive": 0.60, "attestation": 0.40},
    }
    
    # Stake/Collateral Settings
    STAKE_ENABLED = False
    MIN_STAKE_TO_VOUCH = 10
    STAKE_HALFLIFE_DAYS = 180
    SLASHING_THRESHOLD = 0.5
    VOUCH_STAKE_MULTIPLIER = 0.1
    
    # Security Settings
    MAX_VOUCHES_PER_DAY = 10
    MIN_VOUCH_REASON_LENGTH = 10
    
    # Proposal Settings
    MIN_STAKE_TO_PROPOSE = 20
    PROPOSAL_STAKE_MULTIPLIER = 0.2
    
    def __init__(self, state_dir: str = "./state", hybrid_ratios: Dict = None):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure directories exist
        (self.state_dir / "attestations").mkdir(exist_ok=True)
        (self.state_dir / "proposals").mkdir(exist_ok=True)
        (self.state_dir / "did_documents").mkdir(exist_ok=True)
        
        # Store hybrid ratios (configurable by domain)
        self.hybrid_ratios = hybrid_ratios or self.DEFAULT_HYBRID_RATIOS
        
        # Initialize registry if not exists
        self.registry_file = self.state_dir / "registry.json"
        if not self.registry_file.exists():
            self._save_json(self.registry_file, {
                "agents": {},
                "_version": 1
            })
    
    def _load_json(self, filepath: Path) -> Any:
        """Load JSON from file."""
        if not filepath.exists():
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_json(self, filepath: Path, data: Any) -> None:
        """Save JSON to file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _read_with_version(self, filepath: Path) -> Tuple[Any, int]:
        """Read JSON and return data with version number."""
        data = self._load_json(filepath)
        if data is None:
            return None, 0
        if isinstance(data, dict):
            version = data.get("_version", 1)
            # If data is wrapped (_data), unwrap it
            if "_data" in data:
                return data["_data"], version
            return data, version
        # Legacy list format
        return data, 1
    
    def _conditional_write(self, filepath: Path, data: Any, expected_version: int) -> bool:
        """
        Write only if version hasn't changed (optimistic locking).
        Returns True if write succeeded, raises OptimisticLockError if failed.
        """
        # Always allow writing if file doesn't exist (new file)
        if not filepath.exists():
            if isinstance(data, dict):
                data["_version"] = 1
            elif isinstance(data, list):
                wrapped = {"_version": 1, "_data": data}
                self._save_json(filepath, wrapped)
                return True
            else:
                self._save_json(filepath, data)
                return True
        
        current_data = self._load_json(filepath)
        
        if current_data is None:
            current_version = 0
        elif isinstance(current_data, dict):
            current_version = current_data.get("_version", 1)
        else:
            # Legacy list format - treat as version 1
            current_version = 1
        
        if current_version != expected_version:
            raise OptimisticLockError(
                f"Version conflict: expected {expected_version}, found {current_version}"
            )
        
        # Increment version
        if isinstance(data, dict):
            data["_version"] = current_version + 1
        elif isinstance(data, list):
            # For lists, wrap in dict with version
            wrapped = {"_version": current_version + 1, "_data": data}
            self._save_json(filepath, wrapped)
            return True
        
        self._save_json(filepath, data)
        return True
    
    def _generate_id(self) -> str:
        """Generate unique ID."""
        return uuid.uuid4().hex[:12]
    
    # ========== AGENT REGISTRY ==========
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get agent info by ID."""
        registry = self._load_json(self.registry_file)
        return registry.get("agents", {}).get(agent_id)
    
    def register_agent(self, agent_id: str, agent_info: Dict) -> bool:
        """Register a new agent in the swarm with optimistic locking."""
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                
                if "agents" not in registry:
                    registry["agents"] = {}
                
                agent_info["registered_at"] = datetime.utcnow().isoformat()
                agent_info["last_activity_at"] = datetime.utcnow().isoformat()
                agent_info["trust_score"] = 0.0
                agent_info["vouch_count"] = 0
                
                # Public key is mandatory for new agents (Phase 3)
                if "public_key" not in agent_info:
                    return False
                    
                registry["agents"][agent_id] = agent_info
                
                self._conditional_write(self.registry_file, registry, version)
                return True
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))  # Backoff
        
        return False
    
    def get_all_agents(self) -> List[Dict]:
        """Get all registered agents."""
        registry = self._load_json(self.registry_file)
        return list(registry.get("agents", {}).values())
    
    # ========== DID DOCUMENTS (Phase 3.1) ==========
    
    def store_did_document(self, did: str, did_document: dict) -> bool:
        """Store a DID Document for an agent."""
        safe_name = did.replace(":", "_")
        filepath = self.state_dir / "did_documents" / f"{safe_name}.json"
        self._save_json(filepath, did_document)
        return True
    
    def get_did_document(self, did: str) -> Optional[Dict]:
        """Resolve a DID to its document."""
        safe_name = did.replace(":", "_")
        filepath = self.state_dir / "did_documents" / f"{safe_name}.json"
        return self._load_json(filepath)
    
    def update_did_document(self, did: str, did_document: dict) -> bool:
        """Update an existing DID Document (e.g., after key rotation)."""
        safe_name = did.replace(":", "_")
        filepath = self.state_dir / "did_documents" / f"{safe_name}.json"
        if not filepath.exists():
            return False
        self._save_json(filepath, did_document)
        return True
    
    def link_did_to_agent(self, agent_id: str, did: str) -> bool:
        """Link a DID to an agent record in the registry."""
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                agent = registry.get("agents", {}).get(agent_id)
                if not agent:
                    return False
                agent["did"] = did
                self._conditional_write(self.registry_file, registry, version)
                return True
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
        return False

    # ========== TRUST & VOUCHES ==========
    
    def _calculate_decay_factor(self, last_activity_iso: str) -> float:
        """Calculate exponential decay factor based on last activity."""
        if not last_activity_iso:
            return 1.0
        
        try:
            last_activity = datetime.fromisoformat(last_activity_iso)
            days_inactive = (datetime.utcnow() - last_activity).days
            
            if days_inactive <= 0:
                return 1.0
            
            # Exponential decay: factor = 0.5^(days/halflife)
            import math
            decay_factor = math.pow(0.5, days_inactive / self.DECAY_HALFLIFE_DAYS)
            return decay_factor
        except:
            return 1.0
    
    def get_trust_score(self, agent_id: str) -> float:
        """Calculate trust score from vouches (0-100) with decay."""
        base_score = self._calculate_trust_recursive(agent_id, set())
        
        # Apply decay if enabled
        if self.DECAY_ENABLED:
            agent = self.get_agent(agent_id)
            if agent:
                last_activity = agent.get("last_activity_at")
                decay_factor = self._calculate_decay_factor(last_activity)
                return round(base_score * decay_factor, 2)
        
        return base_score
    
    def get_hybrid_trust_score(self, agent_id: str, domain: str = "general") -> Dict:
        """Get hybrid trust score combining Hive + Attestation with configurable ratios."""
        hive_score = self.get_trust_score(agent_id)
        
        # Get domain-specific ratio or use default
        ratio = self.hybrid_ratios.get(domain, self.hybrid_ratios["general"])
        
        # Attestation score would come from external system (placeholder)
        attestation_score = 0.0  # Would integrate with Agent Attestation system
        
        # Calculate hybrid
        hybrid = (hive_score * ratio["hive"]) + (attestation_score * ratio["attestation"])
        
        return {
            "hive_score": hive_score,
            "attestation_score": attestation_score,
            "hybrid_score": round(hybrid, 2),
            "domain": domain,
            "ratio": ratio
        }
    
    def get_trust_by_domain(self, agent_id: str) -> Dict:
        """Calculate trust scores per domain."""
        vouches = self.get_vouches(agent_id)
        
        domain_scores = {}
        
        for vouch in vouches:
            domain = vouch.get("domain", "general")
            if domain not in domain_scores:
                domain_scores[domain] = {
                    "score": 0,
                    "vouches": 0,
                    "total_weighted": 0,
                    "total_weight": 0
                }
            
            voucher_id = vouch["from_agent"]
            voucher_trust = self.get_trust_score(voucher_id)
            if voucher_trust == 0:
                voucher_trust = 30  # Bootstrap
            
            score = vouch["score"]
            domain_scores[domain]["total_weighted"] += score * voucher_trust
            domain_scores[domain]["total_weight"] += voucher_trust
            domain_scores[domain]["vouches"] += 1
        
        # Calculate final scores
        result = {}
        for domain, data in domain_scores.items():
            if data["total_weight"] > 0:
                score = data["total_weighted"] / data["total_weight"]
                result[domain] = {
                    "score": round(min(100.0, score), 2),
                    "attestations": data["vouches"]
                }
            else:
                result[domain] = {"score": 0, "attestations": 0}
        
        return result
    
    def get_graph_properties(self, agent_id: str) -> Dict:
        """Get graph properties: connections, diversity, reciprocity, depth."""
        vouches_received = self.get_vouches(agent_id)
        vouches_given = self.get_vouches_given(agent_id)
        
        # Connections: total vouches received
        connections = len(vouches_received)
        
        # Unique attestors
        unique_attestors = set(v["from_agent"] for v in vouches_received)
        unique_attestor_count = len(unique_attestors)
        
        # Reciprocity ratio: how much does this agent vouch back?
        agents_vouched = set(v["to_agent"] for v in vouches_given)
        reciprocal_vouches = len(agents_vouched.intersection(unique_attestors))
        reciprocity_ratio = reciprocal_vouches / connections if connections > 0 else 0
        
        # Max depth: longest chain of trust
        max_depth = self._calculate_max_depth(agent_id, set(), 0)
        
        # Diversity: how diverse are the attestors?
        # (measured by how spread out trust is across different trust levels)
        if connections > 0:
            trust_levels = [self.get_trust_score(a) for a in unique_attestors]
            avg_trust = sum(trust_levels) / len(trust_levels)
            # Low variance = high diversity (many different trust levels)
            if avg_trust > 0:
                variance = sum((t - avg_trust) ** 2 for t in trust_levels) / len(trust_levels)
                diversity = min(100, variance / 10)  # Normalize to 0-100
            else:
                diversity = 0
        else:
            diversity = 0
        
        return {
            "connections": connections,
            "unique_attestors": unique_attestor_count,
            "reciprocity_ratio": round(reciprocity_ratio, 3),
            "max_depth": max_depth,
            "diversity_score": round(diversity, 2)
        }
    
    def _calculate_max_depth(self, agent_id: str, visited: set, depth: int) -> int:
        """Calculate maximum depth of trust chain."""
        if agent_id in visited or depth > 10:  # Cap at 10 to prevent infinite loops
            return depth
        
        visited.add(agent_id)
        
        vouches = self.get_vouches(agent_id)
        if not vouches:
            return depth
        
        max_child_depth = depth
        for vouch in vouches:
            child_depth = self._calculate_max_depth(
                vouch["from_agent"], 
                visited.copy(), 
                depth + 1
            )
            max_child_depth = max(max_child_depth, child_depth)
        
        return max_child_depth
    
    def detect_cliques(self, min_size: int = 3) -> List[Dict]:
        """Detect cliques (mutual vouching rings) using simplified Bron-Kerbosch."""
        # Build adjacency graph
        agents = {a["agent_id"] for a in self.get_all_agents()}
        adjacency = {a: set() for a in agents}
        
        for agent in agents:
            vouches_given = self.get_vouches_given(agent)
            for v in vouches_given:
                to_agent = v.get("to_agent")
                if to_agent in agents:
                    adjacency[agent].add(to_agent)
        
        # Find cliques (Symmetry-based and Cyclic)
        cliques = []
        cliques.extend(self._find_cliques_bronkerosch(adjacency, min_size))
        
        # Add Cycle Detection for directed rings
        cycles = self._find_cycles(adjacency, min_size)
        for cycle in cycles:
            if cycle not in [set(c["members"]) for c in cliques]:
                cliques.append({
                    "members": list(cycle),
                    "size": len(cycle),
                    "type": "collusion_cycle"
                })
        
        return cliques

    def _find_cycles(self, adjacency: Dict, min_size: int) -> List[set]:
        """Simple DFS to find cycles in a directed graph."""
        cycles = []
        
        def dfs(start_node, current_node, visited, path):
            for neighbor in adjacency.get(current_node, set()):
                if neighbor == start_node:
                    if len(path) >= min_size:
                        cycles.append(set(path))
                    continue
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(start_node, neighbor, visited, path)
                    path.pop()
                    visited.remove(neighbor)

        for node in adjacency:
            dfs(node, node, {node}, [node])
            
        # Deduplicate sets
        unique_cycles = []
        for c in cycles:
            if c not in unique_cycles:
                unique_cycles.append(c)
        return unique_cycles
    
    def _find_cliques_bronkerosch(self, adjacency: Dict, min_size: int) -> List[Dict]:
        """Simplified clique detection - find all maximal cliques."""
        nodes = set(adjacency.keys())
        cliques = []
        
        # For each pair of nodes, check if they're mutually connected
        for node in nodes:
            neighbors = adjacency[node]
            for neighbor in neighbors:
                if neighbor == node:
                    continue
                
                # Check if it's mutual
                if node in adjacency.get(neighbor, set()):
                    # Found a potential clique pair - expand
                    clique = self._expand_clique(node, neighbor, adjacency, {node, neighbor})
                    if len(clique) >= min_size and clique not in [c["members"] for c in cliques]:
                        cliques.append({
                            "members": list(clique),
                            "size": len(clique),
                            "type": "mutual_vouch_ring"
                        })
        
        return cliques
    
    def _expand_clique(self, node1: str, node2: str, adjacency: Dict, current: set) -> set:
        """Expand a clique by finding common neighbors."""
        common = adjacency[node1].intersection(adjacency[node2])
        common = common.difference(current)
        
        if not common:
            return current
        
        # Just take the first common neighbor for simplicity
        new_node = list(common)[0]
        current.add(new_node)
        
        # Try to expand further with new node
        for existing in list(current):
            if existing != new_node:
                new_common = current.intersection(adjacency[existing])
                if new_common:
                    current = current.union(new_common)
        
        return current
    
    def check_suspicious_patterns(self, agent_id: str = None) -> Dict:
        """Check for suspicious patterns in the trust graph."""
        results = {
            "suspicious_agents": [],
            "high_reciprocity": [],
            "cliques": [],
            "isolated_agents": []
        }
        
        # Check high reciprocity
        if agent_id:
            graph = self.get_graph_properties(agent_id)
            if graph["reciprocity_ratio"] > 0.8:
                results["high_reciprocity"].append(agent_id)
        else:
            # Check all agents
            for agent in self.get_all_agents():
                agent_id = agent["agent_id"]
                graph = self.get_graph_properties(agent_id)
                if graph["reciprocity_ratio"] > 0.8:
                    results["high_reciprocity"].append(agent_id)
        
        # Find cliques
        results["cliques"] = self.detect_cliques(min_size=3)
        
        # Find isolated agents (no connections)
        for agent in self.get_all_agents():
            agent_id = agent["agent_id"]
            vouches = self.get_vouches(agent_id)
            vouches_given = self.get_vouches_given(agent_id)
            if len(vouches) == 0 and len(vouches_given) == 0:
                results["isolated_agents"].append(agent_id)
        
        return results
    
    def _calculate_trust_recursive(self, agent_id: str, visited: set) -> float:
        """Calculate trust with rooted dampening and cycle detection."""
        if agent_id in visited:
            return 0.0
        
        visited.add(agent_id)
        
        # Check if agent is "pre-trusted" (seed)
        agent = self.get_agent(agent_id)
        if agent and agent.get("metadata", {}).get("pre_trusted"):
            return 100.0

        vouches = self.get_vouches(agent_id)
        if not vouches:
            return 0.0
        
        total_weighted = 0
        total_weight = 0
        
        # Path to root check: we only trust agents that have some connectivity to a trusted source
        max_voucher_trust = 0
        
        for vouch in vouches:
            voucher_id = vouch["from_agent"]
            
            # Get voucher's trust
            if voucher_id == agent_id:
                voucher_trust = 0 # No self-trust bootstrap
            else:
                voucher_trust = self._calculate_trust_recursive(voucher_id, visited.copy())
            
            # If voucher has no trust and isn't a known bootstrap agent, it provides 0 trust flow
            # Unless it's a "Seed Agent" registered by the architect
            if voucher_trust == 0:
                # Check for bootstrap trust only if voucher is legitimately onboarded with high initial stake
                # For now, we use a strict "No Root, No Trust" policy for Phase 2.1
                continue
                
            total_weighted += vouch["score"] * voucher_trust
            total_weight += voucher_trust
            max_voucher_trust = max(max_voucher_trust, voucher_trust)
        
        if total_weight == 0:
            return 0.0
        
        # Damping factor: trust is capped by the strength of the best voucher
        # This prevents sybil rings from amplifying themselves without a root
        base_score = total_weighted / total_weight
        dampening = max_voucher_trust / 100.0
        
        score = base_score * dampening
        return min(100.0, round(score, 2))
    
    # Default domains for attestations
    DEFAULT_DOMAINS = ["general", "coding", "writing", "research", "ops", "philosophy"]
    
    def add_vouch(self, from_agent: str, to_agent: str, score: int, reason: str, 
                  domain: str = "general", skill: str = None, signature: str = None) -> bool:
        """Add a vouch for an agent with optimistic locking and cryptographic verification."""
        # Verify both agents exist
        from_agent_info = self.get_agent(from_agent)
        to_agent_info = self.get_agent(to_agent)
        
        if not from_agent_info or not to_agent_info:
            return False
            
        # Cryptographic verification (Phase 3)
        if signature:
            public_key = from_agent_info.get("public_key")
            if not public_key:
                return False
            
            payload = {
                "from_agent": from_agent,
                "to_agent": to_agent,
                "score": score,
                "reason": reason,
                "domain": domain,
                "skill": skill
            }
            
            if not CryptoUtils.verify_signature(public_key, payload, signature):
                return False
        else:
            if from_agent_info.get("public_key"):
                return False

        if not (0 <= score <= 100):
            return False
        
        # Validate domain
        if domain not in self.DEFAULT_DOMAINS:
            domain = "general"
        
        vouch_file = self.state_dir / "attestations" / f"{to_agent}.json"
        
        for attempt in range(self.MAX_RETRIES):
            try:
                attestations = []
                version = 0
                if vouch_file.exists():
                    attestations, version = self._read_with_version(vouch_file)
                
                vouch = {
                    "id": self._generate_id(),
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "score": score,
                    "reason": reason,
                    "signature": signature, # Store the signature for audit
                    "domain": domain,
                    "skill": skill,
                    "created_at": datetime.utcnow().isoformat(),
                    "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
                }
                
                attestations.append(vouch)
                self._conditional_write(vouch_file, attestations, version)
                self._update_agent_trust(to_agent, len(attestations))
                self._update_agent_activity(to_agent)
                return True
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
        
        return False
    
    def _update_agent_trust(self, agent_id: str, vouch_count: int) -> None:
        """Update agent trust score in registry with optimistic locking."""
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                
                if agent_id in registry.get("agents", {}):
                    registry["agents"][agent_id]["trust_score"] = self.get_trust_score(agent_id)
                    registry["agents"][agent_id]["vouch_count"] = vouch_count
                
                self._conditional_write(self.registry_file, registry, version)
                return
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
    
    def _update_agent_activity(self, agent_id: str) -> None:
        """Update agent's last activity timestamp."""
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                
                if agent_id in registry.get("agents", {}):
                    registry["agents"][agent_id]["last_activity_at"] = datetime.utcnow().isoformat()
                
                self._conditional_write(self.registry_file, registry, version)
                return
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
    
    def get_vouches(self, agent_id: str) -> List[Dict]:
        """Get all active vouches for an agent."""
        vouch_file = self.state_dir / "attestations" / f"{agent_id}.json"
        
        if not vouch_file.exists():
            return []
        
        attestations, _ = self._read_with_version(vouch_file)
        if not attestations:
            return []
        
        # Filter expired vouches
        now = datetime.utcnow()
        active = []
        for v in attestations:
            if not isinstance(v, dict):
                continue
            expiry = datetime.fromisoformat(v["expires_at"])
            if expiry > now:
                active.append(v)
        
        return active
    
    def get_vouches_given(self, agent_id: str) -> List[Dict]:
        """Get all vouches given by an agent."""
        attestations_dir = self.state_dir / "attestations"
        all_vouches = []
        
        for vouch_file in attestations_dir.glob("*.json"):
            attestations, _ = self._read_with_version(vouch_file)
            if not attestations:
                continue
            for v in attestations:
                if not isinstance(v, dict):
                    continue
                if v.get("from_agent") == agent_id:
                    all_vouches.append(v)
        
        return all_vouches
    
    # ========== PROPOSALS ==========
    
    def create_proposal(self, proposer_id: str, title: str, description: str, code_diff_hash: str) -> Optional[str]:
        """Create a new evolution proposal with optimistic locking."""
        # Check minimum trust to propose
        trust = self.get_trust_score(proposer_id)
        if trust < self.MIN_TRUST_TO_PROPOSE:
            return None
        
        proposal_id = self._generate_id()
        
        proposal = {
            "id": proposal_id,
            "proposer_id": proposer_id,
            "title": title,
            "description": description,
            "code_diff_hash": code_diff_hash,
            "status": "voting",
            "votes": {},
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "_version": 1
        }
        
        proposal_file = self.state_dir / "proposals" / f"{proposal_id}.json"
        self._save_json(proposal_file, proposal)
        
        return proposal_id
    
    def vote_proposal(self, proposal_id: str, voter_id: str, vote: str, reason: Optional[str] = None) -> bool:
        """Vote on a proposal with optimistic locking."""
        if vote not in ["approve", "reject", "abstain"]:
            return False
        
        proposal_file = self.state_dir / "proposals" / f"{proposal_id}.json"
        if not proposal_file.exists():
            return False
        
        for attempt in range(self.MAX_RETRIES):
            try:
                proposal, version = self._read_with_version(proposal_file)
                
                if proposal["status"] != "voting":
                    return False
                
                # Get voter's trust weight
                trust_weight = self.get_trust_score(voter_id)
                
                proposal["votes"][voter_id] = {
                    "vote": vote,
                    "reason": reason or "",
                    "trust_weight": trust_weight,
                    "voted_at": datetime.utcnow().isoformat()
                }
                
                # Write with optimistic lock
                self._conditional_write(proposal_file, proposal, version)
                
                # Check if proposal should be executed
                self._check_proposal_execution(proposal_id)
                
                return True
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
        
        return False
    
    def _check_proposal_execution(self, proposal_id: str) -> None:
        """Check if proposal should be executed based on quorum."""
        proposal_file = self.state_dir / "proposals" / f"{proposal_id}.json"
        proposal = self._load_json(proposal_file)
        
        quorum_result = self.calculate_quorum(proposal_id)
        
        if quorum_result["can_execute"]:
            proposal["status"] = "approved"
            proposal["executed_at"] = datetime.utcnow().isoformat()
            self._save_json(proposal_file, proposal)
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        """Get proposal by ID."""
        proposal_file = self.state_dir / "proposals" / f"{proposal_id}.json"
        if not proposal_file.exists():
            return None
        return self._load_json(proposal_file)
    
    def get_active_proposals(self) -> List[Dict]:
        """Get all active proposals."""
        proposals = []
        proposals_dir = self.state_dir / "proposals"
        
        for proposal_file in proposals_dir.glob("*.json"):
            proposal = self._load_json(proposal_file)
            if proposal.get("status") == "voting":
                proposals.append(proposal)
        
        return sorted(proposals, key=lambda x: x["created_at"], reverse=True)
    
    def get_proposals_by_status(self, status: str) -> List[Dict]:
        """Get proposals by status."""
        proposals = []
        proposals_dir = self.state_dir / "proposals"
        
        for proposal_file in proposals_dir.glob("*.json"):
            proposal = self._load_json(proposal_file)
            if proposal.get("status") == status:
                proposals.append(proposal)
        
        return sorted(proposals, key=lambda x: x["created_at"], reverse=True)
    
    # ========== GOVERNANCE ==========
    
    def calculate_quorum(self, proposal_id: str) -> Dict:
        """Calculate voting quorum for a proposal."""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return {"valid": False, "error": "Proposal not found"}
        
        votes = proposal.get("votes", {})
        
        if len(votes) < self.MIN_VOTES:
            return {
                "valid": True,
                "can_execute": False,
                "reason": f"Only {len(votes)} votes, need {self.MIN_VOTES}",
                "votes_needed": self.MIN_VOTES - len(votes)
            }
        
        # Calculate weighted approval
        total_weight = 0
        approve_weight = 0
        reject_weight = 0
        
        for voter_id, vote_data in votes.items():
            weight = vote_data.get("trust_weight", 0)
            vote = vote_data.get("vote", "abstain")
            
            total_weight += weight
            
            if vote == "approve":
                approve_weight += weight
            elif vote == "reject":
                reject_weight += weight
        
        if total_weight == 0:
            return {
                "valid": True,
                "can_execute": False,
                "reason": "No voting weight"
            }
        
        approval_rate = approve_weight / total_weight
        reject_rate = reject_weight / total_weight
        
        can_execute = (
            approval_rate >= self.APPROVAL_THRESHOLD and
            len(votes) >= self.MIN_VOTES and
            reject_rate < (1 - self.APPROVAL_THRESHOLD)
        )
        
        return {
            "valid": True,
            "can_execute": can_execute,
            "approval_rate": round(approval_rate * 100, 2),
            "reject_rate": round(reject_rate * 100, 2),
            "total_votes": len(votes),
            "total_weight": total_weight,
            "approve_weight": approve_weight,
            "reject_weight": reject_weight
        }
    
    # ========== SWARM STATUS ==========
    
    def get_swarm_status(self) -> Dict:
        """Get overall swarm status."""
        agents = self.get_all_agents()
        active_proposals = self.get_active_proposals()
        
        total_trust = sum(a.get("trust_score", 0) for a in agents)
        avg_trust = total_trust / len(agents) if agents else 0
        
        return {
            "total_agents": len(agents),
            "average_trust": round(avg_trust, 2),
            "active_proposals": len(active_proposals),
            "agents": [
                {
                    "id": a.get("agent_id"),
                    "name": a.get("name"),
                    "trust_score": a.get("trust_score", 0),
                    "vouch_count": a.get("vouch_count", 0)
                }
                for a in agents
            ]
        }
    
    # ========== STAKE MANAGEMENT ==========
    
    def get_stake(self, agent_id: str) -> float:
        """Get agent's current stake amount."""
        agent = self.get_agent(agent_id)
        if not agent:
            return 0.0
        return agent.get("stake", 0.0)
    
    def get_stake_info(self, agent_id: str) -> Dict:
        """Get detailed stake information including decay."""
        agent = self.get_agent(agent_id)
        if not agent:
            return {"stake": 0.0, "available": 0.0, "staked": 0.0, "decay_factor": 1.0}
        
        stake = agent.get("stake", 0.0)
        staked = agent.get("staked_amount", 0.0)
        last_stake_activity = agent.get("last_stake_activity")
        
        decay_factor = self._calculate_stake_decay_factor(last_stake_activity)
        available = stake - staked
        
        return {
            "stake": stake,
            "available": max(0, available),
            "staked": staked,
            "decay_factor": decay_factor,
            "last_activity": last_stake_activity
        }
    
    def _calculate_stake_decay_factor(self, last_activity_iso: str) -> float:
        """Calculate stake decay factor based on inactivity."""
        if not last_activity_iso:
            return 1.0
        
        try:
            last_activity = datetime.fromisoformat(last_activity_iso)
            days_inactive = (datetime.utcnow() - last_activity).days
            
            if days_inactive <= 0:
                return 1.0
            
            import math
            decay_factor = math.pow(0.5, days_inactive / self.STAKE_HALFLIFE_DAYS)
            return decay_factor
        except:
            return 1.0
    
    def add_stake(self, agent_id: str, amount: float) -> bool:
        """Add stake to an agent's account."""
        if amount <= 0:
            return False
        
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                
                if agent_id in registry.get("agents", {}):
                    current_stake = registry["agents"][agent_id].get("stake", 0.0)
                    registry["agents"][agent_id]["stake"] = current_stake + amount
                    registry["agents"][agent_id]["last_stake_activity"] = datetime.utcnow().isoformat()
                
                self._conditional_write(self.registry_file, registry, version)
                return True
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
        
        return False
    
    def calculate_required_stake(self, agent_id: str, vouch_score: int) -> float:
        """Calculate stake required to make a vouch."""
        required = vouch_score * self.VOUCH_STAKE_MULTIPLIER
        return max(self.MIN_STAKE_TO_VOUCH, required)
    
    def calculate_proposal_stake_required(self, agent_id: str) -> float:
        """Calculate stake required to propose evolution."""
        trust = self.get_trust_score(agent_id)
        required = trust * self.PROPOSAL_STAKE_MULTIPLIER
        return max(self.MIN_STAKE_TO_PROPOSE, required)
    
    def can_vouch_with_stake(self, from_agent: str, vouch_score: int) -> Tuple[bool, str]:
        """Check if agent can vouch based on available stake."""
        if not self.STAKE_ENABLED:
            return True, "Stake not enabled"
        
        info = self.get_stake_info(from_agent)
        required = self.calculate_required_stake(from_agent, vouch_score)
        
        available = info.get("available", 0)
        decay_factor = info.get("decay_factor", 1.0)
        effective_available = available * decay_factor
        
        if effective_available < required:
            return False, f"Insufficient stake: {effective_available:.1f} available, {required:.1f} required"
        
        return True, "OK"
    
    def stake_vouch(self, from_agent: str, to_agent: str, score: int, reason: str,
                    domain: str = "general", skill: str = None) -> Tuple[bool, str]:
        """Vouch with stake commitment - returns (success, message)."""
        if not self.STAKE_ENABLED:
            return self.add_vouch(from_agent, to_agent, score, reason, domain, skill), "Stake not enabled"
        
        can_vouch, msg = self.can_vouch_with_stake(from_agent, score)
        if not can_vouch:
            return False, msg
        
        required = self.calculate_required_stake(from_agent, score)
        
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                
                if from_agent in registry.get("agents", {}):
                    current_staked = registry["agents"][from_agent].get("staked_amount", 0.0)
                    registry["agents"][from_agent]["staked_amount"] = current_staked + required
                
                self._conditional_write(self.registry_file, registry, version)
                
                success = self.add_vouch(from_agent, to_agent, score, reason, domain, skill)
                if not success:
                    self.unstake_vouch(from_agent, required)
                    return False, "Vouch failed"
                
                return True, f"Vouched with {required} stake"
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
        
        return False, "Transaction failed"
    
    def unstake_vouch(self, agent_id: str, amount: float) -> bool:
        """Release staked amount after vouch expires."""
        if amount <= 0:
            return True
        
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                
                if agent_id in registry.get("agents", {}):
                    current_staked = registry["agents"][agent_id].get("staked_amount", 0.0)
                    registry["agents"][agent_id]["staked_amount"] = max(0, current_staked - amount)
                
                self._conditional_write(self.registry_file, registry, version)
                return True
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
        
        return False
    
    def slash_stake(self, agent_id: str, reason: str) -> float:
        """Slash agent's stake for malicious behavior. Returns amount slashed."""
        if not self.STAKE_ENABLED:
            return 0.0
        
        info = self.get_stake_info(agent_id)
        total_stake = info.get("stake", 0.0)
        
        if total_stake == 0:
            return 0.0
        
        slashed_amount = total_stake * self.SLASHING_THRESHOLD
        
        for attempt in range(self.MAX_RETRIES):
            try:
                registry, version = self._read_with_version(self.registry_file)
                
                if agent_id in registry.get("agents", {}):
                    registry["agents"][agent_id]["stake"] = total_stake - slashed_amount
                    registry["agents"][agent_id]["slash_history"] = registry["agents"][agent_id].get("slash_history", [])
                    registry["agents"][agent_id]["slash_history"].append({
                        "amount": slashed_amount,
                        "reason": reason,
                        "slashed_at": datetime.utcnow().isoformat()
                    })
                
                self._conditional_write(self.registry_file, registry, version)
                return slashed_amount
                
            except OptimisticLockError:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                time.sleep(0.01 * (attempt + 1))
        
        return 0.0
