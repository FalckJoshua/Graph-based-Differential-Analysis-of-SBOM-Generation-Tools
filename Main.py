import os
import subprocess
import sys
import shutil
from pathlib import Path
import time
import multiprocessing
from utils.export_confirmed_deps import export_confirmed_dependencies
from utils.syftfixer import process_all_subfolders, copy_valid_sboms
from utils.poetry.poetryCheck import check_and_move_poetry_repos
from utils.poetry.peotryGenerator import main as generate_poetry_locks
from utils.DependencyTrack.deleteProjects import main as delete_dt_projects
from utils.Graph.graphMaker import main as create_graph
from utils.massclone import clone_repositories
from utils.DependencyTrack.upload_boms import main as upload_boms
from utils.DependencyTrack.download_boms import main as download_boms
from utils.vuln_compare import main as run_vuln_compare


# Add the sbom directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'sbom'))
#from copy_sbom import process_sbom_files

class PackageValidator:
    def __init__(self):
        self.original_dir = os.getcwd()

    @staticmethod
    def get_available_cores():
        """Get available CPU cores, leaving some for system processes."""
        return max(1, multiprocessing.cpu_count() - 5)

    def create_sbom_directory(self, repo_name):
        """Create SBOM directory structure for a repository."""
        sbom_dir = os.path.join(self.original_dir, "sbom", repo_name)
        os.makedirs(sbom_dir, exist_ok=True)
        return sbom_dir

    def write_repo_link(self, sbom_dir, repo_url):
        """Write repository URL to a file in the SBOM directory."""
        repo_link_file = os.path.join(sbom_dir, "repo_link.txt")
        try:
            with open(repo_link_file, "w") as link_file:
                link_file.write(repo_url)
            print(f"GitHub repository link written to {repo_link_file}")
        except Exception as e:
            print(f"Error writing GitHub repository link to {repo_link_file}: {e}")

    def run_sbom_tools(self, sbom_dir):
        """Run all SBOM generation tools and return their results."""
        # Run syft display
        print("Running syft scan for terminal display...")
        syft_display = subprocess.run(
            ["syft", "dir:."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Run Syft JSON
        syft_sbom_path = os.path.join(sbom_dir, "sbom-syft.json")
        print(f"Generating SBOM file (cyclonedx-json) at {syft_sbom_path}...")
        with open(syft_sbom_path, "w") as output_file:
            syft_json = subprocess.run(
                ["syft", "dir:.", "-o", "cyclonedx-json"],
                stdout=output_file,
                stderr=subprocess.PIPE,
                text=True
            )

        # Run cdxgen
        cdxgen_sbom_path = os.path.join(sbom_dir, "cdxgen-bom.json")
        print(f"Running cdxgen to generate {cdxgen_sbom_path}...")
        cdxgen_result = subprocess.run(
            ["cdxgen", "-p", "-o", cdxgen_sbom_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Run trivy
        trivy_sbom_path = os.path.join(sbom_dir, "trivy-sbom-cdx.json")
        print(f"Running trivy to generate {trivy_sbom_path}...")
        trivy_result = subprocess.run(
            ["trivy", "fs", "--format", "cyclonedx", "--scanners", "vuln", "--output", trivy_sbom_path, "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        return syft_display, syft_json, cdxgen_result, trivy_result

    def print_tool_outputs(self, syft_display, syft_json, cdxgen_result, trivy_result):
        """Print the outputs and errors from all SBOM tools."""
        print("\n cdxgen Output")
        print("\n cdxgen Errors (if any)")
        print(cdxgen_result.stderr)

        print("\n Syft Output")
        print(syft_display.stdout)
        print("\n Syft Errors (if any)")
        print(syft_display.stderr or syft_json.stderr)

        print("\n Trivy Output")
        print(trivy_result.stdout)
        print("\n Trivy Errors (if any)")
        print(trivy_result.stderr)

    def create_sboms(self, sbom_dir):
        """Create SBOMs for the current directory and save them to the specified directory."""
        # Run all SBOM tools
        syft_display, syft_json, cdxgen_result, trivy_result = self.run_sbom_tools(sbom_dir)
        self.print_tool_outputs(syft_display, syft_json, cdxgen_result, trivy_result)

        # Check if packages were discovered
        packages_discovered = (
            syft_display.returncode == 0 and
            syft_json.returncode == 0 and
            "No packages discovered" not in syft_display.stdout
        )

        print(f"\npackages_discovered = {packages_discovered}")
        return packages_discovered

    def process_repository(self, repo_url):
        """Process a single repository."""
        try:
            success, repo_name = self.analyze_repo(repo_url)
            return repo_name
        except Exception as e:
            print(f"Error processing repository {repo_url}: {str(e)}")
            return None

    def analyze_repo(self, repo_url):
        """Analyze a single repository by cloning and running SBOM tools."""
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        print(f"\n Starting analysis for: {repo_name}")

        # Create cloned_repos directory if it doesn't exist
        cloned_repos_dir = os.path.join(self.original_dir, "cloned_repos")
        os.makedirs(cloned_repos_dir, exist_ok=True)
        
        repo_path = os.path.join(cloned_repos_dir, repo_name)
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)
        else:
            print(f"Folder '{repo_name}' already exists in cloned_repos. hoppa.")
            return False, repo_name

        os.chdir(repo_path)

        # Clone repo
        print(f"Clone {repo_url} into {os.getcwd()}...")
        clone_result = subprocess.run(["git", "clone", repo_url, "."], capture_output=True, text=True)
        if clone_result.returncode != 0:
            print(f"Error cloning repository: {clone_result.stderr}")
            os.chdir(self.original_dir)
            return False, repo_name
        print("Repo cloned success.")

        # Create SBOM directory and write repo link
        sbom_dir = self.create_sbom_directory(repo_name)
        self.write_repo_link(sbom_dir, repo_url)

        # Create SBOMs
        packages_discovered = self.create_sboms(sbom_dir)

        # Go back to original directory
        os.chdir(self.original_dir)
        print("Changed back to original directory:", os.getcwd())

        return True, repo_name

    def analyze_existing_repo(self, repo_dir):
        """Analyze an existing repository directory."""
        repo_name = os.path.basename(repo_dir)
        print(f"\nStarting analysis for existing repo: {repo_name}")

        # Create SBOM directory
        sbom_dir = self.create_sbom_directory(repo_name)

        # Change to repository directory
        os.chdir(repo_dir)

        # Get repository URL
        try:
            repo_url = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                text=True
            ).strip()
        except subprocess.CalledProcessError:
            repo_url = "Unknown"

        # Write repo link and create SBOMs
        self.write_repo_link(sbom_dir, repo_url)
        packages_discovered = self.create_sboms(sbom_dir)

        # Go back to original directory
        os.chdir(self.original_dir)

        return packages_discovered

    def option_scan_text_file(self):
        """Handle batch repository analysis from text file."""
        with open("repos.txt", "r") as file:
            repo_urls = [line.strip() for line in file.readlines()]

        cpu_cores = self.get_available_cores()
        print(f"Using {cpu_cores} CPU cores")

        with multiprocessing.Pool(processes=cpu_cores) as pool:
            results = pool.map(self.process_repository, repo_urls)
        
        successful_results = [r for r in results if r is not None]
        print(f"\nSuccessfully processed {len(successful_results)} out of {len(repo_urls)} repositories")

    def option_mass_clone(self):
        """Handle mass cloning of repositories without immediate analysis."""
        with open("repos.txt", "r") as file:
            repo_urls = [line.strip() for line in file.readlines()]

        cloned_repos_dir = os.path.join(self.original_dir, "cloned_repos")
        os.makedirs(cloned_repos_dir, exist_ok=True)

        success_count = 0
        failed_count = 0
        skipped_count = 0

        # Initialize Git LFS
        print("Initializing Git LFS...")
        subprocess.run(["git", "lfs", "install"], check=True)

        for repo_url in repo_urls:
            try:
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                repo_path = os.path.join(cloned_repos_dir, repo_name)
                
                print(f"\nProcessing {repo_name}...")
                
                # If directory exists, remove it first
                if os.path.exists(repo_path):
                    print(f"Removing existing directory for {repo_name}...")
                    shutil.rmtree(repo_path)
                
                print(f"Cloning {repo_name}...")
                os.makedirs(repo_path)
                os.chdir(repo_path)
                
                # Clone with LFS support
                clone_result = subprocess.run(
                    ["git", "clone", "--recursive", repo_url, "."],
                    capture_output=True,
                    text=True
                )
                
                if clone_result.returncode == 0:
                    # Initialize LFS in the cloned repository
                    subprocess.run(["git", "lfs", "install"], check=True)
                    # Pull LFS objects
                    subprocess.run(["git", "lfs", "pull"], check=True)
                    success_count += 1
                    print(f"Successfully cloned {repo_name}")
                else:
                    failed_count += 1
                    print(f"Failed to clone {repo_name}: {clone_result.stderr}")
                
                os.chdir(self.original_dir)
                
            except Exception as e:
                failed_count += 1
                print(f"Error processing {repo_url}: {str(e)}")
                os.chdir(self.original_dir)

        print(f"\nCloning complete:")
        print(f"Successfully cloned: {success_count}")
        print(f"Failed to clone: {failed_count}")
        print(f"Skipped (already existed): {skipped_count}")
        print(f"Total repositories processed: {len(repo_urls)}")

    def generate_sboms_for_repos(self):
        """Generate SBOMs for repositories in poetryrepo directory."""
        poetryrepo_path = os.path.join(self.original_dir, 'poetryrepo')
        if not os.path.exists(poetryrepo_path):
            print("Error: poetryrepo directory not found!")
            return

        repos = [d for d in os.listdir(poetryrepo_path) 
                if os.path.isdir(os.path.join(poetryrepo_path, d)) and not d.startswith('.')]

        if not repos:
            print("No repositories found in poetryrepo directory.")
            return

        print(f"\nFound {len(repos)} repositories to process:")
        for repo in repos:
            print(f"- {repo}")

        success_count = 0
        for repo_name in repos:
            try:
                repo_path = os.path.join(poetryrepo_path, repo_name)
                print(f"\nProcessing {repo_name}...")
                
                # Create SBOM directory
                sbom_dir = self.create_sbom_directory(repo_name)
                
                # Change to repository directory
                os.chdir(repo_path)
                
                # Get repository URL if available
                try:
                    repo_url = subprocess.check_output(
                        ["git", "config", "--get", "remote.origin.url"],
                        text=True
                    ).strip()
                except subprocess.CalledProcessError:
                    repo_url = "Unknown"
                
                # Write repo link and create SBOMs
                self.write_repo_link(sbom_dir, repo_url)
                if self.create_sboms(sbom_dir):
                    success_count += 1
                    print(f"Successfully generated SBOMs for {repo_name}")
                
                # Go back to original directory
                os.chdir(self.original_dir)
                
            except Exception as e:
                print(f"Error processing repository {repo_name}: {str(e)}")
                os.chdir(self.original_dir)

        print(f"\nSBOM generation complete! Successfully processed {success_count} out of {len(repos)} repositories")
        
        # Run Syft fixer on all generated SBOMs
        print("\nRunning Syft fixer on generated SBOMs...")
        sbom_dir = os.path.join(self.original_dir, "sbom")
        fixed_sbom_dir = os.path.join(self.original_dir, "sbom_fixed")
        process_all_subfolders(sbom_dir, fixed_sbom_dir)
        copy_valid_sboms(sbom_dir, fixed_sbom_dir)
        print("Syft fixer processing complete!")

def main():
    validator = PackageValidator()
    
    while True:
        print("\nMain Menu:")
        print("1. SBOM Analysis")
        print("2. Dependency Track")
        print("3. Graph Analysis")
        print("4. Vulnerability Comparison")
        print("5. All-in-One Analysis")
        print("6. Exit")
        
        main_choice = input("Enter your choice (1/2/3/4/5/6): ").strip()
        
        if main_choice == '1':
            print("\nSBOM Analysis Menu:")
            print("1. Mass Clone repositories")
            print("2. Run Poetry Check")
            print("3. Generate SBOMs for cloned repos")
            print("4. Back to Main Menu")
            
            sbom_choice = input("Enter your choice (1/2/3/4): ").strip()
            
            if sbom_choice == '1':
                clone_repositories()
            elif sbom_choice == '2':
                from utils.poetry.poetry import main as run_poetry_analysis
                run_poetry_analysis()
            elif sbom_choice == '3':
                validator.generate_sboms_for_repos()
            elif sbom_choice == '4':
                continue
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
                
        elif main_choice == '2':
            print("\nDependency Track Menu:")
            print("1. Run Dependency Track Analysis")
            print("2. Back to Main Menu")
            
            dt_choice = input("Enter your choice (1/2): ").strip()
            
            if dt_choice == '1':
                from utils.DependencyTrack.dt import main as run_dt_analysis
                run_dt_analysis()
            elif dt_choice == '2':
                continue
            else:
                print("Invalid choice. Please enter 1 or 2.")
                
        elif main_choice == '3':
            print("\nGraph Analysis Menu:")
            print("1. Run Graph Analysis")
            print("2. Back to Main Menu")
            
            graph_choice = input("Enter your choice (1/2): ").strip()
            
            if graph_choice == '1':
                from utils.Graph.graph import main as run_graph_analysis
                run_graph_analysis()
            elif graph_choice == '2':
                continue
            else:
                print("Invalid choice. Please enter 1 or 2.")
                
        elif main_choice == '4':
            print("\nRunning Vulnerability Comparison...")
            print("--------------------------------")
            run_vuln_compare()
            print("\nVulnerability Comparison completed!")
            
        elif main_choice == '5':
            print("\nStarting All-in-One Analysis...")
            
            # Step 1: Mass Clone repositories
            print("\nStep 1: Mass Cloning Repositories")
            print("--------------------------------")
            clone_repositories()
            
            # Step 2: Run Poetry Analysis
            print("\nStep 2: Running Poetry Check")
            print("-----------------------------")
            from utils.poetry.poetry import main as run_poetry_analysis
            run_poetry_analysis()
            
            # Step 3: Generate SBOMs
            print("\nStep 3: Generating SBOMs")
            print("------------------------")
            validator.generate_sboms_for_repos()
            
            
            # Step 4: Run Dependency Track Analysis
            print("\nStep 5: Running Dependency Track Analysis")
            print("----------------------------------------")
            from utils.DependencyTrack.dt import main as run_dt_analysis
            run_dt_analysis()
            
            # Step 5: Run Graph Analysis
            print("\nStep 6: Running Graph Analysis")
            print("-----------------------------")
            from utils.Graph.graph import main as run_graph_analysis
            run_graph_analysis()
            
            # Step 6: Run Vulnerability Comparison
            print("\nStep 7: Running Vulnerability Comparison")
            print("----------------------------------------")
            run_vuln_compare()
            
            print("\nAll-in-One Analysis completed!")
            
        elif main_choice == '6':
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1, 2, 3, 4, 5, or 6.")

if __name__ == "__main__":
    main()