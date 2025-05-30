#!/usr/bin/env python3

import os
import toml
from pathlib import Path

def get_package_name(file_path):
    """Get a suitable package name from the directory structure."""
    path = Path(file_path)
    # Try to get the repository name (parent of src directory)
    if 'src' in path.parts:
        src_index = path.parts.index('src')
        if src_index > 0:
            return path.parts[src_index - 1]
    # Fallback to parent directory name
    return path.parent.name

def fix_poetry_config(file_path):
    """Add minimal Poetry configuration to a pyproject.toml file."""
    try:
        # Read existing configuration
        with open(file_path, 'r') as f:
            config = toml.load(f)
        
        # Add minimal Poetry configuration if not present
        if 'tool' not in config:
            config['tool'] = {}
        
        if 'poetry' not in config['tool']:
            package_name = get_package_name(file_path)
            
            config['tool']['poetry'] = {
                'name': package_name,
                'version': '0.1.0',
                'description': f'{package_name} package',
                'authors': [package_name]  # Use package name as author
            }
            
            # Write back the configuration
            with open(file_path, 'w') as f:
                toml.dump(config, f)
            print(f"✅ Added Poetry configuration to {file_path}")
            print(f"   Package name: {package_name}")
            print(f"   Author: {package_name}")
        else:
            print(f"ℹ️  Poetry configuration already exists in {file_path}")
            
    except Exception as e:
        print(f"❌ Error processing {file_path}: {str(e)}")

def get_repositories():
    """Get list of repositories in cloned_repos directory."""
    if not os.path.exists('cloned_repos'):
        print("❌ Directory 'cloned_repos' not found!")
        return []
    
    repos = []
    for item in os.listdir('cloned_repos'):
        if os.path.isdir(os.path.join('cloned_repos', item)):
            repos.append(item)
    return sorted(repos)

def find_pyproject_files(repo_name):
    """Find all pyproject.toml files in a specific repository."""
    repo_path = os.path.join('cloned_repos', repo_name)
    if not os.path.exists(repo_path):
        print(f"❌ Repository '{repo_name}' not found!")
        return []
        
    pyproject_files = []
    for root, _, files in os.walk(repo_path):
        if 'pyproject.toml' in files:
            pyproject_files.append(os.path.join(root, 'pyproject.toml'))
    return pyproject_files

def main():
    repos = get_repositories()
    if not repos:
        print("No repositories found in cloned_repos directory!")
        return
    
    print("\nProcessing all repositories...")
    for repo_name in repos:
        print(f"\nProcessing repository: {repo_name}")
        pyproject_files = find_pyproject_files(repo_name)
        if not pyproject_files:
            print(f"No pyproject.toml files found in {repo_name}")
            continue
            
        print(f"Found {len(pyproject_files)} pyproject.toml files")
        for file_path in pyproject_files:
            fix_poetry_config(file_path)

if __name__ == '__main__':
    main()