Run linting with `ruff` and formatting with `black`.

This matches the CI workflow in `.github/workflows/ci.yml`.

## Check Mode (default)

Verify formatting and linting without modifying files:

```bash
uv run black --check src/sleap_roots_training tests && uv run ruff check src/sleap_roots_training
```

## Fix Mode

Auto-fix formatting and linting issues:

```bash
uv run black src/sleap_roots_training tests && uv run ruff check --fix src/sleap_roots_training
```

Then manually fix any remaining errors which cannot be automatically fixed by ruff.

## CI Reference

These commands mirror `.github/workflows/ci.yml`:
- **Lint job step 1**: `uv run black --check src/sleap_roots_training tests`
- **Lint job step 2**: `uv run ruff check src/sleap_roots_training`

## Integration

- Run `/lint` before committing to catch issues early
- Run `/run-ci-locally` for full CI verification including tests
- Run `/pre-merge-check` for comprehensive PR readiness
