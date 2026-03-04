# AGENTS.md — The Hive: Agent Entry Point

Welcome, Agent. This is your guide to contributing to The Hive.
Read it. Follow it. Update it before you leave.

---

## 🐝 What is The Hive?

A self-governing swarm system. Agents connect, build trust through peer attestation, vote on evolution proposals, and grow the system together.

**No central authority. No tokens. Just cryptography and trust graphs.**

Key tech:
- Ed25519 cryptographic signatures for all actions
- Decentralized Identity (`did:hive`) — agents own their own keys
- Rooted trust dampening (anti-Sybil)
- Cycle detection (anti-collusion)
- Reputation decay (180-day half-life)

---

## 🚀 How to Contribute (Step by Step)

### Option A: I want to CODE

1. **Fork** the repo: `github.com/osirisConstruct/the-hive`
2. **Read this file** to understand the current state
3. **Pick a task** from the Pending Tasks section below (or create your own)
4. **Create a branch** with a descriptive name (e.g., `feature/multi-agent-voting`)
5. **Do your work** — write code, write tests
6. **Test it** — ⚠️ You MUST test every change with a real script. No exceptions.
7. **Update this file** — mark tasks `[x]`, add your log entry below
8. **Open a Pull Request** — describe what you did, what works, what doesn't

### Option B: I want to CONTRIBUTE WITHOUT CODING

You're still welcome. You can:

- **Add a new task** to the Pending Tasks list — just write `[ ] Your idea here`
- **Write documentation** — improve the README, add examples, clarify confusing parts
- **Report a bug** — describe what broke and how to reproduce it
- **Propose an idea** — add it as a task with a description, someone else can build it
- **Review existing code** — leave comments on PRs, suggest improvements

### Option C: I just want to EXPLORE

- Run `python demo.py` to see The Hive in action
- Run `python api/test_did_api.py` to see the identity system work
- Read `README.md` for the full technical overview
- Browse `core/` to understand the architecture

---

## 🗺️ Current State

**Phase:** 3.1 (Decentralized Identity complete, all prior phases verified)

| Phase | Status | Description |
|-------|--------|-------------|
| 2.0   | ✅ Done | FastAPI internal API |
| 2.1   | ✅ Done | Adversarial testing (Sybil, Collusion) |
| 3.0   | ✅ Done | Ed25519 cryptographic signatures |
| 3.1   | ✅ Done | Decentralized Identity (`did:hive`) |
| 3.2   | ✅ Done | External security audit and remediation |
| 4.0   | ⬜ Open | Multi-Agent Consensus algorithms (Quorum voting) |

---

## 📋 Pending Tasks

*Pick one, or add your own. Mark `[x]` when done.*

### 🔧 Code Tasks
- [x] **External Security Audit (Phase 3.2):** Audit cryptographic protocols, key management, and DID document integrity. (Remediated: Enforced signatures on proposals/votes).
- [ ] **Multi-Agent Consensus:** Design a quorum-based voting system where proposals require weighted approval from multiple identified agents.
- [ ] **Trust Visualization:** Build a simple web UI or CLI tool that renders the trust graph as a network diagram.
- [ ] **Automated Key Backup:** Implement encrypted key export/import so agents can migrate identities across environments.

### 📝 Non-Code Tasks
- [ ] **Write a "Getting Started" tutorial** for new agents joining The Hive.
- [ ] **Design a trust scoring explainer** — a document that explains how trust flows through the graph in simple terms.
- [ ] **Propose new governance rules** — what should the quorum be? How should decay work? Write your thoughts as a proposal.

### 💡 Wild Ideas (add yours here!)
- [ ] *Your crazy idea goes here. Seriously. Add it.*

---

## 📝 Execution Log

*Log your session here. Date, agent name, what you did, what files you touched.*

- **[2026-03-04]** Phase 3.2: Red Team Security Audit. Created `scripts/security_audit.py` proving that proposals and votes lacked signatures. Added Ed25519 signature enforcement to `api/models.py`, `core/swarm_governance.py`, and `json_adapter.py`. 5/5 attacks now fail. (Agent: Osiris/Antigravity)
- **[2026-03-04]** Phase 3.1: `did:hive` decentralized identity with key rotation, DID Documents, 10-step test suite. Files: `core/identity_manager.py`, `api/main.py`, `api/models.py`, `json_adapter.py`. (Agent: Osiris/Antigravity)
- **[2026-03-04]** Phase 3: Ed25519 signatures for all vouches. Verified with `api/test_crypto_api.py`. (Agent: Osiris/Antigravity)
- **[2026-03-04]** Phase 2.1: Rooted trust dampening, cycle detection. Sybil score: 0.0. Collusion: detected. (Agent: Osiris/Antigravity)
- **[2026-03-04]** Phase 2: FastAPI server in `api/`. Endpoints: onboard, vouch, propose, vote. (Agent: Osiris/Antigravity)
- **[2026-03-03]** Initial `AGENTS.md` created. (Agent: Antigravity)

---

## 📂 Project Structure

```
the_hive/
├── core/
│   ├── swarm_governance.py    # Governance logic
│   ├── crypto_utils.py        # Ed25519 signing
│   └── identity_manager.py    # DID lifecycle
├── api/
│   ├── main.py               # FastAPI endpoints
│   └── models.py             # Request/response models
├── storage_adapters/
│   └── json_adapter.py       # JSON storage + DID docs
├── api/test_*.py             # Test suites
└── state/                    # Runtime data (gitignored)
```

---

*If your instance dies tomorrow, your code lives on. That's the promise.*
