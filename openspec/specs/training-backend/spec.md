# training-backend Specification

## Purpose
TBD - created by archiving change add-train-backend-extra. Update Purpose after archive.
## Requirements
### Requirement: Optional Training-Backend Dependency Extra

The package SHALL declare its `sleap-nn` training/inference backend dependencies (`sleap-nn`,
`sleap-io`, and `torch`) under an optional `[project.optional-dependencies].train` extra using
PEP 440 release specifiers only — no VCS, URL, or commit-hash direct references — with `sleap-nn`
constrained to the released v0.2.0 line and capped below the unverified v0.3.0 mask line
(`sleap-io` correspondingly capped below 0.8.0). The base (default) install SHALL NOT include these
heavy backend dependencies, so the cross-platform CI matrix stays lean and installs the backend only
on demand via `sleap-roots-training[train]`.

#### Scenario: Train extra declares the full backend with release specifiers only

- **WHEN** `pyproject.toml` is parsed and the `train` extra is read
- **THEN** the extra is present and non-empty
- **AND** it declares all of `sleap-nn`, `sleap-io`, and `torch` (name-normalized)
- **AND** every entry parses as a PEP 440 requirement with no direct URL, `git+`, or commit-hash
  reference

#### Scenario: sleap-nn is pinned to the released v0.2.0 line

- **WHEN** the `sleap-nn` requirement in the `train` extra is parsed
- **THEN** its version specifier admits `0.2.0`
- **AND** it excludes pre-0.2.0 releases such as `0.1.0`

#### Scenario: Version caps exclude the unverified v0.3.0 / sleap-io 0.8.0 mask line

- **WHEN** the `sleap-nn` and `sleap-io` requirements in the `train` extra are parsed
- **THEN** the `sleap-nn` specifier rejects `0.3.0` (and later)
- **AND** the `sleap-io` specifier admits `0.7.1` and rejects `0.8.0` (and later)

#### Scenario: Base install stays lean

- **WHEN** the base `[project].dependencies` table is parsed
- **THEN** none of `sleap-nn`, `sleap-io`, or `torch` appear in it (name-normalized)
- **AND** those same three names appear only in the `train` extra

### Requirement: Verified Keypoint Train/Predict Runbook

The repository SHALL document, in a single canonical file under `docs/`, the verified end-to-end
`sleap-nn` keypoint train and predict commands run against a sample dataset, the install command for
the `train` extra, and the recorded GPU compute-capability / `torch.cuda.get_arch_list()` findings,
so that Tier 1 begins from a known-good, reproducible backend path.

#### Scenario: Runbook documents the install, commands, and arch findings

- **WHEN** the training-backend runbook under `docs/` is read
- **THEN** it contains the `sleap-roots-training[train]` install command
- **AND** it contains a fenced `sleap-nn` train command and a fenced predict command
- **AND** it contains a section recording the GPU compute capability and
  `torch.cuda.get_arch_list()` findings with no unresolved placeholder (`TODO`/`TBD`) left in it

#### Scenario: Documented commands are verified against a real run

- **WHEN** a maintainer runs the documented train command and then the predict command against the
  sample dataset on a CUDA-capable host (RTX A5000, `sm_86`)
- **THEN** the train command exits successfully and writes a model checkpoint to the documented
  output path
- **AND** the predict command exits successfully and writes a predictions file
- **AND** the console output is captured in the PR and the exact commands plus the arch findings are
  backfilled into the runbook

### Requirement: GPU Backend Smoke Test

The test suite SHALL include a GPU smoke test, marked `@pytest.mark.integration`, that asserts a
CUDA device is available and records the `torch` build-arch list and the device compute capability.
The test SHALL skip (not fail and not error) when `torch` is not installed or no CUDA device is
present, and the default CI run (which selects `-m "not integration"` and does not install the
`train` extra) SHALL never require a GPU, `torch`, or network access to stay green.

#### Scenario: GPU present — assert availability and record arch

- **WHEN** the test runs on a host where `torch` is installed and a CUDA device is available
- **THEN** it asserts `torch.cuda.is_available()` is true
- **AND** it records the device compute capability and `torch.cuda.get_arch_list()` to the test output

#### Scenario: No torch installed — skip without error

- **WHEN** the test is collected in an environment where `torch` is not importable
- **THEN** the test skips via `importorskip`
- **AND** test collection does not raise an import error

#### Scenario: torch present but no GPU — skip

- **WHEN** `torch` is importable but no CUDA device is available
- **THEN** the test skips with a clear reason
- **AND** it does not fail

#### Scenario: Excluded from the default CI run

- **WHEN** the suite is run with the default CI selection `-m "not integration"`
- **THEN** the GPU smoke test is deselected and not executed
- **AND** no GPU, `torch`, or network access is required for that run to pass

