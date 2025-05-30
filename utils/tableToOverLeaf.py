import json
from collections import Counter
import csv

def generate_latex_table():
    # Read the JSON file
    with open('vulnerability_table.json', 'r') as f:
        data = json.load(f)
    
    # Generate LaTeX table
    latex_table = """\\begin{table}[h!]
\\centering
\\caption{Complete List of Vulnerabilities Found in Repositories}
\\begin{tabular}{|c|l|l|l|c|c|c|}
\\hline
\\textbf{\\#} & \\textbf{Repository} & \\textbf{CVE} & \\textbf{PURL} & \\textbf{syft} & \\textbf{trivy} & \\textbf{cdxgen} \\\\
\\hline
"""
    
    # Add all vulnerability data
    for entry in data:
        # Escape underscores in repository name and PURL
        repo_name = entry['repository'].replace('_', '\\_')
        purl = entry['component_purl'].replace('_', '\\_')
        syft = "\\textcolor{green!80!black}{Yes}" if "syft" in entry['found_by'] else "\\textcolor{red}{No}"
        trivy = "\\textcolor{green!80!black}{Yes}" if "trivy" in entry['found_by'] else "\\textcolor{red}{No}"
        cdxgen = "\\textcolor{green!80!black}{Yes}" if "cdxgen" in entry['found_by'] else "\\textcolor{red}{No}"
        latex_table += f"{entry['number']} & {repo_name} & {entry['cve']} & {purl} & {syft} & {trivy} & {cdxgen} \\\\\n"
    
    latex_table += """\\hline
\\end{tabular}
\\label{tab:all_vulnerabilities}
\\end{table}"""
    
    # Write to file
    with open('vulnerability_tables.tex', 'w') as f:
        f.write(latex_table)

def generate_csv():
    # Read the JSON file
    with open('vulnerability_table.json', 'r') as f:
        data = json.load(f)
    
    # Define CSV headers
    headers = ['#', 'Repository', 'CVE', 'PURL', 'syft', 'trivy', 'cdxgen']
    
    # Write to CSV file
    with open('vulnerability_table.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for entry in data:
            syft = "Yes" if "syft" in entry['found_by'] else "No"
            trivy = "Yes" if "trivy" in entry['found_by'] else "No"
            cdxgen = "Yes" if "cdxgen" in entry['found_by'] else "No"
            
            row = [
                entry['number'],
                entry['repository'],
                entry['cve'],
                entry['component_purl'],
                syft,
                trivy,
                cdxgen
            ]
            writer.writerow(row)

if __name__ == "__main__":
    generate_latex_table()
    generate_csv()
