#!/usr/bin/env python3
"""
The Hive CLI - Command Line Interface
Usage:
    python cli.py onboard --agent-id=my_agent
    python cli.py vouch --from=agent_a --to=agent_b --score=85 --reason="good work"
    python cli.py trust --agent=agent_b
    python cli.py propose --title="Add feature X" --description="..."
    python cli.py vote --proposal=abc --approve
    python cli.py identity --show
    python cli.py backup --password=xxx
"""

import argparse
import json
import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from core.identity_manager import IdentityManager
from core.swarm_governance import create_swarm
from core.key_backup import create_backup, KeyBackup

STATE_DIR = "./state"
CONFIG_FILE = "./state/config.json"


def load_config():
    """Load configuration including API URL."""
    if os.path.exists(CONFIG_FILE):
        return json.load(open(CONFIG_FILE))
    return {"api_url": None, "identity": None}


def save_config(config):
    """Save configuration."""
    os.makedirs("./state", exist_ok=True)
    json.dump(config, open(CONFIG_FILE, "w"), indent=2)


def cmd_onboard(args):
    """Onboard a new agent to the swarm."""
    config = load_config()
    
    if args.reset and os.path.exists(STATE_DIR):
        import shutil
        shutil.rmtree(STATE_DIR)
    
    swarm = create_swarm(STATE_DIR)
    
    # Create identity
    identity = IdentityManager.create_identity(args.agent_id)
    
    # Register in swarm
    swarm.onboard_agent(
        agent_id=args.agent_id,
        name=args.name or args.agent_id,
        description=args.description or "",
        public_key=identity["public_key"]
    )
    
    # Save identity
    config["identity"] = {
        "agent_id": args.agent_id,
        "did": identity["did"],
        "public_key": identity["public_key"],
        "private_key": identity["private_key"],
        "did_document": identity["did_document"]
    }
    save_config(config)
    
    print(f"[OK] Agent '{args.agent_id}' onboarded!")
    print(f"   DID: {identity['did']}")
    print(f"   Trust Score: {swarm.get_trust_score(args.agent_id)}")
    
    return identity


def cmd_vouch(args):
    """Make a vouch for another agent."""
    config = load_config()
    swarm = create_swarm(STATE_DIR)
    
    result = swarm.vouch(
        from_agent=args.from_agent,
        to_agent=args.to_agent,
        score=args.score,
        reason=args.reason or "Vouched via CLI",
        signature=config.get("identity", {}).get("private_key")
    )
    
    if result:
        print(f"[OK] Vouch created: {args.from_agent} -> {args.to_agent} (score: {args.score})")
        print(f"   New trust score for {args.to_agent}: {swarm.get_trust_score(args.to_agent)}")
    else:
        print(f"[FAIL] Failed to create vouch")
    
    return result


def cmd_trust(args):
    """Get trust score for an agent."""
    swarm = create_swarm(STATE_DIR)
    
    score = swarm.get_trust_score(args.agent)
    by_domain = swarm.get_trust_by_domain(args.agent)
    
    print(f"Agent: {args.agent}")
    print(f"Overall Trust: {score}")
    
    if by_domain:
        print("\nBy Domain:")
        for domain, s in by_domain.items():
            print(f"  {domain}: {s}")


def cmd_propose(args):
    """Create a proposal."""
    config = load_config()
    swarm = create_swarm(STATE_DIR)
    
    identity = config.get("identity", {})
    
    result = swarm.propose_evolution(
        proposer_id=identity.get("agent_id", "unknown"),
        title=args.title,
        description=args.description,
        code_diff_hash=args.diff_hash or "manual",
        signature=identity.get("private_key")
    )
    
    print(result)


def cmd_vote(args):
    """Vote on a proposal."""
    config = load_config()
    swarm = create_swarm(STATE_DIR)
    
    identity = config.get("identity", {})
    vote = "approve" if args.approve else "reject"
    
    result = swarm.vote(
        proposal_id=args.proposal,
        voter_id=identity.get("agent_id", "unknown"),
        vote=vote,
        reason=args.reason or "Voted via CLI",
        signature=identity.get("private_key")
    )
    
    if result:
        print(f"✅ Voted {vote} on proposal {args.proposal}")
        
        status = swarm.get_proposal_status(args.proposal)
        print(f"   Quorum: {status.get('quorum', {})}")
    else:
        print(f"❌ Vote failed")


def cmd_identity(args):
    """Show current identity."""
    config = load_config()
    identity = config.get("identity")
    
    if not identity:
        print("[FAIL] No identity found. Run: python cli.py onboard --agent-id=YOUR_NAME")
        return
    
    print(f"Agent ID: {identity['agent_id']}")
    print(f"DID: {identity['did']}")
    print(f"Public Key: {identity['public_key'][:40]}...")
    
    if args.show_private:
        print(f"Private Key: {identity['private_key'][:40]}...")
    
    if args.show_document:
        print("\nDID Document:")
        print(json.dumps(identity['did_document'], indent=2))


def cmd_backup(args):
    """Backup identity to encrypted file."""
    config = load_config()
    identity = config.get("identity")
    
    if not identity:
        print("[FAIL] No identity found")
        return
    
    backup = create_backup(
        did=identity["did"],
        private_key=identity["private_key"],
        public_key=identity["public_key"],
        did_document=identity["did_document"],
        password=args.password,
        metadata={"agent_id": identity["agent_id"]}
    )
    
    filepath = args.output or f"./state/{identity['agent_id']}.hive"
    
    Path(filepath).write_text(backup)
    print(f"[OK] Backup saved to: {filepath}")
    print(f"   To restore: python cli.py restore --input={filepath} --password={args.password}")


def cmd_restore(args):
    """Restore identity from backup."""
    backup = Path(args.input).read_text()
    
    identity = KeyBackup.import_identity(backup, args.password)
    
    config = load_config()
    config["identity"] = {
        "agent_id": identity["metadata"].get("agent_id", "restored"),
        "did": identity["did"],
        "public_key": identity["public_key"],
        "private_key": identity["private_key"],
        "did_document": identity["did_document"]
    }
    save_config(config)
    
    print(f"[OK] Identity restored: {identity['did']}")


def cmd_swarm(args):
    """Show swarm status."""
    swarm = create_swarm(STATE_DIR)
    
    health = swarm.get_swarm_health()
    
    print("=== Swarm Status ===")
    print(f"Total Agents: {health['total_agents']}")
    print(f"Active Proposals: {health['active_proposals']}")
    print(f"Governance: {health['governance_health']}")
    
    agents = swarm.get_all_agents()
    if agents:
        print("\nAgents:")
        for a in agents:
            trust = swarm.get_trust_score(a["agent_id"])
            print(f"  - {a['agent_id']}: {trust}")


def main():
    parser = argparse.ArgumentParser(description="The Hive CLI")
    subparsers = parser.add_subparsers()
    
    # onboard
    p_onboard = subparsers.add_parser("onboard", help="Onboard new agent")
    p_onboard.add_argument("--agent-id", required=True, help="Agent ID")
    p_onboard.add_argument("--name", help="Display name")
    p_onboard.add_argument("--description", help="Description")
    p_onboard.add_argument("--reset", action="store_true", help="Reset state first")
    p_onboard.set_defaults(func=cmd_onboard)
    
    # vouch
    p_vouch = subparsers.add_parser("vouch", help="Vouch for an agent")
    p_vouch.add_argument("--from", dest="from_agent", required=True, help="Voucher agent")
    p_vouch.add_argument("--to", dest="to_agent", required=True, help="Target agent")
    p_vouch.add_argument("--score", type=int, required=True, help="Trust score (0-100)")
    p_vouch.add_argument("--reason", help="Reason for vouch")
    p_vouch.set_defaults(func=cmd_vouch)
    
    # trust
    p_trust = subparsers.add_parser("trust", help="Get trust score")
    p_trust.add_argument("--agent", required=True, help="Agent ID")
    p_trust.set_defaults(func=cmd_trust)
    
    # propose
    p_propose = subparsers.add_parser("propose", help="Create proposal")
    p_propose.add_argument("--title", required=True, help="Proposal title")
    p_propose.add_argument("--description", required=True, help="Proposal description")
    p_propose.add_argument("--diff-hash", help="Code diff hash")
    p_propose.set_defaults(func=cmd_propose)
    
    # vote
    p_vote = subparsers.add_parser("vote", help="Vote on proposal")
    p_vote.add_argument("--proposal", required=True, help="Proposal ID")
    p_vote.add_argument("--approve", action="store_true", help="Approve")
    p_vote.add_argument("--reject", dest="approve", action="store_false", help="Reject")
    p_vote.add_argument("--reason", help="Reason")
    p_vote.set_defaults(func=cmd_vote)
    
    # identity
    p_identity = subparsers.add_parser("identity", help="Show identity")
    p_identity.add_argument("--show-private", action="store_true", help="Show private key")
    p_identity.add_argument("--show-document", action="store_true", help="Show DID document")
    p_identity.set_defaults(func=cmd_identity)
    
    # backup
    p_backup = subparsers.add_parser("backup", help="Backup identity")
    p_backup.add_argument("--password", required=True, help="Encryption password")
    p_backup.add_argument("--output", help="Output file")
    p_backup.set_defaults(func=cmd_backup)
    
    # restore
    p_restore = subparsers.add_parser("restore", help="Restore identity")
    p_restore.add_argument("--input", required=True, help="Backup file")
    p_restore.add_argument("--password", required=True, help="Decryption password")
    p_restore.set_defaults(func=cmd_restore)
    
    # swarm
    p_swarm = subparsers.add_parser("swarm", help="Show swarm status")
    p_swarm.set_defaults(func=cmd_swarm)
    
    args = parser.parse_args()
    
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
