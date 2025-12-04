#!/usr/bin/env python3
"""
Log code quality results to Google Sheets.
Includes ALL data used in score calculation for debugging.

Sheet Schema (~50 columns):
- Meta: timestamp, repo, pr, author, branches, etc.
- Files: count, list, lines added/removed, languages
- Code Quality Raw: issue counts and details
- Code Quality Scores: calculated scores
- Test Health Raw: coverage and test data
- Test Health Scores: calculated scores
- Test Presence Raw: what tests were found
- Test Presence Scores: calculated scores
- Final: score, threshold, status
- Debug: workflow run info, config, errors
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

import yaml

# Google Sheets API
from google.oauth2 import service_account
from googleapiclient.discovery import build


def get_sheets_service(credentials_json: str):
    """Create Google Sheets API service."""
    try:
        creds_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=credentials)
    except Exception as e:
        print(f"Error creating Sheets service: {e}")
        return None


def truncate_str(s: str, max_len: int = 500) -> str:
    """Truncate string to max length."""
    if not s:
        return ""
    s = str(s)
    if len(s) <= max_len:
        return s
    return s[:max_len-3] + "..."


def list_to_str(lst: list, max_len: int = 1000) -> str:
    """Convert list to comma-separated string, truncated."""
    if not lst:
        return ""
    result = ", ".join(str(item) for item in lst)
    return truncate_str(result, max_len)


def issues_to_str(issues: list, max_len: int = 2000) -> str:
    """Convert issues list to readable string."""
    if not issues:
        return ""
    parts = []
    for issue in issues[:20]:  # Limit to 20 issues
        if isinstance(issue, dict):
            file = issue.get("file", "").split("/")[-1]  # Just filename
            line = issue.get("line", "?")
            msg = issue.get("message", "")[:50]
            parts.append(f"{file}:{line} - {msg}")
        else:
            parts.append(str(issue)[:50])
    result = "; ".join(parts)
    if len(issues) > 20:
        result += f"; ...and {len(issues) - 20} more"
    return truncate_str(result, max_len)


def coverage_files_to_str(files: list, max_len: int = 2000) -> str:
    """Convert coverage by file to readable string."""
    if not files:
        return ""
    parts = []
    for f in files[:20]:
        if isinstance(f, dict):
            name = f.get("file", "").split("/")[-1]
            cov = f.get("coverage", 0)
            parts.append(f"{name}:{cov:.0f}%")
        else:
            parts.append(str(f))
    result = ", ".join(parts)
    if len(files) > 20:
        result += f", ...and {len(files) - 20} more"
    return truncate_str(result, max_len)


def build_row(
    score_data: dict,
    repo: str,
    pr_number: str,
    pr_title: str,
    pr_url: str,
    author: str,
    base_branch: str,
    head_branch: str,
    files_changed: str,
    lines_added: str,
    lines_removed: str,
    languages: str,
    workflow_run_id: str,
    workflow_run_url: str,
    config_data: dict,
    error: str = ""
) -> list:
    """Build a row with all columns for Google Sheets."""
    
    bd = score_data.get("breakdown", {})
    cq = bd.get("code_quality", {})
    th = bd.get("test_health", {})
    tp = bd.get("test_presence", {})
    raw = score_data.get("raw_data", {})
    
    # Build row in column order
    row = [
        # === META ===
        datetime.utcnow().isoformat() + "Z",  # Timestamp
        repo,  # Repo
        pr_number,  # PR Number
        truncate_str(pr_title, 200),  # PR Title
        pr_url,  # PR URL
        author,  # Author
        "",  # Author Email (if available)
        base_branch,  # Base Branch
        head_branch,  # Head Branch
        
        # === FILES CHANGED ===
        files_changed,  # Files Changed Count
        list_to_str(score_data.get("files_analyzed", [])),  # Files Changed List
        lines_added,  # Lines Added
        lines_removed,  # Lines Removed
        languages,  # Languages Detected
        
        # === CODE QUALITY - RAW ===
        cq.get("complexity", {}).get("issues_count", 0),  # Complexity Issues Count
        issues_to_str(cq.get("complexity", {}).get("issues", [])),  # Complexity Issues Details
        cq.get("smells", {}).get("issues_count", 0),  # Smells Issues Count
        issues_to_str(cq.get("smells", {}).get("issues", [])),  # Smells Issues Details
        cq.get("duplication", {}).get("percentage", 0),  # Duplication Percentage
        issues_to_str(cq.get("duplication", {}).get("duplications", [])),  # Duplication Details
        
        # === CODE QUALITY - SCORES ===
        cq.get("complexity", {}).get("score", 0),  # Complexity Score
        cq.get("complexity", {}).get("max", 15),  # Complexity Max
        cq.get("complexity", {}).get("penalty", 0),  # Complexity Penalty
        cq.get("smells", {}).get("score", 0),  # Smells Score
        cq.get("smells", {}).get("max", 15),  # Smells Max
        cq.get("smells", {}).get("penalty", 0),  # Smells Penalty
        cq.get("duplication", {}).get("score", 0),  # Duplication Score
        cq.get("duplication", {}).get("max", 10),  # Duplication Max
        cq.get("duplication", {}).get("penalty", 0),  # Duplication Penalty
        cq.get("total", 0),  # Code Quality Total
        cq.get("max", 40),  # Code Quality Max
        
        # === TEST HEALTH - RAW ===
        th.get("results", {}).get("tests_run", 0),  # Tests Run
        th.get("results", {}).get("tests_passed", 0),  # Tests Passed
        th.get("results", {}).get("tests_failed", 0),  # Tests Failed
        th.get("results", {}).get("tests_skipped", 0),  # Tests Skipped
        issues_to_str(th.get("results", {}).get("failures", [])),  # Test Failures Details
        th.get("coverage", {}).get("total_lines", 0),  # Coverage Total Lines
        th.get("coverage", {}).get("covered_lines", 0),  # Coverage Covered Lines
        th.get("coverage", {}).get("percentage", 0),  # Coverage Percentage
        coverage_files_to_str(th.get("coverage", {}).get("by_file", [])),  # Coverage By File
        list_to_str(th.get("coverage", {}).get("uncovered_functions", [])),  # Uncovered Functions
        
        # === TEST HEALTH - SCORES ===
        th.get("coverage", {}).get("score", 0),  # Coverage Score
        th.get("coverage", {}).get("max", 20),  # Coverage Max
        th.get("results", {}).get("score", 0),  # Test Results Score
        th.get("results", {}).get("max", 10),  # Test Results Max
        th.get("total", 0),  # Test Health Total
        th.get("max", 30),  # Test Health Max
        
        # === TEST PRESENCE - RAW ===
        "Yes" if tp.get("unit_tests", {}).get("found", False) else "No",  # Unit Tests Found
        tp.get("unit_tests", {}).get("count", 0),  # Unit Tests Count
        list_to_str(tp.get("unit_tests", {}).get("files", [])),  # Unit Test Files
        "Yes" if tp.get("e2e", {}).get("required", False) else "No",  # E2E Required
        "Yes" if tp.get("e2e", {}).get("found", False) else "No",  # E2E Tests Found
        tp.get("e2e", {}).get("count", 0),  # E2E Tests Count
        
        # === TEST PRESENCE - SCORES ===
        tp.get("unit_tests", {}).get("score", 0),  # Unit Tests Score
        tp.get("unit_tests", {}).get("max", 20),  # Unit Tests Max
        tp.get("e2e", {}).get("score", "N/A"),  # E2E Score
        tp.get("e2e", {}).get("max", "N/A"),  # E2E Max
        tp.get("total", 0),  # Test Presence Total
        tp.get("max", 20),  # Test Presence Max
        
        # === FINAL ===
        score_data.get("final_score", 0),  # Final Score
        score_data.get("threshold", 70),  # Threshold
        "PASS" if score_data.get("passed", False) else "FAIL",  # Status
        
        # === DEBUG ===
        workflow_run_id,  # Workflow Run ID
        workflow_run_url,  # Workflow Run URL
        "",  # Duration (can be added later)
        truncate_str(json.dumps(config_data), 500),  # Config Used
        truncate_str(error, 500),  # Errors
    ]
    
    return row


# Column headers matching the row structure
HEADERS = [
    # META
    "Timestamp", "Repo", "PR Number", "PR Title", "PR URL", "Author", "Author Email",
    "Base Branch", "Head Branch",
    # FILES
    "Files Changed Count", "Files Changed List", "Lines Added", "Lines Removed", "Languages",
    # CODE QUALITY RAW
    "Complexity Issues Count", "Complexity Issues Details",
    "Smells Issues Count", "Smells Issues Details",
    "Duplication %", "Duplication Details",
    # CODE QUALITY SCORES
    "Complexity Score", "Complexity Max", "Complexity Penalty",
    "Smells Score", "Smells Max", "Smells Penalty",
    "Duplication Score", "Duplication Max", "Duplication Penalty",
    "Code Quality Total", "Code Quality Max",
    # TEST HEALTH RAW
    "Tests Run", "Tests Passed", "Tests Failed", "Tests Skipped", "Test Failures Details",
    "Coverage Total Lines", "Coverage Covered Lines", "Coverage %", "Coverage By File", "Uncovered Functions",
    # TEST HEALTH SCORES
    "Coverage Score", "Coverage Max", "Test Results Score", "Test Results Max",
    "Test Health Total", "Test Health Max",
    # TEST PRESENCE RAW
    "Unit Tests Found", "Unit Tests Count", "Unit Test Files",
    "E2E Required", "E2E Found", "E2E Count",
    # TEST PRESENCE SCORES
    "Unit Tests Score", "Unit Tests Max", "E2E Score", "E2E Max",
    "Test Presence Total", "Test Presence Max",
    # FINAL
    "Final Score", "Threshold", "Status",
    # DEBUG
    "Workflow Run ID", "Workflow Run URL", "Duration", "Config", "Errors"
]


def ensure_headers(service, sheet_id: str, sheet_name: str = "Raw PR Logs"):
    """Ensure headers exist in the sheet."""
    try:
        # Check if first row has headers
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A1:BZ1"
        ).execute()
        
        values = result.get("values", [])
        
        if not values or values[0] != HEADERS:
            # Set headers
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS]}
            ).execute()
            print(f"Headers set in {sheet_name}")
    except Exception as e:
        print(f"Warning: Could not verify headers: {e}")


def append_row(service, sheet_id: str, row: list, sheet_name: str = "Raw PR Logs"):
    """Append a row to the sheet."""
    try:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A:BZ",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()
        print(f"Row appended to {sheet_name}")
        return True
    except Exception as e:
        print(f"Error appending row: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Log quality results to Google Sheets")
    parser.add_argument("--score-file", required=True, help="Score JSON file")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--pr-number", required=True, help="PR number")
    parser.add_argument("--pr-title", default="", help="PR title")
    parser.add_argument("--pr-url", default="", help="PR URL")
    parser.add_argument("--author", required=True, help="PR author")
    parser.add_argument("--base-branch", default="main", help="Base branch")
    parser.add_argument("--head-branch", default="", help="Head branch")
    parser.add_argument("--files-changed", default="0", help="Files changed count")
    parser.add_argument("--lines-added", default="0", help="Lines added")
    parser.add_argument("--lines-removed", default="0", help="Lines removed")
    parser.add_argument("--languages", default="", help="Languages detected")
    parser.add_argument("--workflow-run-id", default="", help="Workflow run ID")
    parser.add_argument("--workflow-run-url", default="", help="Workflow run URL")
    parser.add_argument("--config-file", default="", help="Config YAML file")
    parser.add_argument("--credentials", required=True, help="Google credentials JSON string")
    parser.add_argument("--sheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--sheet-name", default="Raw PR Logs", help="Sheet name")
    
    args = parser.parse_args()
    
    # Load score data
    score_data = {}
    error = ""
    try:
        with open(args.score_file) as f:
            score_data = json.load(f)
    except Exception as e:
        error = f"Could not load score file: {e}"
        print(error)
    
    # Load config
    config_data = {}
    if args.config_file and os.path.exists(args.config_file):
        try:
            with open(args.config_file) as f:
                config_data = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
    
    # Build row
    row = build_row(
        score_data=score_data,
        repo=args.repo,
        pr_number=args.pr_number,
        pr_title=args.pr_title,
        pr_url=args.pr_url,
        author=args.author,
        base_branch=args.base_branch,
        head_branch=args.head_branch,
        files_changed=args.files_changed,
        lines_added=args.lines_added,
        lines_removed=args.lines_removed,
        languages=args.languages,
        workflow_run_id=args.workflow_run_id,
        workflow_run_url=args.workflow_run_url,
        config_data=config_data,
        error=error
    )
    
    # Connect to Google Sheets
    service = get_sheets_service(args.credentials)
    if not service:
        print("ERROR: Could not connect to Google Sheets")
        return 1
    
    # Ensure headers exist
    ensure_headers(service, args.sheet_id, args.sheet_name)
    
    # Append row
    success = append_row(service, args.sheet_id, row, args.sheet_name)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
