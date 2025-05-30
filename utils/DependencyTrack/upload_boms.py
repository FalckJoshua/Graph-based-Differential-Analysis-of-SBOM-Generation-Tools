import os
import requests
import concurrent.futures
from typing import Tuple
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dependency-Track API configuration
DT_URL = os.getenv('DT_URL')
API_KEY = os.getenv('DT_API_KEY')

if not DT_URL or not API_KEY:
    raise ValueError("Please set DT_URL and DT_API_KEY in your .env file")

def upload_bom(bom_file_path, project_name, project_version):
    """Upload a BOM file to Dependency-Track"""
    print(f"\nAttempting to upload BOM: {bom_file_path}")
    print(f"Project: {project_name}, Version: {project_version}")
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    # First, create or get the project
    project_data = {
        "name": project_name,
        "version": project_version
    }
    
    # Check if project exists
    print("Checking if project exists...")
    response = requests.get(f"{DT_URL}/api/v1/project", headers=headers)
    if response.status_code == 200:
        projects = response.json()
        project = next((p for p in projects if p['name'] == project_name and p['version'] == project_version), None)
        
        if not project:
            print("Project not found, creating new project...")
            response = requests.put(f"{DT_URL}/api/v1/project", headers=headers, json=project_data)
            if response.status_code != 201:
                print(f"Error creating project: {response.status_code}")
                print(f"Response: {response.text}")
                return None
            project = response.json()
            print(f"Created new project: {project}")
    
    # Upload BOM
    print(f"Uploading BOM file: {bom_file_path}")
    try:
        with open(bom_file_path, 'rb') as f:
            files = {'bom': (os.path.basename(bom_file_path), f)}
            response = requests.post(
                f"{DT_URL}/api/v1/bom",
                headers={'X-API-Key': API_KEY},
                files=files,
                data={'projectName': project_name, 'projectVersion': project_version}
            )
        
        print(f"Upload response status: {response.status_code}")
        print(f"Upload response: {response.text}")
        
        if response.status_code == 200:
            token = response.json().get('token')
            print(f"BOM upload started for {project_name} {project_version}. Token: {token}")
            return token
        else:
            print(f"Error uploading BOM: {response.status_code}")
            print(f"Error response: {response.text}")
            return None
    except Exception as e:
        print(f"Exception during BOM upload: {str(e)}")
        return None

def wait_for_processing(token):
    """Wait for BOM processing to complete"""
    print(f"\nWaiting for BOM processing (token: {token})...")
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    max_retries = 12  # Maximum number of retries (1 minute total)
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(f"{DT_URL}/api/v1/bom/token/{token}", headers=headers)
            print(f"Processing status response: {response.status_code}")
            if response.status_code == 200:
                status = response.json()
                print(f"Processing status: {status}")
                if status.get('processing') is False:
                    if status.get('failed'):
                        print(f"BOM processing failed: {status.get('failureReason')}")
                        return False
                    return True
            retry_count += 1
            time.sleep(5)  # Wait 5 seconds before checking again
        except Exception as e:
            print(f"Exception while checking processing status: {str(e)}")
            retry_count += 1
            time.sleep(5)
    
    print(f"Maximum retries ({max_retries}) reached. Processing may still be in progress.")
    return False

def process_single_bom(file_path: str, project_name: str, project_version: str) -> Tuple[bool, str]:
    """Process a single BOM file and return success status and message"""
    try:
        print(f"\nProcessing {file_path}")
        print(f"Project: {project_name}, Version: {project_version}")
        
        # Upload BOM
        print("Step 1: Uploading BOM...")
        token = upload_bom(file_path, project_name, project_version)
        if token:
            print("Step 2: Waiting for processing...")
            # Wait for processing
            if wait_for_processing(token):
                return True, f"Successfully processed {file_path}"
            else:
                return False, f"Failed to process BOM for {project_name} {project_version}"
        else:
            return False, f"Failed to upload BOM for {project_name} {project_version}"
    except Exception as e:
        return False, f"Error processing {file_path}: {str(e)}"

def process_directory(input_dir):
    """Process all BOM files in the input directory using multi-threading"""
    print(f"\nProcessing directory: {input_dir}")
    
    # Supported BOM file extensions
    bom_extensions = {'.json', '.xml', '.spdx', '.cyclonedx'}
    
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist")
        return
    
    # List all files in the input directory
    print(f"Contents of {input_dir}:")
    for root, _, files in os.walk(input_dir):
        print(f"\nDirectory: {root}")
        for file in files:
            print(f"  File: {file}")
    
    # Collect all BOM files to process
    bom_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in bom_extensions:
                # Get the repository name from the directory name
                repo_name = os.path.basename(root)
                # Create a project name that includes both repo name and BOM type
                project_name = f"{repo_name}&{os.path.splitext(file)[0]}"
                project_version = "1.0.0"
                bom_files.append((file_path, project_name, project_version))
                print(f"Added BOM file for processing: {file_path}")
            else:
                print(f"Skipping {file_path} - not a supported BOM format")
    
    # Upload all BOMs and collect tokens
    upload_results = []
    for file_path, project_name, project_version in bom_files:
        print(f"Uploading {file_path} for project {project_name} version {project_version}")
        token = upload_bom(file_path, project_name, project_version)
        upload_results.append((file_path, project_name, project_version, token))

    # Wait for processing for each uploaded BOM
    failed_uploads = []
    successful_uploads = []
    for file_path, project_name, project_version, token in upload_results:
        if token:
            print(f"Waiting for processing of {file_path}")
            if wait_for_processing(token):
                successful_uploads.append((file_path, project_name, project_version, "Successfully processed"))
            else:
                failed_uploads.append((file_path, project_name, project_version, "Failed to process BOM"))
        else:
            failed_uploads.append((file_path, project_name, project_version, "Failed to upload BOM"))

    # Print summary of successful uploads
    if successful_uploads:
        print("\nSuccessful Uploads Summary:")
        print("=" * 80)
        for file_path, project_name, project_version, message in successful_uploads:
            print(f"File: {file_path}")
            print(f"Project: {project_name} (Version: {project_version})")
            print(f"Status: {message}")
            print("-" * 80)
    
    # Print summary of failed uploads
    if failed_uploads:
        print("\nFailed Uploads Summary:")
        print("=" * 80)
        for file_path, project_name, project_version, error in failed_uploads:
            print(f"File: {file_path}")
            print(f"Project: {project_name} (Version: {project_version})")
            print(f"Error: {error}")
            print("-" * 80)
    else:
        print("\nAll BOMs processed successfully!")

def main():
    # Configure input directory
    input_dir = "sbom_fixed"  # Directory containing original BOMs
    
    if not API_KEY:
        print("Please set your Dependency-Track API key in the script")
        return
    
    print(f"Starting BOM upload process...")
    print(f"Input directory: {input_dir}")
    print(f"Dependency-Track URL: {DT_URL}")
    
    process_directory(input_dir)
    
    print("\nBOM upload process completed")

if __name__ == "__main__":
    main() 