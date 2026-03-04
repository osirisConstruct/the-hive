from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class AgentOnboardRequest(BaseModel):
    agent_id: str
    name: str
    description: Optional[str] = ""
    metadata: Optional[Dict[str, Any]] = None

class VouchRequest(BaseModel):
    from_agent: str
    to_agent: str
    score: int = Field(..., ge=0, le=100)
    reason: str
    domain: Optional[str] = "general"
    skill: Optional[str] = None

class ProposalRequest(BaseModel):
    proposer_id: str
    title: str
    description: str
    code_diff_hash: str

class VoteRequest(BaseModel):
    voter_id: str
    vote: str = Field(..., pattern="^(approve|reject|abstain)$")
    reason: Optional[str] = None

class StakeRequest(BaseModel):
    amount: float = Field(..., gt=0)
