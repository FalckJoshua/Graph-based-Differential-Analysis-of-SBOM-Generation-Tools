# Graph-based Differential Analysis of SBOM Generation Tools

[![AI](https://img.shields.io/badge/AI-Assisted%20Development-blue)](https://github.com/topics/ai)
[![SBOM](https://img.shields.io/badge/SBOM-Security-orange)](https://github.com/topics/sbom)

This project provides a comprehensive framework for analyzing and comparing different Software Bill of Materials (SBOM) generation tools. It helps in understanding the differences and similarities between various SBOM generators and their outputs.

## Topics
- #graph-analysis
- #sbom
- #security
- #dependency-analysis
- #vulnerability-analysis
- #software-security
- #ai-assisted-development

## Features

- **Required Tools**
  - Syft 
  - CDXgen 
  - Trivy 
  - Dependency Track

- **Key Functionalities**
  - Batch processing of repositories
  - Automated SBOM generation
  - Dependency graph contrstction and visualization
  - Graph-based analysis (graph properties & similarity)
  - Vulnerability comparison between the tools

## Tested Environment
This project was developed and tested on Ubuntu 24.04.2 LTS x86_64.

## Prerequisites

- Python 3.x
- Git
- Git LFS
- Dependency Track instance
- The following tools installed:
  - Syft
  - CDXgen
  - Trivy
- A `repos.txt` file containing GitHub repository URLs (one per line) that will be cloned and analyzed

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the following configuration:
```bash
DT_URL=your_dependency_track_url
DT_API_KEY=your_api_key
```

To generate an API key:
1. Log into your Dependency Track instance
2. Go to Administration -> Teams
3. Select the Admin team
4. Generate a new API key

4. Ensure all required tools are installed and available in your system PATH.

## Usage

The project provides a command-line interface with several analysis options:

1. **SBOM Analysis**
   - Mass clone repositories
   - Run Poetry Check
   - Generate SBOMs for cloned repositories

   Before running the analysis, ensure you have a `repos.txt` file in the project root with GitHub repository URLs. Example format:
   ```
   https://github.com/username/repo1.git
   https://github.com/username/repo2.git
   https://github.com/username/repo3.git
   ```

2. **Dependency Track Analysis**
   - Run Dependency Track analysis on generated SBOMs

3. **Graph Analysis**
   - Generate and analyze dependency graphs

4. **Vulnerability Comparison**
   - Compare vulnerabilities across different SBOM tools

5. **All-in-One Analysis**
   - Run complete analysis pipeline including:
     - Repository cloning
     - Poetry analysis
     - SBOM generation
     - Dependency Track analysis
     - Graph analysis
     - Vulnerability Comparison

## Analysis Outputs

After running the analysis, you can find the results in the following locations:

1. **Graph Analysis Outputs** (`graphoutput/` directory)
   - JSON schema for the dependency graphs
   - Graph properties of each graph
   - Pairwise tool comparison results
   - Graph images

2. **Package Analysis** (`package_analysis/` directory)
   - Statistical findings about the packages
   - Graph kernel similarity scores between different tools
