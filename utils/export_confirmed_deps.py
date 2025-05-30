import pandas as pd

def export_confirmed_dependencies():
    # Read the original CSV file
    df = pd.read_csv('repo_sbom_status.csv')

    # Filter repositories where dependencies were found in all three tools
    confirmed_deps = df[
        (df['CycloneDX_Dependency_Count'] > 0) & 
        (df['Trivy_Dependency_Count'] > 0) & 
        (df['Syft_Dependency_Count'] > 0)
    ]

    # Select only the relevant columns
    confirmed_deps = confirmed_deps[[
        'Repository_Name',
        'Repository_URL',
        'CycloneDX_Dependency_Count',
        'Trivy_Dependency_Count',
        'Syft_Dependency_Count'
    ]]

    # Sort by total number of dependencies
    confirmed_deps['Total_Dependencies'] = (
        confirmed_deps['CycloneDX_Dependency_Count'] + 
        confirmed_deps['Trivy_Dependency_Count'] + 
        confirmed_deps['Syft_Dependency_Count']
    )
    confirmed_deps = confirmed_deps.sort_values('Total_Dependencies', ascending=False)

    # Save to new CSV file
    confirmed_deps.to_csv('deptConfirmed.csv', index=False)

    print(f"Found {len(confirmed_deps)} repositories with confirmed dependencies across all three tools")
    print("Results saved to deptConfirmed.csv")

if __name__ == "__main__":
    export_confirmed_dependencies() 