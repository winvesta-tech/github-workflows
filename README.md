# Code Quality Automation Framework

Automated code quality scoring for PRs across all Winvesta repositories. Provides objective, deterministic metrics for code complexity, test coverage, and code duplication.

## Overview

This framework:
- Runs on every PR (opened, updated, reopened)
- Analyzes only **changed files** (not entire repo)
- Posts detailed comments with actionable feedback
- Logs all data to Google Sheets for tracking
- Integrates with monthly performance scorecards

### Scoring Model (100 points)

| Category | Points | Source |
|----------|--------|--------|
| **Code Quality** | /40 | Static analysis |
| ├─ Complexity | /15 | Linters |
| ├─ Code Smells | /15 | Linters |
| └─ Duplication | /10 | jscpd |
| **Test Health** | /30 | Coverage tools |
| ├─ Coverage % | /20 | Changed files only |
| └─ Test Results | /10 | Pass/fail ratio |
| **Test Presence** | /30 | Penalized if missing |
| ├─ Unit Tests | /20 | Required |
| └─ E2E Tests | /10 | If required for repo |

**Pass Threshold: 70/100**

---

## Quick Start (Per Repo Setup)

### Step 1: Add Caller Workflow

Create `.github/workflows/quality.yml`:

```yaml
name: Code Quality

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

jobs:
  quality:
    if: |
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' && 
       github.event.issue.pull_request && 
       contains(github.event.comment.body, '/quality-check'))
    
    uses: winvesta-tech/github-workflows/.github/workflows/code-quality.yml@main
    secrets: inherit
```

### Step 2: Add Quality Config

Create `.github/quality-config.yml`:

**For Python repos:**
```yaml
languages:
  - python

tests:
  enabled: true
  setup:
    - "pip install -r requirements.txt"
    - "pip install pytest pytest-cov"
  command: "pytest --cov=src --cov-report=xml -v"
  coverage_file: "coverage.xml"

e2e:
  required: false
```

**For JavaScript/TypeScript repos:**
```yaml
languages:
  - javascript
  - typescript

tests:
  enabled: true
  setup:
    - "npm ci"
  command: "npm test -- --coverage --watchAll=false"
  coverage_file: "coverage/lcov.info"

e2e:
  required: false
```

**For Swift repos:**
```yaml
languages:
  - swift

tests:
  enabled: true
  setup:
    - "pod install || true"
  command: "xcodebuild test -workspace App.xcworkspace -scheme App -destination 'platform=iOS Simulator,name=iPhone 15' -enableCodeCoverage YES"
  coverage_file: "coverage.json"

e2e:
  required: false
```

**For Kotlin repos:**
```yaml
languages:
  - kotlin

tests:
  enabled: true
  setup:
    - "chmod +x gradlew"
  command: "./gradlew testDebugUnitTest jacocoTestReport"
  coverage_file: "app/build/reports/jacoco/jacocoTestReport/jacocoTestReport.xml"

e2e:
  required: false
```

That's it! PRs will now get quality checks.

---

## One-Time Organization Setup

### 1. Create Central Repository

Create `winvesta-tech/github-workflows` repo with this codebase.

### 2. Enable Workflow Sharing

In `github-workflows` repo:
1. Go to **Settings** → **Actions** → **General**
2. Under "Access", select **"Accessible from repositories in the organization"**
3. Save

### 3. Create Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project or select existing
3. Enable **Google Sheets API**
4. Create Service Account:
   - Go to **IAM & Admin** → **Service Accounts**
   - Click **Create Service Account**
   - Name: `github-quality-logger`
   - Click **Create and Continue**
   - Skip role (not needed)
   - Click **Done**
5. Create Key:
   - Click on the service account
   - Go to **Keys** tab
   - Click **Add Key** → **Create new key** → **JSON**
   - Download the JSON file

### 4. Create Google Sheet

1. Create new Google Sheet named "Code Quality Logs"
2. Share it with the service account email (found in JSON file)
3. Give **Editor** access
4. Copy the Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit
   ```

### 5. Add Organization Secrets

In GitHub org settings (**Settings** → **Secrets and variables** → **Actions**):

| Secret Name | Value |
|-------------|-------|
| `GOOGLE_SHEETS_CREDENTIALS` | Entire contents of the JSON key file |
| `GOOGLE_SHEET_ID` | The Sheet ID from step 4 |

---

## How It Works

### Workflow Execution

```
PR Opened/Updated
    ↓
Repo calls central reusable workflow
    ↓
Central workflow runs IN CONTEXT of calling repo:
  1. Checkout PR code
  2. Checkout central scripts
  3. Read repo's quality-config.yml
  4. Get list of changed files
  5. Run language-specific linters on changed files
  6. Run duplication check
  7. Run tests with coverage
  8. Parse coverage for changed files only
  9. Calculate score
  10. Post detailed PR comment
  11. Apply quality label
  12. Log everything to Google Sheets
```

### Linters Used

| Language | Tool | What It Checks |
|----------|------|----------------|
| Python | Ruff | Complexity, code smells, style |
| JavaScript/TypeScript | ESLint + SonarJS | Complexity, cognitive complexity, smells |
| Swift | SwiftLint | Complexity, body length, naming |
| Kotlin/Java | Detekt | Complexity, code smells, style |
| All | jscpd | Copy-paste/duplication |

### Coverage Calculation

**Important:** Coverage is calculated ONLY for changed files, not the entire repo.

This prevents gaming where old code has high coverage but new code ships untested.

Formula:
```
coverage = sum(covered_lines_in_changed_files) / sum(total_lines_in_changed_files) × 100
```

---

## PR Comment Example

```markdown
## 🔍 Code Quality Report

| Category | Score | Status |
|----------|-------|--------|
| **Overall** | **72/100** | ✅ Pass |

---

### 📊 Code Quality (20/40)

| Metric | Score | Status |
|--------|-------|--------|
| Complexity | 7/15 | 🟡 |
| Code Smells | 6/15 | 🟡 |
| Duplication | 7/10 | 🟢 |

#### 🔴 Complexity Issues (2 found, -8 points)

| File | Line | Issue |
|------|------|-------|
| `src/api/users.py` | 45 | Function `process_registration` is too complex (18 > 10) |

---

### 🧪 Test Health (25/30)

| Metric | Value | Score | Status |
|--------|-------|-------|--------|
| Coverage (changed files) | 65% | 15/20 | 🟡 |
| Tests Passing | 24/24 | 10/10 | 🟢 |

---

### ✅ Test Presence (20/20)

| Type | Status | Score |
|------|--------|-------|
| Unit Tests | ✅ Found (24 tests) | 20/20 |
| E2E Tests | ⏭️ Not required | N/A |
```

---

## Re-triggering Workflows

### Method 1: Comment on PR
```
/quality-check
```

### Method 2: Push Empty Commit
```bash
git commit --allow-empty -m "Retrigger quality check"
git push
```

### Method 3: GitHub UI
1. Go to PR → **Checks** tab
2. Click **Re-run jobs**

### Method 4: GitHub CLI
```bash
gh run rerun <run-id> --repo winvesta-tech/<repo-name>
```

---

## Google Sheet Schema

All data used in score calculation is logged for debugging:

**Columns (50+):**
- Meta: Timestamp, Repo, PR#, Title, URL, Author, Branches
- Files: Count, List, Lines Added/Removed, Languages
- Code Quality Raw: Issue counts and details
- Code Quality Scores: Calculated scores and penalties
- Test Health Raw: Tests run/passed/failed, coverage data
- Test Health Scores: Calculated scores
- Test Presence: What tests were found
- Final: Score, Threshold, Status
- Debug: Workflow Run URL, Config, Errors

---

## Scorecard Integration

Monthly averages from Google Sheets feed into performance scorecard:

| Avg Monthly Score | Points | Tier |
|-------------------|--------|------|
| ≥85 | 10 | Excellent |
| 70-84 | 8 | Good |
| 55-69 | 5 | Average |
| <55 | 2 | Needs Work |

---

## Labels

Labels are automatically applied to PRs:

| Score | Label | Color |
|-------|-------|-------|
| ≥85 | `quality:excellent` | 🟢 Green |
| 70-84 | `quality:good` | 🔵 Blue |
| 55-69 | `quality:needs-work` | 🟡 Yellow |
| <55 | `quality:poor` | 🔴 Red |

---

## Troubleshooting

### Workflow Not Running
- Check if `.github/workflows/quality.yml` exists
- Verify org secrets are set
- Check Actions are enabled for the repo

### Tests Not Running
- Verify `tests.enabled: true` in config
- Check `tests.command` is correct
- View workflow logs for errors

### Coverage Shows 0%
- Verify `coverage_file` path is correct
- Check test command generates coverage
- Confirm file format matches (XML/LCOV/JSON)

### Google Sheets Not Logging
- Verify `GOOGLE_SHEETS_CREDENTIALS` secret is set
- Check service account has Editor access to sheet
- Verify `GOOGLE_SHEET_ID` is correct

---

## Files in This Repo

```
github-workflows/
├── .github/workflows/
│   └── code-quality.yml      # Main reusable workflow
├── scripts/
│   ├── calculate_score.py    # Score calculation
│   ├── generate_comment.py   # PR comment generation
│   ├── log_to_sheets.py      # Google Sheets logging
│   ├── run_tests.py          # Test runner & coverage parser
│   └── requirements.txt      # Python dependencies
├── configs/
│   ├── ruff.toml             # Python linter config
│   ├── eslint.config.js      # JS/TS linter config
│   ├── swiftlint.yml         # Swift linter config
│   ├── detekt.yml            # Kotlin linter config
│   └── jscpd.json            # Duplication checker config
├── templates/
│   ├── caller-workflow.yml   # Template for repos
│   ├── quality-config-python.yml
│   ├── quality-config-javascript.yml
│   ├── quality-config-swift.yml
│   └── quality-config-kotlin.yml
└── README.md                 # This file
```

---

## Support

Questions? Issues? 
- Check workflow logs in GitHub Actions
- Review Google Sheets for raw data
- Contact Engineering Manager
