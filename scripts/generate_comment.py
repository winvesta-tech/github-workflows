#!/usr/bin/env python3
"""
Generate a detailed PR comment from the quality score results.
"""

import argparse
import json
import os
import sys
from datetime import datetime


def get_status_emoji(score: int | float, max_score: int | float) -> str:
    """Get status emoji based on score percentage."""
    if max_score == 0:
        return "⚪"
    pct = (score / max_score) * 100
    if pct >= 80:
        return "🟢"
    elif pct >= 60:
        return "🟡"
    else:
        return "🔴"


def get_overall_emoji(passed: bool) -> str:
    """Get overall status emoji."""
    return "✅" if passed else "❌"


def format_file_path(filepath: str, max_len: int = 40) -> str:
    """Truncate long file paths."""
    if len(filepath) <= max_len:
        return f"`{filepath}`"
    return f"`...{filepath[-(max_len-3):]}`"


def generate_comment(score_data: dict) -> str:
    """Generate markdown comment from score data."""
    
    final_score = score_data["final_score"]
    threshold = score_data["threshold"]
    passed = score_data["passed"]
    breakdown = score_data["breakdown"]
    
    # Header
    lines = [
        "## 🔍 Code Quality Report",
        "",
        "| Category | Score | Status |",
        "|----------|-------|--------|",
        f"| **Overall** | **{final_score}/100** | {get_overall_emoji(passed)} {'Pass' if passed else f'Below threshold ({threshold})'} |",
        "",
        "---",
        ""
    ]
    
    # Code Quality Section
    cq = breakdown["code_quality"]
    lines.extend([
        f"### 📊 Code Quality ({cq['total']}/{cq['max']})",
        "",
        "| Metric | Score | Status |",
        "|--------|-------|--------|",
        f"| Complexity | {cq['complexity']['score']}/{cq['complexity']['max']} | {get_status_emoji(cq['complexity']['score'], cq['complexity']['max'])} |",
        f"| Code Smells | {cq['smells']['score']}/{cq['smells']['max']} | {get_status_emoji(cq['smells']['score'], cq['smells']['max'])} |",
        f"| Duplication | {cq['duplication']['score']}/{cq['duplication']['max']} | {get_status_emoji(cq['duplication']['score'], cq['duplication']['max'])} |",
        ""
    ])
    
    # Complexity Issues
    complexity_issues = cq["complexity"]["issues"]
    if complexity_issues:
        lines.extend([
            f"#### 🔴 Complexity Issues ({cq['complexity']['issues_count']} found, -{cq['complexity']['penalty']} points)",
            "",
            "| File | Line | Issue |",
            "|------|------|-------|",
        ])
        for issue in complexity_issues[:5]:
            lines.append(f"| {format_file_path(issue['file'])} | {issue['line']} | {issue['message'][:60]}{'...' if len(issue['message']) > 60 else ''} |")
        
        if cq['complexity']['issues_count'] > 5:
            lines.append(f"| ... | ... | *{cq['complexity']['issues_count'] - 5} more issues* |")
        
        lines.extend([
            "",
            "<details>",
            "<summary>💡 How to fix complexity issues</summary>",
            "",
            "- Break large functions into smaller, focused functions",
            "- Extract helper functions for distinct logic blocks",
            "- Use early returns to reduce nesting",
            "- Consider the Single Responsibility Principle",
            "- Aim for functions under 20 lines and complexity under 10",
            "",
            "</details>",
            ""
        ])
    
    # Code Smells
    smell_issues = cq["smells"]["issues"]
    if smell_issues:
        lines.extend([
            f"#### 🟡 Code Smells ({cq['smells']['issues_count']} found, -{cq['smells']['penalty']} points)",
            "",
            "| File | Line | Issue | Rule |",
            "|------|------|-------|------|",
        ])
        for issue in smell_issues[:5]:
            lines.append(f"| {format_file_path(issue['file'])} | {issue['line']} | {issue['message'][:40]}{'...' if len(issue['message']) > 40 else ''} | `{issue['code']}` |")
        
        if cq['smells']['issues_count'] > 5:
            lines.append(f"| ... | ... | *{cq['smells']['issues_count'] - 5} more issues* | ... |")
        
        lines.append("")
    
    # Duplication
    if cq["duplication"]["percentage"] > 0:
        lines.extend([
            f"#### 📋 Duplication ({cq['duplication']['percentage']:.1f}%, -{cq['duplication']['penalty']} points)",
            "",
        ])
        if cq["duplication"]["duplications"]:
            lines.extend([
                "| First File | Second File | Lines |",
                "|------------|-------------|-------|",
            ])
            for dup in cq["duplication"]["duplications"][:3]:
                lines.append(f"| {format_file_path(dup['first_file'])} | {format_file_path(dup['second_file'])} | {dup['lines']} |")
            lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # Test Health Section
    th = breakdown["test_health"]
    lines.extend([
        f"### 🧪 Test Health ({th['total']}/{th['max']})",
        "",
        "| Metric | Value | Score | Status |",
        "|--------|-------|-------|--------|",
        f"| Coverage (changed files) | {th['coverage']['percentage']:.1f}% | {th['coverage']['score']}/{th['coverage']['max']} | {get_status_emoji(th['coverage']['score'], th['coverage']['max'])} |",
        f"| Tests Passing | {th['results']['tests_passed']}/{th['results']['tests_run']} | {th['results']['score']}/{th['results']['max']} | {get_status_emoji(th['results']['score'], th['results']['max'])} |",
        ""
    ])
    
    # Coverage by file
    coverage_files = th["coverage"]["by_file"]
    if coverage_files:
        lines.extend([
            "<details>",
            "<summary>📁 Coverage by File</summary>",
            "",
            "| File | Lines | Covered | Coverage | Status |",
            "|------|-------|---------|----------|--------|",
        ])
        for cf in coverage_files[:10]:
            cov_pct = cf.get("coverage", 0)
            status = "🟢" if cov_pct >= 80 else "🟡" if cov_pct >= 60 else "🔴"
            lines.append(f"| {format_file_path(cf.get('file', ''))} | {cf.get('total_lines', 0)} | {cf.get('covered_lines', 0)} | {cov_pct:.1f}% | {status} |")
        
        if len(coverage_files) > 10:
            lines.append(f"| ... | ... | ... | *{len(coverage_files) - 10} more files* | ... |")
        
        lines.extend([
            "",
            "</details>",
            ""
        ])
    
    # Uncovered functions
    uncovered = th["coverage"]["uncovered_functions"]
    if uncovered:
        lines.extend([
            "<details>",
            "<summary>⚠️ Uncovered Functions</summary>",
            "",
        ])
        for func in uncovered[:10]:
            lines.append(f"- `{func}`")
        if len(uncovered) > 10:
            lines.append(f"- *...and {len(uncovered) - 10} more*")
        lines.extend([
            "",
            "</details>",
            ""
        ])
    
    # Test failures
    failures = th["results"]["failures"]
    if failures:
        lines.extend([
            "#### ❌ Failed Tests",
            "",
        ])
        for fail in failures[:5]:
            lines.append(f"- `{fail}`")
        if len(failures) > 5:
            lines.append(f"- *...and {len(failures) - 5} more*")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    
    # Test Presence Section
    tp = breakdown["test_presence"]
    lines.extend([
        f"### ✅ Test Presence ({tp['total']}/{tp['max']})",
        "",
        "| Type | Status | Score |",
        "|------|--------|-------|",
    ])
    
    unit_status = "✅ Found" if tp["unit_tests"]["found"] else "❌ Not found"
    unit_count = f" ({tp['unit_tests']['count']} tests)" if tp["unit_tests"]["found"] else ""
    lines.append(f"| Unit Tests | {unit_status}{unit_count} | {tp['unit_tests']['score']}/{tp['unit_tests']['max']} |")
    
    if tp["e2e"]["required"]:
        e2e_status = "✅ Found" if tp["e2e"]["found"] else "❌ Not found"
        e2e_count = f" ({tp['e2e']['count']} tests)" if tp["e2e"]["found"] else ""
        lines.append(f"| E2E Tests | {e2e_status}{e2e_count} | {tp['e2e']['score']}/{tp['e2e']['max']} |")
    else:
        lines.append(f"| E2E Tests | ⏭️ Not required | N/A |")
    
    lines.extend(["", "---", ""])
    
    # Score Breakdown
    lines.extend([
        "### 📊 Score Breakdown",
        "",
        "| Category | Earned | Max |",
        "|----------|--------|-----|",
        f"| Code Quality | {cq['total']} | {cq['max']} |",
        f"| Test Health | {th['total']} | {th['max']} |",
        f"| Test Presence | {tp['total']} | {tp['max']} |",
        f"| **Total** | **{final_score}** | **100** |",
        "",
        "---",
        ""
    ])
    
    # Final message
    if passed:
        lines.extend([
            "> ✅ **This PR meets quality standards.**",
        ])
        
        # Suggestions for improvement even if passed
        suggestions = []
        if th['coverage']['percentage'] < 80:
            suggestions.append(f"Consider improving coverage (currently {th['coverage']['percentage']:.1f}%)")
        if cq['complexity']['issues_count'] > 0:
            suggestions.append(f"Consider reducing complexity ({cq['complexity']['issues_count']} issues)")
        if cq['smells']['issues_count'] > 0:
            suggestions.append(f"Consider fixing code smells ({cq['smells']['issues_count']} issues)")
        
        if suggestions:
            lines.append(f"> 💡 Suggestions: {'; '.join(suggestions)}")
    else:
        lines.extend([
            f"> ❌ **This PR is below the quality threshold ({threshold}).**",
            "> Please address the issues above before merging.",
        ])
    
    lines.extend([
        "",
        "---",
        f"<sub>Generated by Code Quality Check • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</sub>",
    ])
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate PR comment markdown")
    parser.add_argument("--score-file", required=True, help="Score JSON file")
    parser.add_argument("--output", required=True, help="Output markdown file")
    
    args = parser.parse_args()
    
    # Load score data
    with open(args.score_file) as f:
        score_data = json.load(f)
    
    # Generate comment
    comment = generate_comment(score_data)
    
    # Write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write(comment)
    
    print(f"Comment generated: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
