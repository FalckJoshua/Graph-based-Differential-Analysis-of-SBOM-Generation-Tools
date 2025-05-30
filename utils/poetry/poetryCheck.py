import os
import shutil
from pathlib import Path

def check_and_move_poetry_repos():
    # Define paths
    original_dir = os.getcwd()
    cloned_repos_path = Path(os.path.join(original_dir, "cloned_repos"))
    poetry_repo_path = Path(os.path.join(original_dir, "poetryrepo"))
    
    # Create poetryrepo directory if it doesn't exist
    poetry_repo_path.mkdir(exist_ok=True)
    
    # Check if cloned_repos directory exists
    if not cloned_repos_path.exists():
        print("Error: 'cloned_repos' directory not found!")
        return
    
    # Get all directories in cloned_repos
    repos = [d for d in cloned_repos_path.iterdir() if d.is_dir()]
    
    # Counter for moved repos and list for non-poetry repos
    moved_count = 0
    non_poetry_repos = []
    
    # Check each repository
    for repo in repos:
        poetry_lock = repo / "poetry.lock"
        if poetry_lock.exists():
            # Move the repository to poetryrepo
            target_path = poetry_repo_path / repo.name
            shutil.move(str(repo), str(target_path))
            print(f"Moved {repo.name} to poetryrepo")
            moved_count += 1
        else:
            non_poetry_repos.append(repo.name)
    
    print(f"\nTotal repositories moved: {moved_count}")
    print("\nRepositories without poetry.lock:")
    for repo_name in non_poetry_repos:
        print(f"- {repo_name}")

if __name__ == "__main__":
    check_and_move_poetry_repos()
