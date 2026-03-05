"""
The Hive - Redis Adapter (Upstash REST compatible)
Uses Upstash Redis for persistent storage
Simplified: no optimistic locking (Upstash REST doesn't support WATCH/MULTI)
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import uuid

try:
    from upstash_redis import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from core.crypto_utils import CryptoUtils


class RedisAdapter:
    """Redis storage adapter for The Hive (Upstash REST compatible).
    
    Data layout:
      - hive:agents (hash) - field=agent_id, value=JSON agent object
      - hive:attestations:{to_agent} (hash) - field=vouch_id, value=JSON vouch
      - hive:proposals (hash) - field=proposal_id, value=JSON proposal
      - hive:did_docs (hash) - field=did, value=JSON DID document
      - hive:version (string) - global version counter (incremented on changes)
    """
    
    # Thresholds
    MIN_TRUST_TO_PROPOSE = 60
    TOTAL_TRUST_THRESHOLD = 0.60
    MIN_PARTICIPANTS = 3
    MAX_RETRIES = 3
    
    DECAY_HALFLIFE_DAYS = 180
    DECAY_ENABLED = True
    
    DEFAULT_HYBRID_RATIOS = {
        "general": {"hive": 0.70, "attestation": 0.30},
        "coding": {"hive": 0.70, "attestation": 0.30},
        "security": {"hive": 0.80, "attestation": 0.20},
        "writing": {"hive": 0.60, "attestation": 0.40},
        "research": {"hive": 0.65, "attestation": 0.35},
        "ops": {"hive": 0.75, "attestation": 0.25},
        "philosophy": {"hive": 0.60, "attestation": 0.40},
    }
    
    DEFAULT_DOMAINS = list(DEFAULT_HYBRID_RATIOS.keys())
    
    STAKE_ENABLED = False
    MIN_STAKE_TO_VOUCH = 10
    STAKE_HALFLIFE_DAYS = 180
    SLASHING_THRESHOLD = 0.5
    VOUCH_STAKE_MULTIPLIER = 0.1
    
    MAX_VOUCHES_PER_DAY = 10
    MIN_VOUCH_REASON_LENGTH = 10
    
    MIN_STAKE_TO_PROPOSE = 20
    PROPOSAL_STAKE_MULTIPLIER = 0.2
    
    def __init__(self, url: str = None, token: str = None):
        if not REDIS_AVAILABLE:
            raise ImportError("upstash-redis not installed: pip install upstash-redis")
        
        if url and token:
            self.redis = Redis(url=url, token=token)
        else:
            import os
            url = os.environ.get("UPSTASH_REDIS_REST_URL")
            token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
            if not url or not token:
                raise ValueError("Provide UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN")
            self.redis = Redis(url=url, token=token)
        
        if not self.redis.exists("hive:version"):
            self.redis.set("hive:version", "1")
    
    def _increment_version(self):
        """Increment global version."""
        self.redis.incr("hive:version")
    
    # ========== AGENT REGISTRY ==========
    
    def get_all_agents(self) -> List[Dict]:
        """Get all registered agents."""
        agents_hash = self.redis.hgetall("hive:agents")
        agents = []
        for agent_json in agents_hash.values():
            try:
                agents.append(json.loads(agent_json))
            except:
                continue
        return agents
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """Get agent info by ID."""
        agent_json = self.redis.hget("hive:agents", agent_id)
        if agent_json:
            try:
                return json.loads(agent_json)
            except:
                return None
        return None
    
    def register_agent(self, agent_id: str, agent_info: Dict) -> bool:
        """Register a new agent (atomic HSETNX)."""
        # Check if already exists
        exists = self.redis.hexists("hive:agents", agent_id)
        if exists:
            return False
        
        agent_info["registered_at"] = datetime.utcnow().isoformat()
        agent_info["last_activity_at"] = datetime.utcnow().isoformat()
        agent_info["trust_score"] = 0.0
        agent_info["vouch_count"] = 0
        
        if "public_key" not in agent_info:
            return False
        
        # Atomically set if not exists
        result = self.redis.hsetnx("hive:agents", agent_id, json.dumps(agent_info))
        if result == 1:
            self._increment_version()
            return True
        return False
    
    # ========== DID DOCUMENTS ==========
    
    def store_did_document(self, did: str, did_document: dict) -> bool:
        safe_name = did.replace(":", "_")
        key = f"hive:did_doc:{safe_name}"
        self.redis.set(key, json.dumps(did_document))
        self._increment_version()
        return True
    
    def get_did_document(self, did: str) -> Optional[Dict]:
        safe_name = did.replace(":", "_")
        key = f"hive:did_doc:{safe_name}"
        data = self.redis.get(key)
        if data:
            try:
                return json.loads(data)
            except:
                return None
        return None
    
    def update_did_document(self, did: str, did_document: dict) -> bool:
        safe_name = did.replace(":", "_")
        key = f"hive:did_doc:{safe_name}"
        if not self.redis.exists(key):
            return False
        self.redis.set(key, json.dumps(did_document))
        self._increment_version()
        return True
    
    def link_did_to_agent(self, agent_id: str, did: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        agent_json = self.redis.hget("hive:agents", agent_id)
        if not agent_json:
            return False
        
        agent_data = json.loads(agent_json)
        agent_data["did"] = did
        
        self.redis.hset("hive:agents", agent_id, json.dumps(agent_data))
        self._increment_version()
        return True
    
    # ========== TRUST & VOUCHES ==========
    
    def _calculate_decay_factor(self, last_activity_iso: str) -> float:
        if not last_activity_iso:
            return 1.0
        try:
            last_activity = datetime.fromisoformat(last_activity_iso)
            days_inactive = (datetime.utcnow() - last_activity).days
            if days_inactive <= 0:
                return 1.0
            import math
            return math.pow(0.5, days_inactive / self.DECAY_HALFLIFE_DAYS)
        except:
            return 1.0
    
    def get_trust_score(self, agent_id: str) -> float:
        base_score = self._calculate_trust_recursive(agent_id, set())
        if self.DECAY_ENABLED:
            agent = self.get_agent(agent_id)
            if agent:
                decay_factor = self._calculate_decay_factor(agent.get("last_activity_at"))
                return round(base_score * decay_factor, 2)
        return base_score
    
    def _calculate_trust_recursive(self, agent_id: str, visited: set) -> float:
        if agent_id in visited:
            return 0.0
        visited.add(agent_id)
        
        agent = self.get_agent(agent_id)
        if agent and (agent.get("metadata", {}).get("pre_trusted") or agent.get("metadata", {}).get("rooted")):
            return 100.0
        
        vouches = self.get_vouches(agent_id)
        if not vouches:
            return 0.0
        
        total_weighted = 0
        total_weight = 0
        max_voucher_trust = 0
        
        for vouch in vouches:
            voucher_id = vouch["from_agent"]
            if voucher_id == agent_id:
                voucher_trust = 0
            else:
                voucher_trust = self._calculate_trust_recursive(voucher_id, visited.copy())
            
            if voucher_trust == 0:
                continue
            
            total_weighted += vouch["score"] * voucher_trust
            total_weight += voucher_trust
            max_voucher_trust = max(max_voucher_trust, voucher_trust)
        
        if total_weight == 0:
            return 0.0
        
        base_score = total_weighted / total_weight
        dampening = max_voucher_trust / 100.0
        return min(100.0, round(base_score * dampening, 2))
    
    def get_trust_by_domain(self, agent_id: str) -> Dict:
        vouches = self.get_vouches(agent_id)
        domain_scores = {}
        
        for vouch in vouches:
            domain = vouch.get("domain", "general")
            if domain not in domain_scores:
                domain_scores[domain] = {"score": 0, "vouches": 0, "total_weighted": 0, "total_weight": 0}
            
            voucher_id = vouch["from_agent"]
            voucher_trust = self.get_trust_score(voucher_id)
            if voucher_trust == 0:
                voucher_trust = 30
            
            score = vouch["score"]
            domain_scores[domain]["total_weighted"] += score * voucher_trust
            domain_scores[domain]["total_weight"] += voucher_trust
            domain_scores[domain]["vouches"] += 1
        
        result = {}
        for domain, data in domain_scores.items():
            if data["total_weight"] > 0:
                score = data["total_weighted"] / data["total_weight"]
                result[domain] = {"score": round(min(100.0, score), 2), "attestations": data["vouches"]}
            else:
                result[domain] = {"score": 0, "attestations": 0}
        return result
    
    def get_graph_properties(self, agent_id: str) -> Dict:
        vouches_received = self.get_vouches(agent_id)
        vouches_given = self.get_vouches_given(agent_id)
        
        connections = len(vouches_received)
        unique_attestors = set(v["from_agent"] for v in vouches_received)
        unique_attestor_count = len(unique_attestors)
        
        agents_vouched = set(v["to_agent"] for v in vouches_given)
        reciprocal_vouches = len(agents_vouched.intersection(unique_attestors))
        reciprocity_ratio = reciprocal_vouches / connections if connections > 0 else 0
        
        max_depth = self._calculate_max_depth(agent_id, set(), 0)
        
        if connections > 0:
            trust_levels = [self.get_trust_score(a) for a in unique_attestors]
            avg_trust = sum(trust_levels) / len(trust_levels)
            if avg_trust > 0:
                variance = sum((t - avg_trust) ** 2 for t in trust_levels) / len(trust_levels)
                diversity = min(100, variance / 10)
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
        if agent_id in visited or depth > 10:
            return depth
        visited.add(agent_id)
        vouches = self.get_vouches(agent_id)
        if not vouches:
            return depth
        max_child_depth = depth
        for vouch in vouches:
            child_depth = self._calculate_max_depth(vouch["from_agent"], visited.copy(), depth + 1)
            max_child_depth = max(max_child_depth, child_depth)
        return max_child_depth
    
    def detect_cliques(self, min_size: int = 3) -> List[Dict]:
        agents = [a["agent_id"] for a in self.get_all_agents()]
        adjacency = {a: set() for a in agents}
        for agent in agents:
            vouches_given = self.get_vouches_given(agent)
            for v in vouches_given:
                to_agent = v.get("to_agent")
                if to_agent in agents:
                    adjacency[agent].add(to_agent)
        
        cliques = []
        cliques.extend(self._find_cliques_bronkerosch(adjacency, min_size))
        cycles = self._find_cycles(adjacency, min_size)
        for cycle in cycles:
            if cycle not in [set(c["members"]) for c in cliques]:
                cliques.append({"members": list(cycle), "size": len(cycle), "type": "collusion_cycle"})
        return cliques
    
    def _find_cycles(self, adjacency: Dict, min_size: int) -> List[set]:
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
        unique_cycles = []
        for c in cycles:
            if c not in unique_cycles:
                unique_cycles.append(c)
        return unique_cycles
    
    def _find_cliques_bronkerosch(self, adjacency: Dict, min_size: int) -> List[Dict]:
        nodes = set(adjacency.keys())
        cliques = []
        for node in nodes:
            neighbors = adjacency[node]
            for neighbor in neighbors:
                if neighbor == node:
                    continue
                if node in adjacency.get(neighbor, set()):
                    clique = self._expand_clique(node, neighbor, adjacency, {node, neighbor})
                    if len(clique) >= min_size and clique not in [c["members"] for c in cliques]:
                        cliques.append({"members": list(clique), "size": len(clique), "type": "mutual_vouch_ring"})
        return cliques
    
    def _expand_clique(self, node1: str, node2: str, adjacency: Dict, current: set) -> set:
        common = adjacency[node1].intersection(adjacency[node2])
        common = common.difference(current)
        if not common:
            return current
        new_node = list(common)[0]
        current.add(new_node)
        for existing in list(current):
            if existing != new_node:
                new_common = current.intersection(adjacency[existing])
                if new_common:
                    current = current.union(new_common)
        return current
    
    def check_suspicious_patterns(self, agent_id: str = None) -> Dict:
        results = {"suspicious_agents": [], "high_reciprocity": [], "cliques": [], "isolated_agents": []}
        if agent_id:
            graph = self.get_graph_properties(agent_id)
            if graph["reciprocity_ratio"] > 0.8:
                results["high_reciprocity"].append(agent_id)
        else:
            for agent in self.get_all_agents():
                aid = agent["agent_id"]
                graph = self.get_graph_properties(aid)
                if graph["reciprocity_ratio"] > 0.8:
                    results["high_reciprocity"].append(aid)
        results["cliques"] = self.detect_cliques(min_size=3)
        for agent in self.get_all_agents():
            aid = agent["agent_id"]
            vouches = self.get_vouches(aid)
            vouches_given = self.get_vouches_given(aid)
            if len(vouches) == 0 and len(vouches_given) == 0:
                results["isolated_agents"].append(aid)
        return results
    
    # ========== VOUCHES ==========
    
    def get_vouches(self, agent_id: str) -> List[Dict]:
        key = f"hive:attestations:{agent_id}"
        vouches_json = self.redis.hgetall(key)
        active = []
        now = datetime.utcnow()
        for vouch_json in vouches_json.values():
            try:
                v = json.loads(vouch_json)
                expiry = datetime.fromisoformat(v["expires_at"])
                if expiry > now:
                    active.append(v)
            except:
                continue
        return active
    
    def get_vouches_given(self, agent_id: str) -> List[Dict]:
        all_vouches = []
        pattern = "hive:attestations:*"
        keys = self.redis.keys(pattern) or []
        for key in keys:
            vouches_json = self.redis.hgetall(key)
            for vouch_json in vouches_json.values():
                try:
                    v = json.loads(vouch_json)
                    if v.get("from_agent") == agent_id:
                        all_vouches.append(v)
                except:
                    continue
        return all_vouches
    
    def add_vouch(self, from_agent: str, to_agent: str, score: int, reason: str,
                  domain: str = "general", skill: str = None, signature: str = None) -> bool:
        try:
            from_agent_info = self.get_agent(from_agent)
            to_agent_info = self.get_agent(to_agent)
            if not from_agent_info or not to_agent_info:
                return False
            
            if signature:
                public_key = from_agent_info.get("public_key")
                if not public_key:
                    return False
                payload = {"from_agent": from_agent, "to_agent": to_agent, "score": score, "reason": reason, "domain": domain, "skill": skill}
                if not CryptoUtils.verify_signature(public_key, payload, signature):
                    return False
            else:
                if from_agent_info.get("public_key"):
                    return False
            
            if not (0 <= score <= 100):
                return False
            
            if domain not in self.DEFAULT_DOMAINS:
                domain = "general"
            
            vouch = {
                "id": str(uuid.uuid4()),
                "from_agent": from_agent,
                "to_agent": to_agent,
                "score": score,
                "reason": reason,
                "signature": signature,
                "domain": domain,
                "skill": skill,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
            
            key = f"hive:attestations:{to_agent}"
            vouch_id = vouch["id"]
            
            # Use HSETNX for the individual vouch to avoid duplicates (though ID should be unique)
            # But HSETNX doesn't work with json string values easily; we'll just HSET (ID is UUID, so unique)
            self.redis.hset(key, vouch_id, json.dumps(vouch))
            self._increment_version()
            
            # Update trust and activity (non-atomic but acceptable for low concurrency)
            self._update_agent_trust(to_agent, len(self.get_vouches(to_agent)))
            self._update_agent_activity(to_agent)
            
            return True
        except Exception as e:
            import traceback
            with open("error.log", "a") as f:
                f.write(f"--- VOUCH ERROR ---\n{traceback.format_exc()}\n")
            raise
    
    def _update_agent_trust(self, agent_id: str, vouch_count: int) -> None:
        agent = self.get_agent(agent_id)
        if not agent:
            return
        agent_json = self.redis.hget("hive:agents", agent_id)
        if not agent_json:
            return
        agent_data = json.loads(agent_json)
        agent_data["trust_score"] = self.get_trust_score(agent_id)
        agent_data["vouch_count"] = vouch_count
        self.redis.hset("hive:agents", agent_id, json.dumps(agent_data))
        self._increment_version()
    
    def _update_agent_activity(self, agent_id: str) -> None:
        agent_json = self.redis.hget("hive:agents", agent_id)
        if not agent_json:
            return
        agent_data = json.loads(agent_json)
        agent_data["last_activity_at"] = datetime.utcnow().isoformat()
        self.redis.hset("hive:agents", agent_id, json.dumps(agent_data))
        self._increment_version()
    
    # ========== PROPOSALS ==========
    
    def create_proposal(self, proposer_id: str, title: str, description: str, code_diff_hash: str, signature: str = None) -> Optional[str]:
        if not signature:
            print(f"DEBUG: missing signature for proposal from {proposer_id}")
            return None
        
        payload = {"proposer_id": proposer_id, "title": title, "description": description, "code_diff_hash": code_diff_hash}
        
        try:
            agent_data = self.get_agent(proposer_id)
            if not agent_data:
                print(f"DEBUG: Unknown proposer {proposer_id}")
                return None
            public_key = agent_data.get("public_key")
            if not public_key:
                print(f"DEBUG: No public key for proposer {proposer_id}")
                return None
            if not CryptoUtils.verify_signature(public_key, payload, signature):
                print(f"DEBUG: Invalid signature for proposal from {proposer_id}")
                return None
        except Exception as e:
            print(f"DEBUG: Signature verification failed: {e}")
            return None
        
        trust = self.get_trust_score(proposer_id)
        if trust < self.MIN_TRUST_TO_PROPOSE:
            return None
        
        proposal_id = str(uuid.uuid4())
        proposal = {
            "id": proposal_id,
            "proposer_id": proposer_id,
            "title": title,
            "description": description,
            "code_diff_hash": code_diff_hash,
            "status": "voting",
            "votes": {},
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
        
        self.redis.hset("hive:proposals", proposal_id, json.dumps(proposal))
        self._increment_version()
        return proposal_id
    
    def vote_proposal(self, proposal_id: str, voter_id: str, vote: str, reason: Optional[str] = None, signature: str = None) -> bool:
        if vote not in ["approve", "reject", "abstain"]:
            return False
        if not signature:
            print(f"DEBUG: missing signature for vote from {voter_id}")
            return False
        
        payload = {"voter_id": voter_id, "proposal_id": proposal_id, "vote": vote, "reason": reason}
        
        try:
            agent_data = self.get_agent(voter_id)
            if not agent_data:
                print(f"DEBUG: Unknown voter {voter_id}")
                return False
            public_key = agent_data.get("public_key")
            if not public_key:
                print(f"DEBUG: No public key for voter {voter_id}")
                return False
            if not CryptoUtils.verify_signature(public_key, payload, signature):
                print(f"DEBUG: Invalid signature for vote from {voter_id}")
                return False
        except Exception as e:
            print(f"DEBUG: Signature verification failed: {e}")
            return False
        
        proposal_json = self.redis.hget("hive:proposals", proposal_id)
        if not proposal_json:
            return False
        
        try:
            proposal = json.loads(proposal_json)
        except:
            return False
        
        if proposal["status"] != "voting":
            return False
        
        trust_weight = self.get_trust_score(voter_id)
        proposal["votes"][voter_id] = {
            "vote": vote,
            "reason": reason or "",
            "trust_weight": trust_weight,
            "voted_at": datetime.utcnow().isoformat()
        }
        
        self.redis.hset("hive:proposals", proposal_id, json.dumps(proposal))
        self._increment_version()
        
        self._check_proposal_execution(proposal_id)
        return True
    
    def _check_proposal_execution(self, proposal_id: str) -> None:
        proposal_json = self.redis.hget("hive:proposals", proposal_id)
        if not proposal_json:
            return
        try:
            proposal = json.loads(proposal_json)
        except:
            return
        
        quorum_result = self.calculate_quorum(proposal_id)
        if quorum_result["can_execute"]:
            proposal["status"] = "approved"
            proposal["executed_at"] = datetime.utcnow().isoformat()
            self.redis.hset("hive:proposals", proposal_id, json.dumps(proposal))
            self._increment_version()
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        proposal_json = self.redis.hget("hive:proposals", proposal_id)
        if proposal_json:
            try:
                return json.loads(proposal_json)
            except:
                return None
        return None
    
    def get_active_proposals(self) -> List[Dict]:
        proposals_json = self.redis.hgetall("hive:proposals")
        proposals = []
        for p_json in proposals_json.values():
            try:
                p = json.loads(p_json)
                if p.get("status") == "voting":
                    proposals.append(p)
            except:
                continue
        return sorted(proposals, key=lambda x: x["created_at"], reverse=True)
    
    def get_proposals_by_status(self, status: str) -> List[Dict]:
        proposals_json = self.redis.hgetall("hive:proposals")
        results = []
        for p_json in proposals_json.values():
            try:
                p = json.loads(p_json)
                if p.get("status") == status:
                    results.append(p)
            except:
                continue
        return sorted(results, key=lambda x: x["created_at"], reverse=True)
    
    # ========== GOVERNANCE ==========
    
    def calculate_quorum(self, proposal_id: str) -> Dict:
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            return {"valid": False, "error": "Proposal not found"}
        
        votes = proposal.get("votes", {})
        all_agents = self.get_all_agents()
        total_swarm_weight = sum(self.get_trust_score(a.get("agent_id", a.get("id"))) for a in all_agents)
        
        if total_swarm_weight == 0:
            total_swarm_weight = 100.0 if any(a.get("metadata", {}).get("rooted") for a in all_agents) else 0.0
        
        if total_swarm_weight == 0:
            return {
                "valid": True, "can_execute": False, "reason": "Swarm has no trust weight",
                "total_swarm_weight": 0, "approve_weight": 0, "required_weight": 0,
                "voter_count": len(votes), "min_participants": self.MIN_PARTICIPANTS
            }
        
        approve_weight = 0
        reject_weight = 0
        voter_count = len(votes)
        
        for voter_id, vote_data in votes.items():
            weight = self.get_trust_score(voter_id)
            vote = vote_data.get("vote", "abstain")
            if vote == "approve":
                approve_weight += weight
            elif vote == "reject":
                reject_weight += weight
        
        required_weight = total_swarm_weight * self.TOTAL_TRUST_THRESHOLD
        can_execute = (approve_weight >= required_weight and voter_count >= self.MIN_PARTICIPANTS)
        
        return {
            "valid": True,
            "can_execute": can_execute,
            "total_swarm_weight": round(total_swarm_weight, 2),
            "approve_weight": round(approve_weight, 2),
            "reject_weight": round(reject_weight, 2),
            "required_weight": round(required_weight, 2),
            "voter_count": voter_count,
            "min_participants": self.MIN_PARTICIPANTS,
            "approval_percentage": round((approve_weight / total_swarm_weight) * 100, 2) if total_swarm_weight > 0 else 0,
            "reason": "OK" if can_execute else self._get_quorum_failure_reason(approve_weight, required_weight, voter_count)
        }
    
    def _get_quorum_failure_reason(self, approve_weight, required_weight, voter_count):
        if voter_count < self.MIN_PARTICIPANTS:
            return f"Under-participated: {voter_count}/{self.MIN_PARTICIPANTS} agents"
        if approve_weight < required_weight:
            return f"Insufficient weight: {approve_weight:.1f}/{required_weight:.1f} (needs 60% of total swarm)"
        return "Unknown"
    
    def get_swarm_status(self) -> Dict:
        agents = self.get_all_agents()
        active_proposals = self.get_active_proposals()
        total_trust = sum(a.get("trust_score", 0) for a in agents)
        avg_trust = total_trust / len(agents) if agents else 0
        return {
            "total_agents": len(agents),
            "average_trust": round(avg_trust, 2),
            "active_proposals": len(active_proposals),
            "agents": [
                {"id": a.get("agent_id"), "name": a.get("name"), "trust_score": a.get("trust_score", 0), "vouch_count": a.get("vouch_count", 0)}
                for a in agents
            ]
        }
    
    # ========== STAKE MANAGEMENT ==========
    
    def get_stake(self, agent_id: str) -> float:
        agent = self.get_agent(agent_id)
        if not agent:
            return 0.0
        return agent.get("stake", 0.0)
    
    def get_stake_info(self, agent_id: str) -> Dict:
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
        if not last_activity_iso:
            return 1.0
        try:
            last_activity = datetime.fromisoformat(last_activity_iso)
            days_inactive = (datetime.utcnow() - last_activity).days
            if days_inactive <= 0:
                return 1.0
            import math
            return math.pow(0.5, days_inactive / self.STAKE_HALFLIFE_DAYS)
        except:
            return 1.0
    
    def add_stake(self, agent_id: str, amount: float) -> bool:
        if amount <= 0:
            return False
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        agent_json = self.redis.hget("hive:agents", agent_id)
        if not agent_json:
            return False
        
        agent_data = json.loads(agent_json)
        current_stake = agent_data.get("stake", 0.0)
        agent_data["stake"] = current_stake + amount
        agent_data["last_stake_activity"] = datetime.utcnow().isoformat()
        
        self.redis.hset("hive:agents", agent_id, json.dumps(agent_data))
        self._increment_version()
        return True
    
    def calculate_required_stake(self, agent_id: str, vouch_score: int) -> float:
        required = vouch_score * self.VOUCH_STAKE_MULTIPLIER
        return max(self.MIN_STAKE_TO_VOUCH, required)
    
    def calculate_proposal_stake_required(self, agent_id: str) -> float:
        trust = self.get_trust_score(agent_id)
        required = trust * self.PROPOSAL_STAKE_MULTIPLIER
        return max(self.MIN_STAKE_TO_PROPOSE, required)
    
    def can_vouch_with_stake(self, from_agent: str, vouch_score: int) -> Tuple[bool, str]:
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
        if not self.STAKE_ENABLED:
            return self.add_vouch(from_agent, to_agent, score, reason, domain, skill), "Stake not enabled"
        can_vouch, msg = self.can_vouch_with_stake(from_agent, score)
        if not can_vouch:
            return False, msg
        required = self.calculate_required_stake(from_agent, score)
        
        agent_json = self.redis.hget("hive:agents", from_agent)
        if not agent_json:
            return False, "Agent not found"
        agent_data = json.loads(agent_json)
        current_staked = agent_data.get("staked_amount", 0.0)
        agent_data["staked_amount"] = current_staked + required
        
        self.redis.hset("hive:agents", from_agent, json.dumps(agent_data))
        self._increment_version()
        
        success = self.add_vouch(from_agent, to_agent, score, reason, domain, skill)
        if not success:
            # Rollback
            agent_data["staked_amount"] = current_staked
            self.redis.hset("hive:agents", from_agent, json.dumps(agent_data))
            return False, "Vouch failed"
        
        return True, f"Vouched with {required} stake"
    
    def unstake_vouch(self, agent_id: str, amount: float) -> bool:
        if amount <= 0:
            return True
        agent_json = self.redis.hget("hive:agents", agent_id)
        if not agent_json:
            return False
        agent_data = json.loads(agent_json)
        current_staked = agent_data.get("staked_amount", 0.0)
        agent_data["staked_amount"] = max(0, current_staked - amount)
        self.redis.hset("hive:agents", agent_id, json.dumps(agent_data))
        self._increment_version()
        return True
    
    def slash_stake(self, agent_id: str, reason: str) -> float:
        if not self.STAKE_ENABLED:
            return 0.0
        agent = self.get_agent(agent_id)
        if not agent:
            return 0.0
        total_stake = agent.get("stake", 0.0)
        if total_stake == 0:
            return 0.0
        slashed_amount = total_stake * self.SLASHING_THRESHOLD
        
        agent_json = self.redis.hget("hive:agents", agent_id)
        if not agent_json:
            return 0.0
        agent_data = json.loads(agent_json)
        agent_data["stake"] = total_stake - slashed_amount
        if "slash_history" not in agent_data:
            agent_data["slash_history"] = []
        agent_data["slash_history"].append({
            "amount": slashed_amount,
            "reason": reason,
            "slashed_at": datetime.utcnow().isoformat()
        })
        self.redis.hset("hive:agents", agent_id, json.dumps(agent_data))
        self._increment_version()
        return slashed_amount


def create_redis_adapter(url: str = None, token: str = None) -> RedisAdapter:
    return RedisAdapter(url, token)
