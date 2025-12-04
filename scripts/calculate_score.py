#!/usr/bin/env python3
"""
Calculate code quality score from linter and test results.
Score breakdown:
- Code Quality: 40 points (Complexity: 15, Smells: 15, Duplication: 10)
- Test Health: 30 points (Coverage: 20, Test Results: 10)
- Test Presence: 30 points (Unit: 20, E2E: 10 if required)
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml


def load_json_safe(filepath: str) -> dict | list | None:
    """Load JSON file, return None if doesn't exist or invalid."""
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        with open(filepath) as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Warning: Could not parse {filepath}: {e}")
        return None


def load_yaml_safe(filepath: str) -> dict | None:
    """Load YAML file, return empty dict if doesn't exist."""
    if not filepath or not os.path.exists(filepath):
        return {}
    try:
        with open(filepath) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")
        return {}


def parse_ruff_results(data: list | None) -> dict:
    """Parse Ruff (Python) linter output."""
    result = {
        "complexity_issues": [],
        "smell_issues": [],
        "total_issues": 0
    }
    
    if not data or not isinstance(data, list):
        return result
    
    complexity_rules = {"C901", "PLR0915", "PLR0912", "PLR0911"}
    
    for issue in data:
        if not isinstance(issue, dict):
            continue
            
        code = issue.get("code", "")
        entry = {
            "file": issue.get("filename", ""),
            "line": issue.get("location", {}).get("row", 0),
            "code": code,
            "message": issue.get("message", "")
        }
        
        if code in complexity_rules:
            result["complexity_issues"].append(entry)
        else:
            result["smell_issues"].append(entry)
        
        result["total_issues"] += 1
    
    return result


def parse_eslint_results(data: list | None) -> dict:
    """Parse ESLint (JavaScript/TypeScript) output."""
    result = {
        "complexity_issues": [],
        "smell_issues": [],
        "total_issues": 0
    }
    
    if not data or not isinstance(data, list):
        return result
    
    complexity_rules = {"complexity", "max-depth", "max-nested-callbacks", "max-lines-per-function"}
    
    for file_result in data:
        if not isinstance(file_result, dict):
            continue
            
        filepath = file_result.get("filePath", "")
        messages = file_result.get("messages", [])
        
        for msg in messages:
            if not isinstance(msg, dict):
                continue
                
            rule_id = msg.get("ruleId", "") or ""
            entry = {
                "file": filepath,
                "line": msg.get("line", 0),
                "code": rule_id,
                "message": msg.get("message", "")
            }
            
            if any(r in rule_id for r in complexity_rules):
                result["complexity_issues"].append(entry)
            else:
                result["smell_issues"].append(entry)
            
            result["total_issues"] += 1
    
    return result


def parse_swiftlint_results(data: list | None) -> dict:
    """Parse SwiftLint output."""
    result = {
        "complexity_issues": [],
        "smell_issues": [],
        "total_issues": 0
    }
    
    if not data or not isinstance(data, list):
        return result
    
    complexity_rules = {"cyclomatic_complexity", "function_body_length", "type_body_length", "file_length"}
    
    for issue in data:
        if not isinstance(issue, dict):
            continue
            
        rule_id = issue.get("rule_id", "")
        entry = {
            "file": issue.get("file", ""),
            "line": issue.get("line", 0),
            "code": rule_id,
            "message": issue.get("reason", "")
        }
        
        if rule_id in complexity_rules:
            result["complexity_issues"].append(entry)
        else:
            result["smell_issues"].append(entry)
        
        result["total_issues"] += 1
    
    return result


def parse_detekt_results(data: dict | None) -> dict:
    """Parse Detekt (Kotlin/Java) output."""
    result = {
        "complexity_issues": [],
        "smell_issues": [],
        "total_issues": 0
    }
    
    if not data or not isinstance(data, dict):
        return result
    
    complexity_rules = {"ComplexMethod", "LongMethod", "LargeClass", "NestedBlockDepth", "CyclomaticComplexMethod"}
    
    findings = data.get("findings", {})
    for category, issues in findings.items():
        if not isinstance(issues, list):
            continue
            
        for issue in issues:
            if not isinstance(issue, dict):
                continue
                
            rule = issue.get("rule", "")
            location = issue.get("location", {})
            entry = {
                "file": location.get("path", ""),
                "line": location.get("line", 0),
                "code": rule,
                "message": issue.get("message", "")
            }
            
            if rule in complexity_rules:
                result["complexity_issues"].append(entry)
            else:
                result["smell_issues"].append(entry)
            
            result["total_issues"] += 1
    
    return result


def parse_jscpd_results(data: dict | None) -> dict:
    """Parse jscpd duplication output."""
    result = {
        "percentage": 0.0,
        "duplications": [],
        "total_lines": 0,
        "duplicated_lines": 0
    }
    
    if not data or not isinstance(data, dict):
        return result
    
    stats = data.get("statistics", {})
    total = stats.get("total", {})
    
    result["percentage"] = total.get("percentage", 0.0)
    result["total_lines"] = total.get("lines", 0)
    result["duplicated_lines"] = total.get("duplicatedLines", 0)
    
    for dup in data.get("duplicates", []):
        if not isinstance(dup, dict):
            continue
        result["duplications"].append({
            "first_file": dup.get("firstFile", {}).get("name", ""),
            "second_file": dup.get("secondFile", {}).get("name", ""),
            "lines": dup.get("lines", 0),
            "tokens": dup.get("tokens", 0)
        })
    
    return result


def parse_test_results(data: dict | None) -> dict:
    """Parse test results from run_tests.py output."""
    result = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
        "failures_details": [],
        "coverage_percentage": 0.0,
        "coverage_by_file": [],
        "uncovered_functions": [],
        "unit_tests_found": False,
        "unit_tests_count": 0,
        "unit_test_files": [],
        "e2e_tests_found": False,
        "e2e_tests_count": 0,
        "coverage_total_lines": 0,
        "coverage_covered_lines": 0
    }
    
    if not data or not isinstance(data, dict):
        return result
    
    result["tests_run"] = data.get("tests_run", 0)
    result["tests_passed"] = data.get("tests_passed", 0)
    result["tests_failed"] = data.get("tests_failed", 0)
    result["tests_skipped"] = data.get("tests_skipped", 0)
    result["failures_details"] = data.get("failures", [])
    result["coverage_percentage"] = data.get("coverage_percentage", 0.0)
    result["coverage_by_file"] = data.get("coverage_by_file", [])
    result["uncovered_functions"] = data.get("uncovered_functions", [])
    result["unit_tests_found"] = data.get("unit_tests_found", False)
    result["unit_tests_count"] = data.get("unit_tests_count", 0)
    result["unit_test_files"] = data.get("unit_test_files", [])
    result["e2e_tests_found"] = data.get("e2e_tests_found", False)
    result["e2e_tests_count"] = data.get("e2e_tests_count", 0)
    result["coverage_total_lines"] = data.get("coverage_total_lines", 0)
    result["coverage_covered_lines"] = data.get("coverage_covered_lines", 0)
    
    return result


def calculate_complexity_score(issues: list, max_points: int = 15) -> tuple[int, int]:
    """Calculate complexity score. Returns (score, penalty)."""
    penalty_per_issue = 4
    penalty = min(max_points, len(issues) * penalty_per_issue)
    score = max_points - penalty
    return max(0, score), penalty


def calculate_smells_score(issues: list, max_points: int = 15) -> tuple[int, int]:
    """Calculate code smells score. Returns (score, penalty)."""
    penalty_per_issue = 3
    penalty = min(max_points, len(issues) * penalty_per_issue)
    score = max_points - penalty
    return max(0, score), penalty


def calculate_duplication_score(percentage: float, max_points: int = 10) -> tuple[float, float]:
    """Calculate duplication score. Returns (score, penalty)."""
    penalty = min(max_points, percentage * 1.0)
    score = max_points - penalty
    return max(0, round(score, 1)), round(penalty, 1)


def calculate_coverage_score(percentage: float, max_points: int = 20) -> int:
    """Calculate coverage score based on percentage."""
    if percentage >= 80:
        return max_points
    elif percentage >= 60:
        return 15
    elif percentage >= 40:
        return 10
    elif percentage >= 20:
        return 5
    else:
        return 0


def calculate_test_results_score(passed: int, failed: int, max_points: int = 10) -> int:
    """Calculate test results score based on pass rate."""
    total = passed + failed
    if total == 0:
        return 0
    
    pass_rate = (passed / total) * 100
    
    if pass_rate == 100:
        return max_points
    elif pass_rate >= 95:
        return 8
    elif pass_rate >= 80:
        return 5
    else:
        return 0


def calculate_score(
    config: dict,
    changed_files: list[str],
    ruff_data: dict,
    eslint_data: dict,
    swiftlint_data: dict,
    detekt_data: dict,
    jscpd_data: dict,
    test_data: dict,
    threshold: int = 70
) -> dict:
    """Calculate the final quality score."""
    
    # Combine all linter results
    all_complexity_issues = (
        ruff_data["complexity_issues"] +
        eslint_data["complexity_issues"] +
        swiftlint_data["complexity_issues"] +
        detekt_data["complexity_issues"]
    )
    
    all_smell_issues = (
        ruff_data["smell_issues"] +
        eslint_data["smell_issues"] +
        swiftlint_data["smell_issues"] +
        detekt_data["smell_issues"]
    )
    
    # Calculate code quality scores
    complexity_score, complexity_penalty = calculate_complexity_score(all_complexity_issues)
    smells_score, smells_penalty = calculate_smells_score(all_smell_issues)
    duplication_score, duplication_penalty = calculate_duplication_score(jscpd_data["percentage"])
    
    code_quality_total = complexity_score + smells_score + duplication_score
    code_quality_max = 40
    
    # Calculate test health scores
    coverage_score = calculate_coverage_score(test_data["coverage_percentage"])
    test_results_score = calculate_test_results_score(
        test_data["tests_passed"],
        test_data["tests_failed"]
    )
    
    test_health_total = coverage_score + test_results_score
    test_health_max = 30
    
    # Calculate test presence scores
    e2e_required = config.get("e2e", {}).get("required", False)
    
    unit_tests_score = 20 if test_data["unit_tests_found"] and test_data["tests_failed"] == 0 else 0
    
    if e2e_required:
        e2e_score = 10 if test_data["e2e_tests_found"] else 0
        test_presence_max = 30
    else:
        e2e_score = None  # N/A
        test_presence_max = 20
    
    test_presence_total = unit_tests_score + (e2e_score if e2e_score is not None else 0)
    
    # Calculate final score (normalized to 100)
    total_earned = code_quality_total + test_health_total + test_presence_total
    total_max = code_quality_max + test_health_max + test_presence_max
    
    final_score = round((total_earned / total_max) * 100) if total_max > 0 else 0
    passed = final_score >= threshold
    
    return {
        "final_score": final_score,
        "threshold": threshold,
        "passed": passed,
        "breakdown": {
            "code_quality": {
                "total": round(code_quality_total, 1),
                "max": code_quality_max,
                "complexity": {
                    "score": complexity_score,
                    "max": 15,
                    "penalty": complexity_penalty,
                    "issues_count": len(all_complexity_issues),
                    "issues": all_complexity_issues[:10]  # Limit to 10 for readability
                },
                "smells": {
                    "score": smells_score,
                    "max": 15,
                    "penalty": smells_penalty,
                    "issues_count": len(all_smell_issues),
                    "issues": all_smell_issues[:10]
                },
                "duplication": {
                    "score": duplication_score,
                    "max": 10,
                    "penalty": duplication_penalty,
                    "percentage": jscpd_data["percentage"],
                    "duplications": jscpd_data["duplications"][:5]
                }
            },
            "test_health": {
                "total": test_health_total,
                "max": test_health_max,
                "coverage": {
                    "score": coverage_score,
                    "max": 20,
                    "percentage": test_data["coverage_percentage"],
                    "total_lines": test_data["coverage_total_lines"],
                    "covered_lines": test_data["coverage_covered_lines"],
                    "by_file": test_data["coverage_by_file"],
                    "uncovered_functions": test_data["uncovered_functions"][:10]
                },
                "results": {
                    "score": test_results_score,
                    "max": 10,
                    "tests_run": test_data["tests_run"],
                    "tests_passed": test_data["tests_passed"],
                    "tests_failed": test_data["tests_failed"],
                    "tests_skipped": test_data["tests_skipped"],
                    "failures": test_data["failures_details"][:5]
                }
            },
            "test_presence": {
                "total": test_presence_total,
                "max": test_presence_max,
                "unit_tests": {
                    "score": unit_tests_score,
                    "max": 20,
                    "found": test_data["unit_tests_found"],
                    "count": test_data["unit_tests_count"],
                    "files": test_data["unit_test_files"][:10]
                },
                "e2e": {
                    "score": e2e_score if e2e_score is not None else "N/A",
                    "max": 10 if e2e_required else "N/A",
                    "required": e2e_required,
                    "found": test_data["e2e_tests_found"],
                    "count": test_data["e2e_tests_count"]
                }
            }
        },
        "raw_data": {
            "total_linter_issues": (
                ruff_data["total_issues"] +
                eslint_data["total_issues"] +
                swiftlint_data["total_issues"] +
                detekt_data["total_issues"]
            ),
            "complexity_issues_count": len(all_complexity_issues),
            "smell_issues_count": len(all_smell_issues),
            "duplication_percentage": jscpd_data["percentage"],
            "duplication_lines": jscpd_data["duplicated_lines"],
            "coverage_percentage": test_data["coverage_percentage"],
            "tests_total": test_data["tests_run"],
            "tests_passed": test_data["tests_passed"],
            "tests_failed": test_data["tests_failed"]
        },
        "files_analyzed": changed_files,
        "files_count": len(changed_files)
    }


def main():
    parser = argparse.ArgumentParser(description="Calculate code quality score")
    parser.add_argument("--changed-files", required=True, help="File with list of changed files")
    parser.add_argument("--config", required=True, help="Quality config YAML file")
    parser.add_argument("--ruff-results", help="Ruff JSON results")
    parser.add_argument("--eslint-results", help="ESLint JSON results")
    parser.add_argument("--swiftlint-results", help="SwiftLint JSON results")
    parser.add_argument("--detekt-results", help="Detekt JSON results")
    parser.add_argument("--jscpd-results", help="jscpd JSON results")
    parser.add_argument("--test-results", help="Test results JSON")
    parser.add_argument("--threshold", type=int, default=70, help="Pass threshold")
    parser.add_argument("--output", required=True, help="Output JSON file")
    
    args = parser.parse_args()
    
    # Load changed files
    changed_files = []
    if os.path.exists(args.changed_files):
        with open(args.changed_files) as f:
            changed_files = [line.strip() for line in f if line.strip()]
    
    # Load config
    config = load_yaml_safe(args.config)
    
    # Parse all results
    ruff_data = parse_ruff_results(load_json_safe(args.ruff_results))
    eslint_data = parse_eslint_results(load_json_safe(args.eslint_results))
    swiftlint_data = parse_swiftlint_results(load_json_safe(args.swiftlint_results))
    detekt_data = parse_detekt_results(load_json_safe(args.detekt_results))
    jscpd_data = parse_jscpd_results(load_json_safe(args.jscpd_results))
    test_data = parse_test_results(load_json_safe(args.test_results))
    
    # Calculate score
    result = calculate_score(
        config=config,
        changed_files=changed_files,
        ruff_data=ruff_data,
        eslint_data=eslint_data,
        swiftlint_data=swiftlint_data,
        detekt_data=detekt_data,
        jscpd_data=jscpd_data,
        test_data=test_data,
        threshold=args.threshold
    )
    
    # Write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Score calculated: {result['final_score']}/100 ({'PASS' if result['passed'] else 'FAIL'})")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
