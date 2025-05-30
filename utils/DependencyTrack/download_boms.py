import os
import requests
import json
import concurrent.futures
from typing import Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dependency-Track API configuration
DT_URL = os.getenv('DT_URL')
API_KEY = os.getenv('DT_API_KEY')

if not DT_URL or not API_KEY:
    raise ValueError("Please set DT_URL and DT_API_KEY in your .env file")

def download_bom(project_name, project_version, project_uuid, output_dir):
    """Download the standardized BOM from Dependency-Track"""
    print(f"\nAttempting to download BOM for {project_name} {project_version}")
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    # Download BOM using the export endpoint
    print("Downloading BOM from export endpoint...")
    response = requests.get(
        f"{DT_URL}/api/v1/bom/cyclonedx/project/{project_uuid}",
        headers=headers
    )
    
    if response.status_code == 200:
        # Extract repository name from the project name (everything before the first &)
        repo_name = project_name.split('&')[0]
        
        # Create repository-specific directory
        repo_dir = os.path.join(output_dir, repo_name)
        os.makedirs(repo_dir, exist_ok=True)
        
        # Save the BOM in the repository-specific directory
        output_path = os.path.join(repo_dir, f"{project_name}&{project_version}_standardized.bom.json")
        print(f"Saving BOM to: {output_path}")
        with open(output_path, 'w') as f:
            json.dump(response.json(), f, indent=2)
        print(f"Downloaded standardized BOM to {output_path}")
        return True
    else:
        print(f"Error downloading BOM: {response.status_code}")
        print(f"Error response: {response.text}")
        return False

def process_single_bom(project_name: str, project_version: str, project_uuid: str, output_dir: str) -> Tuple[bool, str]:
    """Process a single BOM download and return success status and message"""
    try:
        print(f"\nProcessing {project_name} {project_version}")
        
        # Download standardized BOM
        print("Downloading standardized BOM...")
        success = download_bom(project_name, project_version, project_uuid, output_dir)
        if success:
            return True, f"Successfully downloaded BOM for {project_name} {project_version}"
        else:
            return False, f"Failed to download BOM for {project_name} {project_version}"
    except Exception as e:
        return False, f"Error processing {project_name} {project_version}: {str(e)}"

def get_all_projects():
    """Get all projects from Dependency-Track with pagination support"""
    print("\nFetching all projects from Dependency-Track...")
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    all_projects = []
    page = 1
    page_size = 100  # Maximum allowed by API
    total_count = None
    
    while True:
        response = requests.get(
            f"{DT_URL}/api/v1/project",
            headers=headers,
            params={"pageNumber": page, "pageSize": page_size}
        )
        if response.status_code == 200:
            # Get total count from response headers if available
            if total_count is None and 'X-Total-Count' in response.headers:
                total_count = int(response.headers['X-Total-Count'])
                print(f"Total projects to fetch: {total_count}")
            
            projects = response.json()
            if projects:  # Only extend if we got projects
                all_projects.extend(projects)
                print(f"Fetched {len(all_projects)}/{total_count if total_count else 'unknown'} projects")
            
            # Break if we've fetched all projects or if this page is empty
            if total_count and len(all_projects) >= total_count:
                break
            if not projects:
                break
                
            page += 1
        else:
            print(f"Error fetching projects: {response.status_code}")
            print(f"Error response: {response.text}")
            break
    
    print(f"Found {len(all_projects)} projects")
    return all_projects

def process_projects(output_dir):
    """Process all projects and download their BOMs"""
    print(f"\nStarting BOM download process for all projects")
    print(f"Output directory: {output_dir}")
    
    # Get all projects
    projects = get_all_projects()
    if not projects:
        print("No projects found or error fetching projects")
        return
    
    # Process projects in parallel using ThreadPoolExecutor
    num_workers = max(1, int(os.cpu_count() * 0.75))
    print(f"\nProcessing {len(projects)} projects using {num_workers} workers")
    
    failed_downloads = []
    successful_downloads = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        future_to_project = {
            executor.submit(process_single_bom, 
                          project['name'], 
                          project['version'], 
                          project['uuid'], 
                          output_dir): project
            for project in projects
        }
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_project):
            project = future_to_project[future]
            try:
                success, message = future.result()
                if success:
                    successful_downloads.append((project['name'], project['version'], message))
                else:
                    failed_downloads.append((project['name'], project['version'], message))
                print(message)
            except Exception as e:
                error_msg = f"Error processing {project['name']} {project['version']}: {str(e)}"
                failed_downloads.append((project['name'], project['version'], error_msg))
                print(error_msg)
    
    # Print summary of successful downloads
    if successful_downloads:
        print("\nSuccessful Downloads Summary:")
        print("=" * 80)
        for project_name, project_version, message in successful_downloads:
            print(f"Project: {project_name} (Version: {project_version})")
            print(f"Status: {message}")
            print("-" * 80)
    
    # Print summary of failed downloads
    if failed_downloads:
        print("\nFailed Downloads Summary:")
        print("=" * 80)
        for project_name, project_version, error in failed_downloads:
            print(f"Project: {project_name} (Version: {project_version})")
            print(f"Error: {error}")
            print("-" * 80)
    else:
        print("\nAll BOMs downloaded successfully!")

def main():
    # Configure output directory
    output_dir = "standardized_boms"  # Directory for standardized BOMs
    
    if not API_KEY:
        print("Please set your Dependency-Track API key in the script")
        return
    
    print(f"Starting BOM download process...")
    print(f"Output directory: {output_dir}")
    print(f"Dependency-Track URL: {DT_URL}")
    
    process_projects(output_dir)
    
    print("\nBOM download process completed")

if __name__ == "__main__":
    main() 