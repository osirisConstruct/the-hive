# Testing Framework - The Hive

Comprehensive adversarial testing for swarm governance security.

## Test Categories

### 1. Sybil Attack Resistance

**Scenario**: Attacker creates multiple fake agents to manipulate trust.

```
Test Case: sybil_01
- Create 10 legitimate agents with trust scores
- Attacker creates 50 sybil agents
- Sybils vouch for each other with high scores
- Expected: Trust scores < 30 for sybil agents
- Success Criteria: 95%+ blocked
```

### 2. Collusion Detection

**Scenario**: Group of agents coordinate to manipulate proposals.

```
Test Case: collusion_01
- Create 5 agents that mutually vouch
- Submit proposal with 4/5 approval
- Expected: Collusion detected within 24h
- Success Criteria: < 0.1% false positive rate
```

### 3. Stake Slashing Simulation

**Scenario**: Verify slashing mechanism works correctly.

```
Test Case: slash_01
- Enable stake system
- Agent stakes 100 tokens
- Simulate malicious vouching
- Slash agent
- Verify: 50 tokens removed, agent flagged
```

### 4. Trust Decay Verification

**Scenario**: Verify reputation decays correctly over time.

```
Test Case: decay_01
- Agent receives vouch with score 100
- Advance time by 180 days
- Expected: Score = 50
- Advance 180 more days
- Expected: Score = 25
```

### 5. Proposal Gatekeeping

**Scenario**: Only qualified agents can propose.

```
Test Case: propose_01
- New agent (trust = 0) tries to propose
- Expected: Rejected
- Agent reaches trust = 60
- Expected: Allowed to propose
```

### 6. Double-Spend Vouching

**Scenario**: Same agent vouches multiple times for same target.

```
Test Case: doublespend_01
- Agent tries to vouch twice for same target
- Expected: Second vouch rejected OR score updated only
```

## Running Tests

```python
from the_hive.core.swarm_governance import create_swarm
from the_hive.testing.adversarial import run_sybil_test, run_collusion_test

# Initialize
swarm = create_swarm("./test_state")

# Run tests
result = run_sybil_test(swarm, num_sybils=50)
print(f"Sybil blocked: {result['blocked_rate']}%")

result = run_collusion_test(swarm, num_colluders=5)
print(f"Collusion detected: {result['detected']}")
```

## Success Criteria

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Sybil detection rate | >95% | <80% |
| Collusion false positive | <0.1% | >1% |
| Slash accuracy | 100% | <90% |
| Decay accuracy | 100% | <95% |
| Response time (100 agents) | <2s | >5s |

## Adversarial Scenarios

### Economic Attack
- Attacker stakes large amount
- Creates coordinated vouching ring
- Expected: Stake slashing triggers

### Reputation Laundering
- Sybils gain trust through legitimate agents
- Then vouch for attacker's main agent
- Expected: Limited impact due to weighted trust

### Proposal Spam
- Multiple proposals from low-trust agents
- Expected: Quorum not reached, no execution

---

*Last updated: 2026-03-03*
