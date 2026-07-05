## ADDED Requirements

### Requirement: Production Model Selection Matrix

The package SHALL read the production model selection matrix from a committed,
provenance-stamped YAML file (loaded via OmegaConf) that preserves the native chooser-table schema
(`species`, `mode`, `age`, `primary_model_id`, `lateral_model_id`, `crown_model_id`, with absent
root-type ids expressed as `null`), and SHALL parse each row's `age` comma-list into an integer
`age_min`/`age_max` window treated as contiguous. Each row's `species` and `mode` SHALL be
validated against the canonical `models-downloader` vocabularies the consumer selects on (currently
species ∈ {`soybean`, `canola`, `pennycress`, `arabidopsis`, `rice`}; mode ∈ {`cylinder`,
`multiplant cylinder`, `plate`}), so a value skew cannot silently produce cards the consumer will
never match. The accepted vocabulary lives in one place in code and is reconciled with the consumer
at acceptance.

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

### Requirement: Per-Species, Per-Root-Type Card Expansion

The package SHALL expand each selection row into one selection card per non-empty root-type model
id, where each card carries that row's own `species`, `mode`, and age window, so that a model shared
across species yields one card per species. Empty (`null`) root-type slots SHALL produce no card.

#### Scenario: Row with primary and lateral models

- **WHEN** a row lists a `primary_model_id` and a `lateral_model_id` and a `null` `crown_model_id`
- **THEN** exactly two cards are produced, with `root_type` `"primary"` and `"lateral"`
- **AND** no card is produced for the `null` crown slot

#### Scenario: Primary-plus-crown row with no lateral

- **WHEN** a row lists a `primary_model_id` and a `crown_model_id` and a `null` `lateral_model_id`
  (for example rice cylinder age 2–5)
- **THEN** exactly two cards are produced, with `root_type` `"primary"` and `"crown"`
- **AND** no card is produced for the `null` lateral slot

#### Scenario: Crown-only row produces a single crown card

- **WHEN** a row lists a `null` `primary_model_id`, a `null` `lateral_model_id`, and a non-null
  `crown_model_id` (for example rice cylinder age 6–10)
- **THEN** exactly one card is produced, with `root_type` `"crown"`
- **AND** no card is produced for the `null` primary or lateral slots

#### Scenario: Shared model expands per species

- **WHEN** the same physical model id appears as the primary model in multiple species rows (canola
  age 2–13, pennycress age 2–14, arabidopsis multiplant-cylinder age 2–14, arabidopsis cylinder age
  2–14)
- **THEN** one `primary` card is produced per such row, each carrying that row's own
  `species`/`mode`/age window (so the cards differ in `species` and also in `age_max` and `mode`
  across rows — they are NOT identical)
- **AND** every such card records the same shared `source_model_id`

### Requirement: ModelCard Selection Metadata

Each card SHALL produce a flat metadata mapping containing exactly the selection dimensions the
consumer reads — `species` (str), `mode` (str), `age_min` (int ≥ 0), `age_max` (int ≥ 0),
`root_type` (one of `"primary"`, `"lateral"`, `"crown"`) — plus a non-contract `source_model_id`
for traceability, and SHALL NOT include the wandb-intrinsic keys `registry_id`, `version`, or
`weights_checksum`. This mapping is the **complete** stored artifact metadata (producer lineage lives
in the run config, not per-artifact — see Seed Run Lineage). The metadata SHALL validate against the
`ModelCard` schema from `sleap-roots-contracts`.

#### Scenario: Metadata validates against the ModelCard contract

- **WHEN** a card's metadata mapping is constructed
- **THEN** it contains exactly `species`, `mode`, `age_min`, `age_max`, `root_type`, and
  `source_model_id`
- **AND** it omits `registry_id`, `version`, and `weights_checksum`
- **AND** constructing the real `sleap_roots_contracts.ModelCard` from the metadata plus placeholder
  `registry_id`/`version`/`weights_checksum` succeeds despite the extra `source_model_id`
  (contract `extra="ignore"`)

#### Scenario: Legacy models carry no sleap_nn_version

- **WHEN** a card is produced for a legacy (non-`sleap-nn`) model
- **THEN** the metadata mapping does not include a `sleap_nn_version` key
- **AND** the resulting `ModelCard.sleap_nn_version` is `None`

### Requirement: Legacy Model Directory Resolution

The package SHALL resolve a card's model id (a forward-slash relative path such as
`soybean/primary/221003_111420.multi_instance.n=1389`) against a caller-provided models-root to a
usable model directory. Because the canonical `models-downloader` snapshot ships each model as a
`<model_id>.zip`, and because the snapshot may sit on a read-only mount, resolution SHALL:

- For a `<models-root>/<model_id>.zip` archive (the **production form**): verify the archive against
  the SHA256 recorded in the committed selection matrix, then extract it (junk-filtered — see below)
  into a fresh temporary/cache directory using a safe extractor (never in-place, never trusting
  member paths). Snapshot zips are internally inconsistent — some hold `best_model.h5` at the archive
  root, others wrap it in an inner directory — so resolution SHALL normalize to the directory that
  actually contains `best_model.h5`, giving a canonical layout regardless of the zip's internal shape
  or the models-root.
- For an already-unzipped `<models-root>/<model_id>/` directory (a **dev/dry-run convenience**):
  return it as-is. This form is **NOT** SHA256-pinned (a directory cannot be verified against a zip's
  byte-hash), so under `--execute` it SHALL be rejected (or warn "snapshot pin NOT enforced") — real
  writes MUST use the archive form so the snapshot is pinned.

Extraction SHALL omit OS-generated junk (`.DS_Store`, `__MACOSX/`, `Thumbs.db`, `Zone.Identifier`) —
achieved by not extracting those members into the working directory, since the wandb `add_dir` API
has no exclude parameter — and resolution SHALL verify the resolved directory contains the essential
inference files `best_model.h5` and `training_config.json` before publishing.

#### Scenario: Resolve by unzipping the snapshot archive (production form)

- **WHEN** a model id is resolved against a models-root that contains `<model_id>.zip`
- **THEN** the archive is verified against its recorded SHA256, then safely extracted (junk members
  omitted) into a fresh temporary directory with a canonical layout
- **AND** the resolved directory is returned and confirmed to contain `best_model.h5` and
  `training_config.json`

#### Scenario: Already-unzipped dir is a dev convenience, not pin-enforced under execute

- **WHEN** a model id resolves to an already-unzipped directory
- **THEN** it is returned as-is for dry-run/dev use
- **AND** under `--execute` it is rejected (or warned) as not-snapshot-pinned, so production writes
  use the archive form

#### Scenario: Missing model, checksum mismatch, or essential file

- **WHEN** a model id resolves to neither a directory nor an archive, or the archive fails its
  recorded SHA256, or the resolved directory lacks `best_model.h5` or `training_config.json`
- **THEN** resolution raises a clear error naming the model id and the specific failure
- **AND** no artifact is published for that card

### Requirement: Production Model Publishing and Registry Linking

The package SHALL publish each card as a wandb artifact of `type="model"` whose metadata is the
card's selection metadata, adding the resolved (junk-free) model directory via `add_dir`, logging it
to a run, and linking it into a per-card collection under the configured registry with the configured
production alias, using the registry target path
`f"{entity}-org/wandb-registry-{registry}/{collection}"` built with literal forward slashes on all
platforms. Each card SHALL map to its own distinct collection so the production alias is unique per
collection; the full card set SHALL be checked for collection-id uniqueness and duplicate ids SHALL
fail the seed before any publish. (Note: the consumer stores `artifact.digest` as `weights_checksum`,
which downstream Bloom uses as a compute-idempotency key; because the whole directory is added, that
digest is a whole-artifact checksum, not weights-only. For the **SHA256-pinned archive form**,
byte-identical zip → identical junk-free contents → identical `add_dir` manifest → **deterministic**
published digest **under the pinned wandb writer** (`<0.29`), so a legitimate re-seed does not churn
`weights_checksum` and cause Bloom double-counting; a `--force` re-seed whose source checksum differs
is the intended signal that the weights genuinely changed. The unpinned dir form does not carry this
guarantee, which is why production writes use the archive form.)

#### Scenario: Publish a card and link it as production

- **WHEN** a card is published
- **THEN** a wandb artifact of type `"model"` is created carrying exactly the card's selection
  metadata
- **AND** the resolved (junk-free) model directory is added via `add_dir`
- **AND** the artifact is linked into its per-card collection under the registry with the production
  alias, using a target path built with forward slashes

#### Scenario: Shared weights are published as distinct per-species artifacts

- **WHEN** two cards for different species resolve to the same physical model directory
- **THEN** each is published as its own artifact carrying its own `species` metadata and the
  production alias, linked into its own distinct collection
- **AND** neither is a single artifact linked into two collections (which would collapse `species`)

#### Scenario: Two age-window crown models of the same species are both production

- **WHEN** two crown cards for the same species and mode but different age windows are published
  (rice cylinder crown age 2–5 and age 6–10)
- **THEN** each is linked into its own distinct collection (`rice-cylinder-crown-age2-5` and
  `rice-cylinder-crown-age6-10`)
- **AND** both carry the production alias simultaneously (linking the second does not move the alias
  off the first)

#### Scenario: Duplicate collection ids fail before any publish

- **WHEN** the expanded card set would produce two cards with the same collection id (a guard
  against future matrix edits)
- **THEN** the seed fails fast, naming the colliding cards, before any artifact is published

### Requirement: Seed Run Lineage

The seed SHALL record run-level lineage in the wandb run config for traceability: the
`sleap-roots-training` git SHA, a dirty-working-tree flag, the **SHA256 content hash of the actually
loaded `model_selection.yaml`** (so the exact matrix used is pinned independently of git cleanliness —
the per-model SHA256 anchor now lives in that tracked file), the selection-matrix source (URL) and
verification date, the `models-downloader` snapshot date, and the `sleap-roots-training` / `wandb` /
`sleap-roots-contracts` versions. Git-SHA resolution SHALL be robust — it SHALL prefer an explicit
env override, otherwise resolve from a `.git` anchored at the installed package (never the current
working directory), otherwise fall back to the package version, and SHALL never raise or abort the
seed; tool/contract versions come from `importlib.metadata`. A dirty working tree under `--execute`
SHALL emit a warning (the recorded matrix content hash makes the exact inputs recoverable regardless).
Lineage SHALL NOT be written into per-artifact metadata (which stays exactly the selection keys).

#### Scenario: Run records producer lineage

- **WHEN** a real seed runs
- **THEN** the run config records the git SHA (or a documented fallback sentinel), the dirty flag,
  the loaded `model_selection.yaml` content hash, the selection-matrix source + date, the
  models-downloader snapshot date, and the tool/contract versions
- **AND** no per-artifact metadata carries lineage keys

#### Scenario: Git SHA resolves without a repository

- **WHEN** the git SHA is resolved from an installed package with no `.git` and no env override
- **THEN** it returns the package-version fallback (or `"unknown"`) without raising

### Requirement: Idempotent Re-Seed

Re-running the seed SHALL be safe on a shared registry: for each card, if the target collection
already holds an artifact carrying the production alias, the seed SHALL skip that card and report it,
unless `--force` is given. With `--force`, the seed SHALL publish a new version and re-point the
production alias. Re-running after a partial failure SHALL therefore resume by skipping the
already-seeded collections.

#### Scenario: Re-seed skips already-seeded collections

- **WHEN** `seed-registry --execute` runs and a card's target collection already has a
  production-aliased artifact
- **THEN** the seed skips that card and reports it as skipped
- **AND** it does not move the production alias

#### Scenario: Force re-points the production alias

- **WHEN** `seed-registry --execute --force` runs for a card whose collection already has a
  production-aliased artifact
- **THEN** the seed publishes a new version and re-points the production alias to it
- **AND** it reports the move

### Requirement: Registry Verification Command

The CLI SHALL provide a `seed-registry --verify` mode that re-runs the consumer read path against the
live registry — using the same registry project string the consumer uses
(`f"{entity}-org/wandb-registry-{registry}"`, **not** the seed run's project) — and reports, for
every expected collection (derived from the selection matrix), whether an artifact carrying the
production alias is present. It is read-only, so it requires only the selection matrix + registry
config (not `--models-root`), but it SHALL check `WANDB_API_KEY` before contacting wandb. This is
real, re-runnable software (not a one-time procedure), so post-seed verification is embodied by a
command rather than an unimplemented spec clause.

#### Scenario: Verify reads back the production alias

- **WHEN** `seed-registry --verify` is run after a seed
- **THEN** it iterates `api.artifact_collections(project_name=<registry project>, type_name="model")`
  and, for each expected collection, `api.artifacts(type_name="model",
  name=f"{<registry project>}/{collection.name}")`
- **AND** it reports every collection whose production-aliased artifact is present or missing
- **AND** it exits non-zero if any expected collection lacks the production alias

### Requirement: Environment-Driven Registry Configuration

The package SHALL resolve the wandb entity (`WANDB_ENTITY`), the **models** registry name
(`SLEAP_ROOTS_MODEL_REGISTRY` — named explicitly for the models registry because a separate
`sleap-roots-labels` registry also exists), and the production alias (`SLEAP_ROOTS_MODEL_ALIAS`) from
environment variables with defaults (entity default `eberrigan-salk-institute-for-biological-studies`,
registry default `sleap-roots-models`, alias default `production`), and SHALL require `WANDB_API_KEY`
to be set for any operation that contacts wandb, failing fast with a clear error when it is absent.

#### Scenario: Defaults when environment unset

- **WHEN** no registry environment variables are set
- **THEN** entity resolves to the eberrigan default, `SLEAP_ROOTS_MODEL_REGISTRY` to
  `sleap-roots-models`, and `SLEAP_ROOTS_MODEL_ALIAS` to `production`

#### Scenario: Overrides from environment

- **WHEN** the registry environment variables are set to other values
- **THEN** the resolved configuration uses those values

#### Scenario: Missing API key fails fast

- **WHEN** a wandb-contacting operation runs without `WANDB_API_KEY` set
- **THEN** it raises a clear error before any network call is made

### Requirement: Registry Seeding CLI with Confirmed Execution

The CLI SHALL provide a `seed-registry` subcommand that reads the selection matrix, expands cards,
resolves model directories, and — by default — runs a **dry run** that prints the planned
collections and per-card metadata and resolves every model directory on the filesystem (reporting
any missing model) **without** contacting wandb. Actually publishing SHALL require an explicit
`--execute`, which SHALL check `WANDB_API_KEY` **before** confirming the target entity/registry
(interactive, bypassed with `--yes`), and SHALL validate that every card **in the invocation's scope**
resolves before publishing any artifact, so a partial production seed is not left in a shared
registry. The CLI SHALL accept a repeatable `--only <collection_id>` filter so a single card can be
seeded first as a canary (verify the consumer can read it across the producer/consumer wandb version
skew); with `--only`, both the validation set and the publish set narrow to the named card(s) (so a
canary needs only its own model staged), and an `--only` value naming no known collection SHALL fail
fast. A subsequent full `--execute` publishes the rest and skips the already-seeded canary. The
`--models-root` is required for dry-run and `--execute`; `--verify` is a distinct read-only mode that
requires only the selection matrix + registry config (not `--models-root`) and SHALL check
`WANDB_API_KEY`.

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

#### Scenario: Missing API key fails before the confirmation prompt

- **WHEN** `seed-registry --execute` is run without `WANDB_API_KEY` set
- **THEN** the command fails fast with a clear error before prompting for confirmation
- **AND** no wandb network call is made

#### Scenario: Execution requires confirmation

- **WHEN** `seed-registry --execute` is run with `WANDB_API_KEY` set but without `--yes`
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
