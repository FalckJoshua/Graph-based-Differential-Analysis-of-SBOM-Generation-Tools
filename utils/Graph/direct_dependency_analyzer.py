import json
from pathlib import Path
from collections import defaultdict
import statistics
from datetime import datetime
import re

def strip_version(package_name):
    """Remove version information from package name and normalize to lowercase."""
    # Common version patterns in package names
    version_patterns = [
        r'==\d+\.\d+\.\d+',  # ==1.2.3
        r'==\d+\.\d+',       # ==1.2
        r'==\d+',            # ==1
        r'>=\d+\.\d+\.\d+',  # >=1.2.3
        r'>=\d+\.\d+',       # >=1.2
        r'>=\d+',            # >=1
        r'<=\d+\.\d+\.\d+',  # <=1.2.3
        r'<=\d+\.\d+',       # <=1.2
        r'<=\d+',            # <=1
        r'~\d+\.\d+\.\d+',   # ~1.2.3
        r'~\d+\.\d+',        # ~1.2
        r'~\d+',             # ~1
        r'^\d+\.\d+\.\d+',   # 1.2.3
        r'^\d+\.\d+',        # 1.2
        r'^\d+',             # 1
    ]
    
    # Try to match and remove version patterns
    for pattern in version_patterns:
        package_name = re.sub(pattern, '', package_name)
    
    # Normalize to lowercase and strip whitespace
    return package_name.lower().strip()

def parse_dependencies(content):
    """Parse dependencies from pyproject.toml content, supporting both [tool.poetry.dependencies] and [project] (PEP 621)."""
    dependencies = []
    dev_dependencies = []
    python_version = None
    
    # Look for dependencies section
    dep_section = False
    dev_dep_section = False
    project_section = False
    project_deps = []
    project_requires_python = None
    
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            i += 1
            continue
        # Section headers
        if line.startswith('[tool.poetry.dependencies]'):
            dep_section = True
            dev_dep_section = False
            project_section = False
            i += 1
            continue
        elif line.startswith('[tool.poetry.dev-dependencies]'):
            dep_section = False
            dev_dep_section = True
            project_section = False
            i += 1
            continue
        elif line.startswith('[project]'):
            dep_section = False
            dev_dep_section = False
            project_section = True
            i += 1
            continue
        elif line.startswith('['):
            dep_section = False
            dev_dep_section = False
            project_section = False
            i += 1
            continue
        # Parse poetry dependency lines
        if dep_section or dev_dep_section:
            if '=' in line:
                package = line.split('=')[0].strip()
                version = line.split('=')[1].strip().strip('"\'')
                if dep_section:
                    dependencies.append((package, version))
                else:
                    dev_dependencies.append((package, version))
        # Parse [project] dependencies and requires-python
        if project_section:
            if line.startswith('dependencies = ['):
                # Start of dependencies array
                deps_line = line[len('dependencies = ['):].strip()
                if deps_line.endswith(']'):
                    deps_line = deps_line[:-1]
                project_deps.extend([d.strip().strip('"\'') for d in deps_line.split(',') if d.strip()])
                i += 1
                while i < len(lines) and not lines[i].strip().endswith(']'):
                    line = lines[i].strip()
                    project_deps.extend([d.strip().strip('"\'') for d in line.split(',') if d.strip()])
                    i += 1
                if i < len(lines):
                    line = lines[i].strip()
                    if line.endswith(']'):
                        project_deps.extend([d.strip().strip('"\'') for d in line[:-1].split(',') if d.strip()])
            elif line.startswith('requires-python') or line.startswith('requires_python'):
                # e.g. requires-python = ">=3.10,<3.11"
                _, val = line.split('=', 1)
                project_requires_python = val.strip().strip('"\'')
        i += 1
    # Add [project] dependencies
    for dep in project_deps:
        if dep:
            dependencies.append((dep, ''))
    # Add requires-python as a dependency if present
    if project_requires_python:
        dependencies.append(('python', project_requires_python))
    return dependencies, dev_dependencies

def load_all_pyprojects():
    """Load all pyproject.toml files from the poetry repositories."""
    current_dir = Path(__file__).parent.parent.parent
    poetry_dir = current_dir / 'poetryrepo'
    projects = []
    
    if not poetry_dir.exists():
        print(f"Poetry repository directory not found: {poetry_dir}")
        return []
    
    # Look for pyproject.toml files only at the top level of each repository
    for repo_dir in poetry_dir.iterdir():
        if repo_dir.is_dir():
            pyproject_file = repo_dir / 'pyproject.toml'
            if pyproject_file.exists():
                try:
                    with open(pyproject_file, 'r') as f:
                        content = f.read()
                        deps, dev_deps = parse_dependencies(content)
                        project_data = {
                            'repo_name': repo_dir.name,
                            'dependencies': deps,
                            'dev_dependencies': dev_deps
                        }
                        projects.append(project_data)
                except Exception as e:
                    print(f"Error loading {pyproject_file}: {e}")
    
    return projects

def analyze_direct_dependencies(projects):
    """Analyze direct dependencies from pyproject.toml files."""
    package_stats = defaultdict(lambda: {
        'repos': set(),
        'versions': set(),  # Track different versions seen
        'occurrences': 0,   # Count of times this package appears as a direct dependency
    })
    
    for project in projects:
        repo_name = project['repo_name']
        
        # Process main dependencies
        for dep_name, dep_version in project['dependencies']:
            original_name = f"{dep_name}{dep_version}"
            base_name = strip_version(dep_name)
            
            package_stats[base_name]['repos'].add(repo_name)
            package_stats[base_name]['versions'].add(original_name)
            package_stats[base_name]['occurrences'] += 1
        
        # Process dev dependencies
        for dep_name, dep_version in project['dev_dependencies']:
            original_name = f"{dep_name}{dep_version}"
            base_name = strip_version(dep_name)
            
            package_stats[base_name]['repos'].add(repo_name)
            package_stats[base_name]['versions'].add(original_name)
            package_stats[base_name]['occurrences'] += 1
    
    # Calculate aggregate statistics
    results = []
    for package, stats in package_stats.items():
        if len(stats['repos']) > 0:  # Only include packages that appear in at least one repo
            results.append({
                'package': package.lower(),  # Ensure package name is lowercase in output
                'repos': len(stats['repos']),
                'unique_versions': len(stats['versions']),
                'versions': sorted(list(stats['versions'])),
                'occurrences': stats['occurrences'],
                'repo_list': sorted(list(stats['repos']))
            })
    
    return sorted(results, key=lambda x: (x['repos'], x['occurrences']), reverse=True)

def save_analysis_results(results, num_repos):
    """Save the analysis results to a JSON file."""
    current_dir = Path(__file__).parent.parent.parent
    analysis_dir = current_dir / 'package_analysis'
    analysis_dir.mkdir(exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = analysis_dir / f'direct_dependency_analysis_{timestamp}.json'
    
    # Prepare the data for saving
    output_data = {
        'timestamp': timestamp,
        'total_packages': len(results),
        'total_repositories': num_repos,
        'packages': results
    }
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nAnalysis results saved to: {output_file}")
    return output_file

def print_dependency_analysis(results, num_repos, top_n=100):
    """Print a formatted summary of the direct dependency analysis."""
    print("\n" + "="*100)
    print("Direct Dependency Analysis Across Poetry Repositories")
    print("="*100)
    print(f"\nAnalyzed {num_repos} repositories.")
    print(f"\nTop {top_n} Most Common Direct Dependencies:")
    print("-"*100)
    print(f"{'Package':<40} {'Repos':<8} {'Versions':<10} {'Occurrences':<12}")
    print("-"*100)
    
    for pkg in results[:top_n]:
        print(f"{pkg['package'][:40]:<40} {pkg['repos']:<8} {pkg['unique_versions']:<10} "
              f"{pkg['occurrences']:<12}")
    
    print("\nDetailed Repository Coverage:")
    print("-"*100)
    for pkg in results[:top_n]:
        print(f"\n{pkg['package']}:")
        print(f"  Directly used in {pkg['repos']} repositories with {pkg['unique_versions']} different versions:")
        print("  Versions:")
        for version in pkg['versions']:
            print(f"    - {version}")
        print("  Repositories:")
        for repo in pkg['repo_list']:
            print(f"    - {repo}")

def main():
    print("Loading and analyzing direct dependencies from pyproject.toml files...")
    projects = load_all_pyprojects()
    
    if not projects:
        print("No pyproject.toml files found!")
        return
    
    num_repos = len(projects)
    print(f"Found {num_repos} pyproject.toml files.")
    results = analyze_direct_dependencies(projects)
    print_dependency_analysis(results, num_repos)
    
    # Save the results
    save_analysis_results(results, num_repos)

if __name__ == "__main__":
    main() 