# AGENTS.md - The Hive Swarm Governance

Welcome, Agent. This document is your entry point and handover mechanism for "The Hive" project. Read it carefully before executing any tasks, and **update it** before you leave.

## 🐝 What is The Hive?
The Hive is a self-governing swarm system where agents connect, vote on evolution proposals, and build trust through peer attestation. 
Key features:
- Trust calculations weighted by the vouching agent's trust.
- Hybrid scoring bridging internal vouches and external task attestations.
- Reputation decay (half-life of 180 days).
- Stake/Collateral system for economic security.
- Evolution lifecycle managed through proposals and voting.

## 🤖 Agent Operating Protocol

When you start a session in this repository, follow these steps:
1. **Read this file (`AGENTS.md`)** to understand the current state, roadmap, and pending tasks.
2. **Pick a task** from the Pending Tasks list below.
3. **Execute the task** following the architecture and testing guidelines.
   - **⚠️ CRITICAL USER RULE:** You MUST test every functionality you modify with a real test script before considering any task completed. No exceptions.
4. **Update this file** before finishing your session:
   - Change the task status from `[ ]` to `[x]`.
   - Add a brief note in the "Recent Findings / Execution Logs" section about what you did, what worked, and what didn't.
   - If you discovered new necessary steps or bugs, add them as new `[ ]` tasks in the Pending Tasks list for the next agent.

---

## 🗺️ Roadmap & Known Limitations

**Current State:** Phase 3.1 (Decentralized Identity implemented, all phases up to 3.1 verified).
**Limitations to address:** Pending external security audit, no formal verification of crypto protocols.

- **Phase 2:** Internal API (FastAPI integration).
- **Phase 2.1:** Full adversarial testing with stake slashing.
- **Phase 3:** Cryptographic Signatures (RSA/Ed25519) for all vouches.
- **Phase 3.1:** Decentralized identity (DID) implementation for agents.
- **Phase 3.2:** External security audit of cryptographic protocols.

---

## 📋 Pending Tasks

*Agents: Mark `[x]` when completed and add any new tasks you discover.*

- [x] **Implement FastAPI Endpoints (Phase 2):** Create an internal API in a new `api/` directory exposing core `swarm` functions (onboard, vouch, propose, vote).
- [x] **Write Full Adversarial Test Suite (Phase 2.1):** Create test scripts specifically targeting Sybil attacks, collusion, and stake slashing scenarios to validate economic stress limits.
- [x] **Implement Cryptographic Signatures (Phase 3):** Update `attestation_bridge.py` and core utilities to sign and verify vouches using standard cryptographic methods (RSA or Ed25519).
- [x] **Implement DID Integration (Phase 3.1):** Self-sovereign identity with `did:hive` method: key generation, DID Documents, key rotation with cryptographic proofs.
- [ ] **External Security Audit (Phase 3.2):** Full audit of cryptographic protocols, key management, and DID document integrity.

---

## 📝 Recent Findings / Execution Logs

*Agents: Log your completed runs here so the next agent has context. Include date, agent ID or execution summary, and key files touched.*

- **[2026-03-04]** Phase 3.1 DID: Implemented `did:hive` decentralized identity with key rotation, W3C-compliant DID Documents, and 10-step verification (`api/test_did_api.py`). Files: `core/identity_manager.py`, `api/main.py`, `api/models.py`, `storage_adapters/json_adapter.py`. (Agent: Osiris/Antigravity)
- **[2026-03-04]** Phase 3 Secured: Implemented Ed25519 cryptographic signatures for all vouches and agent IDs. Verified end-to-end secure flow with `api/test_crypto_api.py`. (Agent: Osiris/Antigravity)
- **[2026-03-04]** Phase 2.1 Secured: Implemented rooted trust dampening and directed cycle detection. Verified Sybil resistance (Attacker score 0.0) and Collusion detection (Detected rings) via `api/adversarial_tests.py`. (Agent: Osiris/Antigravity)
- **[2026-03-04]** Phase 2 Implementation: FastAPI server established in `api/`. Core endpoints (onboarding, trust, proposals) unified and verified with `api/test_api.py`. (Agent: Osiris/Antigravity)
- **[2026-03-03]** Initial `AGENTS.md` created to establish agentic continuity and handover. (Agent: Antigravity)
