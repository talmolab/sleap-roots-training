## ADDED Requirements

### Requirement: Composed Training Configuration Schema

The package SHALL define a training configuration as a **composition** of `sleap-nn`'s own
`TrainingJobConfig` (`data_config` / `model_config` / `trainer_config`) plus a repo-owned
`experiment` metadata block (species / mode / root_type / dataset identity). The wrapper SHALL
validate the `experiment` fields itself — `species` against `SPECIES_VOCAB`, `mode` against
`MODE_VOCAB`, and `root_type` against the known root vocabulary (`primary` / `lateral` / `crown`) —
and SHALL delegate validation of the `sleap-nn` portion to `sleap-nn`'s `TrainingJobConfig` /
`verify_training_cfg`. The wrapper SHALL NOT re-declare `sleap-nn`'s configuration fields, and SHALL
NOT silently discard any top-level key.

#### Scenario: Valid config loads with defaults applied

- **WHEN** a user loads a config with a well-formed `experiment` block and a `sleap-nn` config that
  names at least one backbone and one head
- **THEN** the config parses with defaults applied for omitted fields
- **AND** validation reports success

#### Scenario: Invalid experiment metadata is rejected

- **WHEN** a user loads a config whose `experiment.species`, `experiment.mode`, or
  `experiment.root_type` is outside its known vocabulary
- **THEN** validation raises a clear error naming the offending field and its allowed values
- **AND** no partial or invalid config object is returned

#### Scenario: Missing experiment block is rejected

- **WHEN** a user loads a config that omits the `experiment` block, or omits a required field within
  it (such as `experiment.species`)
- **THEN** validation fails with a clear error naming the missing block or field

#### Scenario: Unknown top-level key is rejected, not silently dropped

- **WHEN** a config contains a top-level key that is neither `experiment` nor a recognized `sleap-nn`
  block (for example a typo such as `trainer_confg` or `expriment`)
- **THEN** validation fails naming the unrecognized key
- **AND** the key is not silently discarded from the config

#### Scenario: sleap-nn structural validation is delegated, not reimplemented

- **WHEN** a config sets neither a backbone nor a head under `model_config`
- **THEN** validation fails and the error surfaced is `sleap-nn`'s own must-be-set message
  (backbone and head required)
- **AND** the wrapper adds no parallel backbone/head check of its own

### Requirement: Config Validation CLI

The CLI SHALL provide a `validate` subcommand that loads a configuration file, validates it, and
reports the result with an appropriate exit code. Experiment-metadata and reproducibility checks
SHALL run without the optional `train` extra installed; deep `sleap-nn` validation SHALL run when
the extra is importable and SHALL report a clear, non-failing note when it is not.

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
base-install safe (no `train` extra required).

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

### Requirement: Per-Epoch W&B Metric Logging

Per-epoch training/validation loss and the stopping epoch MUST be logged to W&B and recoverable via
`run.scan_history()`, closing the observability gap the legacy TensorFlow reference runs exposed
(for those runs `scan_history()` returns zero rows, so there is no loss curve and no epoch count;
see `docs/tf-reference.md` and `docs/roadmap.md` Tier 1). Because per-epoch logging is
`sleap-nn` / Lightning internal behavior and NOT a `sleap-nn` configuration field, this requirement
SHALL be satisfied by **empirical verification** documented in the training guide, not by a schema
field that purports to "enable" it. The wrapper SHALL, however, validate that enabling W&B
(`trainer_config.use_wandb = true`) requires both `wandb.entity` and `wandb.project`.

#### Scenario: Per-epoch history is recoverable

- **WHEN** a short `use_wandb = true` training run completes
- **THEN** `run.scan_history()` for that run returns per-epoch rows (train/val loss and epoch)
- **AND** the training guide documents this verification and its observed result

#### Scenario: Enabling W&B requires an entity and a project

- **WHEN** a config sets `trainer_config.use_wandb = true` but omits `wandb.entity` or
  `wandb.project`
- **THEN** validation fails naming the missing field

#### Scenario: Absent or disabled W&B needs no target

- **WHEN** a config leaves `trainer_config.use_wandb` absent or set to `false`
- **THEN** validation does not require `wandb.entity` / `wandb.project`
- **AND** validation succeeds
