import json
import networkx as nx
import os
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import logging
import sys

# Set up logging with detailed console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add file handler for persistent logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
file_handler = logging.FileHandler(log_dir / 'graph_maker.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

def process_sbom(sbom_file, output_dir):
    logger.info(f"Loading SBOM data from {sbom_file}...")
    # Load SBOM data
    with open(sbom_file, 'r') as f:
        sbom_data = json.load(f)
    
    logger.info("Creating NetworkX graph...")
    # Create a NetworkX graph
    G = nx.DiGraph()
    
    # Get root component from metadata
    root_component = sbom_data['metadata']['component']
    root_ref = root_component['bom-ref']
    root_name = root_component['name']
    root_purl = root_component.get('purl', root_name)
    
    # Add root node
    G.add_node('root', 
              name='root',
              type='root',
              level=0,
              bom_ref=root_ref)
    
    logger.info("Processing components...")
    # Create a mapping of ref to package info
    package_map = {}
    # Track all components that appear in the SBOM
    all_components = set()
    
    # Handle SBOMs that might not have a components section
    if 'components' in sbom_data:
        for component in sbom_data['components']:
            purl = component.get('purl', component.get('name', component['bom-ref']))
            package_map[component['bom-ref']] = {
                'purl': purl,
                'name': component.get('name', ''),
                'bom_ref': component['bom-ref']
            }
            all_components.add(component['bom-ref'])
            logger.debug(f"Added component to package_map: {purl}")
    
    logger.info("Processing dependencies...")
    # Process dependencies
    processed_nodes = set()  # Track processed nodes to prevent cycles
    queue = [(root_ref, 0)]  # (current_ref, level)
    processed_count = 0
    missing_components = set()  # Track components referenced but not found
    connected_components = set()  # Track components that are connected to the root
    
    while queue:
        current_ref, level = queue.pop(0)
        if current_ref in processed_nodes:
            continue  # Skip if already processed
        
        processed_nodes.add(current_ref)
        connected_components.add(current_ref)
        processed_count += 1
        if processed_count % 100 == 0:
            logger.info(f"Processed {processed_count} dependencies...")
        
        # Find dependencies for current node
        for dep in sbom_data.get('dependencies', []):
            if dep['ref'] == current_ref:
                for child_ref in dep.get('dependsOn', []):
                    if child_ref not in processed_nodes:  # Only process new nodes
                        # Get package info
                        package_info = package_map.get(child_ref, {})
                        if not package_info:
                            missing_components.add(child_ref)
                            logger.warning(f"Component not found in package_map: {child_ref}")
                            # Create a basic package info for missing components
                            package_info = {
                                'purl': child_ref,
                                'name': child_ref,
                                'bom_ref': child_ref
                            }
                        
                        child_purl = package_info.get('purl', child_ref)
                        
                        # Add node if not already present
                        if not G.has_node(child_purl):
                            G.add_node(child_purl,
                                     name=package_info.get('name', ''),
                                     type='dependency',
                                     level=level + 1,
                                     bom_ref=child_ref)
                            logger.debug(f"Added node: {child_purl}")
                        
                        # Add edge - use 'root' as source if it's the root node
                        source_node = 'root' if current_ref == root_ref else package_map.get(current_ref, {}).get('purl', current_ref)
                        G.add_edge(source_node, child_purl, type='depends_on')
                        logger.debug(f"Added edge: {source_node} -> {child_purl}")
                        
                        # Add to queue for processing with incremented level
                        queue.append((child_ref, level + 1))
    
    # Identify disconnected components
    disconnected_components = all_components - connected_components
    if disconnected_components:
        logger.warning(f"Found {len(disconnected_components)} disconnected components:")
        for comp in disconnected_components:
            logger.warning(f"  - {comp}")
            # Add disconnected component to graph with special edge from root
            package_info = package_map.get(comp, {})
            purl = package_info.get('purl', comp)
            if not G.has_node(purl):
                G.add_node(purl,
                          name=package_info.get('name', ''),
                          type='disconnected_dependency',
                          level=1,
                          bom_ref=comp)
                G.add_edge('root', purl, type='disconnected_depends_on')
                logger.info(f"Added disconnected component to graph: {purl}")
    
    if missing_components:
        logger.warning(f"Found {len(missing_components)} components referenced in dependencies but not found in components section:")
        for comp in missing_components:
            logger.warning(f"  - {comp}")
    
    logger.info(f"Total nodes in graph: {len(G.nodes())}")
    logger.info(f"Total edges in graph: {len(G.edges())}")
    
    # Get repository name from the SBOM file path
    repo_name = Path(sbom_file).parent.name
    
    # Create repository-specific output directories
    repo_output_dir = output_dir / repo_name
    json_output_dir = repo_output_dir / 'json'
    png_output_dir = repo_output_dir / 'png'
    
    # Create directories if they don't exist
    json_output_dir.mkdir(parents=True, exist_ok=True)
    png_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get base name of the SBOM file
    base_name = Path(sbom_file).stem
    
    print("Converting graph to JSON format...")
    # Convert to a format that can be serialized to JSON
    graph_data = {
        "directed": True,
        "multigraph": False,
        "graph": {},
        "nodes": [{"id": n, **G.nodes[n], "disconnected": G.nodes[n]['type'] == 'disconnected_dependency'} for n in G.nodes()],
        "links": [{"source": u, "target": v, **G.edges[u, v]} for u, v in G.edges()]
    }
    
    print("Saving JSON file...")
    # Save the NetworkX graph structure
    with open(json_output_dir / f'{base_name}_graph.json', 'w') as f:
        json.dump(graph_data, f, indent=2)
    
    print("Generating visualization...")
    # Create PNG visualization
    plt.figure(figsize=(20, 15))
    pos = nx.spring_layout(G, k=1, iterations=50)
    
    print("Drawing nodes...")
    # Calculate incoming edges for each node
    incoming_edges = {node: 0 for node in G.nodes()}
    for _, target in G.edges():
        incoming_edges[target] += 1
    
    # Draw nodes with different colors based on type and incoming edges
    node_colors = []
    for n in G.nodes():
        if G.nodes[n]['type'] == 'root':
            node_colors.append('gold')
        elif G.nodes[n]['type'] == 'disconnected_dependency':
            node_colors.append('lightgreen')  # Different color for disconnected nodes
        else:
            node_colors.append('lightblue')
    
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500)
    
    print("Drawing edges...")
    # Draw edges with different styles for disconnected dependencies
    edge_colors = ['red' if G.edges[e]['type'] == 'disconnected_depends_on' else 'black' for e in G.edges()]
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, arrows=True, arrowsize=20)
    
    print("Adding labels...")
    # Add labels - use name for root, purl for others
    labels = {n: G.nodes[n]['name'] if G.nodes[n]['type'] == 'root' else n for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=12)
    
    # Add legend
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Root Node',
               markerfacecolor='gold', markersize=15),
        Line2D([0], [0], marker='o', color='w', label='Connected Dependency',
               markerfacecolor='lightblue', markersize=15),
        Line2D([0], [0], marker='o', color='w', label='Disconnected Dependency',
               markerfacecolor='lightgreen', markersize=15),
        Line2D([0], [0], color='red', label='Disconnected Edge',
               markersize=15)
    ]
    plt.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.1, 1), fontsize=12)
    
    print("Saving PNG file...")
    # Save the plot
    plt.savefig(png_output_dir / f'{base_name}_graph.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\nGraph structure has been saved as '{json_output_dir}/{base_name}_graph.json'")
    print(f"Graph visualization has been saved as '{png_output_dir}/{base_name}_graph.png'")
    return G

def main():
    # Create main output directory
    output_dir = Path('graphoutput')
    output_dir.mkdir(exist_ok=True)
    
    # Get the standardized_boms directory path from the root directory
    standardized_boms_dir = Path(__file__).parent.parent.parent / 'standardized_boms'
    
    # Get all JSON files in the standardized_boms directory
    sbom_files = list(standardized_boms_dir.glob('**/*.json'))
    
    if not sbom_files:
        print(f"No JSON files found in {standardized_boms_dir}")
        return {}
    
    # Process each SBOM file
    graphs = {}
    for sbom_file in sbom_files:
        try:
            print(f"\nProcessing {sbom_file}...")
            graphs[sbom_file.name] = process_sbom(str(sbom_file), output_dir)
        except Exception as e:
            print(f"Error processing {sbom_file}: {str(e)}")
    
    return graphs

if __name__ == "__main__":
    graphs = main()