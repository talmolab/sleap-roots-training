# Validate Development Environment

Check that your development environment is correctly set up and ready for sleap-roots-training development.

## Quick Start

```bash
# Run full environment validation
```

This checks:
1. Python version
2. uv installation
3. Package installation
4. Required dependencies
5. Git LFS configuration (only if the repo tracks LFS files)
6. Test data availability (only if the repo ships test data)
7. Import smoke test

## What Gets Checked

### 1. Python Version
- ✅ Python version matches .python-version file
- ❌ Python version mismatch

### 2. uv Installation
- ✅ uv installed and accessible
- ✅ uv version compatible

### 3. Package Installation
- ✅ Dependencies synced via uv.lock
- ✅ All core dependencies present
- ✅ Dev dependencies present (pytest, black, ruff, etc.)

### 4. Git LFS (only if `.gitattributes` declares LFS filters)
- ✅ Git LFS installed
- ✅ LFS filters configured
- ✅ Tracked data files downloaded (not pointers)

### 5. Test Data (only if the repo ships fixtures/data)
- ✅ Test data files exist
- ✅ Files are actual data (not LFS pointers)
- ✅ Files can be loaded

### 6. Smoke Test
- ✅ Package can be imported (`import sleap_roots_training`)
- ✅ Core modules load without errors
- ✅ CLI entry point responds

## Expected Output

### ✅ Fully Configured Environment

```
================================
Environment Validation
================================

[1/7] Python Version
✅ Python 3.11 (matches .python-version)

[2/7] uv Installation
✅ uv 0.5.0 installed

[3/7] Package Installation
✅ Dependencies synced from uv.lock
   Location: /Users/you/repos/sleap-roots-training/.venv
✅ All core dependencies installed:
   numpy ...
   omegaconf ...
   sleap-nn ...
   sleap-io ...
✅ All dev dependencies installed:
   pytest ...
   black ...
   ruff ...

[4/7] Git LFS
⏭  Skipped (no LFS filters declared in .gitattributes)

[5/7] Test Data
✅ Test data present (or N/A)

[6/7] Smoke Test
✅ Package imports successfully
✅ CLI entry point responds: sleap-roots-training --help

================================
✅ ENVIRONMENT VALID
================================

Your environment is ready for development! 🚀

Next steps:
  - Run tests: uv run pytest tests/
  - Check formatting: uv run black --check src/sleap_roots_training tests
  - Start developing!
```

### ❌ Issues Found

```
================================
Environment Validation
================================

[1/7] Python Version
✅ Python 3.11.0

[2/7] uv Installation
❌ uv not found

FIX: Install uv with:
     curl -LsSf https://astral.sh/uv/install.sh | sh

[3/7] Package Installation
⏭  Skipped (environment not active)

[6/7] Smoke Test
⏭  Skipped (package not installed)

================================
❌ ENVIRONMENT HAS ISSUES
================================

Found 2 issues. Fix them using the commands above.
```

## Common Issues & Fixes

### Issue: "uv not found"

**Cause:** uv not installed

**Fix:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Issue: "Dependencies not synced"

**Cause:** Virtual environment not created or dependencies not installed

**Fix:**
```bash
uv sync --group dev
```

### Issue: "Git LFS not configured" (only relevant if the repo uses LFS)

**Cause:** Git LFS not installed or initialized

**Fix:**
```bash
# macOS
brew install git-lfs

# Ubuntu
sudo apt-get install git-lfs

# Then initialize
git lfs install
```

### Issue: "Test data files are LFS pointers"

**Cause:** LFS files not downloaded (shows as small ~130 byte files)

**Fix:**
```bash
git lfs pull
```

### Issue: "Import errors during smoke test"

**Cause:** Missing dependencies or broken installation

**Fix:**
```bash
# Recreate virtual environment
rm -rf .venv
uv sync --group dev
```

## When to Run This

### Initial Setup
Run after cloning the repository for the first time.

### After Environment Changes
- After updating `pyproject.toml` dependencies
- After `uv lock`
- After installing new dependencies

### Troubleshooting
- When tests fail unexpectedly
- When imports don't work
- When getting "module not found" errors
- After switching machines

### Onboarding
- Help new contributors verify setup
- Include in onboarding documentation

## Detailed Checks Explained

### Python Version Check
```bash
uv run python --version
# Should match the version in .python-version file
```

The Python version is automatically managed by uv based on the .python-version file.

### Virtual Environment Check
```bash
ls -la .venv
# Should show the .venv directory if it exists
```

### Dependency Sync Check
```bash
uv tree
# Should show all dependencies installed from uv.lock
```

Dependencies are managed by uv and installed in the .venv directory.

### Git LFS Check (only if applicable)
```bash
# First confirm the repo actually uses LFS:
grep -q "filter=lfs" .gitattributes && echo "LFS in use" || echo "No LFS — skip this check"

git lfs install
git lfs ls-files
```

### LFS Pointer Detection
```bash
# LFS pointer files are ~130 bytes and start with:
# "version https://git-lfs.github.com/spec/v1"

# Actual files are larger (MB range)
```

### Smoke Test
```python
import sleap_roots_training

print("✅ Package imports")
```

```bash
# CLI entry point
uv run sleap-roots-training --help
```

## Platform-Specific Notes

### macOS
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Git LFS (if needed): `brew install git-lfs`

### Ubuntu
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Git LFS (if needed): `sudo apt-get install git-lfs`
- May need build tools: `sudo apt-get install build-essential`

### Windows
- Install uv: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- Git LFS (if needed): Download from https://git-lfs.github.com/
- Use Git Bash or PowerShell for git commands

## Integration with Other Commands

```bash
# 1. First time setup
git clone <repo-url>
cd sleap-roots-training

# 2. Install dependencies
uv sync --group dev

# 3. Validate environment
/validate-env
# Fix any issues it identifies

# 4. Run tests to verify
/run-ci-locally

# 5. Start development!
```

## Output Format

The command outputs:
- ✅ Green checkmark: Validation passed
- ❌ Red X: Validation failed (with fix instructions)
- ⚠️  Yellow warning: Non-critical issue
- ⏭  Skipped: Check skipped due to previous failure or not applicable

## Related Commands

- `/run-ci-locally` - Run all CI checks (requires valid environment)
- `/coverage` - Run tests with coverage (requires valid environment)
- `/lint` - Check formatting and linting

## Tips

1. **Run after long breaks**: Environment can drift over time
2. **Before filing bug reports**: Attach validation output to bugs
3. **Team onboarding**: Send validation output to verify new contributors
4. **CI debugging**: Compare local validation with CI environment
5. **After system updates**: OS/Python updates can break environment
