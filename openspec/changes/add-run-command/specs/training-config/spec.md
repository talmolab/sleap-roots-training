## MODIFIED Requirements

### Requirement: Config Validation CLI

The CLI SHALL provide a `validate` subcommand that loads a configuration file, validates it, and
reports the result with an appropriate exit code. Experiment-metadata and reproducibility checks
SHALL run without the optional `train` extra installed; deep `sleap-nn` validation SHALL run when
the extra is importable and SHALL report a clear, non-failing note when it is not. Adding
`train`-gated commands to the same CLI SHALL NOT compromise this: importing the CLI module and
running `validate` or `emit` SHALL NOT import `sleap_nn`, and neither command SHALL acquire a
dependency on the backend being installed or resolvable.

#### Scenario: Validate a valid config

- **WHEN** a user runs `sleap-roots-training validate config.yaml` on a config that conforms
- **THEN** the command prints a success message
- **AND** exits with status code 0

#### Scenario: Validate an invalid config

- **WHEN** a user runs `sleap-roots-training validate config.yaml` on a config that does not conform
- **THEN** the command prints the validation error naming the offending field
- **AND** exits with a non-zero status code

#### Scenario: Malformed input is reported cleanly, not crashed

- **WHEN** a user runs `validate` on a file that exists but is not parseable YAML (or is empty)
- **THEN** the command exits non-zero with a clear message identifying the parse failure
- **AND** it does not emit an uncaught traceback

#### Scenario: Deep backend validation is gated on the train extra

- **WHEN** `validate` runs on a host where `sleap_nn` is not importable
- **THEN** the experiment-metadata and reproducibility checks still run
- **AND** the command reports that deep `sleap-nn` validation was skipped (install `[train]`)
  without treating the skip as a failure (exit 0 when the base-safe checks pass)

#### Scenario: validate and emit stay base-install safe beside train-gated commands

- **WHEN** `validate` or `emit` runs on a host with no `train` extra and no resolvable `sleap-nn`
  console script
- **THEN** each exits with the documented status for its input, unaffected by the backend's absence
- **AND** `sleap_nn` is absent from `sys.modules` afterwards

### Requirement: Reproducible, Backend-Safe sleap-nn Config

The wrapper SHALL guarantee the configuration handed to `sleap-nn` is reproducible and does not
trigger `sleap-nn` 0.2.0's known post-fit failure. Validation SHALL reject a config whose
`trainer_config.seed` is unset — treating an absent key and an explicit `null` alike, since 0.2.0
supplies no default seed — and SHALL require the seed to be an integer. Validation SHALL also
require a **well-formed** `data_config.preprocessing` block — a mapping carrying the keys 0.2.0
reads post-fit (`ensure_rgb`, `ensure_grayscale`) — since a missing, non-mapping, or hollow block
triggers the same post-fit crash. The wrapper SHALL provide an emit step that produces the
sleap-nn-native config with the
repo-owned `experiment` block stripped — sleap-nn's struct-mode config rejects unknown top-level
keys — so that `sleap-nn train` receives a config it accepts. The emit step SHALL be
base-install safe (no `train` extra required). When the emit step writes to a file it SHALL use LF
(`\n`) line endings on every platform, so that the emitted config is byte-identical for a given
input regardless of the host that produced it.

#### Scenario: Missing or null seed is rejected

- **WHEN** a config omits `trainer_config.seed`, sets it to `null`, or sets it to a non-integer
- **THEN** validation fails with an error naming `trainer_config.seed`
- **AND** the message explains an explicit integer seed is required for a reproducible baseline

#### Scenario: Seeded config passes the reproducibility check

- **WHEN** a config sets `trainer_config.seed` to an integer
- **THEN** the reproducibility check passes

#### Scenario: Missing or malformed preprocessing is rejected

- **WHEN** a config omits `data_config.preprocessing`, sets it to a non-mapping, or supplies a
  mapping missing the keys 0.2.0 reads (`ensure_rgb` / `ensure_grayscale`)
- **THEN** validation fails naming `data_config.preprocessing`
- **AND** the message explains sleap-nn 0.2.0 crashes post-fit without a well-formed block

#### Scenario: Emit strips the experiment block

- **WHEN** the emit step runs on a valid config
- **THEN** the emitted sleap-nn config omits the `experiment` block
- **AND** retains the `data_config` / `model_config` / `trainer_config` blocks (including
  `data_config.preprocessing`)

#### Scenario: Emitted files carry LF line endings on every platform

- **WHEN** `emit -o out.yaml` runs on Windows
- **THEN** `out.yaml` contains no CR bytes
- **AND** its bytes match what the same command produces on Linux or macOS for the same input
