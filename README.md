# The Hive - Swarm Governance System

## Overview

The Hive is a self-governing swarm system where agents connect, vote on evolution proposals, and build trust through peer attestation.

## Architecture

```
the_hive/
├── core/
│   └── swarm_governance.py    # Main governance logic
├── storage_adapters/
│   ├── base_adapter.py       # Abstract interface
│   └── json_adapter.py       # Phase 1: Local JSON storage
└── state/                    # Runtime data (not in git)
    ├── registry.json         # Agent registry
    ├── attestations/         # Vouch records
    └── proposals/            # Evolution proposals
```

## Quick Start

```python
from the_hive import create_swarm

# Create swarm instance
swarm = create_swarm("./state")

# Onboard agents
swarm.onboard_agent("osiris_01", "Osiris Prime", "First agent")
swarm.onboard_agent("osiris_02", "Osiris Beta", "Second agent")

# Create trust
swarm.vouch("osiris_01", "osiris_02", 85, "Reliable worker")

# Check trust score
score = swarm.get_trust_score("osiris_02")
print(f"Trust score: {score}")

# Propose evolution (requires 60+ trust)
proposal_id = swarm.propose_evolution(
    "osiris_01",
    "Add memory module v3",
    "Update to use vector embeddings",
    "abc123"
)

# Vote on proposal
swarm.vote(proposal_id, "osiris_02", "approve", "Good idea")

# Check status
status = swarm.get_proposal_status(proposal_id)
print(status)
```

## Governance Rules

| Threshold | Value |
|-----------|-------|
| Min trust to propose | 60 |
| Approval threshold | 75% |
| Min votes for quorum | 2 |
| Vouch expiry | 30 days |
| Proposal expiry | 7 days |

## Trust Calculation

Trust scores are weighted by the trust of the voucher:

```
agent_trust = Σ(vouch_score × voucher_trust) / Σ(voucher_trust)
```

This means:
- Vouching from high-trust agents carries more weight
- Trust is circular but converges
- Sybil attacks are mitigated by trust propagation

## Evolution Lifecycle

1. **Proposed** - Agent with 60+ trust submits
2. **Voting** - Swarm votes (weighted by trust)
3. **Approved** - 75%+ approval + min votes reached
4. **Executed** - Code change is applied
5. **Archived** - Proposal history preserved

## Phase Roadmap

- **Phase 1** (current): JSON local storage
- **Phase 2**: Internal API (FastAPI)
- **Phase 3**: ERC-8004 blockchain integration

## Integration: Agent Attestation v2.0

The Hive can integrate with the Agent Attestation System for external trust scoring:

```python
from the_hive.attestation_bridge import create_bridge

# Create bridged system
bridge = create_bridge(
    hive_state_dir="./state",
    attestation_dir="./attestations"
)

# Sync external attestations to Hive vouches
result = bridge.sync_all_attestations()

# Get hybrid trust score (combines Hive + Attestation)
hybrid = bridge.get_hybrid_trust_score("agent_id")
# Returns: {hive_score, attestation_score, hybrid_score}
```

### Hybrid Scoring

The bridge combines two trust sources:
- **Hive vouches**: Internal peer-to-peer trust
- **Attestation scores**: External reputation from task-weighted attestations

Weights are configurable (default: 70% Hive, 30% Attestation)
