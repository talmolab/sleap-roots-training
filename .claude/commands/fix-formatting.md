# Fix Formatting Issues

Automatically fix formatting and style issues instead of just checking them.

## Quick Start

```bash
# Auto-fix all formatting issues
```

This command will:
1. Run Black to auto-format all Python code
2. Show what changed
3. Optionally sort imports (if isort is installed)

## What Gets Fixed

### Black Formatting
- Line length (88 characters)
- Quote style (double quotes)
- Indentation (4 spaces)
- Trailing commas
- Whitespace normalization

### Not Auto-Fixed
- Docstring content (must fix manually)
- Variable names
- Logic errors
- Missing docstrings

## Commands Executed

```bash
# Format all Python files
uv run black src/sleap_roots_training tests

# Optional: Sort imports (if isort installed)
uv run isort src/sleap_roots_training tests
```

## Expected Output

### ✅ Files Reformatted

```
Running Black formatter...

reformatted src/sleap_roots_training/config.py
reformatted tests/test_config.py
All done! ✨ 🍰 ✨
2 files reformatted, 21 files left unchanged.

Changes made:
  src/sleap_roots_training/config.py
    - Line 42: Fixed line too long (92 > 88 characters)
    - Line 67: Added trailing comma

  tests/test_config.py
    - Line 15: Normalized quotes (single → double)

✅ Formatting fixed! Review changes with 'git diff'
```

### ✅ No Changes Needed

```
Running Black formatter...

All done! ✨ 🍰 ✨
23 files left unchanged.

✅ Code already properly formatted!
```

## Usage Workflow

### Before Committing

```bash
# 1. Fix formatting automatically
/fix-formatting

# 2. Review changes
git diff

# 3. Stage and commit
git add -u
git commit -m "style: apply Black formatting"
```

### After PR Review

```bash
# Reviewer says: "Please fix formatting"

# Quick fix:
/fix-formatting

# Commit the fixes
git add -u
git commit -m "style: fix formatting per review"
git push
```

### Before Creating PR

```bash
# Clean up formatting before opening PR
/fix-formatting

# Check everything passes
/run-ci-locally

# Create PR
gh pr create
```

## What to Review After Running

### Check Git Diff

Always review what Black changed:

```bash
git diff src/sleap_roots_training/
```

**Look for:**
- Line wrapping changes (long lines split)
- Quote normalization (' → ")
- Trailing comma additions
- Whitespace changes

**Common changes:**
```python
# Before
def calculate_length(points: np.ndarray, normalize: bool = True, scale: float = 1.0, offset: int = 0) -> float:
    return sum([distance(p1, p2) for p1, p2 in zip(points[:-1], points[1:])])

# After (Black formatted)
def calculate_length(
    points: np.ndarray,
    normalize: bool = True,
    scale: float = 1.0,
    offset: int = 0,
) -> float:
    return sum(
        [distance(p1, p2) for p1, p2 in zip(points[:-1], points[1:])]
    )
```

### Verify Tests Still Pass

Formatting should never break tests, but verify:

```bash
uv run pytest tests/
```

If tests fail after formatting, you likely have a syntax error (rare).

## Comparison with /lint

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/lint` | **Check** formatting without changing | Before push, to verify |
| `/fix-formatting` | **Fix** formatting automatically | After changes, to clean up |

**Workflow:**
1. Write code
2. Run `/fix-formatting` to auto-fix
3. Run `/lint` to verify docstrings
4. Commit

## Import Sorting (Optional)

If `isort` is installed, imports will also be sorted:

```python
# Before
import os
import sleap_roots_training
import numpy as np
import pandas as pd
from typing import Dict
import attrs

# After (isort + Black)
import os
from typing import Dict

import attrs
import numpy as np
import pandas as pd

import sleap_roots_training
```

**Install isort:**
```bash
pip install isort
```

## Common Scenarios

### 1. "CI says formatting failed"

```bash
# Fix it
/fix-formatting

# Verify
uv run black --check src/sleap_roots_training tests

# Commit
git add -u
git commit -m "style: apply Black formatting"
git push
```

### 2. "I made lots of changes"

```bash
# Before committing, clean up formatting
/fix-formatting

# Commit formatting separately from logic
git add -u
git commit -m "style: apply Black formatting"

# Then commit your actual changes
git add <your-files>
git commit -m "feat: your actual change"
```

### 3. "Merge conflict formatting mess"

```bash
# After resolving conflicts
git add <resolved-files>

# Clean up formatting (conflicts often break it)
/fix-formatting

# Verify resolved correctly
git diff

# Commit merge
git commit
```

## Configuration

Black configuration in `pyproject.toml`:

```toml
[tool.black]
line-length = 88
```

No configuration needed - Black is intentionally opinionated.

## Manual Fixes Still Needed

Some issues require manual fixing:

### Docstring Issues (pydocstyle)

```python
# Black won't fix this
def calculate_length(points):
    """Calculate length"""  # ❌ Missing period

# You must fix manually:
def calculate_length(points):
    """Calculate length."""  # ✅ Correct
```

### Missing Docstrings

```python
# Black won't add docstrings
def helper_function(x):  # ❌ No docstring
    return x * 2

# You must add:
def helper_function(x):
    """Multiply input by 2.

    Args:
        x: Input value.

    Returns:
        Input multiplied by 2.
    """
    return x * 2
```

Run `/lint` after `/fix-formatting` to find these issues.

## Tips

1. **Run frequently**: Format as you go, not at the end
2. **Separate commits**: Formatting changes in their own commit
3. **Review diffs**: Make sure Black didn't do anything unexpected
4. **IDE integration**: Set up Black in your editor to format on save
5. **Pre-commit hook**: Automatically format before each commit

## IDE Integration

### VSCode

```json
// .vscode/settings.json
{
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

### PyCharm

Settings → Tools → Black → Enable Black formatter

### Vim/Neovim

```vim
" Use Black on save
autocmd BufWritePre *.py execute ':Black'
```

## Pre-Commit Hook

Auto-format on every commit:

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
EOF

# Install hooks
pre-commit install
```

Now Black runs automatically on `git commit`.

## Troubleshooting

### "Black not found"
```bash
uv sync --group dev
```

### "Black version mismatch"
```bash
# Check version
uv run black --version

# Re-sync dev dependencies
uv sync --group dev
```

### "Formatting broke my code"
Very rare, but if it happens:
```bash
# Revert
git checkout -- src/sleap_roots_training/

# Report bug to Black maintainers
```

## Related Commands

- `/lint` - Check formatting without fixing
- `/run-ci-locally` - Run all CI checks (includes formatting check)
- `/coverage` - Verify tests still pass and are covered after formatting
