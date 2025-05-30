import os
import subprocess
import json
from pathlib import Path
from datetime import datetime

def generate_poetry_lock(repo_path):
    """Generate poetry.lock file for a repository if it has pyproject.toml"""
    repo_path = Path(repo_path)
    pyproject_path = repo_path / "pyproject.toml"
    poetry_lock_path = repo_path / "poetry.lock"
    
    print(f"\nProcessing repository: {repo_path.name}")
    
    result = {
        "repository": repo_path.name,
        "has_pyproject": pyproject_path.exists(),
        "had_poetry_lock": poetry_lock_path.exists(),
        "success": False,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    if not result["has_pyproject"]:
        print(f"  ❌ No pyproject.toml found")
        result["error"] = "No pyproject.toml found"
        return result
    
    if result["had_poetry_lock"]:
        print(f"  ⚠️ poetry.lock already exists")
        result["error"] = "poetry.lock already exists"
        return result
    
    try:
        # Try to read pyproject.toml to get package name
        with open(pyproject_path, 'r') as f:
            content = f.read()
            if 'name =' in content:
                result["package_name"] = content.split('name =')[1].split('\n')[0].strip().strip('"\'')
                print(f"  📦 Package name: {result['package_name']}")
    except Exception as e:
        result["package_name"] = "unknown"
        result["error"] = f"Failed to read package name: {str(e)}"
        print(f"  ❌ Failed to read package name: {str(e)}")
        return result
    
    print(f"  🔄 Generating poetry.lock...")
    try:
        process = subprocess.run(["poetry", "lock"], cwd=repo_path, check=True, capture_output=True, text=True)
        result["success"] = True
        print(f"  ✅ Successfully generated poetry.lock")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed to generate poetry.lock")
        print(f"    Return code: {e.returncode}")
        if e.stdout:
            print(f"    stdout: {e.stdout}")
        if e.stderr:
            print(f"    stderr: {e.stderr}")
        result["error"] = {
            "type": "CalledProcessError",
            "return_code": e.returncode,
            "stdout": e.stdout,
            "stderr": e.stderr
        }
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        result["error"] = {
            "type": "Exception",
            "message": str(e)
        }
    
    return result

def main():
    cloned_repos_dir = Path("cloned_repos")
    if not cloned_repos_dir.exists():
        print("❌ cloned_repos directory not found!")
        return
    
    print("Starting poetry.lock generation process...")
    print(f"Found {len(list(cloned_repos_dir.iterdir()))} repositories to process")
    
    successful = 0
    failed = 0
    skipped = 0
    
    # Process each repository
    for repo_dir in cloned_repos_dir.iterdir():
        if repo_dir.is_dir():
            result = generate_poetry_lock(repo_dir)
            
            if result["success"]:
                successful += 1
            elif result["error"]:
                if isinstance(result["error"], str) and "already exists" in result["error"]:
                    skipped += 1
                else:
                    failed += 1
    
    print("\n" + "="*50)
    print("Final Summary:")
    print(f"📊 Total repositories processed: {successful + failed + skipped}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️ Skipped (already had poetry.lock): {skipped}")
    print("="*50)

if __name__ == "__main__":
    main()
