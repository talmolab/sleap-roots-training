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
