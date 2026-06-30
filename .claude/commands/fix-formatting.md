# Fix Formatting

Auto-fix formatting and lint issues (the fix complement to `/lint`, which only checks).

## Commands

```bash
uv run black src/sleap_roots_training tests          # auto-format
uv run ruff check --fix src/sleap_roots_training tests   # auto-fix the lint issues ruff can fix
```

## What gets fixed
- **black**: line length (88), quotes, indentation, trailing commas, whitespace.
- **ruff --fix**: import sorting and other auto-fixable lint findings.

## Not auto-fixed (do manually, then `/lint` to confirm)
- Docstring **content** (google convention) and **missing** docstrings — ruff's pydocstyle
  (`D`) rules flag these but can't write them for you.
- Logic, naming.

## Workflow
1. `/fix-formatting`
2. `git diff` — review what changed.
3. `/lint` — confirm remaining (docstring) issues are clean.
4. Commit formatting separately from logic when the diff is large.
