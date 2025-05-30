#!/usr/bin/env python3

import subprocess
import os
from pathlib import Path
import multiprocessing
from math import ceil

def clone_repository(repo_info):
    repo, clone_dir = repo_info
    try:
        print(f"Cloning {repo}...")
        # Extract repository name from URL
        repo_name = repo.split('/')[-1].replace('.git', '')
        target_dir = clone_dir / repo_name

        # Clone the repository
        subprocess.run(['git', 'clone', repo, str(target_dir)], check=True)
        
        # Initialize Git LFS in the cloned repository
        try:
            subprocess.run(['git', 'lfs', 'install'], cwd=str(target_dir), check=True)
            subprocess.run(['git', 'lfs', 'pull'], cwd=str(target_dir), check=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Git LFS initialization failed for {repo}: {e}")
            # Continue even if LFS fails - the repository is still cloned
        
        print(f"Successfully cloned {repo}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cloning {repo}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error while cloning {repo}: {e}")
        return False

def clone_repositories():
    # Check if repos.txt exists
    if not os.path.exists('repos.txt'):
        print("Error: repos.txt file not found!")
        return

    # Create a directory for cloned repositories if it doesn't exist
    clone_dir = Path('cloned_repos')
    clone_dir.mkdir(exist_ok=True)

    # Read repositories from repos.txt
    with open('repos.txt', 'r') as file:
        repos = [line.strip() for line in file if line.strip()]

    # Calculate number of processes to use (75% of available cores)
    num_cores = multiprocessing.cpu_count()
    num_processes = ceil(num_cores * 0.75)
    print(f"Using {num_processes} processes for cloning")

    # Prepare repository info for multiprocessing
    repo_info_list = [(repo, clone_dir) for repo in repos]

    # Create a pool of workers and process repositories in parallel
    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(clone_repository, repo_info_list)

    # Count successful clones
    successful_clones = sum(1 for result in results if result)
    print(f"\nCloning complete! Successfully cloned {successful_clones} out of {len(repos)} repositories")

if __name__ == "__main__":
    clone_repositories()
