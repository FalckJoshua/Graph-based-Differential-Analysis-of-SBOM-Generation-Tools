import os
import glob

def find_and_remove_uv_lock_files():
    # Get the root directory and construct path to poetryrepo
    root_dir = os.getcwd()
    poetryrepo_dir = os.path.join(root_dir, 'poetryrepo')
    
    # Check if poetryrepo directory exists
    if not os.path.exists(poetryrepo_dir):
        print(f"Error: poetryrepo directory not found at {poetryrepo_dir}")
        return
    
    # Find all uv.lock files recursively in poetryrepo
    uv_lock_files = glob.glob(os.path.join(poetryrepo_dir, '**', 'uv.lock'), recursive=True)
    
    # Remove each uv.lock file
    for file_path in uv_lock_files:
        try:
            os.remove(file_path)
            print(f"Removed: {file_path}")
        except Exception as e:
            print(f"Error removing {file_path}: {str(e)}")
    
    print(f"\nTotal uv.lock files removed: {len(uv_lock_files)}")

if __name__ == "__main__":
    find_and_remove_uv_lock_files()
