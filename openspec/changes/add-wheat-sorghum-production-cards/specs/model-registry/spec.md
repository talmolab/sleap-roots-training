## ADDED Requirements

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
which in-scope collections are absent from the registry or hold no version carrying that alias, and
SHALL refuse — exiting with status 1 as a CLI error (not a usage error), naming those collections and
publishing nothing — unless `--promote` is given. Linking `production` to a collection for the first
time makes it live for the consumer at once, so it SHALL never happen as a side effect of a routine
re-seed, a forgotten alias variable, or `--force`.

A collection absent from the registry's collection listing SHALL be treated as unpromoted without
reading its versions (the wandb client raises when asked for the versions of a collection that does not
exist). The check SHALL run after the credential check and before the confirmation prompt, model
resolution and `wandb.init`, so a refused run creates no wandb run. It SHALL run under `--force` even
though `--force` skips the idempotency read. A registry read error during the check SHALL fail the
command closed. `--promote` SHALL be accepted only with `--execute`, under the default alias, and
together with `--only`, so every promotion names its collections; any other use SHALL be a usage error
in every mode, raised before the dry-run return and the credential check. A seed whose in-scope
collections already all carry `production` SHALL proceed unchanged, with or without `--promote`.

#### Scenario: A first-time production link without --promote is refused

- **WHEN** `seed-registry --execute` runs under the default alias, with or without `--yes`, and an
  in-scope collection has no `production`-aliased version (absent, or carrying only `candidate`)
- **THEN** the command exits with status 1 naming every such collection and `--promote`
- **AND** no confirmation prompt is shown, no model is resolved, and `wandb.init` is not called

#### Scenario: Losing the candidate alias variable cannot publish to production

- **WHEN** none of the three wheat and sorghum collections carries `production`, and the candidate
  command is run without its `SLEAP_ROOTS_MODEL_ALIAS` setting, i.e.
  `seed-registry --models-root <dir> --only <3 new ids> --execute --yes` under the default alias
- **THEN** it is refused as a first-time production link, `wandb.init` is not called and nothing is
  linked

#### Scenario: Force does not bypass the promotion check

- **WHEN** the refused invocation above is repeated with `--force`
- **THEN** it is refused in the same way

#### Scenario: Promotion with --only proceeds

- **WHEN** `seed-registry --execute --yes --only <id> --promote` runs under the default alias for a
  collection with no `production`-aliased version
- **THEN** the check does not refuse it and that card proceeds to publishing under `production`

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
talmolab/sleap-roots-pipeline#118 (talmolab/sleap-roots-training#72) with their exact models, windows,
root types and source-zip checksums, so a later edit that changes any of them fails a test rather than
silently re-pointing a card.

#### Scenario: Committed matrix expands to 11 cards, including the wheat and sorghum cards

- **WHEN** the committed selection matrix is loaded and expanded to cards
- **THEN** it has 9 rows and 11 checksums, and yields 11 cards over 11 distinct physical models
- **AND** `20250401_wheat_models/250328_095645.multi_instance.n=1658` is one `crown` card with the
  single selector (`wheat`, `cylinder`, 5, 14) and checksum
  `650fe30ba2d61e0a292c6dbeaac531a655e811e551bae8c4d9bef0b5f51ba13f`
- **AND** `20250204_sorghum_experimental/sorghum_soybean_primary_6nodes/250203_181521.multi_instance.n=1689`
  is one `primary` card with checksum
  `7c2cd05ded5b3f80163ccd171f3b4abb074ba609f4d52473799162ab763a7c07`, and
  `20250204_sorghum_experimental/sorghum_soybean_lateral_4nodes/250203_214033.multi_instance.n=590` is
  one `lateral` card with checksum
  `f694d6da5a71b17ad72a48c308916ea7d95c5cb9a5c7fcdfe619e59c90130028`, each with the single selector
  (`sorghum`, `cylinder`, 3, 14)
- **AND** the wheat origin has `snapshot` `null` and both sorghum origins have `snapshot` `"20250204"`
- **AND** the existing 8 cards' selectors are unchanged

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

#### Scenario: Git SHA resolves without a repository

- **WHEN** the git SHA is resolved from an installed package with no `.git` and no env override
- **THEN** it returns the package-version fallback (or `"unknown"`) without raising

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
the consumer can read it across the producer/consumer wandb version skew); with `--only`, the
validation set, the publish set, **and the `--verify` expected set** all narrow to the named card(s)
(so a canary needs only its own model staged, and can be verified without the rest of the registry
counting as missing), and an `--only` value naming no known collection SHALL fail fast. A subsequent
`--execute` whose scope includes the canary publishes the rest and skips the canary; under the default
alias any first-time card in that scope requires `--promote`, which requires `--only`, so that run lists
its collections (see First-Time Production Link Requires Promotion). The `--models-root` is required
for dry-run and `--execute`; `--verify` is a distinct read-only mode that requires only the selection
matrix + registry config (not `--models-root`) and SHALL check for a resolvable wandb credential. A
selection-matrix rejection — an unreadable file, an out-of-vocabulary `species` or `mode`, a
non-contiguous `age` window, missing or mistyped provenance — SHALL reach the operator as a clean CLI
error carrying the loader's row- or model-naming message, not as an unhandled traceback.

Every invocation SHALL print, as its first output once the alias resolves and before any wandb contact,
prompt or publish, a target line naming the entity, the registry, the alias (ASCII-escaped, so hidden
characters show and any console can print it), whether the alias came from `SLEAP_ROOTS_MODEL_ALIAS` or
the default, and the seed project. A
`SLEAP_ROOTS_MODEL_ALIAS` that is set but blank (see Environment-Driven Registry Configuration) SHALL be
a CLI error for `seed-registry` in every mode, before any wandb call; it SHALL NOT fall back to
`production`.

`--execute` under a **non-default alias** SHALL require `--only`, and SHALL otherwise fail as a usage
error **before** the credential check, the confirmation prompt, or any wandb call — including under
`--force`. Without `--only`, the idempotency check finds no card seeded under the new alias and
re-publishes every card in the matrix under it. A dry run and `--verify` under a non-default alias SHALL
remain allowed, since neither writes.

Because the collection-id scheme changed (update-model-card-selectors), an `--only` value written
against the previous scheme SHALL fail fast under the existing unknown-id check rather than silently
matching nothing, so a stale id in an operator runbook is reported rather than acted on as an empty
scope.

#### Scenario: Only-filter seeds a single canary card, validating only its scope

- **WHEN** `seed-registry --execute --yes --only <collection_id> --promote` is run under the default
  alias with only that card's model staged
- **THEN** only that card is validated and published and linked with the production alias
- **AND** a subsequent `seed-registry --execute --yes --only <canary> --only <each remaining id>
  --promote` reports the canary as skipped and publishes the rest

#### Scenario: Unknown --only collection fails fast

- **WHEN** `--only` names a collection id not in the expanded card set — including an id valid under
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

- **WHEN** `seed-registry --execute --yes` is run and any in-scope card's model cannot be resolved
  (checksum, missing, or missing essential file)
- **THEN** the seed fails fast, naming the offending card, before any artifact is published
- **AND** no partial set of production artifacts is left in the registry

#### Scenario: Successful execution publishes and reports collections

- **WHEN** `seed-registry --execute --yes` is run with valid credentials and a complete models-root,
  and the promotion check passes
- **THEN** each not-yet-seeded card is published and linked with the production alias
- **AND** the command reports the published and skipped collections

#### Scenario: A rejected selection matrix is reported as a CLI error

- **WHEN** `seed-registry` is run against a matrix whose row is out of vocabulary (for example
  `mode: teacup`), or that lacks a row's `source` or a referenced model's `origins` entry
- **THEN** the command exits non-zero with the loader's row- or model-naming message rendered as a CLI
  error
- **AND** no traceback is printed and no wandb call is made

#### Scenario: An unreadable or unparseable selection matrix is reported as a CLI error

- **WHEN** `--selection-matrix` names a path that cannot be loaded as a matrix — a directory, a
  file that is not valid YAML, or YAML whose top level is not a mapping
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

- **WHEN** `seed-registry` is run with `SLEAP_ROOTS_MODEL_ALIAS=candidate` and no `--only`, either
  as a dry run (no `--execute`) or with `--verify`
- **THEN** the alias guard does not fire, and the command behaves as it does under the default alias,
  using `candidate`

#### Scenario: A blank alias is refused and a padded one is the default

- **WHEN** `SLEAP_ROOTS_MODEL_ALIAS` is set to `""` or only whitespace and `seed-registry` runs in any
  mode
- **THEN** it exits non-zero with a CLI error naming the variable, before any wandb call
- **AND WHEN** it is `" production "` and `--execute` runs without `--only`
- **THEN** the non-default-alias guard does not fire and the promotion check applies

#### Scenario: Default verify reports candidate-only cards as missing

- **WHEN** some matrix cards have been published under a non-default alias only, every other expected
  collection carries `production`, and a default-alias `--verify` is run without `--only`
- **THEN** it reports exactly the candidate-only collections as missing and exits non-zero — the
  expected state until they are promoted — and reports every other expected collection as present

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
