import networkx as nx
import numpy as np
import json
import os
import pandas as pd
from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Tuple

def load_graphs_from_json(json_path: str) -> List[nx.Graph]:
    """Load graphs from a JSON file or a directory of JSON files (each file is a single graph object)."""
    graphs = []
    if os.path.isdir(json_path):
        for filename in os.listdir(json_path):
            if filename.endswith('.json'):
                file_path = os.path.join(json_path, filename)
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    G = nx.DiGraph() if data.get('directed', False) else nx.Graph()
                    # Add nodes with their labels (use 'name' or fallback to 'type' or 'id')
                    for node in data['nodes']:
                        label = node.get('name') or node.get('type') or node.get('id')
                        G.add_node(node['id'], label=label)
                    # Add edges from 'links' (not 'edges')
                    for edge in data.get('links', []):
                        G.add_edge(edge['source'], edge['target'])
                    graphs.append(G)
    else:
        with open(json_path, 'r') as f:
            data = json.load(f)
            G = nx.DiGraph() if data.get('directed', False) else nx.Graph()
            for node in data['nodes']:
                label = node.get('name') or node.get('type') or node.get('id')
                G.add_node(node['id'], label=label)
            for edge in data.get('links', []):
                G.add_edge(edge['source'], edge['target'])
            graphs.append(G)
    return graphs

def wl_subtree_kernel(G1: nx.Graph, G2: nx.Graph, h: int = 3) -> float:
    """
    Compute the Weisfeiler-Lehman subtree kernel between two graphs.
    
    Args:
        G1, G2: NetworkX graphs
        h: Number of iterations
    
    Returns:
        Kernel value (float)
    """
    def get_initial_labels(G):
        return {node: str(G.nodes[node]['label']) for node in G.nodes()}
    
    def get_multiset_labels(G, labels):
        return {node: [labels[neighbor] for neighbor in G.neighbors(node)] for node in G.nodes()}
    
    def get_new_labels(G, labels, multiset_labels):
        new_labels = {}
        for node in G.nodes():
            # Sort the multiset to ensure consistent ordering
            sorted_multiset = sorted(multiset_labels[node])
            # Create new label by combining current label with sorted multiset
            new_label = labels[node] + '_' + '_'.join(sorted_multiset)
            new_labels[node] = new_label
        return new_labels
    
    def count_labels(labels):
        label_counts = defaultdict(int)
        for label in labels.values():
            label_counts[label] += 1
        return label_counts
    
    # Initialize labels
    labels1 = get_initial_labels(G1)
    labels2 = get_initial_labels(G2)
    
    # Initialize kernel value
    kernel = 0
    
    # Iterate h times
    for _ in range(h):
        # Count current labels
        counts1 = count_labels(labels1)
        counts2 = count_labels(labels2)
        
        # Add contribution of current iteration
        for label in set(counts1.keys()) & set(counts2.keys()):
            kernel += counts1[label] * counts2[label]
        
        # Update labels
        multiset_labels1 = get_multiset_labels(G1, labels1)
        multiset_labels2 = get_multiset_labels(G2, labels2)
        
        labels1 = get_new_labels(G1, labels1, multiset_labels1)
        labels2 = get_new_labels(G2, labels2, multiset_labels2)
    
    return kernel

def normalize_kernel(kernel_value: float, self_sim1: float, self_sim2: float) -> float:
    """Normalize kernel value using geometric mean of self-similarities."""
    return kernel_value / np.sqrt(self_sim1 * self_sim2)

def summarize_results(file_path):
    df = pd.read_csv(file_path)
    summary = df['normalized_kernel'].agg(['mean', 'median', 'std']).to_dict()
    print(f"Summary for {file_path}:")
    print(f"Mean: {summary['mean']:.4f}")
    print(f"Median: {summary['median']:.4f}")
    print(f"Std: {summary['std']:.4f}")
    print()

def main():
    # Directory containing the repositories
    base_dir = "graphoutput"
    
    # Ensure output directory exists
    output_dir = "package_analysis"
    os.makedirs(output_dir, exist_ok=True)

    results = []

    for repo in os.listdir(base_dir):
        json_dir = os.path.join(base_dir, repo, "json")
        if not os.path.isdir(json_dir):
            continue
        # Map tool name to graph
        tool_graphs = {}
        for filename in os.listdir(json_dir):
            if filename.endswith('.json'):
                tool_name = filename.split('&')[1] if '&' in filename else filename.replace('_graph.json', '').replace('.json', '')
                file_path = os.path.join(json_dir, filename)
                graphs = load_graphs_from_json(file_path)
                if graphs:
                    tool_graphs[tool_name] = graphs[0]  # Each file is a single graph
        # Pairwise comparison of tools
        tool_names = list(tool_graphs.keys())
        for i in range(len(tool_names)):
            for j in range(i+1, len(tool_names)):
                tool1, tool2 = tool_names[i], tool_names[j]
                G1, G2 = tool_graphs[tool1], tool_graphs[tool2]
                kernel_value = wl_subtree_kernel(G1, G2)
                self_sim1 = wl_subtree_kernel(G1, G1)
                self_sim2 = wl_subtree_kernel(G2, G2)
                normalized_kernel = normalize_kernel(kernel_value, self_sim1, self_sim2)
                results.append({
                    'repo': repo,
                    'tool1': tool1,
                    'tool2': tool2,
                    'kernel_value': kernel_value,
                    'normalized_kernel': normalized_kernel
                })
    # Create DataFrame and save to CSV
    df = pd.DataFrame(results)
    output_file = os.path.join(output_dir, 'graph_kernel_analysis_results.csv')
    df.to_csv(output_file, index=False)
    print(f"Analysis complete. Results saved to {output_file}")

    # Summarize results
    summarize_results(output_file)

if __name__ == "__main__":
    main() 