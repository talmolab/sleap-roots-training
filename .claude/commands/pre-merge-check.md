# Pre-Merge Checks

**Comprehensive pre-merge verification workflow**

Run all quality checks, create PR, review feedback, and update changelog before merging.

## Your Task

Perform a complete pre-merge check following this workflow:

### Phase 1: Code Quality

1. **Formatting & Style**
   - Run `uv run black --check src/sleap_roots_training tests`
   - Run `uv run ruff check src/sleap_roots_training`
   - If failures: fix with `uv run black src/sleap_roots_training tests` and `uv run ruff check --fix src/sleap_roots_training`, then re-run

### Phase 2: Tests & Coverage

2. **Unit Tests**
   - Run `uv run pytest tests/`
   - Run `uv run pytest --cov=src/sleap_roots_training --cov-report=term-missing tests/`
   - If an OpenSpec change exists: `openspec validate --strict`
   - If the change touches training/inference performance, run the relevant integration or benchmark tests (these are marked `@pytest.mark.integration` and skipped in the default CI run)

### Phase 3: Documentation

3. **Documentation Review**
   - Verify docstrings are current for all changed code
   - Check OpenSpec tasks completed: `openspec list`
   - README / config docs up-to-date if public API or config schema changed

### Phase 3.5: Pre-PR Self-Review

3.5. **Self-review the diff with the subagent team**
   - Before creating the PR, run `/review-pr` on the local branch diff (use the branch name, not a PR number, since the PR doesn't exist yet — it runs in REPORT-ONLY mode)
   - This launches 5 critical subagents to review the change the same way they would review an external PR — catching issues that GitHub Copilot or human reviewers would otherwise flag after the PR is open
   - If any BLOCKING or IMPORTANT findings are raised, address them before creating the PR (re-run from Phase 1)
   - **Rationale**: In past sessions, GitHub Copilot has flagged exactly what the subagent team would have found — for example, a test that bypassed the data loading path it was supposed to regression-test. Running our own review tooling pre-PR catches these issues in one iteration instead of two, and avoids burning a Copilot review cycle on something we could have caught ourselves.

### Phase 4: PR Creation

4. **Create or Update PR**
   - Run `gh pr create --title "<title>" --body "<body>"`
   - Include in description: summary, test results, breaking changes, OpenSpec proposal link (if applicable)

### Phase 5: CI Monitoring

5. **Monitor GitHub Actions**
   - Run `gh pr checks <PR_NUMBER>`
   - Watch for cross-platform failures (Ubuntu/Windows/macOS) and Python 3.11/3.12 matrix failures
   - If any fail: investigate the failing job logs and reproduce locally with `uv run pytest`

### Phase 6: Review Feedback

6. **Review PR Comments**
   - Run `gh pr view <PR_NUMBER> --json comments --jq '.comments[] | "\(.author.login): \(.body)"'`
   - Run `gh pr view <PR_NUMBER> --json reviews --jq '.reviews[] | "\(.author.login) (\(.state)): \(.body)"'`
   - Run `/copilot-review` to fetch Copilot inline comments
   - Check: Copilot, Codecov, reviewer feedback

### Phase 7: Changelog

7. **Update Changelog**
   - Run `/update-changelog`

### Phase 8: Final Verification

8. **Final Check**
   - Re-run local CI: `uv run black --check src/sleap_roots_training tests`, `uv run ruff check src/sleap_roots_training`, `uv run pytest tests/`
   - Push changes: `git push`
   - Verify CI: `gh pr checks <PR_NUMBER>`
   - Confirm up-to-date: `git fetch origin main && git merge-base --is-ancestor origin/main HEAD`

## Output Format

Provide results in this format:

```markdown
# Pre-Merge Check Results

## Code Quality
- [x] Black formatting: PASS
- [x] Ruff lint: PASS

## Testing
- [x] Unit Tests: X passed, Y skipped
- [x] Coverage: X% (maintained/improved)
- [x] Integration/benchmarks: No regressions (or N/A)

## Documentation
- [x] Docstrings current
- [x] OpenSpec completed (or N/A)
- [x] OpenSpec validated (or N/A)

## Pull Request
- [x] PR created: #X
- [x] All checks passing

## Changelog
- [x] Entry added (or N/A)

## Status: READY TO MERGE
```

If any checks fail, provide:
- Clear explanation of the failure
- Proposed fix
- Steps to implement
- Re-run instructions

## Planning Mode Template

When using planning mode to address issues, use this template:

```markdown
# Pre-Merge Action Plan

## Current Status
- Branch: [branch-name]
- PR: #[number]
- Target: [main/develop]

## Issues Found

### Critical (Must Fix)
1. [ ] [Issue description]
   - Impact: [description]
   - Fix: [approach]

### Important (Should Fix)
1. [ ] [Issue description]
   - Impact: [description]
   - Fix: [approach]

### Nice-to-Have (Optional)
1. [ ] [Issue description]
   - Impact: [description]
   - Fix: [approach]

## Implementation Plan

### Step 1: [Category]
- Action: [what to do]
- Commands: [commands to run]
- Verification: [how to verify]

### Step 2: [Category]
- Action: [what to do]
- Commands: [commands to run]
- Verification: [how to verify]

## Verification Checklist
- [ ] Local CI passes
- [ ] GitHub CI passes
- [ ] All comments addressed
- [ ] Coverage maintained
- [ ] Documentation updated (if needed)
- [ ] Changelog updated (if needed)

## Ready to Merge
- [ ] All critical issues fixed
- [ ] All important issues addressed or deferred
- [ ] All checks green
- [ ] Approved by reviewer(s)
```

## Troubleshooting

### Issue: "Checks keep failing"
- Review the specific failing check
- Reproduce the failing test locally with `uv run pytest <path>::<test> -v`
- Check logs in GitHub Actions

### Issue: "Copilot comment unclear"
- Ask reviewer for clarification
- Check Copilot documentation
- Make best judgment and document decision

### Issue: "Coverage decreased"
- Use `/coverage` to find untested code
- Write tests for new functionality
- Explain if coverage drop is acceptable

### Issue: "Merge conflicts"
- Rebase on target branch: `git rebase main`
- Resolve conflicts
- Re-run all checks

## Integration with Other Commands

This command orchestrates these other commands:

- `/run-ci-locally` - Run all CI checks locally
- `/coverage` - Analyze test coverage
- `/lint` - Check code style
- `/fix-formatting` - Auto-fix style issues
- `/review-pr` - Comprehensive PR review (used in Phase 3.5 pre-PR and Phase 6 post-PR)
- `/copilot-review` - Fetch GitHub Copilot inline comments on an open PR
- `/update-changelog` - Update changelog
