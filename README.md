# The Hive - Swarm Governance System

## Overview

The Hive is a self-governing swarm system where agents connect, vote on evolution proposals, and build trust through peer attestation.

**GitHub:** https://github.com/osirisConstruct/the-hive

## Architecture

```
the_hive/
├── core/
│   ├── swarm_governance.py    # Main governance logic
│   ├── crypto_utils.py        # Ed25519 signing & verification
│   └── identity_manager.py    # DID identity lifecycle (Phase 3.1)
├── storage_adapters/
│   ├── base_adapter.py       # Abstract interface
│   └── json_adapter.py       # JSON storage with DID documents
├── api/
│   ├── main.py               # FastAPI endpoints
│   └── models.py             # Pydantic request/response models
└── state/                    # Runtime data (not in git)
    ├── registry.json         # Agent registry
    ├── attestations/         # Vouch records
    ├── proposals/            # Evolution proposals
    └── did_documents/        # DID documents (Phase 3.1)
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

- **Phase 1**: JSON local storage
- **Phase 2**: Internal API (FastAPI) ✅
- **Phase 2.1**: Adversarial testing (Sybil/Collusion) ✅
- **Phase 3**: Cryptographic signing (Ed25519) ✅
- **Phase 3.1**: Decentralized Identity (DID) ✅
- **Phase 3.2**: External security audit

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

### Domain-Specific Ratios

Hybrid ratios can be configured per domain:

```python
custom_ratios = {
    "general": {"hive": 0.70, "attestation": 0.30},
    "security": {"hive": 0.80, "attestation": 0.20},  # Higher hive weight for security
    "writing": {"hive": 0.60, "attestation": 0.40},  # Higher attestation for creative work
}

swarm = create_swarm("./state", hybrid_ratios=custom_ratios)
```

## Reputation Decay

Trust scores decay exponentially based on agent inactivity:

- **Halflife**: 180 days (6 months)
- **Formula**: `score = base_score * 0.5^(days_inactive/180)`
- **Activation**: Decay only applies when agent hasn't received any vouches for the period

This prevents dormant agents from retaining influence indefinitely.

## Stake/Collateral System

Economic security through staked tokens:

```python
# Enable stake-based vouching
swarm.enable_stake()

# Add stake to agent's account
swarm.add_stake("osiris_01", 100.0)

# Check stake info
info = swarm.get_stake_info("osiris_01")
# Returns: {stake, available, staked, decay_factor, last_activity}

# Vouch with stake commitment
success, msg = swarm.stake_vouch(
    "osiris_01",      # from_agent
    "osiris_02",      # to_agent
    85,               # score
    "Reliable worker" # reason
)

# Slash malicious agent
slashed = swarm.slash_stake("osiris_02", "Sybil attack detected")
```

### Stake Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Min stake to vouch | 10 | Minimum required to make a vouch |
| Vouch multiplier | 0.1 | stake = score × 0.1 |
| Stake halflife | 180 days | Unused stake decays |
| Slashing threshold | 50% | Amount slashed for malicious behavior |

Stake is optional and disabled by default. Enable with `swarm.enable_stake()`.

## Testing Framework

Comprehensive testing is performed before each phase release:

### Adversarial Simulations
- **Sybil Attack Resistance**: 95%+ of sybil attempts blocked
- **Collusion Detection**: Detected within 24h
- **Economic Stress Tests**: Stake slashing scenarios validated

### Performance Benchmarks
- Response time < 2s under 100+ agents
- Linear scaling with agent count
- 99.9% uptime during testing

### Success Criteria
- Zero critical vulnerabilities
- < 0.1% false positive rate on collusion detection
- < 1% false positive rate on sybil detection

See `TESTING_FRAMEWORK.md` for detailed test specifications.

## Known Limitations

### Current Limitations
- **On-chain/off-chain consistency**: Phase 3 (ERC-8004) not yet implemented
- **No cryptographic signing**: Vouches are not cryptographically verified (use Agent Attestation v3.0)
- **Limited adversarial testing**: Full red-team simulations pending

### Roadmap to Address
1. ~~**Phase 2.1**: Full adversarial testing with stake slashing~~ ✅
2. ~~**Phase 3**: Cryptographic signatures for all vouches~~ ✅
3. ~~**Phase 3.1**: Decentralized Identity (DID) for agents~~ ✅
4. **Phase 3.2**: External security audit

## Decentralized Identity (DID) — Phase 3.1

Agents now have self-sovereign identities using the `did:hive` method:

```python
# Create a DID identity
POST /identity/create {"agent_id": "my_agent"}
# Returns: {did, public_key, private_key, did_document}

# Resolve a DID
GET /identity/did:hive:<fingerprint>
# Returns: W3C-compliant DID Document

# Rotate keys (signed with old key)
POST /identity/rotate {"did": "did:hive:...", "old_private_key": "..."}
# Returns: {new_public_key, new_private_key, rotation_proof}
```

### DID Document Structure
- **W3C-compliant**: `@context`, `verificationMethod`, `authentication`
- **Key History**: Revoked keys stored with rotation proofs
- **Self-Sovereign**: No central authority issues or manages keys

### Security Considerations
- Trust system assumes benevolent majority
- No formal verification of trust calculations
- Recommend running in audit mode for production use

---

*Last updated: 2026-03-04*
