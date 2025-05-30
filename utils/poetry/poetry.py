#!/usr/bin/env python3

import subprocess
import sys
import os
from pathlib import Path

def run_script(script_name):
    """Run a Python script and return its exit code."""
    try:
        result = subprocess.run([sys.executable, script_name], check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        return e.returncode

def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    # Define the sequence of scripts to run
    scripts = [
        "poetryCheck.py",
        "peotryGenerator.py",
        "poetryCheck.py",
        "fix_poetry_config.py",
        "peotryGenerator.py",
        "poetryCheck.py",
        "remove_uv.lock.py"
    ]
    
    # Run each script in sequence
    for script in scripts:
        script_path = script_dir / script
        print(f"\nRunning {script}...")
        exit_code = run_script(str(script_path))
        
        if exit_code != 0:
            print(f"Error: {script} failed with exit code {exit_code}")
            sys.exit(exit_code)
        
        print(f"Successfully completed {script}")

if __name__ == "__main__":
    main()
