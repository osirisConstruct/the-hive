import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from typing import List, Dict, Any

# Add parent to path to allow imports from core and storage_adapters
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.swarm_governance import create_swarm
from api.models import AgentOnboardRequest, VouchRequest, ProposalRequest, VoteRequest, StakeRequest

app = FastAPI(title="The Hive Swarm API", version="0.1.0")

# Initialize swarm (using a default state directory relative to the project)
STATE_DIR = str(Path(__file__).parent.parent / "state")
swarm = create_swarm(STATE_DIR)

@app.get("/health")
def get_health():
    """Get swarm and API health."""
    return swarm.get_swarm_health()

# ---------- AGENT ENDPOINTS ----------

@app.post("/agents/onboard", status_code=201)
def onboard_agent(req: AgentOnboardRequest):
    """Register a new agent."""
    success = swarm.onboard_agent(
        agent_id=req.agent_id,
        name=req.name,
        description=req.description,
        metadata=req.metadata
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to onboard agent (possibly already exists)")
    return {"message": f"Agent {req.agent_id} onboarded successfully"}

@app.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    """Get specific agent info."""
    agent = swarm.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.get("/agents")
def list_agents():
    """List all agents in the swarm."""
    return swarm.get_all_agents()

# ---------- TRUST ENDPOINTS ----------

@app.post("/trust/vouch")
def vouch_for_agent(req: VouchRequest):
    """Submit a peer vouch."""
    success = swarm.vouch(
        from_agent=req.from_agent,
        to_agent=req.to_agent,
        score=req.score,
        reason=req.reason,
        domain=req.domain,
        skill=req.skill
    )
    if not success:
        raise HTTPException(status_code=400, detail="Vouch failed (check agent IDs and permissions)")
    return {"message": "Vouch recorded"}

@app.get("/trust/{agent_id}")
def get_trust(agent_id: str):
    """Get agent's overall trust score."""
    score = swarm.get_trust_score(agent_id)
    return {"agent_id": agent_id, "score": score}

@app.get("/trust/{agent_id}/details")
def get_trust_details(agent_id: str):
    """Get detailed trust metrics (domain-specific and graph properties)."""
    return {
        "domains": swarm.get_trust_by_domain(agent_id),
        "graph": swarm.get_graph_properties(agent_id),
        "suspicious": swarm.check_suspicious_patterns(agent_id)
    }

# ---------- PROPOSAL ENDPOINTS ----------

@app.post("/proposals", status_code=201)
def create_proposal(req: ProposalRequest):
    """Create a new evolution proposal."""
    result = swarm.propose_evolution(
        proposer_id=req.proposer_id,
        title=req.title,
        description=req.description,
        code_diff_hash=req.code_diff_hash
    )
    if result.startswith("Failed"):
        raise HTTPException(status_code=403, detail=result)
    return {"message": result}

@app.get("/proposals/active")
def list_active_proposals():
    """List all active proposals."""
    return swarm.get_active_proposals()

@app.get("/proposals/{proposal_id}")
def get_proposal_status(proposal_id: str):
    """Get status and details of a specific proposal."""
    status = swarm.get_proposal_status(proposal_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status

@app.post("/proposals/{proposal_id}/vote")
def vote_on_proposal(proposal_id: str, req: VoteRequest):
    """Submit a vote on an active proposal."""
    success = swarm.vote(
        proposal_id=proposal_id,
        voter_id=req.voter_id,
        vote=req.vote,
        reason=req.reason
    )
    if not success:
        raise HTTPException(status_code=400, detail="Vote failed (check proposal state and agent permissions)")
    return {"message": "Vote recorded"}

# ---------- STAKE (Optional) ----------

@app.post("/stake/{agent_id}/enable")
def enable_stake():
    swarm.enable_stake()
    return {"message": "Stake system enabled"}

@app.post("/stake/{agent_id}/add")
def add_stake(agent_id: str, req: StakeRequest):
    success = swarm.add_stake(agent_id, req.amount)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add stake")
    return {"message": f"Added {req.amount} stake to {agent_id}"}
