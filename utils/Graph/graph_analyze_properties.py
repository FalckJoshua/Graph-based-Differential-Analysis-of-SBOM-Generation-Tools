import json
import networkx as nx
from pathlib import Path
from collections import defaultdict
import os
import numpy as np
from typing import Dict, List, Any


def load_graph_from_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    G = nx.DiGraph() if data.get('directed', False) else nx.Graph()
    
    # First pass: create all nodes
    for node in data['nodes']:
        # Use purl as the primary identifier if available
        node_id = node.get('purl', node['id'])
        # Preserve all attributes
        attrs = {k: v for k, v in node.items() if k not in ['id', 'purl']}
        G.add_node(node_id, **attrs)
    
    # Second pass: create edges using the correct node identifiers
    for link in data['links']:
        # Find the source and target nodes
        source_node = next((n for n in data['nodes'] if n['id'] == link['source']), None)
        target_node = next((n for n in data['nodes'] if n['id'] == link['target']), None)
        
        if source_node and target_node:
            # Use purl as identifier if available, otherwise use original id
            source_id = source_node.get('purl', source_node['id'])
            target_id = target_node.get('purl', target_node['id'])
            
            # Add edge with all attributes
            attrs = {k: v for k, v in link.items() if k not in ['source', 'target']}
            G.add_edge(source_id, target_id, **attrs)
    
    # Debug printout: show all nodes and their outgoing edges
    print("\n[DEBUG] Graph Nodes and Outgoing Edges:")
    for node in G.nodes():
        print(f"Node: {node} -> {[n for n in G.successors(node)]}")
    print(f"[DEBUG] Total nodes: {G.number_of_nodes()}, Total edges: {G.number_of_edges()}")
    
    return G


def analyze_graph(G, graph_name=""):
    analysis = {}
    analysis['name'] = graph_name
    analysis['nodes'] = G.number_of_nodes()
    analysis['edges'] = G.number_of_edges()
    analysis['density'] = nx.density(G)

    # Node type analysis
    root_nodes = [n for n in G.nodes() if G.nodes[n].get('type') == 'root']
    dependency_nodes = [n for n in G.nodes() if G.nodes[n].get('type') == 'dependency']
    analysis['node_types'] = {
        'root_nodes': len(root_nodes),
        'dependency_nodes': len(dependency_nodes)
    }

    # Level analysis
    levels = [G.nodes[n].get('level', 0) for n in G.nodes()]
    analysis['max_level'] = max(levels) if levels else 0
    analysis['avg_level'] = sum(levels) / len(levels) if levels else 0
    analysis['level_std'] = np.std(levels) if levels else 0

    # Centrality
    degree_centrality = nx.degree_centrality(G)
    max_central_node = max(degree_centrality, key=degree_centrality.get)
    node_data = G.nodes[max_central_node]
    analysis['max_central_node'] = {
        'purl': max_central_node,
        'name': node_data.get('name', ''),
        'type': node_data.get('type', 'unknown'),
        'centrality': degree_centrality[max_central_node],
        'bom_ref': node_data.get('bom_ref', '')
    }

    # Depth analysis - Modified to handle different dependency structures
    if root_nodes:
        root = root_nodes[0]
        try:
            forward_lengths = nx.single_source_shortest_path_length(G, root)
            forward_depth = max(forward_lengths.values())
        except:
            forward_depth = 0
        try:
            reverse_lengths = nx.single_source_shortest_path_length(G.reverse(), root)
            reverse_depth = max(reverse_lengths.values())
        except:
            reverse_depth = 0
        analysis['depth'] = max(forward_depth, reverse_depth)
        analysis['root'] = root
        # Additional depth metrics
        if forward_lengths:
            analysis['avg_path_length'] = sum(forward_lengths.values()) / len(forward_lengths)
            analysis['path_length_std'] = np.std(list(forward_lengths.values()))
        else:
            analysis['avg_path_length'] = None
            analysis['path_length_std'] = None
        # Debug printout: show root, depth, and all shortest paths
        print(f"\n[DEBUG] Root node: {root}")
        print(f"[DEBUG] Calculated depth: {analysis['depth']}")
        print("[DEBUG] Shortest paths from root:")
        for target, length in forward_lengths.items():
            print(f"  {root} -> {target}: {length}")
    else:
        analysis['depth'] = None
        analysis['root'] = None
        analysis['avg_path_length'] = None
        analysis['path_length_std'] = None

    # Component type distribution
    component_types = defaultdict(int)
    for node in G.nodes():
        comp_type = G.nodes[node].get('type', 'unknown')
        component_types[comp_type] += 1
    analysis['component_type_distribution'] = dict(component_types)

    # Dependency chain analysis
    if root_nodes:
        root = root_nodes[0]
        try:
            paths = nx.single_source_shortest_path(G, root)
            max_path = max(paths.values(), key=len)
            analysis['longest_dependency_chain'] = {
                'length': len(max_path),
                'path': max_path
            }
        except:
            analysis['longest_dependency_chain'] = None
    else:
        analysis['longest_dependency_chain'] = None

    # Top dependencies (all)
    in_degree = dict(G.in_degree())
    top_deps = sorted([(n, d) for n, d in in_degree.items()], 
                     key=lambda x: x[1], reverse=True)
    analysis['top_dependencies'] = [
        {
            'purl': n,
            'name': G.nodes[n].get('name', ''),
            'type': G.nodes[n].get('type', 'unknown'),
            'level': G.nodes[n].get('level', 0),
            'dependents (incoming edges)': d,
            'centrality': degree_centrality[n],
            'bom_ref': G.nodes[n].get('bom_ref', '')
        } for n, d in top_deps if n in G.nodes
    ]

    return analysis


def find_all_graphs():
    """Find all graph JSON files in the project."""
    current_dir = Path(__file__).parent.parent.parent
    graph_files = []
    
    # Look in graphoutput directory
    graphoutput_dir = current_dir / 'graphoutput'
    if graphoutput_dir.exists():
        for json_file in graphoutput_dir.rglob('*_graph.json'):
            graph_files.append(json_file)
    
    return graph_files


def print_analysis_summary(analysis):
    """Print a formatted summary of the graph analysis."""
    print(f"\n{'='*80}")
    print(f"Analysis for: {analysis['name']}")
    print(f"{'='*80}")
    print(f"Nodes: {analysis['nodes']}")
    print(f"Edges: {analysis['edges']}")
    print(f"Density: {analysis['density']:.4f}")
    
    print("\nNode Types:")
    print(f"  Root Nodes: {analysis['node_types']['root_nodes']}")
    print(f"  Dependency Nodes: {analysis['node_types']['dependency_nodes']}")
    
    print("\nLevel Analysis:")
    print(f"  Maximum Level: {analysis['max_level']}")
    print(f"  Average Level: {analysis['avg_level']:.2f}")
    
    if analysis['root']:
        print(f"\nRoot node PURL: {analysis['root']}")
        print(f"Maximum depth: {analysis['depth']}")
    else:
        print("\nNo root node found")
    
    print(f"\nMost central node:")
    print(f"  PURL: {analysis['max_central_node']['purl']}")
    if analysis['max_central_node']['name']:
        print(f"  Name: {analysis['max_central_node']['name']}")
    print(f"  Type: {analysis['max_central_node']['type']}")
    print(f"  Centrality score: {analysis['max_central_node']['centrality']:.4f}")
    if analysis['max_central_node']['bom_ref']:
        print(f"  BOM Reference: {analysis['max_central_node']['bom_ref']}")
    
    print("\nAll dependencies:")
    for node in analysis['top_dependencies']:
        print(f"  PURL: {node['purl']}")
        if node['name']:
            print(f"    Name: {node['name']}")
        print(f"    Type: {node['type']}")
        print(f"    Level: {node['level']}")
        print(f"    Dependents: {node['dependents (incoming edges)']}")
        if node['bom_ref']:
            print(f"    BOM Reference: {node['bom_ref']}")
        print()  # Add blank line between entries


def save_analysis_json(analysis, graph_json_path):
    """
    Save the analysis as a JSON file in a 'graphProperties' subfolder under the same repo folder as the original graph JSON.
    """
    graph_json_path = Path(graph_json_path)
    repo_dir = graph_json_path.parent.parent  # e.g., graphoutput/<repo_name>
    graph_properties_dir = repo_dir / 'graphProperties'
    graph_properties_dir.mkdir(parents=True, exist_ok=True)
    base_name = graph_json_path.stem.replace('_graph', '')
    out_path = graph_properties_dir / f'{base_name}_graph_properties.json'
    with open(out_path, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"Saved analysis JSON to: {out_path}")


def compare_sbom_tools(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare multiple SBOM tool analyses and highlight key differences.
    """
    comparison = {
        'tool_count': len(analyses),
        'tool_summaries': {},
        'common_dependencies': defaultdict(int),
        'unique_dependencies': defaultdict(set)
    }
    
    # Group analyses by tool
    tool_analyses = defaultdict(list)
    for analysis in analyses:
        # Extract tool name from filename (trivy, syft, or cdxgen)
        filename = analysis['name'].lower()
        if 'trivy' in filename:
            tool_name = 'trivy'
        elif 'syft' in filename:
            tool_name = 'syft'
        elif 'cdxgen' in filename:
            tool_name = 'cdxgen'
        else:
            continue  # Skip if tool name not recognized
        
        tool_analyses[tool_name].append(analysis)
    
    # Generate summary for each tool
    metrics = ['nodes', 'edges', 'density', 'depth']  # Added depth
    
    for tool_name, tool_data in tool_analyses.items():
        tool_summary = {}
        
        # Calculate statistics for each metric
        for metric in metrics:
            values = [a.get(metric, 0) for a in tool_data if a.get(metric) is not None]  # Handle None values
            if values:  # Only calculate if we have values
                tool_summary[metric] = {
                    'min': min(values),
                    'max': max(values),
                    'mean': np.mean(values),
                    'median': np.median(values),
                    'std': np.std(values),
                    'range': max(values) - min(values)
                }
            else:
                tool_summary[metric] = {
                    'min': 0,
                    'max': 0,
                    'mean': 0,
                    'median': 0,
                    'std': 0,
                    'range': 0
                }
        
        # Calculate component type statistics
        all_types = set()
        for analysis in tool_data:
            types = analysis.get('component_type_distribution', {}).keys()
            all_types.update(types)
        
        tool_summary['component_types'] = {
            type_name: {
                'min': min(a.get('component_type_distribution', {}).get(type_name, 0) for a in tool_data),
                'max': max(a.get('component_type_distribution', {}).get(type_name, 0) for a in tool_data),
                'mean': np.mean([a.get('component_type_distribution', {}).get(type_name, 0) for a in tool_data]),
                'median': np.median([a.get('component_type_distribution', {}).get(type_name, 0) for a in tool_data]),
                'std': np.std([a.get('component_type_distribution', {}).get(type_name, 0) for a in tool_data])
            }
            for type_name in all_types
        }
        
        comparison['tool_summaries'][tool_name] = tool_summary
    
    return comparison


def print_comparison_summary(comparison: Dict[str, Any]):
    """Print a formatted summary of the SBOM tool comparison."""
    print("\n" + "="*80)
    print("SBOM Tool Comparison Summary")
    print("="*80)
    
    print(f"\nNumber of tools compared: {comparison['tool_count']}")
    
    # Print summary for each tool
    for tool_name, summary in comparison['tool_summaries'].items():
        print(f"\n{'='*40}")
        print(f"{tool_name.upper()} SUMMARY")
        print(f"{'='*40}")
        
        print("\nCore Metrics:")
        for metric, stats in summary.items():
            if metric != 'component_types':
                print(f"\n{metric.replace('_', ' ').title()}:")
                print(f"  Range: {stats['min']:.2f} to {stats['max']:.2f}")
                print(f"  Mean: {stats['mean']:.2f}")
                print(f"  Median: {stats['median']:.2f}")
                print(f"  Standard Deviation: {stats['std']:.2f}")
        
        print("\nComponent Type Distribution:")
        for type_name, stats in summary['component_types'].items():
            print(f"\n{type_name}:")
            print(f"  Range: {stats['min']} to {stats['max']}")
            print(f"  Mean: {stats['mean']:.2f}")
            print(f"  Median: {stats['median']:.2f}")
            print(f"  Standard Deviation: {stats['std']:.2f}")


def analyze_all_graphs():
    """Find and analyze all graphs in the project."""
    graph_files = find_all_graphs()
    
    if not graph_files:
        print("No graph files found in the project.")
        return
    
    print(f"Found {len(graph_files)} graph files.")
    
    # Analyze each graph
    all_analyses = []
    common_deps = defaultdict(int)
    
    for graph_file in graph_files:
        print(f"\nAnalyzing {graph_file.name}...")
        G = load_graph_from_json(graph_file)
        analysis = analyze_graph(G, graph_file.name)
        all_analyses.append(analysis)
        save_analysis_json(analysis, graph_file)
        
        # Track common dependencies using PURLs
        for node in G.nodes():
            if G.in_degree(node) > 0:  # if it's a dependency
                common_deps[node] += 1
    
    # Print individual analyses
    for analysis in all_analyses:
        print_analysis_summary(analysis)
    
    # Generate and print comparison summary
    comparison = compare_sbom_tools(all_analyses)
    print_comparison_summary(comparison)
    
    # Print common dependencies across graphs
    print("\n" + "="*80)
    print("Common Dependencies Across All Graphs")
    print("="*80)
    common_deps = sorted(common_deps.items(), key=lambda x: x[1], reverse=True)
    for purl, count in common_deps[:10]:  # Show top 10
        if count > 1:  # Only show deps that appear in multiple graphs
            print(f"{purl}: appears in {count} graphs")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze graph properties from JSON files.")
    parser.add_argument('json_path', nargs='?', type=str, 
                       help='Path to a specific graph JSON file (optional)')
    args = parser.parse_args()

    if args.json_path:
        # Analyze specific file
        G = load_graph_from_json(args.json_path)
        analysis = analyze_graph(G, Path(args.json_path).name)
        print_analysis_summary(analysis)
        save_analysis_json(analysis, args.json_path)
    else:
        # Analyze all graphs in project
        analyze_all_graphs()


if __name__ == "__main__":
    main() 