import os
import json
from pathlib import Path
import shutil

def add_root_node_to_sbom(file_path, output_dir):
    with open(file_path, 'r') as f:
        sbom = json.load(f)

    # Ensure it's a Syft/CycloneDX SBOM
    if not sbom.get("bomFormat", "").lower() == "cyclonedx" or "metadata" not in sbom:
        print(f"Skipping {file_path} (not a CycloneDX SBOM)")
        return

    # If no dependencies section, nothing to do
    if "dependencies" not in sbom or not sbom["dependencies"]:
        print(f"Skipping {file_path} (no dependencies section)")
        return

    # Find all refs and all dependsOn targets
    all_refs = set(dep['ref'] for dep in sbom['dependencies'])
    all_depends = set(child for dep in sbom['dependencies'] for child in dep.get('dependsOn', []))
    top_level = all_refs - all_depends

    # Use the metadata component as the root ref if possible
    root_ref = sbom["metadata"]["component"].get("bom-ref", "root")

    root_node = {
        "ref": root_ref,
        "dependsOn": list(top_level)
    }

    # Avoid duplicate root entry if it exists
    if not any(dep.get("ref") == root_ref for dep in sbom["dependencies"]):
        sbom["dependencies"].insert(0, root_node)

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create output path in the fixedSyft directory, preserving the relative path
    relative_path = file_path.relative_to(input_path)
    output_path = output_dir / relative_path
    
    # Create parent directories if they don't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(sbom, f, indent=2)

    print(f"✔ Added root to: {relative_path} → {output_path}")

def process_all_sboms(input_folder, output_folder):
    global input_path
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Process all SBOM files
    for sbom_file in input_path.rglob("*.json"):
        if sbom_file.name == "sbom-syft.json":
            # Process and fix Syft SBOMs
            add_root_node_to_sbom(sbom_file, output_path)
        elif sbom_file.name in ["cdxgen-bom.json", "trivy-sbom-cdx.json"]:
            # Copy other SBOMs directly
            relative_path = sbom_file.relative_to(input_path)
            output_file = output_path / relative_path
            output_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sbom_file, output_file)
            print(f"✔ Copied: {relative_path} → {output_file}")

def process_all_subfolders(input_folder, output_folder):
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    for subfolder in input_path.iterdir():
        if subfolder.is_dir():
            subfolder_name = subfolder.name
            sub_output_folder = output_path / subfolder_name
            process_all_sboms(subfolder, sub_output_folder)

def copy_valid_sboms(input_folder, output_folder):
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    for sbom_file in input_path.glob("*.json"):
        if sbom_file.name != "sbom-syft.json":
            shutil.copy(sbom_file, output_path)

if __name__ == "__main__":
    # Example usage
    input_folder = "sbom"
    output_folder = "fixedSBOM"
    process_all_subfolders(input_folder, output_folder)
    copy_valid_sboms(input_folder, output_folder)