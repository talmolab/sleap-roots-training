# Run CI Checks Locally

Run CI-equivalent checks locally before pushing your code.

## What This Command Does

This command runs CI-equivalent checks matching `.github/workflows/ci.yml`:

### Step 1: Black Formatting Check

```bash
uv run black --check src/sleap_roots_training tests
```

### Step 2: Ruff Linting

```bash
uv run ruff check src/sleap_roots_training
```

### Step 3: Run Tests

```bash
uv run pytest tests/
```

### Step 4: Coverage Report

```bash
uv run pytest --cov=src/sleap_roots_training --cov-report=xml --cov-report=term-missing --durations=-1 tests/
```

Run each step sequentially. If any step fails, stop and report the failure with instructions to fix.

## Expected Output

### Success (All Checks Pass)

```
[1/4] Black formatting check...
All done!
23 files would be left unchanged.
PASSED

[2/4] Ruff linting...
All checks passed!
PASSED

[3/4] Running tests...
================================ test session starts =================================
...
================================ XX passed in XX.XXs =================================
PASSED

[4/4] Running coverage...
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
...
PASSED

ALL CI CHECKS PASSED
```

### Failure (Checks Failed)

```
[1/4] Black formatting check...
would reformat src/sleap_roots_training/<module>.py
1 file would be reformatted, 22 files would be left unchanged.
FAILED

Fix: Run 'uv run black src/sleap_roots_training tests' to auto-fix formatting
```

## Quick Fixes

When checks fail:

- **Black fails**: `uv run black src/sleap_roots_training tests`
- **Ruff fails**: `uv run ruff check --fix src/sleap_roots_training` (then fix remaining manually)
- **Tests fail**: Read the test output and fix the failing tests
- **Coverage low**: Write tests for uncovered lines (use `/coverage` for details)

## CI Configuration Reference

These commands mirror `.github/workflows/ci.yml`:

- **Lint job step 1**: `uv run black --check src/sleap_roots_training tests`
- **Lint job step 2**: `uv run ruff check src/sleap_roots_training`
- **Test job**: `uv run pytest --cov=src/sleap_roots_training --cov-report=xml --durations=-1 tests/`

CI runs on: ubuntu-latest, windows-latest, macos-14 with Python 3.11 and 3.12.

## When to Use

- Before every `git push`
- Before creating a PR
- After making significant changes
- When you want confidence your PR will pass CI

## Integration

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/lint` | Black + Ruff check | Quick formatting check |
| `/coverage` | Pytest + coverage report | Checking test coverage |
| **`/run-ci-locally`** | **All of the above** | **Before pushing/PR** |

## Comparison with CI

| Check | Local command | CI command | Match? |
|-------|-------------|------------|--------|
| Black | `uv run black --check src/sleap_roots_training tests` | Same | Yes |
| Ruff | `uv run ruff check src/sleap_roots_training` | Same | Yes |
| Tests | `uv run pytest tests/` | `uv run pytest --cov=... tests/` | Yes (CI adds coverage) |

## Troubleshooting

### "Module not found"
```bash
# Install dev dependencies
uv sync --group dev
```

### "Tests fail locally but pass in CI"
- Check Python version: `uv run python --version` (should be 3.11 or 3.12)
- Check dependencies are synced: `uv sync --group dev`
- Try running on a clean install: `uv sync --reinstall`

## Related Commands

- `/lint` - Just formatting and linting checks
- `/coverage` - Full coverage analysis with line-by-line detail
- `/pre-merge-check` - Comprehensive pre-merge workflow including CI
