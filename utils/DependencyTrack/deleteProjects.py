import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dependency-Track API configuration
DT_URL = os.getenv('DT_URL')
API_KEY = os.getenv('DT_API_KEY')

if not DT_URL or not API_KEY:
    raise ValueError("Please set DT_URL and DT_API_KEY in your .env file")

def get_all_projects():
    """Fetch all projects from Dependency-Track with pagination support"""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    all_projects = []
    page = 1
    page_size = 100  # Maximum allowed by API
    
    while True:
        response = requests.get(
            f"{DT_URL}/api/v1/project",
            headers=headers,
            params={"pageNumber": page, "pageSize": page_size}
        )
        
        if response.status_code == 200:
            projects = response.json()
            if not projects:  # No more projects
                break
            all_projects.extend(projects)
            if len(projects) < page_size:  # Last page
                break
            page += 1
        else:
            print(f"Error fetching projects: {response.status_code}")
            break
    
    return all_projects

def delete_project(project_uuid):
    """Delete a specific project by UUID"""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.delete(f"{DT_URL}/api/v1/project/{project_uuid}", headers=headers)
    if response.status_code == 204:
        print(f"Successfully deleted project {project_uuid}")
    else:
        print(f"Error deleting project {project_uuid}: {response.status_code}")

def main():
    if not API_KEY:
        print("Please set your Dependency-Track API key in the script")
        return

    print("Starting project cleanup of Dependency-Track...")
    
    # Delete all projects
    print("\nDeleting all projects...")
    projects = get_all_projects()
    if projects:
        print(f"Found {len(projects)} projects. Starting deletion...")
        for project in projects:
            project_uuid = project.get('uuid')
            if project_uuid:
                delete_project(project_uuid)
    else:
        print("No projects found or error occurred")
    
    print("\nProject cleanup completed")

if __name__ == "__main__":
    main()
