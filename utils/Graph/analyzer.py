import json
from pathlib import Path
from collections import defaultdict
import statistics
from datetime import datetime

def load_all_analyses():
    """Load all graph property analysis files from the graphProperties directories."""
    current_dir = Path(__file__).parent.parent.parent
    analyses = []
    
    # Look in all graphProperties directories
    for properties_file in current_dir.rglob('graphProperties/*_graph_properties.json'):
        # Skip .whl files as they are metadata files
        if properties_file.name.endswith('.whl'):
            continue
            
        try:
            with open(properties_file, 'r') as f:
                analysis = json.load(f)
                analyses.append(analysis)
        except Exception as e:
            print(f"Error loading {properties_file}: {e}")
    
    return analyses

def analyze_package_popularity(analyses):
    """Analyze package popularity across all repositories."""
    package_stats = defaultdict(lambda: {
        'centrality_scores': [],
        'dependents': [],
        'repos': set(),
        'names': set(),  # Track all names associated with this PURL
        'bom_refs': set()  # Track all BOM refs associated with this PURL
    })
    
    for analysis in analyses:
        repo_name = analysis['name']
        
        # Track central node
        central_node = analysis['max_central_node']
        if central_node['type'] == 'dependency':
            purl = central_node['purl']  # PURL is now the primary identifier
            # Skip .whl packages
            if purl.endswith('.whl'):
                continue
            package_stats[purl]['centrality_scores'].append(central_node['centrality'])
            package_stats[purl]['repos'].add(repo_name)
            if central_node.get('name'):
                package_stats[purl]['names'].add(central_node['name'])
            if central_node.get('bom_ref'):
                package_stats[purl]['bom_refs'].add(central_node['bom_ref'])
        
        # Track top dependencies
        for dep in analysis['top_dependencies']:
            purl = dep['purl']  # PURL is now the primary identifier
            # Skip .whl packages
            if purl.endswith('.whl'):
                continue
            package_stats[purl]['dependents'].append(dep['dependents (incoming edges)'])
            package_stats[purl]['repos'].add(repo_name)
            if dep.get('name'):
                package_stats[purl]['names'].add(dep['name'])
            if dep.get('bom_ref'):
                package_stats[purl]['bom_refs'].add(dep['bom_ref'])
            
            # Add centrality score if available in the dependency data
            if 'centrality' in dep:
                package_stats[purl]['centrality_scores'].append(dep['centrality'])
    
    # Calculate aggregate statistics
    results = []
    for purl, stats in package_stats.items():
        if len(stats['repos']) > 0:  # Only include packages that appear in at least one repo
            results.append({
                'purl': purl,  # PURL is now the primary identifier
                'names': sorted(list(stats['names'])),  # List of all names associated with this PURL
                'bom_refs': sorted(list(stats['bom_refs'])),  # List of all BOM refs associated with this PURL
                'repos': len(stats['repos']),
                'avg_centrality': statistics.mean(stats['centrality_scores']) if stats['centrality_scores'] else 0,
                'max_centrality': max(stats['centrality_scores']) if stats['centrality_scores'] else 0,
                'avg_dependents': statistics.mean(stats['dependents']) if stats['dependents'] else 0,
                'max_dependents': max(stats['dependents']) if stats['dependents'] else 0,
                'repo_list': sorted(list(stats['repos']))
            })
    
    return sorted(results, key=lambda x: (x['repos'], x['avg_dependents']), reverse=True)

def analyze_package_versions(analyses):
    """Analyze package versions across all repositories."""
    version_stats = defaultdict(lambda: {
        'versions': set(),
        'total_count': 0,  # Track total appearances
        'repos': set(),
        'names': set(),
        'bom_refs': set(),
        'purls': set()
    })
    
    for analysis in analyses:
        repo_name = analysis['name']
        
        # Track central node
        central_node = analysis['max_central_node']
        if central_node['type'] == 'dependency':
            purl = central_node['purl']
            if purl.endswith('.whl'):
                continue
            base_purl = purl.split('@')[0] if '@' in purl else purl
            version = purl.split('@')[-1] if '@' in purl else 'unknown'
            version_stats[base_purl]['versions'].add(version)
            version_stats[base_purl]['total_count'] += 1
            version_stats[base_purl]['repos'].add(repo_name)
            version_stats[base_purl]['purls'].add(purl)
            if central_node.get('name'):
                version_stats[base_purl]['names'].add(central_node['name'])
            if central_node.get('bom_ref'):
                version_stats[base_purl]['bom_refs'].add(central_node['bom_ref'])
        
        # Track top dependencies
        for dep in analysis['top_dependencies']:
            purl = dep['purl']
            if purl.endswith('.whl'):
                continue
            base_purl = purl.split('@')[0] if '@' in purl else purl
            version = purl.split('@')[-1] if '@' in purl else 'unknown'
            version_stats[base_purl]['versions'].add(version)
            version_stats[base_purl]['total_count'] += 1
            version_stats[base_purl]['repos'].add(repo_name)
            version_stats[base_purl]['purls'].add(purl)
            if dep.get('name'):
                version_stats[base_purl]['names'].add(dep['name'])
            if dep.get('bom_ref'):
                version_stats[base_purl]['bom_refs'].add(dep['bom_ref'])
    
    # Calculate aggregate statistics
    results = []
    for base_purl, stats in version_stats.items():
        if len(stats['repos']) > 0:
            results.append({
                'base_purl': base_purl,
                'names': sorted(list(stats['names'])),
                'bom_refs': sorted(list(stats['bom_refs'])),
                'unique_versions': len(stats['versions']),
                'versions': sorted(list(stats['versions'])),
                'total_count': stats['total_count'],
                'repos': len(stats['repos']),
                'purls': sorted(list(stats['purls']))
            })
    
    return sorted(results, key=lambda x: (x['total_count'], x['unique_versions']), reverse=True)

def save_analysis_results(results):
    """Save the analysis results to a single JSON file with both popularity and centrality information."""
    current_dir = Path(__file__).parent.parent.parent
    analysis_dir = current_dir / 'package_analysis'
    analysis_dir.mkdir(exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Sort results by both appearances and centrality
    popularity_sorted = sorted(results, key=lambda x: (x['repos'], x['avg_dependents']), reverse=True)
    centrality_sorted = sorted(results, key=lambda x: x['avg_centrality'], reverse=True)
    
    # Get version analysis
    version_analysis = analyze_package_versions(load_all_analyses())
    
    # Save results with both sorting information and version analysis
    output_file = analysis_dir / f'package_analysis_{timestamp}.json'
    output_data = {
        'timestamp': timestamp,
        'total_packages': len(results),
        'popularity_sorted': popularity_sorted,
        'centrality_sorted': centrality_sorted,
        'version_analysis': version_analysis
    }
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nAnalysis results saved to: {output_file}")
    return output_file

def print_popularity_analysis(results, top_n=100):
    """Print a formatted summary of the package popularity analysis."""
    print("\n" + "="*100)
    print("Package Popularity Analysis Across All Repositories")
    print("="*100)
    
    print(f"\nTop {top_n} Most Popular Packages:")
    print("-"*100)
    print(f"{'PURL':<60} {'Names':<30} {'Repos':<8} {'Avg Deps':<12} {'Max Deps':<12} {'Avg Centrality':<15}")
    print("-"*100)
    
    for pkg in results[:top_n]:
        # Get the primary name (first name in the list) or use PURL if no names
        primary_name = pkg['names'][0] if pkg['names'] else pkg['purl']
        print(f"{pkg['purl'][:60]:<60} {primary_name[:30]:<30} {pkg['repos']:<8} "
              f"{pkg['avg_dependents']:<12.1f} {pkg['max_dependents']:<12} {pkg['avg_centrality']:<15.4f}")
    
    print("\nDetailed Repository Coverage:")
    print("-"*100)
    for pkg in results[:top_n]:
        print(f"\nPURL: {pkg['purl']}")
        if pkg['names']:
            print(f"Names: {', '.join(pkg['names'])}")
        if pkg['bom_refs']:
            print(f"BOM References: {', '.join(pkg['bom_refs'])}")
        print(f"Appears in {pkg['repos']} repositories:")
        for repo in pkg['repo_list']:
            print(f"    - {repo}")

def print_version_analysis(results, top_n=100):
    """Print a formatted summary of the package version analysis."""
    print("\n" + "="*100)
    print("Package Version Analysis Across All Repositories")
    print("="*100)
    
    print(f"\nTop {top_n} Packages by Total Count and Version Diversity:")
    print("-"*100)
    print(f"{'Package':<40} {'Unique Versions':<15} {'Total Count':<12} {'Versions':<40}")
    print("-"*100)
    
    for pkg in results[:top_n]:
        # Get the primary name (first name in the list) or use base PURL if no names
        primary_name = pkg['names'][0] if pkg['names'] else pkg['base_purl']
        versions_str = ', '.join(pkg['versions'])
        print(f"{primary_name[:40]:<40} {pkg['unique_versions']:<15} {pkg['total_count']:<12} {versions_str[:40]:<40}")
    
    print("\nDetailed Version Information:")
    print("-"*100)
    for pkg in results[:top_n]:
        print(f"\nPackage: {pkg['base_purl']}")
        if pkg['names']:
            print(f"Names: {', '.join(pkg['names'])}")
        print(f"Unique Versions: {pkg['unique_versions']}")
        print(f"Total Count: {pkg['total_count']}")
        print(f"Versions: {', '.join(pkg['versions'])}")

def main():
    print("Loading and analyzing package popularity across all repositories...")
    analyses = load_all_analyses()
    
    if not analyses:
        print("No analysis files found!")
        return
    
    print(f"Found {len(analyses)} repository analyses.")
    results = analyze_package_popularity(analyses)
    print_popularity_analysis(results)
    
    # Print version analysis
    version_results = analyze_package_versions(analyses)
    print_version_analysis(version_results)
    
    # Save the results
    save_analysis_results(results)

if __name__ == "__main__":
    main() 