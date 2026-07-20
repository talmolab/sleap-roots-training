## ADDED Requirements

### Requirement: Typed Training Configuration Schema

The package SHALL define a typed OmegaConf configuration schema for training experiments, with
defaults and structured validation, so that experiments are reproducible configuration files
rather than notebooks.

#### Scenario: Valid config loads and validates

- **WHEN** a user loads a config file that conforms to the schema
- **THEN** the config is parsed into the typed schema with defaults applied for omitted fields
- **AND** validation reports success

#### Scenario: Invalid config is rejected

- **WHEN** a user loads a config that omits a required field or sets a wrong-typed value
- **THEN** validation raises a clear error naming the offending field
- **AND** no partial or invalid config object is returned

### Requirement: Config Validation CLI

The CLI SHALL provide a `validate` subcommand that loads a configuration file, validates it
against the schema, and reports the result with an appropriate exit code.

#### Scenario: Validate a valid config

- **WHEN** a user runs `sleap-roots-training validate config.yaml` on a config that conforms
- **THEN** the command prints a success message
- **AND** exits with status code 0

#### Scenario: Validate an invalid config

- **WHEN** a user runs `sleap-roots-training validate config.yaml` on a config that does not conform
- **THEN** the command prints the validation error
- **AND** exits with a non-zero status code

### Requirement: Per-Epoch W&B Metric Logging

The training-config schema SHALL include a Weights & Biases logging configuration whose default
enables **per-epoch** metric logging, so that Tier-1 sleap-nn runs log per-epoch train/val loss and
the stopping epoch to W&B (recoverable via `run.scan_history()`). This closes the observability gap
exposed by the legacy TensorFlow reference runs, which logged only final eval summaries — for those
runs `scan_history()` returns zero rows, so there is no loss curve and no epoch count, which made
the Tier-0 onboarding repro impossible to compare against the original (see `docs/roadmap.md` Tier 1
and `docs/tf-reference.md`). Disabling per-epoch logging SHALL be an explicit, non-default choice.

#### Scenario: Per-epoch logging is enabled by default

- **WHEN** a config is loaded that does not set the W&B logging cadence
- **THEN** the resolved config enables per-epoch metric logging by default

#### Scenario: Per-epoch logging can be explicitly disabled

- **WHEN** a config explicitly sets the W&B logging cadence to disable per-epoch logging
- **THEN** the resolved config reflects that choice
- **AND** validation still succeeds
