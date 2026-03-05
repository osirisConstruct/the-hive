"""
The Hive - Redis Adapter
Uses Upstash Redis for persistent storage
"""

import json
from typing import Any, Dict, List, Optional

try:
    from upstash_redis import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisAdapter:
    """Redis storage adapter for The Hive swarm governance."""
    
    AGENTS_KEY = "hive:agents"
    ATTESTATIONS_KEY = "hive:attestations"
    PROPOSALS_KEY = "hive:proposals"
    DID_DOCS_KEY = "hive:did_docs"
    VERSION_KEY = "hive:version"
    
    def __init__(self, url: str = None, token: str = None):
        if not REDIS_AVAILABLE:
            raise ImportError("upstash-redis not installed: pip install upstash-redis")
        
        if url and token:
            self.redis = Redis(url=url, token=token)
        else:
            # Try environment variables
            import os
            url = os.environ.get("UPSTASH_REDIS_REST_URL")
            token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
            if not url or not token:
                raise ValueError("Provide UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN")
            self.redis = Redis(url=url, token=token)
        
        # Initialize version
        if not self.redis.exists(self.VERSION_KEY):
            self.redis.set(self.VERSION_KEY, "1")
    
    def _get_hash(self, key: str) -> Dict:
        """Get all fields from a hash."""
        data = self.redis.hgetall(key)
        if not data:
            return {}
        # Decode bytes to string
        return {k: v for k, v in data.items()}
    
    def _set_hash(self, key: str, data: Dict) -> None:
        """Set all fields in a hash."""
        if data:
            # upstash-redis uses hset(key, field, value)
            for field, value in data.items():
                str_value = value if isinstance(value, str) else str(value)
                self.redis.hset(key, field, str_value)
    
    # --- Agents ---
    def get_all_agents(self) -> Dict:
        return self._get_hash(self.AGENTS_KEY)
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        agents = self.get_all_agents()
        return agents.get(agent_id)
    
    def save_agent(self, agent_id: str, agent_data: Dict) -> None:
        agents = self.get_all_agents()
        agents[agent_id] = json.dumps(agent_data)
        self._set_hash(self.AGENTS_KEY, agents)
    
    # --- Attestations ---
    def get_all_attestations(self) -> Dict:
        return self._get_hash(self.ATTESTATIONS_KEY)
    
    def save_attestation(self, attestor_id: str, attestation_data: Dict) -> None:
        atts = self.get_all_attestations()
        atts[attestor_id] = json.dumps(attestation_data)
        self._set_hash(self.ATTESTATIONS_KEY, atts)
    
    # --- Proposals ---
    def get_all_proposals(self) -> Dict:
        return self._get_hash(self.PROPOSALS_KEY)
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        props = self.get_all_proposals()
        data = props.get(proposal_id)
        if data:
            return json.loads(data)
        return None
    
    def save_proposal(self, proposal_id: str, proposal_data: Dict) -> None:
        props = self.get_all_proposals()
        props[proposal_id] = json.dumps(proposal_data)
        self._set_hash(self.PROPOSALS_KEY, props)
    
    # --- DID Documents ---
    def get_all_did_documents(self) -> Dict:
        return self._get_hash(self.DID_DOCS_KEY)
    
    def get_did_document(self, did: str) -> Optional[Dict]:
        docs = self.get_all_did_documents()
        data = docs.get(did)
        if data:
            return json.loads(data)
        return None
    
    def save_did_document(self, did: str, doc_data: Dict) -> None:
        docs = self.get_all_did_documents()
        docs[did] = json.dumps(doc_data)
        self._set_hash(self.DID_DOCS_KEY, docs)


def create_redis_adapter(url: str = None, token: str = None) -> RedisAdapter:
    """Create a Redis adapter."""
    return RedisAdapter(url, token)
