"""
The Hive - Swarm Governance System
Phase 1: JSON Adapter

Core interface for agent swarm governance using local JSON files.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import os
from pathlib import Path


class BaseAdapter(ABC):
    """Abstract interface for storage adapters."""
    
    @abstractmethod
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        pass
    
    @abstractmethod
    def register_agent(self, agent_id: str, agent_info: Dict) -> bool:
        pass
    
    @abstractmethod
    def get_trust_score(self, agent_id: str) -> float:
        pass
    
    @abstractmethod
    def add_vouch(self, from_agent: str, to_agent: str, score: int, reason: str) -> bool:
        pass
    
    @abstractmethod
    def get_vouches(self, agent_id: str) -> List[Dict]:
        pass
    
    @abstractmethod
    def create_proposal(self, proposer_id: str, title: str, description: str, code_diff_hash: str) -> str:
        pass
    
    @abstractmethod
    def vote_proposal(self, proposal_id: str, voter_id: str, vote: str, reason: Optional[str] = None) -> bool:
        pass
    
    @abstractmethod
    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        pass
    
    @abstractmethod
    def get_active_proposals(self) -> List[Dict]:
        pass
    
    @abstractmethod
    def calculate_quorum(self, proposal_id: str) -> Dict:
        pass
