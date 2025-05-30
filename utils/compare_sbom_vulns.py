#!/usr/bin/env python3

import json
import os
from pathlib import Path
from collections import defaultdict
import glob

def find_sbom_files(base_dir):
    """Find all SBOM files in the given directory and its subdirectories."""
    pattern = os.path.join(base_dir, "**", "*.bom.json")
    return glob.glob(pattern, recursive=True)

def get_tool_name(filename):
    """Extract tool name from filename."""
    if "trivy" in filename:
        return "trivy"
    elif "syft" in filename:
        return "syft"
    elif "cdxgen" in filename:
        return "cdxgen"
    return "unknown"

def get_repo_name(filepath):
    """Extract repository name from filepath."""
    return os.path.basename(os.path.dirname(filepath))

def is_critical_severity(severity):
    """Check if the severity is critical, case-insensitive."""
    if not severity:
        return False
    return severity.upper() == "CRITICAL"

def analyze_sbom(filepath):
    """Analyze a single SBOM file and return critical vulnerabilities."""
    tool = get_tool_name(filepath)
    repo = get_repo_name(filepath)
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

    critical_vulns = []
    
    # Create a mapping of component refs to their details
    component_map = {}
    if "components" in data:
        for component in data["components"]:
            if "bom-ref" in component:
                component_map[component["bom-ref"]] = {
                    "name": component.get("name", "unknown"),
                    "version": component.get("version", "unknown"),
                    "type": component.get("type", "unknown"),
                    "purl": component.get("purl", "unknown")
                }
    
    # Handle different SBOM formats
    if "vulnerabilities" in data:
        # Direct vulnerabilities array
        for vuln in data["vulnerabilities"]:
            ratings = vuln.get("ratings", [{}])
            for rating in ratings:
                if is_critical_severity(rating.get("severity")):
                    # Get component details from the affects array
                    component_ref = vuln.get("affects", [{}])[0].get("ref", "unknown")
                    component_details = component_map.get(component_ref, {
                        "name": "unknown",
                        "version": "unknown",
                        "type": "unknown",
                        "purl": "unknown"
                    })
                    
                    critical_vulns.append({
                        "id": vuln.get("id", "unknown"),
                        "component": component_details["name"],
                        "component_version": component_details["version"],
                        "component_type": component_details["type"],
                        "component_purl": component_details["purl"],
                        "description": vuln.get("description", "No description")
                    })
                    break
    elif "components" in data:
        # Components with vulnerabilities
        for component in data["components"]:
            if "vulnerabilities" in component:
                for vuln in component["vulnerabilities"]:
                    ratings = vuln.get("ratings", [{}])
                    for rating in ratings:
                        if is_critical_severity(rating.get("severity")):
                            critical_vulns.append({
                                "id": vuln.get("id", "unknown"),
                                "component": component.get("name", "unknown"),
                                "component_version": component.get("version", "unknown"),
                                "component_type": component.get("type", "unknown"),
                                "component_purl": component.get("purl", "unknown"),
                                "description": vuln.get("description", "No description")
                            })
                            break

    return {
        "tool": tool,
        "repo": repo,
        "vulnerabilities": critical_vulns
    }

def compare_tool_vulnerabilities(results):
    """Compare vulnerabilities across tools to find unique findings."""
    tool_comparison = {}
    
    for repo, tools in results.items():
        # Get all vulnerability IDs for each tool
        tool_vulns = {tool: set(vuln["id"] for vuln in vulns) 
                     for tool, vulns in tools.items()}
        
        # Find vulnerabilities unique to each tool
        unique_findings = {}
        for tool, vuln_ids in tool_vulns.items():
            other_tools = set(tool_vulns.keys()) - {tool}
            other_vuln_ids = set().union(*[tool_vulns[t] for t in other_tools])
            unique_ids = vuln_ids - other_vuln_ids
            
            if unique_ids:
                unique_findings[tool] = {
                    "count": len(unique_ids),
                    "vulnerabilities": [
                        next(v for v in tools[tool] if v["id"] == vuln_id)
                        for vuln_id in unique_ids
                    ]
                }
        
        if unique_findings:
            tool_comparison[repo] = unique_findings
    
    return tool_comparison

def create_vulnerability_table(results):
    """Create a flat table of vulnerabilities with number, repo, CVE, and found by."""
    table = []
    number = 1
    
    # Add diagnostic counters
    total_vulns = 0
    unique_cves = set()
    cve_by_repo = defaultdict(set)
    
    for repo, tools in results.items():
        # Get all unique vulnerabilities for this repo
        all_vuln_ids = set()
        for tool_vulns in tools.values():
            all_vuln_ids.update(vuln["id"] for vuln in tool_vulns)
            total_vulns += len(tool_vulns)
        
        # Track unique CVEs per repo
        cve_by_repo[repo].update(all_vuln_ids)
        unique_cves.update(all_vuln_ids)
        
        # For each vulnerability, find which tools detected it
        for vuln_id in sorted(all_vuln_ids):
            found_by = []
            component_info = None
            for tool, vulns in tools.items():
                if any(v["id"] == vuln_id for v in vulns):
                    found_by.append(tool)
                    # Get component info from the first tool that found it
                    if not component_info:
                        component_info = next(v for v in vulns if v["id"] == vuln_id)
            
            table.append({
                "number": number,
                "repo": repo,
                "cve": vuln_id,
                "found_by": found_by,
                "component_purl": component_info.get("component_purl", "unknown") if component_info else "unknown"
            })
            number += 1
    
    # Add diagnostic information to the table
    diagnostic_info = {
        "total_vulnerabilities_found": total_vulns,
        "unique_cves": len(unique_cves),
        "cves_per_repo": {repo: len(cves) for repo, cves in cve_by_repo.items()},
        "all_unique_cves": sorted(list(unique_cves))
    }
    
    return table, diagnostic_info

def analyze_duplicate_cves(results):
    """Analyze which CVEs are found multiple times in the same repository."""
    duplicates = defaultdict(lambda: defaultdict(list))
    
    for repo, tools in results.items():
        # Get all vulnerabilities for this repo
        all_vulns = []
        for tool, vulns in tools.items():
            for vuln in vulns:
                all_vulns.append({
                    'cve': vuln['id'],
                    'tool': tool,
                    'component': vuln['component']
                })
        
        # Group by CVE
        cve_groups = defaultdict(list)
        for vuln in all_vulns:
            cve_groups[vuln['cve']].append(vuln)
        
        # Find duplicates (CVEs found by multiple tools)
        for cve, findings in cve_groups.items():
            if len(findings) > 1:
                duplicates[repo][cve] = findings
    
    return duplicates

def analyze_overlaps(results):
    """Analyze overlaps between tools and repositories."""
    # Tool overlap analysis
    tool_overlaps = defaultdict(lambda: defaultdict(int))
    repo_overlaps = defaultdict(lambda: defaultdict(int))
    cve_frequency = defaultdict(int)
    
    for repo, tools in results.items():
        # Get all vulnerabilities for this repo
        all_vulns = []
        for tool, vulns in tools.items():
            for vuln in vulns:
                all_vulns.append({
                    'cve': vuln['id'],
                    'tool': tool,
                    'component': vuln['component']
                })
                cve_frequency[vuln['id']] += 1
        
        # Analyze tool overlaps
        tool_vulns = defaultdict(set)
        for vuln in all_vulns:
            tool_vulns[vuln['tool']].add(vuln['cve'])
        
        # Count overlaps between tools
        tools_list = list(tool_vulns.keys())
        for i in range(len(tools_list)):
            for j in range(i + 1, len(tools_list)):
                tool1, tool2 = tools_list[i], tools_list[j]
                overlap = len(tool_vulns[tool1] & tool_vulns[tool2])
                tool_overlaps[tool1][tool2] += overlap
                tool_overlaps[tool2][tool1] += overlap
    
    # Analyze repository overlaps
    repo_vulns = defaultdict(set)
    for repo, tools in results.items():
        for tool, vulns in tools.items():
            for vuln in vulns:
                repo_vulns[repo].add(vuln['id'])
    
    repos_list = list(repo_vulns.keys())
    for i in range(len(repos_list)):
        for j in range(i + 1, len(repos_list)):
            repo1, repo2 = repos_list[i], repos_list[j]
            overlap = len(repo_vulns[repo1] & repo_vulns[repo2])
            if overlap > 0:
                repo_overlaps[repo1][repo2] = overlap
                repo_overlaps[repo2][repo1] = overlap
    
    return {
        'tool_overlaps': dict(tool_overlaps),
        'repo_overlaps': dict(repo_overlaps),
        'cve_frequency': dict(cve_frequency)
    }

def count_overlaps(vulnerability_table):
    """Count exact numbers of overlaps in the vulnerability table."""
    # Count tool combinations
    tool_combinations = defaultdict(int)
    # Count repository overlaps
    repo_cves = defaultdict(set)
    # Count CVE frequencies
    cve_frequency = defaultdict(int)
    
    for entry in vulnerability_table:
        # Count tool combinations
        tools = tuple(sorted(entry['found_by']))
        tool_combinations[tools] += 1
        
        # Count repository CVEs
        repo_cves[entry['repo']].add(entry['cve'])
        
        # Count CVE frequency
        cve_frequency[entry['cve']] += 1
    
    # Count repository overlaps
    repo_overlaps = defaultdict(int)
    repos = list(repo_cves.keys())
    for i in range(len(repos)):
        for j in range(i + 1, len(repos)):
            repo1, repo2 = repos[i], repos[j]
            overlap = len(repo_cves[repo1] & repo_cves[repo2])
            if overlap > 0:
                repo_overlaps[(repo1, repo2)] = overlap
    
    # Convert tuple keys to strings for JSON serialization
    return {
        'tool_combinations': {','.join(k): v for k, v in tool_combinations.items()},
        'repo_overlaps': {f"{k[0]},{k[1]}": v for k, v in repo_overlaps.items()},
        'cve_frequency': dict(cve_frequency)
    }

def verify_total_count(vulnerability_table, tool_totals):
    """Verify and break down the total count of vulnerabilities."""
    # Count total unique entries in table
    total_entries = len(vulnerability_table)
    
    # Count total from tool_totals
    total_from_tools = sum(tool_totals.values())
    
    # Count unique CVEs
    unique_cves = len(set(entry['cve'] for entry in vulnerability_table))
    
    # Count entries per tool combination
    tool_combinations = defaultdict(int)
    for entry in vulnerability_table:
        tools = tuple(sorted(entry['found_by']))
        tool_combinations[tools] += 1
    
    # Convert tuple keys to strings for JSON serialization
    return {
        'total_entries': total_entries,
        'total_from_tools': total_from_tools,
        'unique_cves': unique_cves,
        'tool_combinations': {','.join(k): v for k, v in tool_combinations.items()}
    }

def analyze_cve_breakdown(vulnerability_table):
    """Analyze CVE findings without making them unique."""
    # Count total findings per tool
    tool_findings = defaultdict(int)
    # Count all CVE instances
    cve_instances = defaultdict(int)
    # Count repositories per CVE
    cve_repos = defaultdict(set)
    
    for entry in vulnerability_table:
        for tool in entry['found_by']:
            tool_findings[tool] += 1
            cve_instances[entry['cve']] += 1
        cve_repos[entry['cve']].add(entry['repo'])
    
    # Calculate breakdown
    breakdown = {
        'tool_findings': dict(tool_findings),
        'cve_instances': dict(cve_instances),
        'cve_repo_counts': {cve: len(repos) for cve, repos in cve_repos.items()},
        'total_cve_instances': sum(cve_instances.values())
    }
    
    return breakdown

def analyze_repository_vulnerabilities(vulnerability_table, repo_name, results):
    """Analyze vulnerabilities for a specific repository in detail."""
    repo_vulns = [entry for entry in vulnerability_table if entry['repo'] == repo_name]
    
    # Get raw tool counts from original results
    raw_tool_counts = {tool: len(vulns) for tool, vulns in results[repo_name].items()}
    
    # Count by tool in vulnerability table
    tool_counts = defaultdict(int)
    # Count by CVE
    cve_counts = defaultdict(int)
    # Group by CVE and tools
    cve_tools = defaultdict(set)
    
    for entry in repo_vulns:
        for tool in entry['found_by']:
            tool_counts[tool] += 1
        cve_counts[entry['cve']] += 1
        cve_tools[entry['cve']].update(entry['found_by'])
    
    return {
        'total_entries': len(repo_vulns),
        'raw_tool_counts': raw_tool_counts,
        'tool_counts': dict(tool_counts),
        'cve_counts': dict(cve_counts),
        'cve_tools': {cve: list(tools) for cve, tools in cve_tools.items()}
    }

def main():
    base_dir = "standardized_boms_with_vulns"
    results = defaultdict(lambda: defaultdict(list))
    
    # Find and analyze all SBOM files
    sbom_files = find_sbom_files(base_dir)
    
    if not sbom_files:
        print(f"No SBOM files found in {base_dir}")
        return

    print(f"Found {len(sbom_files)} SBOM files to analyze")
    
    for filepath in sbom_files:
        result = analyze_sbom(filepath)
        if result["vulnerabilities"]:
            results[result["repo"]][result["tool"]] = result["vulnerabilities"]
    
    # Calculate tool totals for JSON
    tool_totals = defaultdict(int)
    for repo_tools in results.values():
        for tool, vulns in repo_tools.items():
            tool_totals[tool] += len(vulns)
    
    # Create vulnerability table with diagnostic info
    vulnerability_table, diagnostic_info = create_vulnerability_table(results)
    
    # Print vulnerability table
    print("\nVulnerability Table")
    print("==================")
    print("Number | Repository | CVE | PURL | Found By")
    print("-" * 120)
    for entry in vulnerability_table:
        print(f"{entry['number']:6d} | {entry['repo']:10} | {entry['cve']} | {entry['component_purl']:40} | {', '.join(entry['found_by'])}")

    # Export vulnerability table to separate JSON file in the same format as console output
    table_output_file = "vulnerability_table.json"
    table_data = []
    for entry in vulnerability_table:
        table_data.append({
            "number": entry["number"],
            "repository": entry["repo"],
            "cve": entry["cve"],
            "component_purl": entry["component_purl"],
            "found_by": entry["found_by"]
        })
    
    with open(table_output_file, 'w') as f:
        json.dump(table_data, f, indent=2)
    print(f"\nVulnerability table exported to {table_output_file}")
    
    # Analyze duplicate CVEs
    duplicate_cves = analyze_duplicate_cves(results)
    
    # Analyze overlaps
    overlap_analysis = analyze_overlaps(results)
    
    # Count exact overlaps
    overlap_counts = count_overlaps(vulnerability_table)
    
    # Verify total count
    count_verification = verify_total_count(vulnerability_table, tool_totals)
    
    # Analyze CVE breakdown
    cve_breakdown = analyze_cve_breakdown(vulnerability_table)
    
    # Analyze arena-marl specifically
    arena_marl_analysis = analyze_repository_vulnerabilities(vulnerability_table, "arena-marl", results)
    
    # Prepare summary with counts
    summary = {
        "total_repositories": len(results),
        "repositories": {},
        "tool_summary": dict(tool_totals),
        "vulnerability_table": vulnerability_table,
        "diagnostic_info": diagnostic_info,
        "duplicate_cves": duplicate_cves,
        "overlap_analysis": overlap_analysis,
        "overlap_counts": overlap_counts,
        "count_verification": count_verification,
        "cve_breakdown": cve_breakdown,
        "arena_marl_analysis": arena_marl_analysis
    }
    
    for repo, tools in results.items():
        repo_summary = {
            "total_vulnerabilities": sum(len(vulns) for vulns in tools.values()),
            "tool_counts": {tool: len(vulns) for tool, vulns in tools.items()},
            "vulnerabilities": tools
        }
        summary["repositories"][repo] = repo_summary
    
    # Add tool comparison section
    summary["tool_comparison"] = compare_tool_vulnerabilities(results)
    
    # Export results to JSON
    output_file = "vulnerability_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults exported to {output_file}")
    
    # Print results
    print("\nCritical Vulnerabilities Analysis Report")
    print("=======================================")
    
    if not results:
        print("\nNo critical vulnerabilities found in any repository.")
        return
    
    # Print arena-marl analysis
    print("\nArena-Marl Vulnerability Analysis")
    print("================================")
    print(f"Total entries in table: {arena_marl_analysis['total_entries']}")
    print("\nRaw tool counts (from original results):")
    for tool, count in arena_marl_analysis['raw_tool_counts'].items():
        print(f"  {tool.upper()}: {count} findings")
    print("\nTool counts in vulnerability table:")
    for tool, count in arena_marl_analysis['tool_counts'].items():
        print(f"  {tool.upper()}: {count} findings")
    print("\nCVE breakdown:")
    for cve, count in sorted(arena_marl_analysis['cve_counts'].items()):
        tools = arena_marl_analysis['cve_tools'][cve]
        print(f"  {cve}: Found {count} times by {', '.join(tools)}")
    
    # Print CVE breakdown
    print("\nCVE Breakdown Analysis")
    print("=====================")
    print(f"Total CVE instances: {cve_breakdown['total_cve_instances']}")
    print("\nTool Findings Breakdown:")
    for tool, findings in cve_breakdown['tool_findings'].items():
        print(f"\n{tool.upper()}:")
        print(f"  Total findings: {findings}")
    
    print("\nTop CVEs by Instance Count:")
    sorted_cves = sorted(cve_breakdown['cve_instances'].items(), 
                        key=lambda x: x[1], reverse=True)
    for cve, count in sorted_cves[:10]:  # Show top 10
        repos = cve_breakdown['cve_repo_counts'][cve]
        print(f"  {cve}: Found {count} times across {repos} repositories")
    
    # Print count verification
    print("\nCount Verification")
    print("=================")
    print(f"Total entries in vulnerability table: {count_verification['total_entries']}")
    print(f"Total from tool counts: {count_verification['total_from_tools']}")
    print(f"Total CVE instances: {cve_breakdown['total_cve_instances']}")
    print("\nBreakdown by tool combinations:")
    for tools, count in sorted(count_verification['tool_combinations'].items()):
        print(f"  {tools}: {count} entries")
    
    # Print diagnostic information
    print("\nDiagnostic Information")
    print("=====================")
    print(f"Total vulnerabilities found: {diagnostic_info['total_vulnerabilities_found']}")
    print(f"Total CVE instances: {cve_breakdown['total_cve_instances']}")
    print("\nCVEs per repository:")
    for repo, count in diagnostic_info['cves_per_repo'].items():
        print(f"  {repo}: {count} CVEs")
    
    # Print exact overlap counts
    print("\nTool Combination Counts")
    print("======================")
    for tools, count in sorted(overlap_counts['tool_combinations'].items()):
        print(f"{tools}: {count} CVEs")
    
    print("\nRepository Overlap Counts")
    print("========================")
    for repos, count in sorted(overlap_counts['repo_overlaps'].items(), 
                             key=lambda x: x[1], reverse=True):
        repo1, repo2 = repos.split(',')
        print(f"{repo1} and {repo2}: {count} shared CVEs")
    
    print("\nCVE Frequency Counts")
    print("===================")
    for cve, count in sorted(overlap_counts['cve_frequency'].items(), 
                           key=lambda x: x[1], reverse=True):
        print(f"{cve}: Found in {count} repositories")
    
    # Print overlap analysis
    print("\nTool Overlap Analysis")
    print("====================")
    for tool1, overlaps in overlap_analysis['tool_overlaps'].items():
        for tool2, count in overlaps.items():
            if count > 0:
                print(f"{tool1.upper()} and {tool2.upper()} overlap on {count} CVEs")
    
    print("\nRepository Overlap Analysis")
    print("=========================")
    for repo1, overlaps in overlap_analysis['repo_overlaps'].items():
        for repo2, count in overlaps.items():
            if count > 0:
                print(f"{repo1} and {repo2} share {count} CVEs")
    
    print("\nCVE Frequency Analysis")
    print("=====================")
    sorted_cves = sorted(overlap_analysis['cve_frequency'].items(), 
                        key=lambda x: x[1], reverse=True)
    for cve, count in sorted_cves:
        print(f"{cve}: Found in {count} repositories")
    
    # Print duplicate CVE analysis
    print("\nDuplicate CVE Analysis")
    print("=====================")
    for repo, cves in duplicate_cves.items():
        if cves:  # Only show repos with duplicates
            print(f"\nRepository: {repo}")
            print("-" * (len(repo) + 13))
            for cve, findings in cves.items():
                print(f"\nCVE: {cve}")
                for finding in findings:
                    print(f"  Found by {finding['tool']} in {finding['component']}")
    
    for repo, tools in results.items():
        print(f"\nRepository: {repo}")
        print("-" * (len(repo) + 13))
        
        for tool, vulns in tools.items():
            print(f"\n{tool.upper()} found {len(vulns)} critical vulnerabilities:")
            for vuln in vulns:
                print(f"  - {vuln['id']} in {vuln['component']}")
                print(f"    Description: {vuln['description'][:100]}...")
        
        # Compare tools
        print("\nTool Comparison:")
        all_vuln_ids = set()
        for tool_vulns in tools.values():
            all_vuln_ids.update(vuln["id"] for vuln in tool_vulns)
        
        for vuln_id in all_vuln_ids:
            found_by = [tool for tool, vulns in tools.items() 
                       if any(v["id"] == vuln_id for v in vulns)]
            print(f"  - {vuln_id}: Found by {', '.join(found_by)}")

    # Add tool summary section
    print("\nTool Summary")
    print("============")
    for tool, total in sorted(tool_totals.items()):
        print(f"{tool.upper()}: {total} critical vulnerabilities")

if __name__ == "__main__":
    main() 