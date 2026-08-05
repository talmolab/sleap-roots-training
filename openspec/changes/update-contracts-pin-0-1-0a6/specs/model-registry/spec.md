## MODIFIED Requirements

### Requirement: Production Model Selection Matrix

The package SHALL read the production model selection matrix from a committed,
provenance-stamped YAML file (loaded via OmegaConf) that preserves the native chooser-table schema
(`species`, `mode`, `age`, `primary_model_id`, `lateral_model_id`, `crown_model_id`, with absent
root-type ids expressed as `null`), and SHALL parse each row's `age` comma-list into an integer
`age_min`/`age_max` window treated as contiguous. Each row's `species` and `mode` SHALL be
validated against the canonical vocabularies the consumer selects on, so a value skew cannot
silently produce cards the consumer will never match. The `mode` vocabulary SHALL be the
contract-owned `sleap_roots_contracts.Mode`, not a value list restated here or in this package —
producer and consumer therefore agree by construction rather than by reconciliation. The `species`
vocabulary (currently {`soybean`, `canola`, `pennycress`, `arabidopsis`, `rice`}) remains owned by
this package, as the contract models no species vocabulary.

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

#### Scenario: Every committed matrix mode is contract-valid

- **WHEN** the committed selection matrix file is read
- **THEN** every row's `mode` is a member of the contract-owned `Mode` vocabulary
- **AND** a contract change that narrowed `Mode` past a committed row would fail this check at bump
  time rather than at consumer-match time

### Requirement: ModelCard Selection Metadata

Each card SHALL produce a flat metadata mapping containing exactly the selection dimensions the
consumer reads — `species` (str), `mode` (a member of the contract-owned `Mode` vocabulary, stored
raw with its space preserved and never the hyphenated collection-id slug), `age_min` (int ≥ 0),
`age_max` (int ≥ 0), `root_type` (one of `"primary"`, `"lateral"`, `"crown"`) — plus a non-contract
`source_model_id` for traceability, and SHALL NOT include the wandb-intrinsic keys `registry_id`,
`version`, or `weights_checksum`. This mapping is the **complete** stored artifact metadata
(producer lineage lives in the run config, not per-artifact — see Seed Run Lineage). The metadata
SHALL validate against the `ModelCard` schema from `sleap-roots-contracts`, which matches `mode`
exactly and normalizes neither case nor whitespace.

#### Scenario: Metadata validates against the ModelCard contract

- **WHEN** a card's metadata mapping is constructed
- **THEN** it contains exactly `species`, `mode`, `age_min`, `age_max`, `root_type`, and
  `source_model_id`
- **AND** it omits `registry_id`, `version`, and `weights_checksum`
- **AND** constructing the real `sleap_roots_contracts.ModelCard` from the metadata plus placeholder
  `registry_id`/`version`/`weights_checksum` succeeds despite the extra `source_model_id`
  (contract `extra="ignore"`)

#### Scenario: Every accepted mode survives the round trip

- **WHEN** a card is built for each mode the matrix loader accepts
- **THEN** its metadata mapping validates against the real `ModelCard` for every one of them
- **AND** the validated `ModelCard.mode` equals the raw stored value

#### Scenario: Legacy models carry no sleap_nn_version

- **WHEN** a card is produced for a legacy (non-`sleap-nn`) model
- **THEN** the metadata mapping does not include a `sleap_nn_version` key
- **AND** the resulting `ModelCard.sleap_nn_version` is `None`

### Requirement: Registry Seeding CLI with Confirmed Execution

The CLI SHALL provide a `seed-registry` subcommand that reads the selection matrix, expands cards,
resolves model directories, and — by default — runs a **dry run** that prints the planned
collections and per-card metadata and resolves every model directory on the filesystem (reporting
any missing model) **without** contacting wandb. Actually publishing SHALL require an explicit
`--execute`, which SHALL check for a resolvable wandb credential (`WANDB_API_KEY` or a netrc entry
for `api.wandb.ai`) **before** confirming the target entity/registry (interactive, bypassed with
`--yes`), and SHALL validate that every card **in the invocation's scope** resolves before publishing
any artifact, so a partial production seed is not left in a shared registry. The CLI SHALL accept a
repeatable `--only <collection_id>` filter so a single card can be seeded first as a canary (verify
the consumer can read it across the producer/consumer wandb version skew); with `--only`, both the
validation set and the publish set narrow to the named card(s) (so a canary needs only its own model
staged), and an `--only` value naming no known collection SHALL fail fast. A subsequent full
`--execute` publishes the rest and skips the already-seeded canary. The `--models-root` is required
for dry-run and `--execute`; `--verify` is a distinct read-only mode that requires only the selection
matrix + registry config (not `--models-root`) and SHALL check for a resolvable wandb credential.
A selection-matrix rejection — an unreadable file, an out-of-vocabulary `species` or `mode`, a
non-contiguous `age` window — SHALL reach the operator as a clean CLI error carrying the loader's
row-numbered message, not as an unhandled traceback.

#### Scenario: A rejected selection matrix is reported as a CLI error

- **WHEN** `seed-registry` is run against a matrix whose row is out of vocabulary (for example
  `mode: teacup`)
- **THEN** the command exits non-zero with the loader's row-numbered message rendered as a CLI error
- **AND** no traceback is printed and no wandb call is made

#### Scenario: An unreadable or unparseable selection matrix is reported as a CLI error

- **WHEN** `--selection-matrix` names a path that cannot be loaded as a matrix — a directory, a
  file that is not valid YAML, or YAML whose top level is not a mapping
- **THEN** the command exits non-zero with a message naming the path and what was wrong with it
- **AND** no traceback is printed and no wandb call is made
