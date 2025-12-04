#!/usr/bin/env python3
"""
Run tests and parse coverage reports.
Supports multiple formats: Cobertura XML, LCOV, JSON (Istanbul).
Only measures coverage of changed files.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
import glob

import yaml


def load_yaml_safe(filepath: str) -> dict:
    """Load YAML file safely."""
    if not filepath or not os.path.exists(filepath):
        return {}
    try:
        with open(filepath) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load {filepath}: {e}")
        return {}


def load_changed_files(filepath: str) -> list[str]:
    """Load list of changed files."""
    if not filepath or not os.path.exists(filepath):
        return []
    with open(filepath) as f:
        return [line.strip() for line in f if line.strip()]


def run_command(cmd: str, cwd: str = ".") -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out after 600 seconds"
    except Exception as e:
        return 1, "", str(e)


def find_test_files(patterns: list[str] = None) -> dict:
    """Find test files in the repository."""
    if patterns is None:
        patterns = [
            "test_*.py", "*_test.py",
            "*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts",
            "*Test.kt", "*Test.java",
            "*Tests.swift", "*Spec.swift"
        ]
    
    result = {
        "unit_test_files": [],
        "e2e_test_files": [],
        "unit_tests_found": False,
        "e2e_tests_found": False
    }
    
    e2e_patterns = ["e2e", "integration", "cypress", "playwright", "selenium"]
    
    for pattern in patterns:
        try:
            files = glob.glob(f"**/{pattern}", recursive=True)
            
            for f in files:
                if any(skip in f for skip in ["node_modules", "venv", ".venv", "__pycache__", "dist", "build"]):
                    continue
                
                is_e2e = any(e2e in f.lower() for e2e in e2e_patterns)
                
                if is_e2e:
                    result["e2e_test_files"].append(f)
                    result["e2e_tests_found"] = True
                else:
                    result["unit_test_files"].append(f)
                    result["unit_tests_found"] = True
        except Exception as e:
            print(f"Warning: Error finding files with pattern {pattern}: {e}")
    
    return result


def parse_cobertura_xml(filepath: str, changed_files: list[str]) -> dict:
    """Parse Cobertura XML coverage report."""
    result = {
        "total_lines": 0,
        "covered_lines": 0,
        "percentage": 0.0,
        "by_file": [],
        "uncovered_functions": []
    }
    
    if not filepath or not os.path.exists(filepath):
        return result
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        changed_normalized = set(os.path.normpath(f) for f in changed_files)
        
        for package in root.findall(".//package"):
            for cls in package.findall(".//class"):
                filename = cls.get("filename", "")
                filename_norm = os.path.normpath(filename)
                
                is_changed = False
                for cf in changed_normalized:
                    if filename_norm.endswith(cf) or cf.endswith(filename_norm) or filename in cf or cf in filename:
                        is_changed = True
                        break
                
                if not is_changed:
                    continue
                
                file_total = 0
                file_covered = 0
                
                for line in cls.findall(".//line"):
                    file_total += 1
                    hits = int(line.get("hits", 0))
                    if hits > 0:
                        file_covered += 1
                
                if file_total > 0:
                    result["total_lines"] += file_total
                    result["covered_lines"] += file_covered
                    
                    file_pct = (file_covered / file_total) * 100
                    result["by_file"].append({
                        "file": filename,
                        "total_lines": file_total,
                        "covered_lines": file_covered,
                        "coverage": round(file_pct, 1)
                    })
                    
                    for method in cls.findall(".//method"):
                        method_name = method.get("name", "")
                        method_line = method.get("line", "?")
                        for line in method.findall(".//line"):
                            if int(line.get("hits", 0)) == 0:
                                result["uncovered_functions"].append(f"{filename}:{method_line} ({method_name})")
                                break
        
        if result["total_lines"] > 0:
            result["percentage"] = round((result["covered_lines"] / result["total_lines"]) * 100, 1)
        
    except Exception as e:
        print(f"Warning: Error parsing Cobertura XML: {e}")
    
    return result


def parse_lcov(filepath: str, changed_files: list[str]) -> dict:
    """Parse LCOV coverage report."""
    result = {
        "total_lines": 0,
        "covered_lines": 0,
        "percentage": 0.0,
        "by_file": [],
        "uncovered_functions": []
    }
    
    if not filepath or not os.path.exists(filepath):
        return result
    
    try:
        changed_normalized = set(os.path.normpath(f) for f in changed_files)
        current_file = None
        file_total = 0
        file_covered = 0
        
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                
                if line.startswith("SF:"):
                    current_file = line[3:]
                    file_total = 0
                    file_covered = 0
                    
                elif line.startswith("DA:"):
                    parts = line[3:].split(",")
                    if len(parts) >= 2:
                        hits = int(parts[1])
                        file_total += 1
                        if hits > 0:
                            file_covered += 1
                
                elif line == "end_of_record" and current_file:
                    file_norm = os.path.normpath(current_file)
                    is_changed = False
                    for cf in changed_normalized:
                        if file_norm.endswith(cf) or cf.endswith(file_norm) or current_file in cf or cf in current_file:
                            is_changed = True
                            break
                    
                    if is_changed and file_total > 0:
                        result["total_lines"] += file_total
                        result["covered_lines"] += file_covered
                        
                        file_pct = (file_covered / file_total) * 100
                        result["by_file"].append({
                            "file": current_file,
                            "total_lines": file_total,
                            "covered_lines": file_covered,
                            "coverage": round(file_pct, 1)
                        })
                    
                    current_file = None
        
        if result["total_lines"] > 0:
            result["percentage"] = round((result["covered_lines"] / result["total_lines"]) * 100, 1)
        
    except Exception as e:
        print(f"Warning: Error parsing LCOV: {e}")
    
    return result


def parse_istanbul_json(filepath: str, changed_files: list[str]) -> dict:
    """Parse Istanbul JSON coverage report."""
    result = {
        "total_lines": 0,
        "covered_lines": 0,
        "percentage": 0.0,
        "by_file": [],
        "uncovered_functions": []
    }
    
    if not filepath or not os.path.exists(filepath):
        return result
    
    try:
        with open(filepath) as f:
            data = json.load(f)
        
        changed_normalized = set(os.path.normpath(f) for f in changed_files)
        
        for file_path, file_data in data.items():
            file_norm = os.path.normpath(file_path)
            
            is_changed = False
            for cf in changed_normalized:
                if file_norm.endswith(cf) or cf.endswith(file_norm) or file_path in cf or cf in file_path:
                    is_changed = True
                    break
            
            if not is_changed:
                continue
            
            statements = file_data.get("s", {})
            file_total = len(statements)
            file_covered = sum(1 for v in statements.values() if v > 0)
            
            if file_total > 0:
                result["total_lines"] += file_total
                result["covered_lines"] += file_covered
                
                file_pct = (file_covered / file_total) * 100
                result["by_file"].append({
                    "file": file_path,
                    "total_lines": file_total,
                    "covered_lines": file_covered,
                    "coverage": round(file_pct, 1)
                })
                
                functions = file_data.get("f", {})
                fn_map = file_data.get("fnMap", {})
                for fn_id, hits in functions.items():
                    if hits == 0 and fn_id in fn_map:
                        fn_info = fn_map[fn_id]
                        fn_name = fn_info.get("name", "anonymous")
                        fn_line = fn_info.get("loc", {}).get("start", {}).get("line", "?")
                        result["uncovered_functions"].append(f"{file_path}:{fn_line} ({fn_name})")
        
        if result["total_lines"] > 0:
            result["percentage"] = round((result["covered_lines"] / result["total_lines"]) * 100, 1)
        
    except Exception as e:
        print(f"Warning: Error parsing Istanbul JSON: {e}")
    
    return result


def parse_test_output(stdout: str, stderr: str) -> dict:
    """Parse test output to extract pass/fail counts."""
    result = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
        "failures": []
    }
    
    combined = stdout + "\n" + stderr
    
    # Pytest format
    pytest_match = re.search(r"(\d+) passed", combined)
    if pytest_match:
        result["tests_passed"] = int(pytest_match.group(1))
    
    pytest_fail = re.search(r"(\d+) failed", combined)
    if pytest_fail:
        result["tests_failed"] = int(pytest_fail.group(1))
    
    pytest_skip = re.search(r"(\d+) skipped", combined)
    if pytest_skip:
        result["tests_skipped"] = int(pytest_skip.group(1))
    
    # Jest format
    jest_match = re.search(r"Tests:\s+(\d+)\s+passed", combined)
    if jest_match:
        result["tests_passed"] = int(jest_match.group(1))
    
    jest_fail = re.search(r"(\d+)\s+failed", combined)
    if jest_fail and result["tests_passed"] > 0:
        result["tests_failed"] = int(jest_fail.group(1))
    
    result["tests_run"] = result["tests_passed"] + result["tests_failed"] + result["tests_skipped"]
    
    failure_patterns = [
        r"FAILED\s+(.+?)\s+-",
        r"✕\s+(.+)",
        r"FAIL\s+(.+)",
    ]
    
    for pattern in failure_patterns:
        failures = re.findall(pattern, combined)
        result["failures"].extend(failures[:5])
        if len(result["failures"]) >= 5:
            break
    
    return result


def run_tests(config: dict, changed_files: list[str]) -> dict:
    """Run tests and collect coverage."""
    result = {
        "tests_run": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
        "failures": [],
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
    
    # Find test files first
    test_files = find_test_files()
    result.update(test_files)
    result["unit_tests_count"] = len(test_files.get("unit_test_files", []))
    result["e2e_tests_count"] = len(test_files.get("e2e_test_files", []))
    
    tests_config = config.get("tests", {})
    
    if not tests_config.get("enabled", False):
        print("Tests not enabled in config")
        return result
    
    # Run setup commands
    setup_cmds = tests_config.get("setup", [])
    for cmd in setup_cmds:
        print(f"Setup: {cmd}")
        returncode, stdout, stderr = run_command(cmd)
        if returncode != 0:
            print(f"Warning: Setup command failed: {stderr}")
    
    # Run test command
    test_cmd = tests_config.get("command", "")
    if not test_cmd:
        # Try language-specific defaults
        commands = tests_config.get("commands", {})
        for lang, cmd in commands.items():
            print(f"Running {lang} tests: {cmd}")
            returncode, stdout, stderr = run_command(cmd)
            
            # Parse results
            test_result = parse_test_output(stdout, stderr)
            result["tests_run"] += test_result["tests_run"]
            result["tests_passed"] += test_result["tests_passed"]
            result["tests_failed"] += test_result["tests_failed"]
            result["tests_skipped"] += test_result["tests_skipped"]
            result["failures"].extend(test_result["failures"])
    else:
        print(f"Running tests: {test_cmd}")
        returncode, stdout, stderr = run_command(test_cmd)
        
        test_result = parse_test_output(stdout, stderr)
        result["tests_run"] = test_result["tests_run"]
        result["tests_passed"] = test_result["tests_passed"]
        result["tests_failed"] = test_result["tests_failed"]
        result["tests_skipped"] = test_result["tests_skipped"]
        result["failures"] = test_result["failures"]
    
    # Parse coverage
    coverage_file = tests_config.get("coverage_file", "")
    coverage_files = tests_config.get("coverage_files", {})
    
    coverage_result = {"total_lines": 0, "covered_lines": 0, "percentage": 0.0, "by_file": [], "uncovered_functions": []}
    
    # Try main coverage file
    if coverage_file:
        if coverage_file.endswith(".xml"):
            coverage_result = parse_cobertura_xml(coverage_file, changed_files)
        elif coverage_file.endswith(".info") or "lcov" in coverage_file:
            coverage_result = parse_lcov(coverage_file, changed_files)
        elif coverage_file.endswith(".json"):
            coverage_result = parse_istanbul_json(coverage_file, changed_files)
    
    # Try language-specific coverage files
    for lang, cov_file in coverage_files.items():
        if not os.path.exists(cov_file):
            continue
            
        if cov_file.endswith(".xml"):
            lang_cov = parse_cobertura_xml(cov_file, changed_files)
        elif cov_file.endswith(".info") or "lcov" in cov_file:
            lang_cov = parse_lcov(cov_file, changed_files)
        elif cov_file.endswith(".json"):
            lang_cov = parse_istanbul_json(cov_file, changed_files)
        else:
            continue
        
        coverage_result["total_lines"] += lang_cov["total_lines"]
        coverage_result["covered_lines"] += lang_cov["covered_lines"]
        coverage_result["by_file"].extend(lang_cov["by_file"])
        coverage_result["uncovered_functions"].extend(lang_cov["uncovered_functions"])
    
    # Recalculate overall percentage
    if coverage_result["total_lines"] > 0:
        coverage_result["percentage"] = round(
            (coverage_result["covered_lines"] / coverage_result["total_lines"]) * 100, 1
        )
    
    result["coverage_percentage"] = coverage_result["percentage"]
    result["coverage_by_file"] = coverage_result["by_file"]
    result["uncovered_functions"] = coverage_result["uncovered_functions"]
    result["coverage_total_lines"] = coverage_result["total_lines"]
    result["coverage_covered_lines"] = coverage_result["covered_lines"]
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Run tests and parse coverage")
    parser.add_argument("--config", required=True, help="Quality config YAML file")
    parser.add_argument("--changed-files", required=True, help="File with list of changed files")
    parser.add_argument("--output", required=True, help="Output JSON file")
    
    args = parser.parse_args()
    
    config = load_yaml_safe(args.config)
    changed_files = load_changed_files(args.changed_files)
    
    print(f"Config: {config}")
    print(f"Changed files: {changed_files}")
    
    result = run_tests(config, changed_files)
    
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Test results written to {args.output}")
    print(f"Tests: {result['tests_passed']}/{result['tests_run']} passed")
    print(f"Coverage: {result['coverage_percentage']}%")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
