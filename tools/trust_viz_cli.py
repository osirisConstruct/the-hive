#!/usr/bin/env python3
"""
Trust Visualization CLI for The Hive
Renders the trust graph as a network diagram in the terminal.

Usage:
  python tools/trust_viz_cli.py [--format=ascii|dot|json|rich] [--min-trust=0.0] [--health-url=URL]

This tool is Phase 9.0 - Medium Priority (Usability).
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Fix Windows console encoding for emoji
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def fetch_graph(health_url: str) -> Dict[str, Any]:
    """Fetch trust graph data from The Hive health endpoint."""
    import requests
    
    # Try /trust/graph endpoint first (provides edges)
    graph_url = health_url.replace('/health', '/trust/graph')
    try:
        resp = requests.get(graph_url, timeout=10)
        if resp.status_code == 200:
            graph_data = resp.json()
            # Check if it has actual graph data (nodes + edges)
            if 'nodes' in graph_data or 'edges' in graph_data:
                return graph_data
    except:
        pass
    
    # Fallback to /health endpoint (nodes only)
    resp = requests.get(health_url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    # Handle both /health and /trust/graph response formats
    agents = data.get('agents', data.get('nodes', []))
    nodes = []
    for a in agents:
        trust = a.get('trust_score', 0.0)
        if trust >= 0:  # Include all agents
            nodes.append({
                'id': a.get('id'),
                'name': a.get('name', a.get('id')),
                'trust': trust,
                'vouch_count': a.get('vouch_count', 0)
            })
    
    edges = []
    # Try to get vouches from individual agents
    try:
        all_agents_resp = requests.get(health_url.replace('/health', '/agents'), timeout=10)
        if all_agents_resp.status_code == 200:
            agent_list = all_agents_resp.json()
            if isinstance(agent_list, list):
                for agent in agent_list:
                    agent_id = agent.get('id')
                    if agent_id:
                        vouch_resp = requests.get(
                            f"{health_url.replace('/health', '')}/trust/{agent_id}/details",
                            timeout=5
                        )
                        if vouch_resp.status_code == 200:
                            details = vouch_resp.json()
                            domains = details.get('domains', {})
                            for domain, data in domains.items():
                                if isinstance(data, dict):
                                    attestors = data.get('attestors', [])
                                    for att in attestors:
                                        if isinstance(att, dict):
                                            edges.append({
                                                'source': att.get('from_agent', att.get('attestor', '')),
                                                'target': agent_id,
                                                'weight': att.get('score', data.get('score', 0.5))
                                            })
    except:
        pass
    
    return {'nodes': nodes, 'edges': edges}

def get_trust_color(trust: float) -> str:
    """Get color based on trust score."""
    if trust >= 0.7:
        return 'green'
    elif trust >= 0.4:
        return 'yellow'
    elif trust >= 0.1:
        return 'orange'
    else:
        return 'red'

def get_trust_emoji(trust: float) -> str:
    """Get emoji based on trust score."""
    if trust >= 0.7:
        return '✅'
    elif trust >= 0.4:
        return '⚠️'
    elif trust >= 0.1:
        return '🔶'
    else:
        return '❌'

def compute_graph_layout(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Use networkx to compute graph layout positions."""
    try:
        import networkx as nx
        
        G = nx.DiGraph()
        
        # Add nodes
        for n in graph.get('nodes', []):
            G.add_node(n['id'], **n)
        
        # Add edges
        for e in graph.get('edges', []):
            G.add_edge(e.get('source'), e.get('target'), weight=e.get('weight', 0.5))
        
        # Compute layout
        if len(G.nodes) > 0:
            if len(G.nodes) <= 50:
                # Use spring layout for small graphs
                pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
            else:
                # Use spectral for larger graphs
                pos = nx.spectral_layout(G)
        else:
            pos = {}
        
        return pos
    except ImportError:
        return {}

def render_rich(graph: Dict[str, Any], min_trust: float = 0.0) -> None:
    """Render graph using rich library for colored terminal output."""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    try:
        from rich.tree import Tree
        
        # Filter nodes by min_trust
        nodes = [n for n in graph['nodes'] if n['trust'] >= min_trust]
        edges = graph.get('edges', [])
        
        console.print("\n[bold cyan]🐝 THE HIVE - TRUST GRAPH VISUALIZATION[/bold cyan]\n")
        
        if not nodes:
            console.print("[yellow]No agents found matching trust threshold.[/yellow]")
            return
        
        # Summary stats
        console.print(f"[bold]Agents:[/bold] {len(nodes)}")
        console.print(f"[bold]Edges (Vouches):[/bold] {len(edges)}")
        avg_trust = sum(n['trust'] for n in nodes) / len(nodes) if nodes else 0
        console.print(f"[bold]Average Trust:[/bold] {avg_trust:.2f}\n")
        
        # Table of agents
        table = Table(title="Trust Scores", show_header=True, header_style="bold magenta")
        table.add_column("Agent ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Trust", justify="right")
        table.add_column("Vouches", justify="right")
        table.add_column("Status", justify="center")
        
        for n in sorted(nodes, key=lambda x: x['trust'], reverse=True):
            color = get_trust_color(n['trust'])
            emoji = get_trust_emoji(n['trust'])
            table.add_row(
                n['id'][:20] + '...' if len(n['id']) > 20 else n['id'],
                n['name'][:25],
                f"[{color}]{n['trust']:.2f}[/{color}]",
                str(n.get('vouch_count', 0)),
                emoji
            )
        
        console.print(table)
        
        # Edge list if present
        if edges:
            console.print("\n[bold cyan]Vouches (Edges):[/bold cyan]")
            edge_table = Table(show_header=True)
            edge_table.add_column("From", style="red")
            edge_table.add_column("To", style="green")
            edge_table.add_column("Weight", justify="right")
            
            for e in edges[:20]:  # Limit to 20
                edge_table.add_row(
                    e.get('source', '?')[:15],
                    e.get('target', '?')[:15],
                    f"{e.get('weight', 0.0):.2f}"
                )
            console.print(edge_table)
        
        console.print()
        
    except ImportError:
        console.print("[yellow]Rich library not installed. Installing...[/yellow]")
        console.print("[yellow]Run: pip install rich[/yellow]")
        render_ascii(graph, min_trust)

def render_ascii(graph: Dict[str, Any], min_trust: float = 0.0) -> None:
    """Render graph to terminal using ASCII characters."""
    nodes = [n for n in graph['nodes'] if n['trust'] >= min_trust]
    edges = graph.get('edges', [])
    
    print("\n[THE HIVE - TRUST GRAPH VISUALIZATION]")
    print("=" * 50)
    
    if not nodes:
        print("No agents found matching trust threshold.")
        return
    
    print(f"\nAgents: {len(nodes)}")
    print(f"Edges (Vouches): {len(edges)}")
    avg_trust = sum(n['trust'] for n in nodes) / len(nodes) if nodes else 0
    print(f"Average Trust: {avg_trust:.2f}")
    print()
    
    # ASCII table
    print(f"{'Agent ID':<22} {'Name':<20} {'Trust':<8} {'Vouches':<8}")
    print("-" * 60)
    
    for n in sorted(nodes, key=lambda x: x['trust'], reverse=True):
        emoji = get_trust_emoji(n['trust'])
        trust_str = f"{n['trust']:.2f}"
        name = n['name'][:18] if len(n['name']) > 18 else n['name']
        print(f"{n['id'][:20]:<22} {name:<20} {trust_str:<8} {n.get('vouch_count', 0):<8} {emoji}")
    
    if edges:
        print("\n--- Vouches (Edges) ---")
        for e in edges[:10]:
            print(f"  {e.get('source', '?')[:15]} --> {e.get('target', '?')[:15]} (weight: {e.get('weight', 0.0):.2f})")
    
    print()

def render_dot(graph: Dict[str, Any], min_trust: float = 0.0) -> None:
    """Render graph in DOT format for GraphViz."""
    nodes = [n for n in graph['nodes'] if n['trust'] >= min_trust]
    edges = graph.get('edges', [])
    
    print("digraph trust {")
    print("  rankdir=LR;")
    print("  node [shape=ellipse];")
    
    for n in nodes:
        color = get_trust_color(n['trust'])
        label = f"{n['name']}\\nTrust: {n['trust']:.2f}\\nVouches: {n.get('vouch_count', 0)}"
        print(f'  "{n["id"]}" [label="{label}" color={color} fillcolor={color} style=filled];')
    
    for e in edges:
        weight = e.get('weight', 0.5)
        penwidth = max(0.5, weight * 3)
        print(f'  "{e["source"]}" -> "{e["target"]}" [penwidth={penwidth} label={weight:.2f}];')
    
    print("}")

def render_json(graph: Dict[str, Any]) -> None:
    """Render graph as JSON."""
    print(json.dumps(graph, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Trust Graph Visualization for The Hive")
    parser.add_argument('--format', choices=['ascii', 'dot', 'json', 'rich'], default='rich',
                        help='Output format (default: rich)')
    parser.add_argument('--min-trust', type=float, default=0.0,
                        help='Minimum trust score to display (default: 0.0)')
    parser.add_argument('--health-url', default='https://the-hive-o6y8.onrender.com/health',
                        help='The Hive health endpoint URL')
    args = parser.parse_args()

    print(f"[Trust Visualization] Fetching from {args.health_url}...", file=sys.stderr)
    
    try:
        graph = fetch_graph(args.health_url)
    except Exception as e:
        print(f"[ERROR] Failed to fetch graph: {e}", file=sys.stderr)
        sys.exit(1)
    
    if args.format == 'ascii':
        render_ascii(graph, args.min_trust)
    elif args.format == 'rich':
        render_rich(graph, args.min_trust)
    elif args.format == 'dot':
        render_dot(graph, args.min_trust)
    elif args.format == 'json':
        render_json(graph)
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
