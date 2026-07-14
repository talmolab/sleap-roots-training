## MODIFIED Requirements

### Requirement: Environment-Driven Registry Configuration

The package SHALL resolve the wandb entity (`WANDB_ENTITY`), the **models** registry name
(`SLEAP_ROOTS_MODEL_REGISTRY` — named explicitly for the models registry because a separate
`sleap-roots-labels` registry also exists), and the production alias (`SLEAP_ROOTS_MODEL_ALIAS`) from
environment variables with defaults (entity default `eberrigan-salk-institute-for-biological-studies`,
registry default `sleap-roots-models`, alias default `production`), and SHALL require a **resolvable
wandb credential** for any operation that contacts wandb — either `WANDB_API_KEY` set in the
environment **or** a netrc entry for `api.wandb.ai` (as written by `wandb login`) — failing fast with
a clear error only when no credential is resolvable anywhere. The netrc file SHALL be located the
same way wandb locates it, so a login session is detected on every platform: the `NETRC` environment
variable if set, otherwise `~/.netrc`, otherwise `~/_netrc` (the file `wandb login` writes on
Windows). The check SHALL use the stdlib `netrc` module (no `import wandb`), and a malformed,
unreadable, or missing netrc SHALL be treated as "no credential" rather than raising.

#### Scenario: Defaults when environment unset

- **WHEN** no registry environment variables are set
- **THEN** entity resolves to the eberrigan default, `SLEAP_ROOTS_MODEL_REGISTRY` to
  `sleap-roots-models`, and `SLEAP_ROOTS_MODEL_ALIAS` to `production`

#### Scenario: Overrides from environment

- **WHEN** the registry environment variables are set to other values
- **THEN** the resolved configuration uses those values

#### Scenario: Netrc login satisfies the credential guard

- **WHEN** `WANDB_API_KEY` is unset but a netrc entry for `api.wandb.ai` is resolvable
- **THEN** the credential guard passes without raising
- **AND** the wandb-contacting operation is allowed to proceed

#### Scenario: No resolvable credential fails fast

- **WHEN** a wandb-contacting operation runs with neither `WANDB_API_KEY` set nor a netrc entry for
  `api.wandb.ai`
- **THEN** it raises a clear error naming both credential sources before any network call is made

#### Scenario: Malformed netrc is treated as no credential

- **WHEN** the credential guard reads a malformed or unreadable netrc while `WANDB_API_KEY` is unset
- **THEN** the parse/read error is swallowed and treated as "no credential"
- **AND** the guard raises the same clear error rather than propagating the netrc parse error

### Requirement: Registry Verification Command

The CLI SHALL provide a `seed-registry --verify` mode that re-runs the consumer read path against the
live registry — using the same registry project string the consumer uses
(`f"{entity}-org/wandb-registry-{registry}"`, **not** the seed run's project) — and reports, for
every expected collection (derived from the selection matrix), whether an artifact carrying the
production alias is present. It is read-only, so it requires only the selection matrix + registry
config (not `--models-root`), but it SHALL check for a resolvable wandb credential (`WANDB_API_KEY`
or a netrc entry for `api.wandb.ai`) before contacting wandb. This is real, re-runnable software (not
a one-time procedure), so post-seed verification is embodied by a command rather than an
unimplemented spec clause.

#### Scenario: Verify reads back the production alias

- **WHEN** `seed-registry --verify` is run after a seed
- **THEN** it iterates `api.artifact_collections(project_name=<registry project>, type_name="model")`
  and, for each expected collection, `api.artifacts(type_name="model",
  name=f"{<registry project>}/{collection.name}")`
- **AND** it reports every collection whose production-aliased artifact is present or missing
- **AND** it exits non-zero if any expected collection lacks the production alias

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

#### Scenario: Only-filter seeds a single canary card, validating only its scope

- **WHEN** `seed-registry --execute --yes --only <collection_id>` is run with only that card's model
  staged
- **THEN** only that card is validated and published and linked with the production alias
- **AND** a subsequent full `seed-registry --execute --yes` skips the canary and publishes the rest

#### Scenario: Unknown --only collection fails fast

- **WHEN** `--only` names a collection id not in the expanded card set
- **THEN** the command fails fast naming the unknown id, publishing nothing

#### Scenario: Default run is a dry run that resolves models without network

- **WHEN** `seed-registry --models-root <dir>` is run without `--execute`
- **THEN** the planned collections and per-card metadata are printed
- **AND** each card's model directory is resolved on the filesystem and any missing model is
  reported
- **AND** no wandb network call is made
- **AND** the command exits with status code 0

#### Scenario: Missing credential fails before the confirmation prompt

- **WHEN** `seed-registry --execute` is run with neither `WANDB_API_KEY` set nor a netrc entry for
  `api.wandb.ai`
- **THEN** the command fails fast with a clear error before prompting for confirmation
- **AND** no wandb network call is made

#### Scenario: Execution requires confirmation

- **WHEN** `seed-registry --execute` is run with a resolvable wandb credential but without `--yes`
- **THEN** the command names the target entity and registry and requires confirmation before
  publishing
- **AND** declining performs no publish

#### Scenario: Execution validates all in-scope cards before publishing any

- **WHEN** `seed-registry --execute --yes` is run and any in-scope card's model cannot be resolved
  (checksum, missing, or missing essential file)
- **THEN** the seed fails fast, naming the offending card, before any artifact is published
- **AND** no partial set of production artifacts is left in the registry

#### Scenario: Successful execution publishes and reports collections

- **WHEN** `seed-registry --execute --yes` is run with valid credentials and a complete models-root
- **THEN** each not-yet-seeded card is published and linked with the production alias
- **AND** the command reports the published and skipped collections
