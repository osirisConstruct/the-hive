import sys
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from typing import List, Dict, Any

# Add parent to path to allow imports from core and storage_adapters
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.swarm_governance import SwarmGovernance, create_swarm
from core.identity_manager import IdentityManager
from api.models import AgentOnboardRequest, VouchRequest, ProposalRequest, VoteRequest, StakeRequest, DIDCreateRequest, KeyRotationRequest
from api.middleware import add_rate_limiting
from api.metrics import get_metrics_collector, metrics_middleware

app = FastAPI(title="The Hive Swarm API", version="0.1.0")

# Add rate limiting middleware
add_rate_limiting(app)

# Add metrics middleware
app.middleware("http")(metrics_middleware)

# Auto-detect Redis if environment variables are set
redis_url = os.environ.get("UPSTASH_REDIS_REST_URL")
redis_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

print(f"[The Hive] Redis env check: URL={redis_url is not None}, TOKEN={redis_token is not None}")
if redis_url:
    print(f"[The Hive] Redis URL (masked): {redis_url[:30]}...")

if redis_url and redis_token:
    try:
        from storage_adapters.redis_adapter import RedisAdapter
        adapter = RedisAdapter(url=redis_url, token=redis_token)
        swarm = SwarmGovernance(adapter)
        print("[The Hive] Using Redis adapter for persistence")
    except Exception as e:
        print(f"[The Hive] Redis connection failed: {e}, falling back to JSONAdapter")
        swarm = create_swarm()
else:
    swarm = create_swarm()
    print("[The Hive] Using JSONAdapter (Render disk)")

@app.get("/health")
def get_health():
    """Get swarm and API health."""
    return swarm.get_swarm_health()

@app.get("/rate-limits")
def get_rate_limits():
    """Get current rate limit configuration and usage."""
    from api.middleware import get_rate_limiter
    limiter = get_rate_limiter()
    return {
        "limits": limiter.get_limits(),
        "message": "Rate limiting is active"
    }

@app.get("/metrics")
def get_metrics():
    """Get Prometheus-format metrics."""
    collector = get_metrics_collector()
    return collector.generate_prometheus()

@app.get("/metrics/summary")
def get_metrics_summary():
    """Get metrics summary as JSON."""
    collector = get_metrics_collector()
    return collector.get_summary()

# ---------- AGENT ENDPOINTS ----------

@app.post("/agents/onboard", status_code=201)
def onboard_agent(req: AgentOnboardRequest):
    """Register a new agent."""
    success = swarm.onboard_agent(
        agent_id=req.agent_id,
        name=req.name,
        description=req.description,
        public_key=req.public_key,
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
        req.from_agent,
        req.to_agent,
        req.score,
        req.reason,
        domain=req.domain,
        skill=req.skill,
        signature=req.signature
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
        code_diff_hash=req.code_diff_hash,
        signature=req.signature
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
        reason=req.reason,
        signature=req.signature
    )
    if not success:
        raise HTTPException(status_code=400, detail="Vote failed (check proposal state and agent permissions)")
    return {"message": "Vote recorded"}

@app.post("/stake/{agent_id}/slash")
def slash_agent(agent_id: str, reason: str):
    """Slash agent's stake (Audit/Governance action)."""
    amount_slashed = swarm.slash_stake(agent_id, reason)
    if amount_slashed == 0:
        raise HTTPException(status_code=400, detail="Slash failed (agent may have no stake or system disabled)")
    return {"message": f"Slashed {amount_slashed} from {agent_id}", "reason": reason}

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

# ---------- IDENTITY ENDPOINTS (Phase 3.1) ----------

@app.post("/identity/create", status_code=201)
def create_identity(req: DIDCreateRequest):
    """Create a new decentralized identity for an agent."""
    identity = IdentityManager.create_identity(req.agent_id)
    
    # Store the DID Document
    swarm.adapter.store_did_document(identity["did"], identity["did_document"])
    
    # Link the DID to the agent if they exist
    swarm.adapter.link_did_to_agent(req.agent_id, identity["did"])
    
    return {
        "did": identity["did"],
        "public_key": identity["public_key"],
        "private_key": identity["private_key"],
        "did_document": identity["did_document"],
        "message": f"Identity created for {req.agent_id}"
    }

@app.get("/identity/{did:path}")
def resolve_did(did: str):
    """Resolve a DID to its DID Document."""
    doc = swarm.adapter.get_did_document(did)
    if not doc:
        raise HTTPException(status_code=404, detail="DID not found")
    return doc

@app.post("/identity/rotate")
def rotate_key(req: KeyRotationRequest):
    """Rotate the cryptographic key for a DID."""
    doc = swarm.adapter.get_did_document(req.did)
    if not doc:
        raise HTTPException(status_code=404, detail="DID not found")
    
    try:
        result = IdentityManager.rotate_key(doc, req.old_private_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Key rotation failed: {str(e)}")
    
    # Update the DID Document
    swarm.adapter.update_did_document(req.did, result["did_document"])
    
    # Update the agent's public key in the registry
    agent_id = doc.get("metadata", {}).get("agent_id")
    if agent_id:
        agent = swarm.get_agent(agent_id)
        if agent:
            for attempt in range(3):
                try:
                    registry, version = swarm.adapter._read_with_version(swarm.adapter.registry_file)
                    registry["agents"][agent_id]["public_key"] = result["new_public_key"]
                    swarm.adapter._conditional_write(swarm.adapter.registry_file, registry, version)
                    break
                except:
                    pass
    
    return {
        "message": "Key rotated successfully",
        "new_public_key": result["new_public_key"],
        "new_private_key": result["new_private_key"],
        "rotation_proof": result["rotation_proof"]
    }
