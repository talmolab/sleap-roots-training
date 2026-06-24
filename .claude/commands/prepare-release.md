---
description: Guide through complete release process for sleap-roots-training package
---

# Release Process for sleap-roots-training

Comprehensive workflow for releasing a new version of the sleap-roots-training package to PyPI.

## Purpose

This command guides you through the complete release process, ensuring:

1. All pre-release checks pass (tests, coverage, linting, CI)
2. Version is bumped correctly following semantic versioning
3. Changes are documented and committed properly
4. GitHub release is created with appropriate notes
5. Package is published to PyPI automatically via `uv publish` with trusted publishing
6. Release is verified and documented

## Tool Usage

This project uses **uv** as its build backend and package manager:

- **`uv run <tool>`** — Run tools from the dev dependency group (pytest, black, ruff)
- **`uvx <tool>`** — Run one-off tools without installing (pip-audit)
- **`uv build`** — Build wheel and sdist using the `uv_build` backend
- **`uv publish`** — Publish to PyPI using trusted publishing (no tokens needed in CI)
- **`uv version`** — Manage version numbers with semantic versioning support

## Prerequisites

Before starting a release, ensure:

- You are on the `main` branch with latest changes
- All PRs intended for this release are merged
- CI is passing on main branch
- You have maintainer permissions for the repository
- `gh` CLI is authenticated
- `uv` is installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Usage

```bash
# Interactive release workflow
/prepare-release

# Or specify version type
/prepare-release patch       # Bug fixes (0.1.0 → 0.1.1)
/prepare-release minor       # New features (0.1.0 → 0.2.0)
/prepare-release major       # Breaking changes (0.1.0 → 1.0.0)
/prepare-release alpha       # Pre-release alpha (0.1.0 → 0.2.0a1)
/prepare-release beta        # Pre-release beta (0.2.0a1 → 0.2.0b1)
/prepare-release rc          # Release candidate (0.2.0b1 → 0.2.0rc1)
/prepare-release stable      # Stable release (0.2.0rc1 → 0.2.0)
```

**Arguments:** `$ARGUMENTS`

## Release Workflow

### Step 0: Resolve the Repository

Derive the GitHub `owner/repo` dynamically so this workflow is repo-agnostic:

```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Releasing repository: $REPO"
```

Use `$REPO` anywhere a `owner/repo` slug is needed below.

### Step 1: Pre-Release Validation

Verify the project is ready for release:

```bash
# Check we're on main branch
git branch --show-current  # Should be 'main'

# Ensure working directory is clean
git status

# Pull latest changes
git pull origin main

# Verify CI is passing on main
gh run list --branch main --limit 5
```

**Run validation commands** (run in parallel where possible):

```bash
# Formatting check (dev dependency)
uv run black --check src/sleap_roots_training tests

# Linting check (dev dependency)
uv run ruff check src/sleap_roots_training tests

# Full test suite with coverage (dev dependency)
uv run pytest tests/ -x -q --cov=src/sleap_roots_training --cov-report=term-missing --cov-branch
```

**Build and validate package:**

```bash
# Build wheel and sdist using uv_build backend
uv build

# Validate package metadata (one-off tool via uvx, no install needed)
# Security audit (one-off tool via uvx)
uvx pip-audit || echo "Security audit found issues (review before releasing)"
```

**Stop if any checks fail.** Fix issues before proceeding.

### Step 2: Determine Version Number

Follow semantic versioning (https://semver.org):

**MAJOR.MINOR.PATCH** with optional pre-release suffix (PEP 440)

- **PATCH** (0.1.0 → 0.1.1): Bug fixes, documentation updates, minor improvements
- **MINOR** (0.1.0 → 0.2.0): New features, backward-compatible changes
- **MAJOR** (0.1.0 → 1.0.0): Breaking changes, incompatible API changes
- **Pre-release** (0.1.0 → 0.2.0a1): Alpha/beta/rc for testing before stable

Pre-release version progression:
```
0.1.0 → 0.2.0a1 → 0.2.0a2 → 0.2.0b1 → 0.2.0rc1 → 0.2.0
```

Pre-releases publish to **regular PyPI** (not TestPyPI) and are marked as pre-release on GitHub.

Current version: Read from `pyproject.toml`

**Review changes since last release:**

```bash
LAST_TAG=$(gh release list --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null || echo "none")
echo "Last release: $LAST_TAG"
if [ "$LAST_TAG" != "none" ]; then
  git log $LAST_TAG..HEAD --oneline --no-merges
else
  echo "No previous releases found. Showing recent commits:"
  git log --oneline -20
fi
```

### Step 3: Metadata Completeness Check

Read `pyproject.toml` and verify these fields exist and are correct:

- `[project]`: name, version, description, readme, authors, requires-python
- `license` field matches the LICENSE file
- `classifiers` include: Development Status, License, Python version, Topic
- `keywords` are present and relevant
- `[project.urls]`: Homepage, Repository, Issues, Changelog
- `[project.scripts]`: CLI entry point is defined
- `[build-system]`: uses `uv_build` backend

Report any missing metadata and fix it.

### Step 4: Documentation Audit

Check for consistency across documentation:

1. **CHANGELOG** (`docs/CHANGELOG.md`):
   - Has content in `[Unreleased]` section (warn if empty)
   - No duplicate section headers (e.g., two `### Added` blocks)
   - No placeholder dates
   - License references match the actual LICENSE file

2. **README.md**:
   - Python version badge matches `requires-python` in pyproject.toml
   - Installation instructions are correct
   - Include both `pip install` and `uv add` examples

3. **Version consistency**:
   - `pyproject.toml` version field (single source of truth)
   - `__init__.py` uses dynamic versioning via `importlib.metadata` — no manual sync needed

Report all issues found. Fix or ask the user about ambiguous issues.

### Step 5: Update CHANGELOG

Move `[Unreleased]` content into a new version section:

```markdown
## [Unreleased]

## [X.Y.Za1] - YYYY-MM-DD (Pre-release)

### Added
- (moved from Unreleased)
...
```

- Use today's date
- Keep an empty `[Unreleased]` section at top
- For pre-releases, use the full PEP 440 version (e.g., `0.1.0a1`)
- Add `(Pre-release)` suffix for alpha/beta/rc versions
- Clean up any formatting issues (duplicate headers, etc.)
- Update comparison links at bottom if they exist

### Step 6: Create Release Branch

```bash
# Determine versions
CURRENT_VERSION=$(uv version)
echo "Current version: $CURRENT_VERSION"

# Set new version based on $ARGUMENTS or user input
NEW_VERSION="X.Y.Z"  # Replace based on Step 2 decision

# Create release branch
git checkout -b release/v$NEW_VERSION
```

### Step 7: Update Version Number

Bump version using uv's built-in version management:

```bash
# Use uv version for semantic bumps
uv version --bump $ARGUMENTS    # e.g., alpha, beta, rc, patch, minor, major, stable

# Or set a specific version directly
uv version $NEW_VERSION
```

`__init__.py` uses dynamic versioning via `importlib.metadata` — no manual update needed.

### Step 8: Build and Test Release Artifacts

```bash
# Clean previous builds
rm -rf dist/ build/

# Build new distribution with uv_build backend
uv build

# Verify build artifacts
ls -lh dist/
# Should see: sleap_roots_training-X.Y.Z-py3-none-any.whl
#             sleap_roots_training-X.Y.Z.tar.gz

# Test wheel installation in isolated environment
uv run --isolated --with dist/*.whl python -c "import sleap_roots_training; print(f'Version: {sleap_roots_training.__version__}')"

# Test CLI entry point
uv run --isolated --with dist/*.whl sleap-roots-training --help
```

### Step 9: Commit Version Bump and Changelog

```bash
# Stage changes (version and changelog)
git add pyproject.toml docs/CHANGELOG.md

# Include any other files fixed during audit (README, etc.)
# git add README.md  # if updated

# Commit with standard message format
# Note: __init__.py uses dynamic versioning, only pyproject.toml needs updating
git commit -m "chore: bump version to v$NEW_VERSION

- Update version in pyproject.toml
- Update CHANGELOG.md with release notes"

# Push release branch
git push origin release/v$NEW_VERSION
```

### Step 10: Create and Merge Version Bump PR

```bash
gh pr create \
  --title "Release v$NEW_VERSION" \
  --body "$(cat <<'EOF'
## Release v$NEW_VERSION

### Version Bump
- Bumps version from $CURRENT_VERSION to $NEW_VERSION

### Pre-Release Checklist
- [x] All tests pass locally
- [x] Coverage verified
- [x] Linting checks pass (uv run black, uv run ruff)
- [x] Build artifacts verified (uv build)
- [x] Package installs correctly from wheel
- [x] CLI entry point works
- [x] CI passing on main branch
- [x] CHANGELOG.md updated

### Post-Merge Steps
1. Create GitHub release with tag v$NEW_VERSION
2. Verify PyPI upload via GitHub Actions (uv publish with trusted publishing)
3. Test installation from PyPI

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"

# Wait for CI checks
gh pr checks --watch

# After approval, merge
echo "Request review from maintainers, then merge when approved"
```

### Step 11: Create GitHub Release

After PR is merged to main:

**GUARDRAILS before creating the release:**

1. **Verify CHANGELOG is up-to-date**: Read `docs/CHANGELOG.md` and confirm:
   - The `[Unreleased]` section is empty (all changes moved to the new version section)
   - The new version section `## [X.Y.Z]` exists with today's date
   - The section contains meaningful content (not just a header)

2. **Extract the exact changelog section** for this version using Python:
   ```python
   import re
   with open("docs/CHANGELOG.md") as f:
       content = f.read()
   # Extract section for NEW_VERSION
   pattern = rf"## \[{re.escape(NEW_VERSION)}\].*?(?=\n## \[|\Z)"
   match = re.search(pattern, content, re.DOTALL)
   if not match:
       raise ValueError(f"Version {NEW_VERSION} not found in CHANGELOG.md!")
   changelog_section = match.group(0).strip()
   print(changelog_section)
   ```
   If the version section is missing or empty, **stop and fix the CHANGELOG first**.

3. **Confirm the extracted content looks correct** before proceeding.

```bash
# Switch to main and pull
git checkout main
git pull origin main

# Resolve the repository slug for the release notes link
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# For pre-releases, add --prerelease flag
# For stable releases, omit --prerelease
gh release create v$NEW_VERSION \
  --title "sleap-roots-training v$NEW_VERSION" \
  --prerelease \
  --notes "$(cat <<EOF
## Installation

\`\`\`bash
pip install sleap-roots-training==$NEW_VERSION
\`\`\`

Or with uv:

\`\`\`bash
uv add sleap-roots-training==$NEW_VERSION
\`\`\`

One-shot usage (no install needed):

\`\`\`bash
uvx --from sleap-roots-training==$NEW_VERSION sleap-roots-training --help
\`\`\`

## What's Changed

<INSERT EXTRACTED CHANGELOG SECTION HERE — the content from docs/CHANGELOG.md for this version, excluding the version header line>

**Full Changelog**: https://github.com/$REPO/commits/v$NEW_VERSION

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

The GitHub Actions workflow `.github/workflows/build.yml` will automatically:
1. Validate version consistency (tag vs pyproject.toml vs CHANGELOG)
2. Run the full test suite
3. Build the wheel and sdist with `uv build`
4. Test wheel installation
5. Publish to PyPI with `uv publish` (trusted publishing, no tokens needed)

### Step 12: Verify Release

```bash
# Watch GitHub Actions workflow
gh run watch

# Once complete, verify on PyPI
echo "Checking PyPI..."
curl -s https://pypi.org/pypi/sleap-roots-training/json | python -c "import sys,json; vers=json.load(sys.stdin)['releases'].keys(); print([v for v in vers if '$NEW_VERSION' in v])"

# Test installation from PyPI (uvx for one-off test, no local install)
uvx --from "sleap-roots-training==$NEW_VERSION" sleap-roots-training --help

# Or test with uv add in a scratch project
uv run --isolated --with "sleap-roots-training==$NEW_VERSION" python -c "import sleap_roots_training; print(f'Installed {sleap_roots_training.__version__} from PyPI')"
```

### Step 13: Post-Release Tasks

```bash
# Clean up release branch (if not auto-deleted)
git branch -d release/v$NEW_VERSION

# Update any version badges or links if needed
# Close any resolved issues
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Release v$NEW_VERSION complete!"
echo "PyPI: https://pypi.org/project/sleap-roots-training/$NEW_VERSION/"
echo "GitHub: https://github.com/$REPO/releases/tag/v$NEW_VERSION"
```

## Rollback Procedures

### If Release Fails Before PyPI Upload

```bash
# Delete GitHub release
gh release delete v$NEW_VERSION --yes

# Delete tag
git tag -d v$NEW_VERSION
git push origin :refs/tags/v$NEW_VERSION

# Revert version bump on main
git revert HEAD
git push origin main
```

### If Release Fails After PyPI Upload

**Note:** You cannot delete releases from PyPI, only "yank" them.

```bash
# PyPI yanking must be done through the PyPI web interface
# Go to: https://pypi.org/manage/project/sleap-roots-training/releases/
# Or release a patch version with fixes
```

## Publishing Architecture

This repo uses **uv-native publishing**:

- **Build backend**: `uv_build` (defined in `pyproject.toml [build-system]`)
- **Build command**: `uv build` (validates metadata, creates wheel + sdist)
- **CI publishing**: `uv publish` with PyPI trusted publishing (`id-token: write`)
- **No tokens needed in CI**: Trusted publishing authenticates via GitHub OIDC

## Integration with Other Commands

- `/run-ci-locally` - Run exact CI checks locally
- `/lint` - Quick formatting and linting check
- `/coverage` - Detailed test coverage analysis
- `/update-changelog` - Update CHANGELOG.md with changes
- `/pre-merge-check` - Comprehensive pre-merge validation
- `/cleanup-merged` - Clean up release branch after merge
