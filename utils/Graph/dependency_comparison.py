import json
import networkx as nx
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import sys
import argparse


def load_graph_from_json(json_path: str) -> nx.DiGraph:
    """Load a graph from a JSON file."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    G = nx.DiGraph() if data.get('directed', False) else nx.Graph()
    for node in data['nodes']:
        G.add_node(node['id'], **{k: v for k, v in node.items() if k != 'id'})
    for link in data['links']:
        G.add_edge(link['source'], link['target'], **{k: v for k, v in link.items() if k not in ['source', 'target']})
    return G


def get_dependencies(G: nx.DiGraph) -> Dict[str, dict]:
    """Extract all nodes from a graph with their metadata."""
    dependencies = {}
    for node in G.nodes():
        node_data = G.nodes[node]
        dependencies[node] = {
            'name': node_data.get('name', ''),
            'type': node_data.get('type', ''),
            'level': node_data.get('level', 0),
            'bom_ref': node_data.get('bom_ref', '')
        }
    return dependencies


def find_repo_graphs():
    """Find all repository directories and their graph files."""
    base_dir = Path(__file__).parent.parent.parent / 'graphoutput'
    repo_graphs = {}
    
    # Find all repository directories
    for repo_dir in base_dir.iterdir():
        if not repo_dir.is_dir():
            continue
            
        json_dir = repo_dir / 'json'
        if not json_dir.exists():
            continue
            
        # Find all graph files for this repository
        graph_files = list(json_dir.glob('*_graph.json'))
        if len(graph_files) >= 3:  # Process repos with 3 or more graphs
            repo_graphs[repo_dir.name] = graph_files
    
    return repo_graphs


def compare_dependencies(graph_paths: List[Path]):
    """
    Compare all nodes across multiple graphs.
    Returns:
        Tuple containing:
        - Dict of nodes present in all graphs
        - Dict of nodes missing from at least one graph
        - Dict of pairwise tool comparisons
        - Dict of tool-specific node counts
    """
    if len(graph_paths) < 3:
        raise ValueError("Need at least 3 graphs to compare dependencies")

    # Load all graphs and their nodes
    graph_deps = {}
    node_counts = {}
    for path in graph_paths:
        G = load_graph_from_json(str(path))
        if 'sbomgold' in path.stem:
            tool_name = 'sbomgold'
        else:
            parts = path.stem.split('&')
            tool_name = parts[1] if len(parts) > 1 else path.stem
        deps = get_dependencies(G)
        graph_deps[tool_name] = deps
        node_counts[tool_name] = len(deps)

    # Find nodes present in all graphs
    common_deps = set.intersection(*[set(deps.keys()) for deps in graph_deps.values()])
    common_deps_dict = {dep: list(graph_deps.keys()) for dep in common_deps}

    # Find nodes missing from at least one graph
    all_deps = set.union(*[set(deps.keys()) for deps in graph_deps.values()])
    missing_deps = {}
    for dep in all_deps:
        missing_from = [name for name, deps in graph_deps.items() if dep not in deps]
        if missing_from:
            missing_deps[dep] = missing_from

    # Calculate pairwise tool comparisons
    tool_comparisons = {}
    tools = list(graph_deps.keys())
    for i, tool1 in enumerate(tools):
        tool_comparisons[tool1] = {}
        for tool2 in tools[i+1:]:
            deps1 = set(graph_deps[tool1].keys())
            deps2 = set(graph_deps[tool2].keys())
            common = deps1.intersection(deps2)
            only_in_tool1 = deps1 - deps2
            only_in_tool2 = deps2 - deps1
            tool_comparisons[tool1][tool2] = {
                'common_dependencies': len(common),
                f'only_in_{tool1}_count': len(only_in_tool1),
                f'only_in_{tool2}_count': len(only_in_tool2),
                'common_dependencies_list': list(common),
                f'only_in_{tool1}_list': list(only_in_tool1),
                f'only_in_{tool2}_list': list(only_in_tool2)
            }

    return common_deps_dict, missing_deps, tool_comparisons, node_counts


def print_comparison_results(repo_name: str, common_deps: Dict[str, list], missing_deps: Dict[str, list], tool_comparisons: Dict[str, dict], node_counts: Dict[str, int]):
    print("\n" + "="*80)
    print(f"Dependency Comparison Analysis for {repo_name}")
    print("="*80)

    total_deps = len(set(common_deps.keys()) | set(missing_deps.keys()))
    common_count = len(common_deps)
    missing_count = len(missing_deps)

    print("\nOverall Statistics:")
    print(f"Total unique nodes found: {total_deps}")
    print(f"Nodes found by all tools: {common_count}/{total_deps} ({common_count/total_deps*100:.1f}%)")
    print(f"Nodes missing from some tools: {missing_count}/{total_deps} ({missing_count/total_deps*100:.1f}%)")

    print("\nTool-specific node counts (should match graph node counts):")
    for tool, count in sorted(node_counts.items()):
        print(f"  {tool}: {count} nodes")

    print("\nPairwise Tool Comparisons:")
    for tool1, comparisons in tool_comparisons.items():
        for tool2, stats in comparisons.items():
            print(f"\n  {tool1} vs {tool2}:")
            print(f"    Common nodes: {stats['common_dependencies']}")
            print(f"    Only in {tool1}: {stats[f'only_in_{tool1}_count']}")
            print(f"    Only in {tool2}: {stats[f'only_in_{tool2}_count']}")
            print(f"    Agreement rate: {stats['common_dependencies']/total_deps*100:.1f}%")

    print("\nNodes Present in All Tools:")
    if common_deps:
        for dep, tools in common_deps.items():
            print(f"  Node: {dep}")
    else:
        print("  No common nodes found")

    print("\nNodes Missing from Some Tools:")
    if missing_deps:
        for dep, missing_from in missing_deps.items():
            print(f"  Node: {dep}")
            print(f"    Missing from: {', '.join(missing_from)}")
    else:
        print("  No missing nodes found")


def save_comparison_json(repo_name: str, common_deps: Dict[str, List[str]], missing_deps: Dict[str, List[str]], tool_comparisons: Dict[str, Dict[str, dict]], node_counts: Dict[str, int], output_dir: Path):
    """Save the comparison results to a JSON file in the repository's graphProperties directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'dependency_comparison.json'
    
    # Calculate statistics
    total_deps = len(set(common_deps.keys()) | set(missing_deps.keys()))
    common_count = len(common_deps)
    missing_count = len(missing_deps)
    
    # Calculate percentages
    common_percentage = (common_count / total_deps * 100) if total_deps > 0 else 0
    missing_percentage = (missing_count / total_deps * 100) if total_deps > 0 else 0
    
    # Use the correct node counts from compare_dependencies
    tool_stats = {}
    for tool, count in node_counts.items():
        tool_stats[tool] = {
            "count": count,
            "percentage": (count / total_deps * 100) if total_deps > 0 else 0
        }
    
    results = {
        "repository": repo_name,
        "statistics": {
            "overall": {
                "total_dependencies": total_deps,
                "common_dependencies": {
                    "count": common_count,
                    "percentage": round(common_percentage, 1)
                },
                "missing_dependencies": {
                    "count": missing_count,
                    "percentage": round(missing_percentage, 1)
                }
            },
            "tool_specific": tool_stats,
            "pairwise_comparisons": tool_comparisons
        },
        "common_dependencies": common_deps,
        "missing_dependencies": missing_deps
    }
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved comparison results to: {output_path}")


def analyze_all_repos():
    """Find and analyze all repositories and their graphs."""
    repo_graphs = find_repo_graphs()
    
    if not repo_graphs:
        print("No repositories with 3 or more graphs found.")
        return
    
    print(f"Found {len(repo_graphs)} repositories with 3 or more graphs each.")
    
    for repo_name, graph_files in repo_graphs.items():
        print(f"\nAnalyzing repository: {repo_name}")
        
        try:
            common_deps, missing_deps, tool_comparisons, node_counts = compare_dependencies(graph_files)
            print_comparison_results(repo_name, common_deps, missing_deps, tool_comparisons, node_counts)
            
            # Save results in the repository's graphProperties directory
            repo_dir = Path(__file__).parent.parent.parent / 'graphoutput' / repo_name
            output_dir = repo_dir / 'graphProperties'
            save_comparison_json(repo_name, common_deps, missing_deps, tool_comparisons, node_counts, output_dir)
            
        except Exception as e:
            print(f"Error analyzing {repo_name}: {str(e)}")


def compare_first_against_rest(graph_paths: List[Path]) -> Dict[str, List[str]]:
    """
    Compare the first graph against all other graphs to find dependencies
    that are found by other graphs but not by the first graph.
    
    Args:
        graph_paths: List of paths to graph JSON files
        
    Returns:
        Dictionary mapping dependency PURLs to the list of tools that found them
    """
    if len(graph_paths) < 2:
        raise ValueError("Need at least 2 graphs to compare")

    # Load all graphs and their dependencies
    graph_deps = {}
    for path in graph_paths:
        G = load_graph_from_json(str(path))
        # Extract tool name from filename
        if 'sbomgold' in path.stem:
            tool_name = 'sbomgold'
        else:
            parts = path.stem.split('&')
            tool_name = parts[1] if len(parts) > 1 else path.stem
        graph_deps[tool_name] = get_dependencies(G)

    # Get the first tool and its dependencies
    first_tool = list(graph_deps.keys())[0]
    first_tool_deps = set(graph_deps[first_tool].keys())
    
    # Find dependencies that other tools found but first tool didn't
    missing_deps = {}
    for tool, deps in graph_deps.items():
        if tool == first_tool:
            continue
        for dep in deps:
            if dep not in first_tool_deps:
                if dep not in missing_deps:
                    missing_deps[dep] = []
                missing_deps[dep].append(tool)
    
    return missing_deps


def print_first_vs_rest_results(repo_name: str, first_tool: str, missing_deps: Dict[str, List[str]]):
    """Print the comparison results between first tool and others."""
    print("\n" + "="*80)
    print(f"Dependencies found by other tools but not by {first_tool} in {repo_name}")
    print("="*80)

    if not missing_deps:
        print(f"\nNo dependencies found by other tools that {first_tool} missed.")
        return

    print(f"\nTotal dependencies missed by {first_tool}: {len(missing_deps)}")
    print("\nDetailed breakdown:")
    for dep, tools in missing_deps.items():
        print(f"\n  PURL: {dep}")
        print(f"    Found by: {', '.join(tools)}")


def compare_all_against_each_other(graph_paths: List[Path]) -> Dict[str, Dict[str, List[str]]]:
    """
    Compare each graph against all others to find dependencies
    that are found by other graphs but not by each graph.
    
    Args:
        graph_paths: List of paths to graph JSON files
        
    Returns:
        Dictionary mapping each tool to a dictionary of its missing dependencies
    """
    if len(graph_paths) < 2:
        raise ValueError("Need at least 2 graphs to compare")

    # Load all graphs and their dependencies
    graph_deps = {}
    for path in graph_paths:
        G = load_graph_from_json(str(path))
        # Extract tool name from filename
        if 'sbomgold' in path.stem:
            tool_name = 'sbomgold'
        else:
            parts = path.stem.split('&')
            tool_name = parts[1] if len(parts) > 1 else path.stem
        graph_deps[tool_name] = get_dependencies(G)

    # For each tool, find what it missed that others found
    all_missing_deps = {}
    for tool, deps in graph_deps.items():
        tool_deps = set(deps.keys())
        missing_deps = {}
        
        # Compare against all other tools
        for other_tool, other_deps in graph_deps.items():
            if other_tool == tool:
                continue
            for dep in other_deps:
                if dep not in tool_deps:
                    if dep not in missing_deps:
                        missing_deps[dep] = []
                    missing_deps[dep].append(other_tool)
        
        all_missing_deps[tool] = missing_deps
    
    return all_missing_deps


def print_all_vs_all_results(repo_name: str, all_missing_deps: Dict[str, Dict[str, List[str]]]):
    """Print the comparison results between all tools."""
    print("\n" + "="*80)
    print(f"Comprehensive Dependency Comparison for {repo_name}")
    print("="*80)

    for tool, missing_deps in all_missing_deps.items():
        print(f"\n\nDependencies found by other tools but not by {tool}:")
        print("-" * 60)
        
        if not missing_deps:
            print(f"No dependencies found by other tools that {tool} missed.")
            continue

        print(f"Total dependencies missed by {tool}: {len(missing_deps)}")
        print("\nDetailed breakdown:")
        for dep, tools in missing_deps.items():
            print(f"\n  PURL: {dep}")
            print(f"    Found by: {', '.join(tools)}")


def main():
    parser = argparse.ArgumentParser(description="Compare dependencies across multiple graph JSON files.")
    parser.add_argument('--specific', nargs='+', type=str,
                       help='Specific repository names to analyze (optional)')
    parser.add_argument('--first-vs-rest', action='store_true',
                       help='Compare first graph against all others')
    parser.add_argument('--all-vs-all', action='store_true',
                       help='Compare each graph against all others')
    args = parser.parse_args()

    if args.specific:
        try:
            base_dir = Path(__file__).parent.parent.parent / 'graphoutput'
            for repo_name in args.specific:
                repo_dir = base_dir / repo_name
                json_dir = repo_dir / 'json'
                if not json_dir.exists():
                    print(f"Repository {repo_name} not found or has no json directory")
                    continue
                graph_files = list(json_dir.glob('*_graph.json'))
                if len(graph_files) < 2:
                    print(f"Repository {repo_name} does not have at least 2 graph files")
                    continue
                print(f"\nAnalyzing repository: {repo_name}")
                common_deps, missing_deps, tool_comparisons, node_counts = compare_dependencies(graph_files)
                print_comparison_results(repo_name, common_deps, missing_deps, tool_comparisons, node_counts)
                
                # Save results to JSON
                output_dir = repo_dir / 'graphProperties'
                save_comparison_json(repo_name, common_deps, missing_deps, tool_comparisons, node_counts, output_dir)
                
        except Exception as e:
            print(f"Error: {str(e)}")
    else:
        analyze_all_repos()


if __name__ == "__main__":
    main() 