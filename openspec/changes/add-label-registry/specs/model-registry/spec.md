## MODIFIED Requirements

### Requirement: Production Model Selection Matrix

The package SHALL read the production model selection matrix from a committed,
provenance-stamped YAML file (loaded via OmegaConf) that preserves the native chooser-table schema
(`species`, `mode`, `age`, `primary_model_id`, `lateral_model_id`, `crown_model_id`, with absent
root-type ids expressed as `null`), and SHALL parse each row's `age` comma-list into an integer
`age_min`/`age_max` window treated as contiguous. Each row's `species` and `mode` SHALL be
validated against the canonical `models-downloader` vocabularies the consumer selects on (currently
species ∈ {`soybean`, `canola`, `pennycress`, `arabidopsis`, `rice`}; mode ∈ {`cylinder`,
`multiplant cylinder`, `plate`}), so a value skew cannot silently produce cards the consumer will
never match.

The accepted vocabulary lives in one place and is reconciled with the consumer at acceptance. For
`mode`, that place SHALL be the `sleap-roots-contracts` `Mode` vocabulary, imported rather than
re-declared, so that model cards and label cards cannot disagree about what the same capture mode is
called. The `species` vocabulary remains defined in this package.

#### Scenario: Load and parse the selection matrix

- **WHEN** the selection matrix YAML is loaded
- **THEN** each row is parsed into a record carrying `species`, `mode`, the three model-id fields
  (`null` where absent), and the raw `age` string
- **AND** an `age` comma-list such as `"2, 3, 4, 5, 6, 7, 8"` yields `age_min = 2` and `age_max = 8`

#### Scenario: Single-age window

- **WHEN** a row's `age` list contains a single value (for example `"5"`)
- **THEN** `age_min` and `age_max` both equal that value

#### Scenario: Non-contiguous age window is rejected

- **WHEN** a row's `age` list has a gap (for example `"2, 3, 5"`)
- **THEN** parsing raises a clear error naming the offending row and the gap
- **AND** no card is produced from that row

#### Scenario: Unknown species or mode is rejected

- **WHEN** a row's `species` or `mode` is not in the canonical vocabulary
- **THEN** loading raises a clear error naming the offending row and the unknown value
- **AND** no card is produced from that row

#### Scenario: The mode vocabulary is sourced from the contract

- **WHEN** a row's `mode` is validated
- **THEN** the accepted values are those of the `sleap-roots-contracts` `Mode` vocabulary
- **AND** this package declares no independent copy of the mode value set
