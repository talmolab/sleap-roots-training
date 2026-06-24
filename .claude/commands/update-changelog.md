# Update CHANGELOG.md

Update the project's CHANGELOG.md file (located at `docs/CHANGELOG.md`) following the Keep a Changelog format.

## When to Update

- Adding new features
- Fixing bugs
- Making breaking changes
- Updating dependencies
- Improving documentation
- Refactoring code

## CHANGELOG Format

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features that have been added

### Changed
- Changes to existing functionality

### Fixed
- Bug fixes

### Deprecated
- Features that will be removed in future versions

### Removed
- Features that have been removed

### Security
- Security fixes and improvements
```

## Categories

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Vulnerability fixes

## Steps to Update

1. **Check current changes**
```bash
# View recent commits since last tag
git log --oneline $(git describe --tags --abbrev=0)..HEAD

# Or view all uncommitted changes
git diff HEAD
```

2. **Identify change category**
- Is it a new feature? → Added
- Is it a bug fix? → Fixed
- Does it change existing behavior? → Changed
- Does it remove something? → Removed

3. **Write clear descriptions**
- Start with a verb (Added, Fixed, Updated, etc.)
- Be concise but descriptive
- Include PR numbers if applicable
- Reference issues if applicable

## Examples

### Good Examples
```markdown
### Added
- Generalist (multi-species) keypoint training config with W&B artifact lineage (#47)
- Skeleton unification step to resample per-crop node counts to a common count
- Reproduce-or-beat evaluation harness against the PyTorch baseline

### Fixed
- Lazy logging format strings to use % style instead of f-strings
- Config validation for missing node-count fields

### Changed
- Default training backend pin from sleap-nn main to the v0.3.0 release
- OmegaConf schema to include explicit units on coordinate fields
```

### Poor Examples
```markdown
### Added
- New stuff  # Too vague
- Fixed things  # Wrong category and vague
- Updated code  # Not descriptive
```

## Version Numbering

Follow Semantic Versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Incompatible API changes
- **MINOR**: Add functionality (backwards compatible)
- **PATCH**: Bug fixes (backwards compatible)

## Releasing a Version

When ready to release:

1. **Move Unreleased items to new version**
```markdown
## [Unreleased]
(empty or future items)

## [0.2.0] - YYYY-MM-DD
### Added
- (move items from Unreleased here)
```

2. **Update version in pyproject.toml**
```bash
uv version 0.2.0
```

3. **Commit and tag**
```bash
git add docs/CHANGELOG.md pyproject.toml
git commit -m "Release version 0.2.0"
git tag -a v0.2.0 -m "Release version 0.2.0"
```

## Best Practices

1. **Update as you go**: Don't wait until release to update the CHANGELOG
2. **Be user-focused**: Write from the user's perspective, not implementation details
3. **Include breaking changes**: Clearly mark any breaking API changes
4. **Credit contributors**: Mention PR authors when applicable
5. **Link to issues/PRs**: Include links for more context

## Integration

- Run `/update-changelog` before creating a PR to capture changes
- Run `/pre-merge-check` to verify the PR is ready, including changelog updates
- Run `/cleanup-merged` after merge to finalize the release cycle
