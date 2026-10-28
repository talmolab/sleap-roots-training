# model-registry Specification

## Purpose

Turn the committed model selection matrix into the set of model artifacts that
`sleap-roots-predict` selects from, linked under the alias a run targets (`production` by default),
with rows marked `status: candidate` never linked to `production`, and keep the two in agreement
over time.

This capability owns the producer half of the model-selection contract: expanding the matrix
into one `ModelCard` per **physical model**, stamping each with the selection metadata a
consumer matches on, publishing it to a wandb registry collection under a deterministic
collection id, and verifying after the fact that the live registry still says what the matrix
says. It deliberately does **not** own selection itself — which card wins for a given
(species, mode, age) request is the consumer's rule, and this capability's job is to make sure
exactly one card can answer.

Its guarantees are re-runnability and legibility rather than throughput: seeding is idempotent
and resumable, every published id is derivable offline from the matrix alone, and a drift
between the matrix and the registry is reportable without a publish.
## Requirements
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
vocabulary remains owned by this package, as the contract models no species vocabulary. Its members
SHALL be the lowercase common names the consumer receives: Bloom's `species.common_name` lowercased by
bloomctl, which predict and the traits chooser compare by plain string equality. Each row additionally
carries the provenance required by Selection Matrix Provenance.

#### Scenario: Load and parse the selection matrix

- **WHEN** the selection matrix YAML is loaded
- **THEN** each row is parsed into a record carrying `species`, `mode`, the three model-id fields
  (`null` where absent), the raw `age` string, and its `source`
- **AND** an `age` comma-list such as `"2, 3, 4, 5, 6, 7, 8"` yields `age_min = 2` and `age_max = 8`

#### Scenario: Single-age window

- **WHEN** a row's `age` list contains a single value (for example `"5"`)
- **THEN** `age_min` and `age_max` both equal that value

#### Scenario: Non-contiguous age window is rejected

- **WHEN** a row's `age` list has a gap (for example `"2, 3, 5"`)
- **THEN** parsing raises a clear error naming the offending row and the gap
- **AND** no card is produced from that row

#### Scenario: Unknown species or mode is rejected

- **WHEN** a row's `species` (for example `alfalfa`) or `mode` is not in the canonical vocabulary
- **THEN** loading raises a clear error naming the offending row and the unknown value
- **AND** no card is produced from that row

#### Scenario: Every committed matrix mode is contract-valid

- **WHEN** the committed selection matrix file is read
- **THEN** every row's `mode` is a member of the contract-owned `Mode` vocabulary
- **AND** a contract change that narrowed `Mode` past a committed row would fail this check at bump
  time rather than at consumer-match time

#### Scenario: Wheat and sorghum rows pass the species check

- **WHEN** a matrix with a `species: wheat` row and a `species: sorghum` row is loaded
- **THEN** both rows pass the species check

#### Scenario: Every species vocabulary member is a lowercase common name

- **WHEN** the species vocabulary is read
- **THEN** every member equals its own lowercase form

### Requirement: Per-Physical-Model, Per-Root-Type Card Expansion

The package SHALL expand the selection matrix into **one card per physical model per root type**,
not one card per matrix row. Rows naming the same `source_model_id` in the same root-type slot SHALL
collapse into a single card whose `selectors` list carries each contributing row's own `species`,
`mode`, and age window **verbatim and bundled together**, so no selection combination is advertised
that no row declared. Selectors SHALL be de-duplicated and emitted in a deterministic order derived
only from the selector values themselves — never from matrix row order, dict insertion order, or
salted `hash()` — so the emitted metadata is reproducible across processes and machines. Empty
(`null`) root-type slots SHALL produce no card. Each card's `root_type` SHALL remain scalar, and the
expansion SHALL fail loudly if any single physical model resolves to more than one `root_type`,
since the one-card-per-physical-model identity rests on that assumption.

Expansion SHALL additionally fail fast if two **different** physical models of the same `root_type`
would carry an identical `(species, mode, age_min, age_max)` selector. Under the previous per-row
naming this was caught incidentally, because the collection id was built from exactly those four
fields and the duplicate-id guard therefore rejected two models claiming one selection context. An id
derived from the physical model gives the two models distinct ids, so both would publish, both would
carry the production alias, and the consumer would find two production cards matching one query and
choose between them arbitrarily. The guard SHALL therefore be restated on the selectors themselves
rather than left to depend on the id scheme.

#### Scenario: Row with primary and lateral models

- **WHEN** a row lists a `primary_model_id` and a `lateral_model_id` and a `null` `crown_model_id`
- **THEN** that row contributes a selector to exactly two cards, with `root_type` `"primary"` and
  `"lateral"`
- **AND** no card is produced for the `null` crown slot

#### Scenario: Primary-plus-crown row with no lateral

- **WHEN** a row lists a `primary_model_id` and a `crown_model_id` and a `null` `lateral_model_id`
  (for example rice cylinder age 2–5)
- **THEN** it contributes a selector to exactly two cards, with `root_type` `"primary"` and
  `"crown"`
- **AND** no card is produced for the `null` lateral slot

#### Scenario: Crown-only row contributes a single crown selector

- **WHEN** a row lists a `null` `primary_model_id`, a `null` `lateral_model_id`, and a non-null
  `crown_model_id` (for example rice cylinder age 6–10)
- **THEN** it contributes a selector to exactly one card, with `root_type` `"crown"`
- **AND** no card is produced for the `null` primary or lateral slots

#### Scenario: A model shared across species collapses to one card

- **WHEN** the same physical model id appears as the primary model in four rows (canola cylinder age
  2–13, pennycress cylinder age 2–14, arabidopsis multiplant-cylinder age 2–14, arabidopsis cylinder
  age 2–14)
- **THEN** exactly **one** `primary` card is produced for that model
- **AND** its `selectors` equal exactly that set of four `(species, mode, age_min, age_max)` tuples,
  each preserving its own row's age window (so canola keeps `age_max = 13` while the other three
  keep `age_max = 14`, and no selector advertises a window no row declared)
- **AND** that single card records the shared `source_model_id` every contributing row named
- **AND** the matrix as a whole yields exactly one card per distinct
  `(source_model_id, root_type)` pair

#### Scenario: A model shared across modes of one species collapses to one card

- **WHEN** the same lateral model id appears under one species in two different modes (arabidopsis
  `cylinder` and arabidopsis `multiplant cylinder`, both age 2–14)
- **THEN** exactly one `lateral` card is produced, carrying both selectors
- **AND** the two selectors differ only in `mode`

#### Scenario: One lateral model serving two species keeps each species' own age window

- **WHEN** one lateral model serves canola (cylinder, age 2–13) and pennycress (cylinder, age 2–14)
- **THEN** one `lateral` card is produced carrying both selectors
- **AND** the two selectors differ in **both** `species` and `age_max`, and neither window is
  widened to cover the other

#### Scenario: A physical model spanning two root types is rejected

- **WHEN** a matrix edit causes one `source_model_id` to appear in two different root-type slots
- **THEN** expansion fails fast, naming the offending model id
- **AND** no cards are produced

#### Scenario: Two different models claiming one selection context are rejected

- **WHEN** a matrix edit gives two different `source_model_id`s of the same `root_type` an identical
  `(species, mode, age_min, age_max)` selector
- **THEN** expansion fails fast, naming the colliding selector and both model ids
- **AND** no cards are produced, so two production-aliased cards cannot both match one query

#### Scenario: Identical rows do not produce a duplicate selector

- **WHEN** two matrix rows would contribute the same (species, mode, age_min, age_max) selector to
  one card
- **THEN** that selector appears exactly once on the card

#### Scenario: Selector order is deterministic across processes

- **WHEN** the same matrix is expanded in two separate processes started with different
  `PYTHONHASHSEED` values
- **THEN** each card's `selectors` are emitted in the same order both times
- **AND** the emitted metadata mapping is byte-identical, so any metadata difference a re-seed
  reports is a real change rather than an ordering artifact

#### Scenario: Selector order does not depend on matrix row order

- **WHEN** the same set of matrix rows is expanded in a different row order
- **THEN** each card's `selectors` are emitted in the same order as before

### Requirement: ModelCard Selection Metadata

Each card SHALL produce a metadata mapping containing **exactly** the selection dimensions the
consumer reads — a scalar `root_type` (a member of the contract-owned `RootType` vocabulary) and a non-empty
`selectors` list, where each selector carries `species` (str), `mode` (a member of the contract-owned
`Mode` vocabulary, stored raw with its space preserved and never the hyphenated collection-id slug),
`age_min` (int ≥ 0), and `age_max` (int ≥ 0), and **exactly** those four keys and nothing else —
plus a non-contract `source_model_id` for traceability. It SHALL NOT include the wandb-intrinsic keys `registry_id`, `version`, or
`weights_checksum`, and SHALL NOT carry card-level `species`, `mode`, `age_min`, or `age_max` fields,
since a card may serve several selection contexts. This mapping is the **complete** stored artifact
metadata (producer lineage lives in the run config, not per-artifact — see Seed Run Lineage). The
mapping SHALL validate against the `ModelCard` schema from `sleap-roots-contracts`, which matches
`mode` exactly and normalizes neither case nor whitespace.

`sleap_nn_version` remains a **scalar card-level** key and SHALL NOT be moved into `Selector`,
because it describes the physical weights rather than a selection context. Every model in the
committed matrix is legacy, so no card emits it today and `ModelCard.sleap_nn_version` stays `None`;
the key is specified here so that a future `sleap-nn`-trained model has one defined home.

Selector values SHALL be emitted as **JSON-native** types — a list of plain mappings of primitives —
not as `Selector` model instances, `NamedTuple`s, or other objects. This is a correctness
requirement, not a style preference: `wandb.Artifact(metadata=...)` passes the mapping through
`wandb.sdk.artifacts._validators.validate_metadata`, which **coerces rather than rejects** anything
non-JSON-native, degrading a pydantic model to its `repr` string and a `NamedTuple` to a positional
list. Either degradation publishes unreadable selection metadata with a successful exit code.

The "no card-level `species`/`mode`/`age_min`/`age_max`" clause deliberately rules out emitting both
shapes at once. New-shape metadata is therefore **not** readable by a consumer still pinned to the
pre-`selectors` contract, whose `ModelCard` is `extra="ignore"` with those four fields required — it
would drop `selectors` and then fail on the missing required fields. Neither direction of mismatch is
repaired in the schema, because the consumer already degrades safely in both: it skips a card it
cannot validate, per artifact, with a warning. What the producer SHALL guarantee instead is
operational: the collections an old-pinned consumer reads SHALL NOT be overwritten or have their
production alias dropped until that consumer's upgrade is confirmed deployed.

#### Scenario: Metadata validates against the ModelCard contract

- **WHEN** a card's metadata mapping is constructed
- **THEN** it contains **exactly** `root_type`, `selectors`, and `source_model_id` — and nothing else
  beyond a scalar `sleap_nn_version` for a `sleap-nn`-produced model
- **AND** it omits `registry_id`, `version`, and `weights_checksum`
- **AND** it carries no card-level `species`, `mode`, `age_min`, or `age_max`
- **AND** constructing the real `sleap_roots_contracts.ModelCard` from the metadata plus placeholder
  `registry_id`/`version`/`weights_checksum` succeeds despite the extra `source_model_id`
  (contract `extra="ignore"`)

#### Scenario: Every accepted mode survives the round trip

- **WHEN** a card is built for each mode the matrix loader accepts
- **THEN** its metadata mapping validates against the real `ModelCard` for every one of them
- **AND** each validated selector's `mode` equals the raw stored value

#### Scenario: Legacy models carry no sleap_nn_version

- **WHEN** a card is produced for a legacy (non-`sleap-nn`) model
- **THEN** the metadata mapping does not include a `sleap_nn_version` key
- **AND** the resulting `ModelCard.sleap_nn_version` is `None`

#### Scenario: A card with no selectors is rejected

- **WHEN** a metadata mapping carries an empty `selectors` list
- **THEN** validation against the `ModelCard` contract fails

#### Scenario: Each selector carries exactly the four contract keys

- **WHEN** a card's metadata mapping is constructed
- **THEN** every selector in `selectors` has the exact key set `{species, mode, age_min, age_max}`
- **AND** no selector carries a `sleap_nn_version`, a `root_type`, a `source_model_id`, or any other
  extra key, because the contract's `Selector` is `extra="ignore"` and would silently drop one rather
  than reject it — so a stray key is a producer bug the producer has to catch

#### Scenario: Metadata survives wandb's own coercion unchanged

- **WHEN** a card's metadata mapping is passed through the coercion `wandb.Artifact(metadata=...)`
  applies (`validate_metadata`)
- **THEN** the returned mapping is unchanged, and each selector is still a mapping carrying
  `species`, `mode`, `age_min`, and `age_max`
- **AND** the coerced mapping still validates against the real `ModelCard`, so a selector emitted as
  a model instance (silently degraded to a `repr` string) or as a `NamedTuple` (degraded to a
  positional list) fails this check rather than reaching the registry

### Requirement: Legacy Model Directory Resolution

The package SHALL resolve a card's model id (a forward-slash relative path such as
`soybean/primary/221003_111420.multi_instance.n=1389`) against a caller-provided models-root to a
usable model directory. Because each model is staged as a `<model_id>.zip` archive pinned by the SHA256
recorded in the committed selection matrix — whether it ships in a models-downloader snapshot or, like
the wheat crown model, in an experiment run directory (see Selection Matrix Provenance) — and because
the models-root may sit on a read-only mount, resolution SHALL:

- For a `<models-root>/<model_id>.zip` archive (the **production form**): verify the archive against
  the SHA256 recorded in the committed selection matrix, then extract it (junk-filtered — see below)
  into a fresh temporary/cache directory using a safe extractor (never in-place, never trusting
  member paths). Model zips are internally inconsistent — some hold `best_model.h5` at the archive
  root, others wrap it in an inner directory — so resolution SHALL normalize to the directory that
  actually contains `best_model.h5`, giving a canonical layout regardless of the zip's internal shape
  or the models-root.
- For an already-unzipped `<models-root>/<model_id>/` directory (a **dev/dry-run convenience**):
  return it as-is. This form is **NOT** SHA256-pinned (a directory cannot be verified against a zip's
  byte-hash), so under `--execute` it SHALL be rejected (or warn "checksum pin NOT enforced") — real
  writes MUST use the archive form so the model is checksum-pinned.

Extraction SHALL omit OS-generated junk (`.DS_Store`, `__MACOSX/`, `Thumbs.db`, `Zone.Identifier`) —
achieved by not extracting those members into the working directory, since the wandb `add_dir` API
has no exclude parameter — and resolution SHALL verify the resolved directory contains the essential
inference files `best_model.h5` and `training_config.json` before publishing.

#### Scenario: Resolve by unzipping the pinned archive (production form)

- **WHEN** a model id is resolved against a models-root that contains `<model_id>.zip`
- **THEN** the archive is verified against its recorded SHA256, then safely extracted (junk members
  omitted) into a fresh temporary directory with a canonical layout
- **AND** the resolved directory is returned and confirmed to contain `best_model.h5` and
  `training_config.json`

#### Scenario: Already-unzipped dir is a dev convenience, not pin-enforced under execute

- **WHEN** a model id resolves to an already-unzipped directory
- **THEN** it is returned as-is for dry-run/dev use
- **AND** under `--execute` it is rejected (or warned) as not checksum-pinned, so production writes
  use the archive form

#### Scenario: Missing model, checksum mismatch, or essential file

- **WHEN** a model id resolves to neither a directory nor an archive, or the archive fails its
  recorded SHA256, or the resolved directory lacks `best_model.h5` or `training_config.json`
- **THEN** resolution raises a clear error naming the model id and the specific failure
- **AND** no artifact is published for that card

### Requirement: Per-Physical-Model Publishing and Registry Linking

The package SHALL publish **one wandb artifact of `type="model"` per physical model**, whose metadata
is that card's selection metadata, adding the resolved (junk-free) model directory via `add_dir`,
logging it to a run, and linking it into that card's collection under the configured registry with
the configured production alias, using the registry target path
`f"{entity}-org/wandb-registry-{registry}/{collection}"` built with literal forward slashes on all
platforms. The same weights SHALL NOT be uploaded more than once. Each card SHALL map to its own
distinct collection so the production alias is unique per collection; the full card set SHALL be
checked for collection-id uniqueness and duplicate ids SHALL fail the seed before any publish. (Note:
the consumer stores `artifact.digest` as `weights_checksum`, which downstream Bloom uses as a
compute-idempotency key; because the whole directory is added, that digest is a whole-artifact
checksum, not weights-only. For the **SHA256-pinned archive form**, byte-identical zip → identical
junk-free contents → identical `add_dir` manifest → **deterministic** published digest **under the
pinned wandb writer** (`<0.29`), so a legitimate re-seed does not churn `weights_checksum` and cause
Bloom double-counting; a `--force` re-seed whose source checksum differs is the intended signal that
the weights genuinely changed. The unpinned dir form does not carry this guarantee, which is why
production writes use the archive form. Artifact **metadata is not an input to that manifest digest
at all**, so moving the selection dimensions into `selectors` neither stabilizes nor churns
`weights_checksum` — it is the pinned archive form, not the metadata layout, that keeps the digest
deterministic.)

#### Scenario: Publish a card and link it as production

- **WHEN** a card is published
- **THEN** a wandb artifact of type `"model"` is created carrying exactly the card's selection
  metadata, including its full `selectors` list
- **AND** the resolved (junk-free) model directory is added via `add_dir`
- **AND** the artifact is linked into its collection under the registry with the production alias,
  using a target path built with forward slashes

#### Scenario: Shared weights are published exactly once

- **WHEN** several matrix rows resolve to the same physical model directory for one root type
- **THEN** exactly one artifact is published for those weights, carrying every one of those rows'
  selectors
- **AND** the same directory is not uploaded a second time under a different collection

#### Scenario: Two age-window crown models of the same species are both production

- **WHEN** two crown models of the same species and mode cover different age windows (rice cylinder
  crown age 2–5, `rice/younger/crown/220821_163331.multi_instance.n=867`, and age 6–10,
  `rice/older/crown/221208_113552.multi_instance.n=574`)
- **THEN** they remain **two distinct cards**, because they are two distinct physical models
- **AND** each is linked into its own distinct collection, whose ids are the two distinct ids the
  Collection Identifier Scheme yields for those two model ids
- **AND** both carry the production alias simultaneously (linking the second does not move the alias
  off the first)

#### Scenario: Duplicate collection ids fail before any publish

- **WHEN** the expanded card set would produce two cards with the same collection id (a guard
  against future matrix edits, and against a lossy slug mapping two distinct model ids onto one id)
- **THEN** the seed fails fast, naming the colliding cards, before any artifact is published

### Requirement: Seed Run Lineage

The seed SHALL record run-level lineage in the wandb run config for traceability: the
`sleap-roots-training` git SHA, a dirty-working-tree flag, the **SHA256 content hash of the actually
loaded `model_selection.yaml`** (so the exact matrix used is pinned independently of git cleanliness —
the per-model SHA256 anchor now lives in that tracked file), the provenance of the run's in-scope cards
(published or skipped), the registry target the run links under (`registry_target`: entity, registry
and alias — so a candidate publish and its later promotion are distinguishable after the fact), and
the `sleap-roots-training` / `wandb` / `sleap-roots-contracts` versions.
Provenance SHALL be read from the loaded matrix, never from constants in code, and SHALL be scoped to
the run's in-scope cards (narrowed by `--only`), as two lists of records:

- `row_sources`: one `{species, mode, age, source}` record (`age` being the row's raw string) per matrix
  row that backs at least one in-scope card, in matrix file order — a row backs a card when it
  contributes one of that card's selectors;
- `model_origins`: one `{model_id, snapshot, location, pinned_by}` record per in-scope card's model,
  sorted by `model_id`.

The lineage SHALL NOT carry a single selection-matrix source, verification date or models-downloader
snapshot for the whole run, since rows and models come from more than one source. Git-SHA resolution
SHALL be robust — it SHALL prefer an explicit env override, otherwise resolve from a `.git` anchored at
the installed package (never the current working directory), otherwise fall back to the package
version, and SHALL never raise or abort the seed; tool/contract versions come from
`importlib.metadata`. A dirty working tree under `--execute` SHALL emit a warning (the recorded matrix
content hash makes the exact inputs recoverable regardless). Lineage SHALL NOT be written into
per-artifact metadata (which stays exactly the selection keys).

So that W&B alone can answer which run made a card live, the seed SHALL also record:

- in the run config, an `invocation` record of `--only`, `--force`, `--promote`, the alias source,
  `first_production_links` (the collections being linked to `production` for the first time,
  or `None` under a non-default alias), and `skipped_by_status` (the candidate-status collections
  an unscoped default-alias run left out of its scope, otherwise empty);
- in the run summary, before the run is closed, the per-collection outcome (`published`,
  `skipped`, `failed`, `stale`).

Failing to record the outcome SHALL only warn. It SHALL NOT change the seed's reported result.

#### Scenario: Run records producer lineage

- **WHEN** a real seed runs
- **THEN** the run config records the git SHA (or a documented fallback sentinel), the dirty flag,
  the loaded `model_selection.yaml` content hash, `row_sources`, `model_origins`,
  `registry_target` (entity, registry, alias), and the tool/contract versions
- **AND** it records no `selection_matrix_source`, `selection_matrix_date` or `models_snapshot` key
- **AND** no per-artifact metadata carries lineage keys

#### Scenario: Lineage provenance is scoped to the in-scope cards

- **WHEN** lineage is built for the three wheat and sorghum cards alone (as under `--only`)
- **THEN** `model_origins` holds exactly those three models' origins, the wheat one with
  `snapshot` `None`, and `row_sources` holds exactly the wheat and sorghum rows with their `source`
- **AND WHEN** it is built for the
  `canola_pennycress_arabidopsis/primary/240611_102513.multi_instance.n=743` card alone
- **THEN** `row_sources` holds the four rows that name it and `model_origins` holds one record
- **AND WHEN** it is built for every committed card
- **THEN** it holds every matrix row and every origin
- **AND** the lineage mapping round-trips through JSON unchanged

#### Scenario: The run records how it was invoked and what it did

- **WHEN** a seed runs under `candidate` with `--only` for the three wheat and sorghum cards
- **THEN** the run config's `invocation` records those ids, `force` and `promote` false, the alias
  source, `first_production_links` `None` and an empty `skipped_by_status`
- **AND** the run summary records the three as `published` before the run is closed
- **AND WHEN** a seed runs with `--promote` under the default alias
- **THEN** `first_production_links` lists exactly the collections linked to `production` for the
  first time

#### Scenario: Git SHA resolves without a repository

- **WHEN** the git SHA is resolved from an installed package with no `.git` and no env override
- **THEN** it returns the package-version fallback (or `"unknown"`) without raising

### Requirement: Idempotent Re-Seed

Re-running the seed SHALL be safe on a shared registry: for each card, if the target collection
already holds an artifact carrying the production alias, the seed SHALL skip that card and report it,
unless `--force` is given. With `--force`, the seed SHALL re-log the artifact and re-point the
production alias. Re-running after a partial failure SHALL therefore resume by skipping the
already-seeded collections.

Because `log_artifact` is a no-op when the content digest matches the collection's latest version
(wandb documents this on `Artifact.digest`), `--force` SHALL NOT be specified or documented as
guaranteeing a **new version** for unchanged weights: what it guarantees is the alias re-point and an
*attempted* metadata refresh, whose success is established by read-back and never inferred from
`--force` having been passed (see Re-Publish Metadata Refresh). A skipped card SHALL still have its stored
metadata shape checked, because the skip path is the default path on every re-run and is therefore
exactly where a half-migrated collection would otherwise sit undetected.

#### Scenario: Re-seed skips already-seeded collections

- **WHEN** `seed-registry --execute` runs and a card's target collection already has a
  production-aliased artifact
- **THEN** the seed skips that card and reports it as skipped
- **AND** it does not move the production alias

#### Scenario: Force re-points the production alias

- **WHEN** `seed-registry --execute --force` runs for a card whose collection already has a
  production-aliased artifact
- **THEN** the seed re-logs the artifact and re-points the production alias
- **AND** it reports the move
- **AND** when the content digest is unchanged, no new version is created — so the alias re-point and
  an attempted metadata refresh, not a new version, are what `--force` delivers
- **AND** whether that refresh actually landed is decided by the read-back, not by `--force` having
  been passed

#### Scenario: A skipped collection carrying legacy metadata is still reported

- **WHEN** a card is skipped because its collection already carries the production alias, and that
  artifact's stored metadata is the legacy flat shape rather than `selectors`
- **THEN** the seed reports that collection as carrying stale metadata, distinctly from an ordinary
  skip
- **AND** the report is actionable without re-running with `--force`

### Requirement: Registry Verification Command

The CLI SHALL provide a `seed-registry --verify` mode that re-runs the consumer read path against the
live registry. It SHALL use the same registry project string the consumer uses
(`f"{entity}-org/wandb-registry-{registry}"`), **not** the seed run's project. For every expected
collection, which is derived from the selection matrix, it SHALL report whether an artifact carrying
the configured alias is present.

`--verify` is read-only. It requires only the selection matrix and the registry config, not
`--models-root`. It SHALL still check for a resolvable wandb credential (`WANDB_API_KEY`, or a netrc
entry for `api.wandb.ai`) before contacting wandb. This is real, re-runnable software, not a one-time
procedure, so post-seed verification is embodied by a command rather than an unimplemented spec
clause.

Without `--only`, the expected set SHALL be the cards whose row status (see Per-Row Publication Status)
equals the configured alias. A default `--verify` therefore checks the `production`-status cards, and
`SLEAP_ROOTS_MODEL_ALIAS=candidate --verify` checks the `candidate`-status cards.

When that expected set is empty, verification SHALL say that no row has the configured alias as its
status, and SHALL exit non-zero without contacting wandb. A mistyped alias variable therefore cannot
produce a passing verification.

Under `--only`, the expected set SHALL narrow to the named collection(s), exactly as the validation and
publish sets do, so a canary can be verified in isolation. There is one exception: under the default
alias, a named `candidate`-status collection SHALL be checked only as described in the next paragraph,
never as expected. This narrowing is what makes orphan reporting meaningless under `--only` (see
Orphaned Collection Reporting).

Under the default alias, verification SHALL also check every in-scope `candidate`-status collection.
It SHALL report as an **unexpected production link** each one that carries the default alias. This
check SHALL behave as follows:

- A collection absent from the registry's collection listing is not linked, and its versions SHALL NOT
  be read. The wandb client raises when asked for the versions of a collection that does not exist.
- A read error while checking a collection SHALL be reported for that collection, with the error's
  type and message, and SHALL make the command exit non-zero, so that the check fails closed.
- An unexpected production link SHALL make the command exit non-zero, because it means a model the
  matrix keeps out of production is live for the consumer.
- Each collection found not linked, including one absent from the registry, SHALL be reported as
  such. A passing check is then a positive statement, not silence.

The pass/fail decision SHALL require every report key it reads. A report missing one of them SHALL
raise rather than count as passing, so a change that stops producing a failure category cannot
silently turn verification green.

Verification SHALL additionally report, for each expected collection whose aliased artifact is present,
whether that artifact's metadata is the current `selectors`-bearing shape or the legacy flat shape. It
SHALL exit non-zero when an expected collection is present but carries the legacy shape. Alias presence
alone is **not** sufficient evidence of a completed migration: without the shape check, `--verify`
reports `present` for a collection an upgraded consumer cannot read, and there is then no re-runnable
way to ask whether the registry has actually been migrated.

The shape check SHALL be **structural**: `selectors` present, and no card-level `species`, `mode`,
`age_min` or `age_max`. It SHALL NOT be implemented as "does this validate against `ModelCard`",
because a tolerant-read contract accepts the legacy flat shape by design and would report every stale
collection as current.

#### Scenario: Verify reads back the production alias

- **WHEN** `seed-registry --verify` is run after a seed
- **THEN** it iterates `api.artifact_collections(project_name=<registry project>, type_name="model")`
  and, for each expected collection, `api.artifacts(type_name="model",
  name=f"{<registry project>}/{collection.name}")`
- **AND** it reports every collection whose production-aliased artifact is present or missing
- **AND** it exits non-zero if any expected collection lacks the production alias

#### Scenario: Verify reports a present-but-legacy-shape collection as a failure

- **WHEN** an expected collection's production-aliased artifact is present but its metadata carries
  card-level `species`/`mode`/`age_min`/`age_max` and no `selectors`
- **THEN** `--verify` names that collection as carrying the legacy shape
- **AND** the command exits non-zero
- **AND** the determination is made structurally, so a tolerant-read contract that accepts the legacy
  shape does not mask it

#### Scenario: Default verify does not expect candidate rows

- **WHEN** every `production`-status collection carries `production`, and the `candidate`-status
  collections either carry only `candidate` or are absent from the registry, and a default-alias
  `--verify` is run without `--only`
- **THEN** it reports the `production`-status collections as present, and exits zero
- **AND** it reports each `candidate`-status collection as not linked, never as missing, orphaned or
  linked
- **AND** it reads no versions of an absent collection

#### Scenario: Candidate-alias verify checks the candidate rows

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS=candidate seed-registry --verify` is run without `--only`
- **THEN** it reports each `candidate`-status collection as present or missing, and checks no
  `production`-status collection as expected
- **AND** it exits zero only when every `candidate`-status collection is present with the current shape

#### Scenario: An alias no row carries fails verification

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS=candidtae seed-registry --verify` is run without `--only`
- **THEN** it reports that no row has status `candidtae`, makes no wandb call, and exits non-zero

#### Scenario: A candidate row linked to production fails verification

- **WHEN** a `candidate`-status collection carries `production`, and a default-alias `--verify` is run,
  with or without that collection named by `--only`
- **THEN** it reports that collection as an unexpected production link, and not as present or orphaned
- **AND** the command exits non-zero

#### Scenario: A read error on the candidate check fails closed

- **WHEN** reading a `candidate`-status collection's versions raises during a default-alias `--verify`
- **THEN** it reports that collection as unreadable, with the error's type and message, and the
  command exits non-zero

#### Scenario: A report missing a failure key does not pass

- **WHEN** the pass/fail decision is given a report without `unexpected_production` or
  `barred_unreadable`
- **THEN** it raises instead of returning a pass

#### Scenario: Verify --only splits production and candidate collections

- **WHEN** a default-alias `--verify --only <production id> --only <candidate id>` runs
- **THEN** the production collection is checked as expected and the candidate collection only as
  barred

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
unreadable, or missing netrc SHALL be treated as "no credential" rather than raising. A netrc entry
for `api.wandb.ai` whose password field is blank or absent SHALL NOT count as a resolvable
credential (mirroring wandb's own resolver), so a stale or partially-written login cannot pass the
guard and then fail deep inside `wandb.init()`.

Throughout this capability, "the production alias" means the alias resolved from
`SLEAP_ROOTS_MODEL_ALIAS` (default `production`): the skip check, the link, `--verify` and orphan
reporting all operate on that resolved alias. The resolved alias SHALL be stripped of surrounding
whitespace. An unset variable SHALL resolve to `production`; a variable that is set but blank after
stripping SHALL resolve to the empty string and SHALL NOT fall back to `production`, so a caller that
writes under the alias (`seed-registry`) can refuse it. Resolving the configuration SHALL NOT itself
raise on a blank alias, so callers that need only the entity (for example the labels-inventory
registry check) are unaffected.

#### Scenario: Defaults when environment unset

- **WHEN** no registry environment variables are set
- **THEN** entity resolves to the eberrigan default, `SLEAP_ROOTS_MODEL_REGISTRY` to
  `sleap-roots-models`, and `SLEAP_ROOTS_MODEL_ALIAS` to `production`

#### Scenario: Overrides from environment

- **WHEN** the registry environment variables are set to other values
- **THEN** the resolved configuration uses those values, with the alias stripped of surrounding
  whitespace

#### Scenario: A blank alias resolves to empty, never to the default

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS` is set to `""` or only whitespace
- **THEN** the resolved alias is the empty string, not `production`
- **AND** resolving the configuration does not raise, so an entity-only caller proceeds

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

#### Scenario: Netrc entry with a blank password is not a credential

- **WHEN** `WANDB_API_KEY` is unset and the netrc has an `api.wandb.ai` entry whose password field is
  blank or absent (a stale/interrupted `wandb login`)
- **THEN** the guard treats it as "no credential" and fails fast before the confirmation prompt
- **AND** the guard does not defer the failure to a later `wandb.init()` call

### Requirement: Registry Seeding CLI with Confirmed Execution

The CLI SHALL provide a `seed-registry` subcommand that reads the selection matrix, expands cards, and
resolves model directories. By default it SHALL run a **dry run**: it prints the planned collections
and per-card metadata, and resolves every model directory on the filesystem, reporting any missing
model, **without** contacting wandb.

Actually publishing SHALL require an explicit `--execute`, which SHALL:

- check for a resolvable wandb credential (`WANDB_API_KEY`, or a netrc entry for `api.wandb.ai`)
  **before** confirming the target entity and registry;
- confirm that target interactively, a step `--yes` bypasses;
- validate that every card **in the invocation's scope** resolves before publishing any artifact, so a
  partial production seed is not left in a shared registry.

Under the default alias, candidate-status cards are not in an `--execute` run's scope (see Candidate
Rows Are Never Linked to Production).

The CLI SHALL accept a repeatable `--only <collection_id>` filter, so that a single card can be seeded
first as a canary, which verifies that the consumer can read it across the producer/consumer wandb
version skew. With `--only`, the validation set, the publish set **and the `--verify` expected set**
all narrow to the named card(s). A canary therefore needs only its own model staged, and can be
verified without the rest of the registry counting as missing. An `--only` value naming no known
collection SHALL fail fast.

A subsequent `--execute` whose scope includes the canary publishes the rest and skips the canary.
Under the default alias, any first-time card in that scope requires `--promote`, which requires
`--only`, so that run lists its collections (see First-Time Production Link Requires Promotion).

`--models-root` is required for a dry run and for `--execute`. `--verify` is a distinct read-only
mode: it requires only the selection matrix and the registry config, not `--models-root`, and SHALL
check for a resolvable wandb credential.

A selection-matrix rejection SHALL reach the operator as a clean CLI error carrying the loader's row-
or model-naming message, not as an unhandled traceback. That covers an unreadable file, an
out-of-vocabulary `species` or `mode`, an invalid `status`, a non-contiguous `age` window, and missing
or mistyped provenance.

Every invocation SHALL print a target line as its first output, once the alias resolves and before any
wandb contact, prompt or publish. The line SHALL name:

- the entity;
- the registry;
- the alias, ASCII-escaped so hidden characters show and any console can print it;
- whether the alias came from `SLEAP_ROOTS_MODEL_ALIAS` or the default;
- the seed project.

A `SLEAP_ROOTS_MODEL_ALIAS` that is set but blank (see Environment-Driven Registry Configuration) SHALL
be a CLI error for `seed-registry` in every mode, before any wandb call. It SHALL NOT fall back to
`production`.

`--execute` under a **non-default alias** SHALL require `--only`. Without it, the command SHALL fail as
a usage error **before** the credential check, the confirmation prompt or any wandb call, including
under `--force`. The reason: without `--only`, the idempotency check finds no card seeded under the
new alias, and re-publishes every card in the matrix under it. A dry run and `--verify` under a
non-default alias SHALL remain allowed, since neither writes. `--verify` checks the cards whose row
status equals that alias (see Registry Verification Command).

The collection-id scheme changed in update-model-card-selectors. An `--only` value written against the
previous scheme SHALL therefore fail fast under the existing unknown-id check, rather than silently
matching nothing. A stale id in an operator runbook is then reported, not acted on as an empty scope.

#### Scenario: Only-filter seeds a single canary card, validating only its scope

- **WHEN** `seed-registry --execute --yes --only <collection_id> --promote` is run under the default
  alias, for a `production`-status collection, with only that card's model staged
- **THEN** only that card is validated, published and linked with the production alias
- **AND** a subsequent `seed-registry --execute --yes --only <canary> --only <each remaining
  production-status id> --promote` reports the canary as skipped and publishes the rest

#### Scenario: Unknown --only collection fails fast

- **WHEN** `--only` names a collection id not in the expanded card set, including an id valid under
  the previous naming scheme
- **THEN** the command fails fast naming the unknown id, publishing nothing

#### Scenario: Default run is a dry run that resolves models without network

- **WHEN** `seed-registry --models-root <dir>` is run without `--execute`
- **THEN** the target line and the planned collections and per-card metadata are printed
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
- **THEN** the command names the target entity, registry and alias and requires confirmation before
  publishing
- **AND** declining performs no publish

#### Scenario: Execution validates all in-scope cards before publishing any

- **WHEN** `seed-registry --execute --yes` is run and any in-scope card's model cannot be resolved,
  because of its checksum, a missing archive or a missing essential file
- **THEN** the seed fails fast, naming the offending card, before any artifact is published
- **AND** no partial set of production artifacts is left in the registry

#### Scenario: Successful execution publishes and reports collections

- **WHEN** `seed-registry --execute --yes` is run with valid credentials and a complete models-root,
  and the promotion check passes
- **THEN** each in-scope, not-yet-seeded card is published and linked with the configured alias
- **AND** the command reports the published and skipped collections, including, under the default
  alias, the candidate-status cards it skipped

#### Scenario: A rejected selection matrix is reported as a CLI error

- **WHEN** `seed-registry` is run against a matrix that has an out-of-vocabulary row (for example
  `mode: teacup` or `status: staging`), or that lacks a row's `source` or a referenced model's
  `origins` entry
- **THEN** the command exits non-zero with the loader's row- or model-naming message rendered as a CLI
  error
- **AND** no traceback is printed and no wandb call is made

#### Scenario: An unreadable or unparseable selection matrix is reported as a CLI error

- **WHEN** `--selection-matrix` names a path that cannot be loaded as a matrix: a directory, a file
  that is not valid YAML, or YAML whose top level is not a mapping
- **THEN** the command exits non-zero with a message naming the path and what was wrong with it
- **AND** no traceback is printed and no wandb call is made

#### Scenario: Non-default alias without --only is refused before any write

- **WHEN** `seed-registry --models-root <dir> --execute` is run with `SLEAP_ROOTS_MODEL_ALIAS=candidate`
  and no `--only`, with or without `--yes` or `--force`
- **THEN** the command exits with click's usage-error status (2) naming `candidate` and `--only`
- **AND** no credential check, confirmation prompt, `wandb.init` or `wandb.Api` call happens

#### Scenario: Non-default alias with --only publishes only the named cards under that alias

- **WHEN** `seed-registry --models-root <dir> --execute --yes --only <id> ...` is run with
  `SLEAP_ROOTS_MODEL_ALIAS=candidate`
- **THEN** only the named cards are validated and published
- **AND** each is linked with exactly the `candidate` alias, and no card is linked with `production`

#### Scenario: Non-default alias still allows a dry run and verify

- **WHEN** `seed-registry` is run with `SLEAP_ROOTS_MODEL_ALIAS=candidate` and no `--only`, either as a
  dry run (no `--execute`) or with `--verify`
- **THEN** the alias guard does not fire
- **AND** the dry run behaves as it does under the default alias, and `--verify` checks the
  `candidate`-status cards

#### Scenario: A blank alias is refused and a padded one is the default

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS` is set to `""` or only whitespace and `seed-registry` runs in any
  mode
- **THEN** it exits non-zero with a CLI error naming the variable, before any wandb call
- **AND WHEN** it is `" production "` and `--execute` runs without `--only`
- **THEN** the non-default-alias guard does not fire, and the candidate-row scoping and the promotion
  check apply

#### Scenario: Default verify reports not-yet-linked production rows as missing

- **WHEN** some `production`-status cards have been published under a non-default alias only, every
  other `production`-status collection carries `production`, and a default-alias `--verify` is run
  without `--only`
- **THEN** it reports exactly those not-yet-linked collections as missing and exits non-zero, which is
  the expected state until they are promoted
- **AND** it reports every other `production`-status collection as present

### Requirement: Collection Identifier Scheme

The package SHALL derive each card's collection id from a **single documented scheme implemented in
one function**, used by publishing, `--only`, and `--verify` alike, so the producer cannot compute one
id when writing and a different one when reading back. A scheme is needed at all because a card no
longer has a single `species`/`mode`/age window to name itself with. The id SHALL be a deterministic function of the
card alone and SHALL be unique across the expanded card set (the duplicate-id fail-fast guard in
Per-Physical-Model Publishing and Registry Linking still applies, and now also guards against a lossy
slug collapsing two distinct model ids).

The id SHALL be accepted by the `wandb.Artifact(name=..., type="model")` constructor itself, which is
the effective rule: it enforces `^[a-zA-Z0-9_\-.]+$` **before** delegating to
`wandb.sdk.artifacts._validators.validate_artifact_name`, so it rejects the `=` that every
`source_model_id` in the committed matrix contains (from the `n=<count>` suffix) as well as the `/`
that `validate_artifact_name` catches. `validate_artifact_name` and `INVALID_ARTIFACT_NAME_CHARS`
(which is exactly `{"/"}`) SHALL NOT be used as the legality oracle, because both accept names the
constructor rejects — a slug that only strips `/` would pass such a check and then abort the live
seed on the first card. The id SHALL also respect the 128-character `NAME_MAXLEN` bound.

The scheme SHALL be stable against a metadata-only edit, so that adding a selector to an existing card
does not rename a live production collection.

The formula SHALL be: take the card's `source_model_id` and replace each `/` and each `=` with `-`,
changing nothing else. Case, dots, underscores and existing hyphens are preserved. So
`rice/younger/crown/220821_163331.multi_instance.n=867` becomes
`rice-younger-crown-220821_163331.multi_instance.n-867`. Deriving the id from the physical model rather
than from a selection context is what satisfies the stability property above: adding a selector to a
card does not change which weights the card describes.

This mapping is **not injective in principle** — two `source_model_id`s differing only by `/` against
`=` in one position would collapse onto a single id — so it does not remove the need for the
duplicate-id fail-fast guard, which is what turns such a collision into a failed seed rather than a
silent overwrite. Every id the committed matrix yields SHALL be distinct, accepted by the
`wandb.Artifact` constructor, and within the 128-character bound, as checked by test against the
committed matrix rather than restated here as counts.

#### Scenario: Collection ids are legal wandb artifact names

- **WHEN** collection ids are computed for every card the committed matrix expands to
- **THEN** each id is accepted by the real `wandb.Artifact(name=<id>, type="model")` constructor,
  which needs no credential and no network
- **AND** the check is not delegated to `validate_artifact_name` or a hand-rolled regex, either of
  which would accept an id the constructor rejects
- **AND** no id exceeds the 128-character name bound

#### Scenario: One scheme serves publish, --only, and --verify

- **WHEN** a card's collection id is computed on the publish path and on the verification path
- **THEN** the two paths yield equal ids for every card
- **AND** an `--only` value matching a card's id therefore selects that card in every mode

### Requirement: Orphaned Collection Reporting

The `--verify` mode SHALL additionally **report any collection in the registry that carries the
configured alias but that the current expansion no longer produces**, so that collections orphaned by
an expansion change are surfaced rather than silently ignored. A collection the expansion produces
SHALL NOT be reported as an orphan, whatever its row status. Under a non-default alias, for example,
collections from `production`-status rows that still carry that alias are leftovers of their candidate
window, not orphans. Orphan reporting SHALL NOT delete a collection or move any alias. Retirement stays
a separate, human-gated act.

Because `--verify --only <id>` narrows the expected set (see Registry Verification Command), orphan
reporting SHALL be **suppressed under `--only`**, where every collection outside the canary's scope
would otherwise be reported as orphaned. The output SHALL state that the orphan check was skipped for
that reason. An orphan count SHALL therefore only ever be read from a full `--verify` run.

Orphans SHALL NOT affect the exit code. These are failures:

- a missing alias on an *expected* collection;
- an expected collection carrying the legacy metadata shape;
- an unexpected production link.

An orphan, by contrast, is an advisory finding a human must act on. A collection whose alias membership
cannot be determined SHALL be reported as indeterminate and SHALL likewise not affect the exit code, so
a transient read error on an unrelated collection cannot fail a verification that previously could not
see that collection at all.

Orphan detection SHALL determine alias membership without paginating every artifact version of every
collection in the registry. The registry holds far more collections than cards, most of them
non-production sweep and training-run artifacts, so a per-version scan is proportional to every version
in the registry rather than to the card set. Alias membership SHALL be read from the per-collection
alias query (`ArtifactCollection.aliases`), which is one lightweight call per collection.

The registry-wide membership query (`Api.registry(...).versions(...)`) MAY be used instead where it is
available, but SHALL NOT be assumed available, for two reasons:

- it is gated on a server feature flag and raises when the flag is absent;
- it additionally requires an `organization` that this package's registry configuration does not carry.

Any use of it SHALL therefore sit behind a capability probe, with the per-collection path as the
documented fallback. Only collections carrying the configured alias SHALL be named. Collections that do
not carry it SHALL be excluded silently, not reported as orphans.

#### Scenario: Verify reports collections the expansion no longer produces

- **WHEN** the registry holds a production-aliased collection whose id is absent from the current
  expanded card set
- **THEN** `--verify` names that collection as orphaned in its report
- **AND** it does not delete the collection or move its production alias
- **AND** the orphan does not by itself make the command exit non-zero

#### Scenario: Collections without the configured alias are not reported as orphans

- **WHEN** the registry holds collections that do not carry the configured alias (sweep and
  training-run artifacts)
- **THEN** they are excluded from the orphan report
- **AND** determining this does not require reading every version of every collection

#### Scenario: Collections the matrix produces are never orphans

- **WHEN** a `candidate`-alias `--verify` is run, and `production`-status collections from an earlier
  candidate window still carry `candidate`
- **THEN** those collections are not reported as orphans
- **AND** a `candidate`-carrying collection the matrix does not produce is still reported as an orphan

#### Scenario: Orphan reporting is suppressed under --only

- **WHEN** `--verify --only <collection_id>` is run during a canary, so the expected set is narrowed
  to one collection
- **THEN** the report does not list the out-of-scope collections as orphaned
- **AND** it states that the orphan check was skipped because `--only` narrowed the scope

### Requirement: Re-Publish Metadata Refresh

A re-seed that reports a collection as `published` SHALL confirm that the metadata visible on the
production-aliased artifact is the new-shape metadata. This is required because artifact metadata is
not part of the `add_dir` manifest digest, so re-logging unchanged weights is a content-level no-op
that can leave the previously published metadata live. `--force` SHALL NOT be treated as sufficient
evidence of a refresh, since it bypasses the idempotency read rather than guaranteeing a new stored
metadata blob.

Where the read-back shows stale metadata, the seed SHALL refresh it in place through the artifact's
own metadata-update path (setting `Artifact.metadata` and calling `Artifact.save()`, which issues an
`updateArtifact` mutation) and re-read to confirm, rather than requiring another `--force` re-log,
which cannot create a new version while the digest is unchanged. The refresh SHALL NOT re-upload the
model directory. If the refresh fails — whether it **raises** or the re-read still shows the legacy
shape — the collection SHALL be reported in a distinct `failed` bucket, the command SHALL exit
non-zero, and the remaining cards SHALL still be attempted, so that neither a stale collection nor a
transient error on one collection aborts the seed.
The determination SHALL use the same structural shape test the Registry Verification Command
requirement defines, and SHALL NOT be restated independently — one definition, so the publish path and
the verification path cannot drift apart on what counts as migrated.

#### Scenario: Re-publish that leaves stale metadata is refreshed in place

- **WHEN** a card is re-published over an existing collection whose weights are byte-identical, and
  the production-aliased artifact still reads back with card-level `species`/`mode`/`age_min`/
  `age_max` and no `selectors`
- **THEN** the seed updates that artifact's metadata in place and re-reads it to confirm
- **AND** it does not re-upload the model directory

#### Scenario: A refresh that does not take is reported as failed

- **WHEN** the in-place metadata refresh is attempted and the artifact still reads back with the
  legacy flat shape
- **THEN** the seed reports that collection in a `failed` bucket, naming it, distinctly from
  `published` and `skipped`
- **AND** the command exits non-zero
- **AND** the remaining cards are still attempted

#### Scenario: Successful re-publish reads back the new shape

- **WHEN** a card is re-published and the production-aliased artifact reads back carrying
  `selectors` and no card-level selection fields
- **THEN** the seed reports that collection as published
- **AND** it is not reported as failed, so the check discriminates rather than failing everything

#### Scenario: A tolerant-read contract does not mask stale metadata

- **WHEN** the read-back metadata is the legacy flat shape and the pinned contract accepts it by
  lifting it into a single-selector card
- **THEN** the collection is still classified as stale, because the check is structural rather than a
  contract validation

### Requirement: Selection Matrix Provenance

Because the selection matrix's rows no longer come from a single source table, the matrix SHALL carry
its provenance in two required places, and the loader SHALL enforce both:

- every row SHALL carry `source`, a non-empty string stating why the row exists with its window (for
  example the models-downloader chooser table and snapshot it was transcribed from, or the owner
  decision and issue that set it);
- a top-level `origins` mapping, keyed by model id exactly as `checksums` is, SHALL hold for every
  model id referenced by any row a mapping with `location` (non-empty string: the directory under
  which `<model_id>.zip` sits), `pinned_by` (non-empty string naming what selected that exact file),
  and `snapshot` (a required key whose value is the models-downloader snapshot the zip ships in, as a
  string, or an explicit `null` when it ships in none). `origins` SHALL NOT name a model id that no
  row references.

The loader SHALL check, in this order: the required row keys (`species`, `mode`, `age`), the
species/mode vocabulary, model-id types, each row's `source`, and — only after every row is read —
`origins` coverage. Each failure SHALL be a `ValueError` naming the offending row or model id and the
key. An absent or `null` `origins` SHALL be reported as the first uncovered model id; an `origins` that
is present but not a mapping SHALL be reported naming `origins`; neither SHALL surface as an unhandled
`KeyError`, `TypeError` or `AttributeError`.

Every `location` in the **committed** matrix SHALL be relative to an experiment run or a snapshot and
SHALL NOT name a share or machine path. This is a property of the committed file, checked by a test,
not a loader rule.

#### Scenario: A row without a valid source is rejected

- **WHEN** a row has no `source`, or its `source` is empty or not a string
- **THEN** loading raises a `ValueError` naming that row and `source`
- **AND** no matrix is returned

#### Scenario: A referenced model with a missing or mistyped origin is rejected

- **WHEN** a referenced model id has no `origins` entry, or its entry is not a mapping, or lacks a
  non-empty string `location` or `pinned_by`, or has no `snapshot` key, or a `snapshot` that is
  neither a string nor `null` (for example an unquoted `20250204`)
- **THEN** loading raises a `ValueError` naming the model id and what is missing or mistyped
- **AND** no matrix is returned

#### Scenario: A matrix with no usable origins map is rejected cleanly

- **WHEN** the matrix has rows but no `origins` key or `origins: null`
- **THEN** loading raises a `ValueError` naming the first uncovered model id
- **AND WHEN** `origins` is a list
- **THEN** loading raises a `ValueError` naming `origins`
- **AND** neither raises `KeyError`, `TypeError` or `AttributeError`

#### Scenario: An origin for an unreferenced model is rejected

- **WHEN** `origins` names a model id that no row references
- **THEN** loading raises a `ValueError` naming that model id as a stale origin

#### Scenario: Earlier checks report before provenance checks

- **WHEN** a row is out of vocabulary, or has a non-string model id, and also has no `source`
- **THEN** the error reported is the vocabulary or model-id error, not the `source` error
- **AND WHEN** row 0 references a model with no origin and row 1 has no `source`
- **THEN** the error reported names row 1 and `source`

#### Scenario: Origins are parsed into records

- **WHEN** a valid matrix is loaded
- **THEN** each referenced model id maps to a record carrying `snapshot` (`None` where `null`),
  `location` and `pinned_by`

#### Scenario: Committed origins name no share path

- **WHEN** the committed matrix is loaded
- **THEN** no origin `location` starts with `/`, or contains `:\`, `\\`, `hpi` or `users/`

### Requirement: First-Time Production Link Requires Promotion

Under the **default** alias (`production`), `seed-registry --execute` SHALL first determine, read-only,
which in-scope collections are absent from the registry or hold no version carrying that alias. It
SHALL then refuse, unless `--promote` is given. The refusal SHALL exit with status 1 as a CLI error
(not a usage error), name those collections, and publish nothing. Linking `production` to a collection
for the first time makes it live for the consumer at once, so it SHALL never happen as a side effect of
a routine re-seed, a forgotten alias variable, or `--force`.

This check applies to the cards in the run's scope, which under the default alias are
`production`-status cards only. A `candidate`-status card is skipped or refused earlier (see Candidate
Rows Are Never Linked to Production), so `--promote` never links one.

A collection absent from the registry's collection listing SHALL be treated as unpromoted without
reading its versions, because the wandb client raises when asked for the versions of a collection that
does not exist.

The check SHALL run after the credential check, and before the confirmation prompt, model resolution
and `wandb.init`, so a refused run creates no wandb run. It SHALL run under `--force`, even though
`--force` skips the idempotency read. A registry read error during the check SHALL fail the command
closed.

`--promote` SHALL be accepted only together with `--execute`, under the default alias, and with
`--only`, so every promotion names its collections. Any other use SHALL be a usage error in every mode,
raised before the dry-run return and the credential check. A seed whose in-scope collections already
all carry `production` SHALL proceed unchanged, with or without `--promote`.

#### Scenario: A first-time production link without --promote is refused

- **WHEN** `seed-registry --execute` runs under the default alias, with or without `--yes`, and an
  in-scope `production`-status collection has no `production`-aliased version (it is absent, or carries
  only `candidate`)
- **THEN** the command exits with status 1 naming every such collection and `--promote`
- **AND** no confirmation prompt is shown, no model is resolved, and `wandb.init` is not called

#### Scenario: Losing the candidate alias variable cannot publish to production

- **WHEN** the three wheat and sorghum collections are `production`-status rows that do not yet carry
  `production`, and the candidate command is run without its `SLEAP_ROOTS_MODEL_ALIAS` setting, i.e.
  `seed-registry --models-root <dir> --only <3 new ids> --execute --yes` under the default alias
- **THEN** it is refused as a first-time production link, `wandb.init` is not called and nothing is
  linked

#### Scenario: Force does not bypass the promotion check

- **WHEN** the refused invocation above is repeated with `--force`
- **THEN** it is refused in the same way

#### Scenario: Promotion with --only proceeds

- **WHEN** `seed-registry --execute --yes --only <id> --promote` runs under the default alias, for a
  `production`-status collection with no `production`-aliased version
- **THEN** the check does not refuse it, and that card proceeds to publishing under `production`
- **AND** the collections being linked for the first time are printed before publishing, even under
  `--yes`, or "nothing to promote" when there are none

#### Scenario: Re-seeding already-production collections needs no promotion

- **WHEN** every in-scope collection already holds a `production`-aliased version
- **THEN** `--execute` proceeds with or without `--promote`, skipping them as before

#### Scenario: --promote is refused where it does not apply

- **WHEN** `--promote` is given without `--execute` (a dry run or `--verify`), without `--only`, or under
  a non-default alias
- **THEN** the command fails as a usage error before any credential check or wandb call

#### Scenario: A registry read error fails closed

- **WHEN** the promotion check's registry read raises
- **THEN** the command exits non-zero with a CLI error (no traceback) and publishes nothing

### Requirement: Committed Wheat and Sorghum Rows

The committed selection matrix SHALL carry the wheat and sorghum rows decided for
talmolab/sleap-roots-pipeline#118 (talmolab/sleap-roots-training#72), with their exact models, windows,
root types and source-zip checksums. A later edit that changes any of them then fails a test, rather
than silently re-pointing a card. Matrix-wide counts are pinned by Committed Matrix Totals.

#### Scenario: Committed matrix includes the wheat and sorghum cards

- **WHEN** the committed selection matrix is loaded and expanded to cards
- **THEN** `20250401_wheat_models/250328_095645.multi_instance.n=1658` is one `crown` card with the
  single selector (`wheat`, `cylinder`, 5, 14) and checksum
  `650fe30ba2d61e0a292c6dbeaac531a655e811e551bae8c4d9bef0b5f51ba13f`
- **AND** `20250204_sorghum_experimental/sorghum_soybean_primary_6nodes/250203_181521.multi_instance.n=1689`
  is one `primary` card with checksum
  `7c2cd05ded5b3f80163ccd171f3b4abb074ba609f4d52473799162ab763a7c07`, and
  `20250204_sorghum_experimental/sorghum_soybean_lateral_4nodes/250203_214033.multi_instance.n=590` is
  one `lateral` card with checksum
  `f694d6da5a71b17ad72a48c308916ea7d95c5cb9a5c7fcdfe619e59c90130028`, each with the single selector
  (`sorghum`, `cylinder`, 3, 14)
- **AND** the wheat origin has `snapshot` `null`, and both sorghum origins have `snapshot` `"20250204"`
- **AND** all three have status `production`, and the original 8 cards' selectors are unchanged

### Requirement: Per-Row Publication Status

A selection-matrix row SHALL accept an optional `status` key. Its value SHALL be exactly the string
`production` (the default alias) or the string `candidate`. A row without a `status` key SHALL be
`production`, so existing matrices load unchanged. Any other value SHALL be rejected at load time with
a row-numbered error naming the two allowed values. That includes `null`, an empty string, a
non-string, a differently cased spelling and a whitespace-padded one. The status check SHALL run after
the row's `source` check and before `origins` coverage.

A row SHALL hold only the known row keys: `species`, `mode`, `age`, `primary_model_id`,
`lateral_model_id`, `crown_model_id`, `source` and `status`. Any other key SHALL be rejected at load
time with a row-numbered error naming it and the known keys. Because a missing `status` means
`production`, a misspelled `status` key (`stauts`, `Status`) would otherwise load a candidate row as
production without a word.

Each card SHALL carry the status of the rows it was expanded from. A model referenced by rows of
different status SHALL be rejected during card expansion with an error naming the model, alongside the
other cross-row expansion checks (see Per-Physical-Model, Per-Root-Type Card Expansion). One collection
cannot be both expected in production and kept out of it. Two rows of the same status that share a
model SHALL expand as before.

`status` SHALL be matrix-local. It SHALL NOT appear in the published card metadata, and every card's
metadata SHALL be identical to what it would be if its row had no `status` key.

#### Scenario: A row without status is production

- **WHEN** a matrix row has no `status` key
- **THEN** the loaded row and its cards have status `production`

#### Scenario: Explicit statuses load

- **WHEN** a matrix row has `status: candidate`, and another has `status: production`
- **THEN** both load, and their cards have status `candidate` and `production` respectively

#### Scenario: An invalid status is rejected

- **WHEN** a matrix row's `status` is `staging`, `null`, `""`, `1`, `Candidate` or `" candidate "`
- **THEN** loading fails with an error naming the row index and both allowed values

#### Scenario: A misspelled status key is rejected

- **WHEN** a matrix row carries `stauts: candidate` or `Status: candidate` instead of `status`
- **THEN** loading fails with an error naming the row index and that key, and no card is produced

#### Scenario: A model under rows of mixed status is rejected

- **WHEN** one model id is referenced by a `production` row and a `candidate` row
- **THEN** card expansion fails with an error naming that model
- **AND WHEN** two `candidate` rows reference one model
- **THEN** they expand to one `candidate` card without error

#### Scenario: Status is not published

- **WHEN** a card from a `candidate` row is converted to card metadata
- **THEN** the metadata has no `status` key and is equal to the metadata of the same card with status
  `production`

### Requirement: Candidate Rows Are Never Linked to Production

Under the **default** alias, `seed-registry --execute` SHALL never publish a card whose row status is
`candidate`:

- **Without `--only`**, candidate-status cards SHALL be out of the run's scope. The run SHALL print
  each one as `skipped (status: candidate)`, SHALL publish the production-status cards exactly as
  before, and SHALL record the skipped collections in its lineage (see Seed Run Lineage). If no
  card is left in scope, the run SHALL say so and stop, exiting zero, before the credential check,
  so that it creates no wandb run.
- **With `--only` naming one or more candidate-status collections**, the command SHALL refuse with
  exit status 1, as a CLI error, publishing nothing. That holds even when production-status
  collections are named alongside them. The error SHALL name those collections, and say that
  promoting one requires changing its row's `status` in a reviewed change to the committed matrix,
  and that a production re-seed should name only production-status collections.

Neither `--promote` nor `--force` SHALL override this. The packaged matrix is the authority for a
row's status: when `--selection-matrix` names another matrix, a collection whose row in the
**packaged** matrix is `candidate`-status SHALL be treated as candidate-status as well, so an edited
copy cannot promote what the reviewed matrix keeps out of production. That holds in every mode:
`--verify` SHALL check such a collection as barred, never as expected, and a dry run SHALL mark it
`status: candidate`. A packaged matrix that fails to load SHALL be reported as a CLI error. The
decision SHALL be made from the matrices alone. It SHALL run after:

- the blank-alias check;
- the matrix load;
- the unknown-`--only` check;
- the `--promote` usage validation.

It SHALL run before:

- the non-default-alias guard;
- the credential check;
- the promotion check;
- the confirmation prompt;
- model resolution;
- `wandb.init`.

A refused run therefore makes no wandb call. These SHALL NOT be refused or narrowed by it:

- a dry run, which SHALL list candidate-status cards marked `status: candidate`, so an operator sees
  what a default `--execute` would skip;
- `--verify`, with or without `--execute`;
- `--execute` under a non-default alias.

#### Scenario: Naming a candidate collection under production is refused

- **WHEN** `seed-registry --execute --yes --only <candidate-status collection> --promote` runs under the
  default alias
- **THEN** it exits with status 1 naming that collection and the row's `status`
- **AND** no credential check, `wandb.Api`, promotion check, confirmation prompt, model resolution or
  `wandb.init` happens

#### Scenario: Neither force nor omitting promote changes the refusal

- **WHEN** the refused invocation above is repeated with `--force`, or without `--promote`
- **THEN** it is refused in the same way, by this check and not by the promotion check

#### Scenario: An edited copy of the matrix cannot promote a packaged candidate

- **WHEN** a copy of the packaged matrix with `status: candidate` removed from a row is passed as
  `--selection-matrix`, and `seed-registry --execute --yes --only <that row's collection> --promote`
  runs under the default alias
- **THEN** it is refused by this check, naming that collection, before any wandb call
- **AND WHEN** the same copy is used for an unscoped `--execute`, a `--verify` or a dry run
- **THEN** that collection is skipped and never published, checked as barred, or marked
  `status: candidate`, respectively

#### Scenario: Losing the candidate alias variable cannot publish a candidate row

- **WHEN** the candidate publish command, `seed-registry --models-root <dir> --only <candidate ids>
  --execute --yes`, is run without its `SLEAP_ROOTS_MODEL_ALIAS=candidate` setting
- **THEN** it is refused by this check before any wandb call

#### Scenario: An unscoped production re-seed skips candidate rows

- **WHEN** `seed-registry --models-root <dir> --execute --yes` runs under the default alias, without
  `--only`, over a matrix with a candidate-status row
- **THEN** each candidate-status card is printed as `skipped (status: candidate)`, and is not checked
  for promotion, resolved or published
- **AND** the production-status cards proceed exactly as they would over a matrix without that row,
  so the run's `row_sources` and `model_origins` hold no candidate row or model
- **AND** the run's `invocation` records the skipped collections as `skipped_by_status`

#### Scenario: A scope of only candidate cards publishes nothing

- **WHEN** the same unscoped command runs over a matrix whose every row is candidate-status
- **THEN** it prints the skipped cards and that nothing is in scope, and exits zero
- **AND** no credential check, `wandb.Api`, confirmation prompt or `wandb.init` happens

#### Scenario: Naming production and candidate collections together is refused whole

- **WHEN** `--execute --only <production id> --only <candidate id>` runs under the default alias
- **THEN** it is refused naming only the candidate collection, and nothing is published

#### Scenario: Candidate rows publish under the candidate alias

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS=candidate seed-registry --models-root <dir> --execute --yes --only
  <candidate-status collections>` runs
- **THEN** this check does not fire, and each named card is linked with exactly the `candidate` alias

#### Scenario: Verify and dry run are not affected

- **WHEN** `seed-registry --verify --execute`, or a dry run, runs under the default alias over a matrix
  with a candidate-status row
- **THEN** this check does not refuse it
- **AND** the dry run lists the candidate-status cards marked `status: candidate`

### Requirement: Aliases That Only Look Like Production Are Refused

`seed-registry` SHALL refuse, in every mode, an alias that differs from `production` only in letter
case or invisible characters (for example `Production`, or `production` followed by a zero-width
space). The refusal SHALL be a CLI error naming the variable, and SHALL come after the blank-alias
check and before any wandb call. Every guard against an accidental production link keys on the alias
being exactly `production`, so such an alias would otherwise pass all of them as a "non-default"
alias.

#### Scenario: A case or invisible-character variant of production is refused

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS` is `Production`, `PRODUCTION`, `production​` or
  `​production`, and `seed-registry --execute --yes --only <candidate-status collection>` or
  `seed-registry --verify` runs
- **THEN** it exits with status 1 naming `SLEAP_ROOTS_MODEL_ALIAS`
- **AND** no credential check, `wandb.Api`, promotion check, confirmation prompt or `wandb.init`
  happens

### Requirement: Reproducible Model Archive Build

The repository SHALL provide `scripts/build_model_zip.py`, which builds a `<model_id>.zip` from a
trained model directory and prints its SHA256. The archive SHALL be byte-reproducible from the same
file tree: the same file names and bytes, under a directory of the same name. That SHALL hold on any
host and any supported Python. To achieve that:

- entries SHALL be stored uncompressed;
- entries SHALL be in sorted path order;
- every entry SHALL have the same fixed timestamp, permission bits and creator system;
- every file SHALL sit under one top-level directory named after the resolved model directory;
- OS junk files (as excluded by model resolution) SHALL be left out.

A checksum committed to the matrix can therefore be re-derived from the source directory, without
keeping the archive.

The script SHALL refuse, exiting non-zero and writing nothing, in these cases:

- the source lacks `best_model.h5` or `training_config.json`;
- the output lies inside the source (the next build would archive it);
- the output already exists.

The script SHALL write the archive to a temporary file and move it into place only when it is
complete. A failed build therefore leaves no archive at the output path. When that temporary file
already exists (left by a killed build, or in use by another one), the script SHALL refuse, exiting
non-zero with a message naming it, and SHALL NOT delete or modify it: it removes only a temporary
file it created.

Each entry's size SHALL be declared before its data is streamed, as `ZipFile.writestr` does, so the
ZIP64 decision, and with it the bytes, match an archive written whole. Otherwise a model file above
the ZIP64 threshold would be archived differently.

#### Scenario: Two builds are byte-identical

- **WHEN** the script builds an archive twice from the same model directory, at different times
- **THEN** both archives have the same SHA256

#### Scenario: The digest does not depend on the host, the Python version or the file modes

- **WHEN** a fixed test tree is built on each CI host and Python version, including after changing a
  file's permission bits
- **THEN** every build has the same pinned SHA256
- **AND** every entry records creator system Unix and mode `0o100644`
- **AND WHEN** the source is given as `.` from inside the model directory
- **THEN** the archive is the same as when it is given by full path

#### Scenario: A source that is not a model, or an output inside it, is refused

- **WHEN** the source is empty, holds only OS junk, or lacks `training_config.json`, or the output
  path is inside the source
- **THEN** the script exits non-zero and no archive is written

#### Scenario: A failed build leaves no archive

- **WHEN** reading a source file fails part-way through a build
- **THEN** the error propagates and nothing exists at the output path

#### Scenario: A leftover temporary file is refused, not deleted

- **WHEN** `<output>.partial` already exists and the script is run for `<output>`
- **THEN** it exits non-zero naming that file, nothing exists at the output path, and the temporary
  file's bytes are unchanged

#### Scenario: Streaming matches writing whole above the ZIP64 threshold

- **WHEN** the ZIP64 threshold is lowered below the size of a file in the source
- **THEN** the script's archive is byte-identical to one written with `ZipFile.writestr` using the
  same entry headers

#### Scenario: The archive resolves as a pinned model

- **WHEN** an archive built by the script is placed at `<models-root>/<model_id>.zip`, with its SHA256
  in the matrix's `checksums`
- **THEN** `resolve_model_dir(model_id, models_root, checksums, require_pinned=True)` returns a
  directory containing `best_model.h5` and `training_config.json`

#### Scenario: An existing output is not overwritten

- **WHEN** the output path already exists
- **THEN** the script exits non-zero without modifying it

### Requirement: Committed Matrix Totals

The committed selection matrix's row, checksum, card and status counts SHALL be pinned by test. Adding
or removing a row then fails a test, rather than silently changing the published set. Requirements
for individual committed rows SHALL NOT restate these totals.

#### Scenario: Committed matrix totals

- **WHEN** the committed selection matrix is loaded and expanded to cards
- **THEN** it has 10 rows and 13 checksums, and yields 13 cards over 13 distinct physical models
- **AND** exactly 2 cards have status `candidate`, and the other 11 have status `production`

### Requirement: Committed Arabidopsis Plate Row

The committed selection matrix SHALL carry the arabidopsis plate row decided for
talmolab/sleap-roots-training#3, with its exact models, window, root types, source-zip checksums and
`candidate` status. A later edit that changes any of them then fails a test, rather than silently
re-pointing a card. Promoting these cards changes `status`, and so SHALL modify this requirement.

#### Scenario: Committed matrix includes the plate cards

- **WHEN** the committed selection matrix is loaded and expanded to cards
- **THEN** `arabidopsis_plates/primary/230804_133809.multi_instance.n=606` is one `primary` card with
  checksum `ed1a939058e7989f938720b5461b795dc75d1c081b41e1d928284c09ad0ab721`
- **AND** `arabidopsis_plates/lateral/231130_135922.multi_instance.n=38` is one `lateral` card with
  checksum `f42c4d06fe46c53c07150a95e308fcbfeadbf0771b6657bbe85346604b0ec265`
- **AND** each has the single selector (`arabidopsis`, `plate`, 2, 7) and status `candidate`
- **AND** their collection ids are `arabidopsis_plates-primary-230804_133809.multi_instance.n-606` and
  `arabidopsis_plates-lateral-231130_135922.multi_instance.n-38`
- **AND** both origins have `snapshot` `null` and a `location` that is not a share path

