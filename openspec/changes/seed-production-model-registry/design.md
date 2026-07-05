## Context

`sleap-roots-predict`'s `WandbRegistrySource` (PR #9) is the **consumer contract** this change must
satisfy exactly. Its read path (verified against the branch `add-warm-model-worker`):

- Registry project path: `f"{entity}-org/wandb-registry-{registry}"`.
- `api.artifact_collections(project_name=<project>, type_name="model")`, then for each collection
  `api.artifacts(type_name="model", name=f"{project}/{collection.name}")`.
- Keeps only artifacts whose `aliases` include `"production"`.
- Builds `ModelCard.model_validate({**artifact.metadata, registry_id=<versionless qualified_name>,
  version=<concrete version>, weights_checksum=<artifact.digest>})`.
- `materialize(ref)` = `api.artifact(f"{registry_id}:{version}", type="model").download()`.

`ModelCard` (from `sleap-roots-contracts==0.1.0a3`) requires flat metadata keys `species: str`,
`mode: str`, `age_min: int (≥0)`, `age_max: int (≥0, ≥ age_min)`, `root_type:
Literal["primary","lateral","crown"]`; optional `sleap_nn_version: str | None`; and it is
`frozen`, `extra="ignore"`. `registry_id` / `version` / `weights_checksum` are **injected by the
consumer** from wandb intrinsics — they MUST NOT be in the artifact's stored metadata.

The models and the selection matrix are the current `models-downloader` (GitLab `salk-tm`) truth:
`model_chooser_table.xlsx` (20250204) + per-model legacy SLEAP zips (each unzips to a dir with
`best_model.h5` + `training_config.json`).

## Goals / Non-Goals

- **Goals:** publish the current legacy models as `type="model"` wandb artifacts with `ModelCard`
  selection metadata, `production` alias, and per-card registry collections such that the consumer's
  gated test (`pytest -m wandb`) goes green; establish the reusable publishing surface; keep the
  pure logic unit-tested with no network.
- **Non-Goals:** no `sleap-nn` training/backend, no model-format conversion (publish legacy as-is),
  no changes to `sleap-roots-predict`, no plate models (deferred).

## Decisions

### D1 — Shared weights → one artifact per (species, mode, age-window, root_type) card

One physical model serves multiple selection rows (e.g. `canola_pennycress_arabidopsis/primary`
→ canola, pennycress, arabidopsis×2). The consumer filters `species == <dataset species>` on
`artifact.metadata`, and **wandb metadata is attached to the artifact version and shared across all
registry links** to that version. So *linking one artifact into N per-species collections cannot
give each collection its own `species`* — every link would report the source's single `species`,
and the consumer's species filter would miss the others.

**Therefore:** publish a **separate artifact per card**, each `add_dir`'d over the *same* physical
directory, each stamped with that row's own `species`/`mode`/`age_min`/`age_max`/`root_type`. wandb
content-addresses the file blobs by hash, so the 62 MB `best_model.h5` is stored **once** and
deduped across the shared-weight cards; because the bytes are identical, `artifact.digest`
(→ `weights_checksum`) is **identical** across them, which is truthful. Every card also stamps a
non-contract `source_model_id` (the shared relative model path) so provenance is traceable back
from each card; `ModelCard` ignores it (`extra="ignore"`).

- Alternatives considered: (a) one artifact linked into many collections — **rejected**, breaks the
  species filter as above; (b) change the consumer's matcher — out of scope (we don't own predict's
  selection here, and the contract is already shipped).

### D2 — One collection per card; env-driven registry, curated `production` alias

The consumer selects production models by the **`production` alias**, not by registry name. In
wandb an alias is **unique within a collection** (assigning `production` to a new version moves it
off the old). Rice has two crown models for two age windows (2–5 younger, 6–10 older) that must
*both* be `production` simultaneously — so they cannot share a collection. **Each card therefore
gets its own collection** (one `production` version each). Collection id:
`f"{species}-{mode_slug}-{root_type}-age{age_min}-{age_max}"` (e.g. `rice-cylinder-crown-age6-10`,
`arabidopsis-multiplant-cylinder-lateral-age2-14`); `mode_slug` replaces spaces with hyphens.

We do **not** create a dedicated `…-production` registry: the alias already does prod-selection, so a
separate registry buys only physical separation at the cost of a migration (YAGNI). Instead
entity/registry/alias are **env-driven with defaults**, so pointing at a dedicated prod registry
later is a config change, not a code change:

| Setting | Env var | Default |
|---|---|---|
| entity | `WANDB_ENTITY` | `eberrigan-salk-institute-for-biological-studies` |
| registry | `SLEAP_ROOTS_MODEL_REGISTRY` | `sleap-roots-models` |
| alias | `SLEAP_ROOTS_MODEL_ALIAS` | `production` |

(The registry var is named `SLEAP_ROOTS_MODEL_REGISTRY`, not `SLEAP_ROOTS_REGISTRY`, because the lab
runs more than one registry — `sleap-roots-models` **and** `sleap-roots-labels` — so the variable must
say *which* registry it points at.)
| auth | `WANDB_API_KEY` | *(required; fail fast if unset — mirrors predict's `_require_key`)* |

These MUST resolve to the same entity+registry the consumer points `SRP_WANDB_ENTITY` /
`SRP_WANDB_REGISTRY` at; the README documents that mapping as a **cross-repo invariant**, calling
out two hazards: (a) the consumer's `SRP_WANDB_REGISTRY` has **no default**, so the operator MUST
set it explicitly to `<registry>` (the producer's `sleap-roots-models` default does not carry
over — a forgotten value fails the consumer loudly, not silently); and (b) the entity default
string `eberrigan-salk-institute-for-biological-studies` is hardcoded independently in both repos,
so a change to one must be mirrored in the other. `WANDB_ENTITY` is also wandb's own native
variable (it steers run placement) — the README notes this so an operator doesn't set it for an
unrelated reason and inadvertently repoint the registry.

### D3 — Selection matrix as committed, provenance-stamped YAML (native schema + tested parser)

The authoritative source is the xlsx; the CSV already in `models-downloader` is a **stale**
2024-05-02 export (wrong model ids) and is not used. We commit a fresh YAML snapshot exported from
the current xlsx, read via OmegaConf (the repo's config idiom — no new dependency), with a `#`
provenance header (source xlsx + verification date) and explicit `null` for absent root types. The
`age` column is kept as the **native comma-list string** (mirroring the xlsx) so (a) the file diffs
row-for-row against the source and (b) the `age comma-list → age_min/age_max` transform stays a real,
unit-tested step rather than an untrusted pre-baked value. Contiguity is asserted (predict assumes
contiguous windows); a gap raises.

### D4 — Publish legacy models AS-IS; current wandb (0.28) API

`add_dir` the entire unzipped model directory verbatim (weights + configs + labels/metrics + `viz/`
PNGs) — faithful provenance; predict's `make_predictor` loads legacy models via its config
sanitizer, no conversion needed. wandb dedup keeps shared re-uploads cheap. Publishing uses the
current API (verified against wandb 0.28.0):
`run.log_artifact(art, type="model")` → `logged.wait()` →
`run.link_artifact(logged, f"{entity}-org/wandb-registry-{registry}/{collection}", aliases=[alias])`
— the `aliases=` kwarg on `link_artifact`/`Artifact.link` lets us set `production` at link time,
replacing the old repo's two-step `wandb.Api().artifact(...).aliases.append(...); save()` workaround
(which existed for a 0.25-era bug). A single `wandb.init(job_type="seed_registry")` run owns the
whole seed for one lineage record. The registry target string is built with **literal forward
slashes** (`f"{entity}-org/wandb-registry-{registry}/{collection}"`) — never `os.path.join`/
`pathlib` — so Windows CI cannot introduce backslashes that would corrupt the path the consumer
iterates; `collection_id` is hyphen-only (no `os.sep`), and `resolve_model_dir` compares `Path`
objects (model ids are forward-slash relative paths).

### Dependency decisions

- **Pins:** `wandb>=0.28.0,<0.29.0` (0.28 is the verified API floor; wandb is pre-1.0 and breaks
  across minors, so cap the next minor to stop `uv lock --upgrade` silently pulling an unverified
  0.29). `sleap-roots-contracts==0.1.0a3` — exact alpha pin (a schema contract that must byte-match
  the consumer). Verified empirically: the alpha **resolves under `uv` with no `--prerelease` flag**
  (the package has only prereleases and the specifier is explicit), and both deps have prebuilt
  wheels for all six CI legs (no source builds, no torch/GPU). `wandb` ships platform-specific
  `py3-none-<platform>` wheels (a bundled Go `wandb-core`, not pure-python/abi3), but prebuilt for
  ubuntu/windows/macos-14, so the "no source build" conclusion holds.
- **`wandb` stays a runtime dep** (project.md lists W&B as core infrastructure; future training code
  needs it) but both `publish.py` **and `cli.py`'s `--execute` branch lazy-import `wandb` inside
  functions**, so importing the package / running the default dry-run / the pure-logic tests never
  require wandb loaded, and the network path is the only thing that touches it. `sleap-roots-contracts`
  is a base runtime dep (used by `card_to_metadata` validation and the dry-run path). OmegaConf is
  already a dep and pulls `pyyaml`; no new YAML dep.
- **Packaging:** the committed `registry/data/model_selection.yaml` ships in the wheel
  automatically under `uv_build` (verified: it appears in the built wheel `RECORD`; no
  `package-data` config needed, no `__init__.py` in `data/`). It is loaded via
  `importlib.resources.files(...).joinpath(...)` wrapped in `as_file(...)`, not a `__file__`-relative
  path, so it resolves identically from an installed wheel, an editable checkout, and a zip import.
- **Lock hygiene:** task 0.2 commits the regenerated `uv.lock` in the **same** commit as the
  `pyproject` dep-add (`uv add` updates both atomically); a separate task 0.3 adds `--locked` to
  **both** `uv sync` steps in `ci.yml` (lint + test jobs) and adds `uv.lock` to the workflow `paths`
  filter, so a lock/pyproject drift fails a PR instead of surfacing only at release time (the current
  `ci.yml` re-locks silently).

### D5 — Confirmed execution: dry-run is the default, `--execute` opts into the write

The real seed is an outward-facing, hard-to-reverse write to a **shared** registry, and a developer
commonly has `WANDB_API_KEY` exported — so "just run `seed-registry`" must not mutate the registry.
`seed-registry` therefore **defaults to a dry run** (prints the plan, resolves every model dir on
the filesystem, no network); `--execute` opts into publishing and first confirms the target
`entity/registry` (interactive `click.confirm`, bypassed only by `--yes`). Under `--execute` the
seed **validates that every card resolves before publishing any artifact** (fail-fast), so a
resolution error can't leave a partial production seed behind.

### D6 — Producer lineage lives in the run config, not per-artifact (simplified from round 2)

Round 1 proposed *per-artifact* provenance extras (`seed_git_sha`, `selection_matrix_date`) in
addition to run-config lineage. Round-2 review showed this was a net loss: a per-artifact
`seed_git_sha` changes every commit (volatile), a dynamically-merged extras dict risks clobbering a
contract key (`species`, `sleap_nn_version`, …), and it created a two-layer "6 keys vs 8 keys"
ambiguity and a contradiction with the digest-based idempotency it referenced. **Decision:** put
**all** lineage in the wandb **run config** and keep per-artifact metadata **exactly** the six
selection keys (`card_to_metadata`). Traceability is still complete: `source_model_id` (per
artifact) → physical model; `weights_checksum` (`artifact.digest`) → exact bytes; the run config →
the batch. `build_lineage()` records: `git_sha`, `git_dirty`, `matrix_content_sha256` (of the actually
loaded `model_selection.yaml` — pins the exact matrix used **independently of git cleanliness**, since
the per-model SHA256 reproducibility anchor now lives in that tracked file), `selection_matrix_source`
(URL), `selection_matrix_date`, `models_snapshot` date, and `sleap_roots_training`/`wandb`/
`sleap_roots_contracts` versions.

`git_sha` is the one field not derivable from `importlib.metadata`, so it uses a **robust resolver**
that never aborts the seed and never misattributes: prefer `SLEAP_ROOTS_TRAINING_GIT_SHA` (lets a
CI-built wheel inject the real SHA); else walk up from `__file__` (never `cwd` — cwd may be an
unrelated repo) to a `.git` and `git -C <that> rev-parse HEAD`, suffixing `+dirty` when
`git status --porcelain` is non-empty; else fall back to `f"v{version('sleap-roots-training')}"`,
else `"unknown"`. Under `--execute` a dirty tree emits a warning. Versions come from
`importlib.metadata` (works from a wheel).

### D7 — Idempotent re-seed keyed on the production alias, not the digest (simplified from round 2)

Round 1 keyed idempotency on the artifact **digest** ("skip if same weights digest"). Round-2 review
showed the digest is a **whole-directory** checksum (weights + configs + `viz/` PNGs + any OS junk),
so a regenerated PNG or a stray `.DS_Store` flips it even when `best_model.h5` is byte-identical —
the skip would miss and `--force` would churn the alias. **Decision:** key idempotency on the
**production alias itself**: before publishing a card, check whether its target collection already
holds an artifact carrying the production alias (`_collection_has_production(api, project,
collection)`); if so, **skip** and report — unless `--force`, which publishes a new version and
re-points the alias. This needs no digest math, is immune to `viz/`/junk churn, and makes "re-running
is safe" true by construction (a partial-failure re-run resumes by skipping already-seeded
collections). To further reduce junk-file sensitivity of the stored `weights_checksum`, `add_dir`
excludes `.DS_Store`/`__MACOSX/`/`Thumbs.db`/`Zone.Identifier`; the substantive model files (weights,
configs, labels, metrics, `viz/`) are still added AS-IS. The README documents the rerun contract
("already-seeded collections are skipped; `--force` re-publishes and re-points `production`;
re-running resumes after a partial failure") and notes that `weights_checksum` is a whole-artifact
digest, so re-seeds should reuse the identical on-disk snapshot.

### D8 — species / mode value vocabulary (silent-break guard)

The consumer filters `species ==` / `mode ==` on free-string metadata, so a value skew (`Arabidopsis`
vs `arabidopsis`, `multiplant cylinder` spacing) would pass every schema check yet return zero
matches in predict. The matrix loader validates each row's `species`/`mode` against the canonical
`models-downloader` vocabulary (currently species ∈ {`soybean`, `canola`, `pennycress`,
`arabidopsis`, `rice`}; mode ∈ {`cylinder`, `multiplant cylinder`, `plate`}); an unknown value fails
loudly at load. The vocabulary is defined **once in `chooser.py`** (spec/design list it
informatively) to limit drift; because `ModelCard` types `species`/`mode` as free `str` with no
shared enum, there is no single cross-repo source of truth today, so the acceptance step (task 9.2)
is the named reconciliation point that confirms the seeded values are the ones predict selects on. A
follow-up may promote the vocabulary to `sleap-roots-contracts` so both repos import one definition.

### D9 — Snapshot is `.zip`; resolution unzips + checksum-pins (from consumer-PR review, sharpened round 3)

The canonical `models-downloader` snapshot ships each model as `<species>/<root>/<id>.zip` (verified
on disk) — **not** an unzipped dir. `resolve_model_dir(model_id, models_root, matrix)`:

- **Archive form (production):** verifies `<models-root>/<model_id>.zip` against the **SHA256 recorded
  in the committed matrix**, then extracts it into a **fresh temp/cache dir** (via
  `tempfile`/`platformdirs`, **never in-place** — the snapshot may be a read-only Box/network mount),
  using `zipfile.extractall(members=<non-junk>)` (sanitizes member paths → Zip-Slip-safe, and omits
  OS junk `.DS_Store`/`__MACOSX/`/`Thumbs.db`/`Zone.Identifier` by not extracting them). Junk
  exclusion happens **at extraction**, because wandb `Artifact.add_dir` (0.28) has **no `exclude=`
  parameter**. The extraction is rooted to a **canonical layout** so the `add_dir` relative-path set
  (and thus `artifact.digest`) is identical regardless of models-root.
- **Dir form (dev/dry-run convenience):** an already-unzipped `<models-root>/<model_id>/` is returned
  as-is but is **NOT** SHA256-pinned (a directory can't be hashed against a zip's byte-hash), so under
  `--execute` it is rejected/warned — real writes MUST use the archive form.

This pins the snapshot: for the archive form, byte-identical zip → identical junk-free contents →
identical `add_dir` manifest → deterministic `artifact.digest` (→ the consumer's `weights_checksum`,
a Bloom compute-idempotency key) **under the pinned wandb writer** (`<0.29`). Per-model SHA256s are
captured into the YAML at commit time (task 1.1, via a documented regenerate helper), presence-checked
offline in CI (64-hex shape), and the real byte-check is the pre-merge dry run (task 8.1). Windows
long-path (`MAX_PATH`) is a real-seed-time concern for the temp root; noted for the implementer.

### Deviations discovered during implementation (docs reconciled to reality)

- **Snapshot zips are internally inconsistent.** Exercising the dry run against the real
  `models-downloader` tree showed some zips hold `best_model.h5` at the archive root and others wrap
  it in an inner `<model>/` directory. `resolve_model_dir` therefore normalizes to the directory that
  actually contains `best_model.h5` (D9) — this is why the resolved layout is canonical across both
  zip shapes. (Not a bug/workaround; correct handling of a real data inconsistency.)
- **Per-model SHA256s live in a top-level `checksums:` map** in the YAML (one entry per distinct
  model), not per-row fields — a shared model appears in several rows, so a map avoids duplicating
  (and drifting) its hash. `resolve_model_dir(model_id, models_root, checksums, …)` and
  `seed_registry(cards, models_root, checksums, cfg, run, …)` take that map.
- **`build_lineage(matrix_sha256)`** takes the matrix content hash (via `chooser.matrix_sha256()`)
  rather than a path — lineage does no file IO, which sidesteps the dangling-temp-path hazard of the
  packaged resource and works identically from a wheel/zip import.

### Hardening from the pre-PR code review (5-subagent pass on the implementation)

- **Idempotency read fails closed (BLOCKING fix).** `api.artifacts()` is a *lazy* wandb paginator
  whose query runs on iteration and raises for a missing collection — so a `try` around the call
  alone would abort the first seed (every collection missing) and swallow transient errors into a
  silent alias re-point. The seed now lists `_existing_collections(api, project)` once and only
  checks the alias on collections known to exist; any real API error propagates. `resolve_all` is
  split from `seed_registry` so the CLI validates every card (filesystem) *before* `wandb.init`,
  failing fast with a clean `ClickException` and minting no empty run.
- **`--only` scopes all modes.** The CLI applies the `--only` filter (with unknown-id fail-fast) up
  front, so dry-run, `--verify`, and the confirmation-prompt count all reflect the canary scope.
- **Cache leaf is content-keyed + atomically extracted + auto-cleaned** — a short SHA-derived leaf
  avoids Windows `MAX_PATH` under the deep model id, self-invalidates on a snapshot change, and is
  `atexit`-removed.
- **Alias invariant:** the consumer hardcodes `"production"`; the producer's env-configurable
  `SLEAP_ROOTS_MODEL_ALIAS` MUST therefore be `"production"` for the current consumer (documented in
  the README).

### Cross-repo contracts surfaced by the consumer-PR review (report back; not code changes here)

- **Seeded `mode` strings are an A3-params contract.** Arabidopsis has *two* cylinder-family modes in
  the matrix — `cylinder` and `multiplant cylinder` — mapping to *different* lateral models. Whatever
  sends selection params (A3-params / Bloom → `ResolvedParams`) MUST emit the exact seeded `mode`
  string; sending `"cylinder"` for a multiplant scan would silently match the single-plant model.
  The seed's `mode` vocabulary therefore becomes a contract A3-params must honor exactly — flagged in
  the report-back (task 9.3).
- **Shared-weight cards deduplicate in the registry but not in the warm cache.** The 4 canola/
  pennycress/arabidopsis×2 primary cards share weights but get 4 distinct `registry_id`s, so predict's
  warm worker may materialize the same weights up to 4×. This is a **known, accepted** consequence of
  D1 (one card per species is required by the consumer's `species==` filter); a predict-side
  follow-up can dedupe by `weights_checksum`. Recorded so it's an explicit accepted trade-off, not a
  surprise.

### D10 — wandb version: compatible-range + canary + recorded tested-pair, NOT an identical cross-repo pin

The producer writes with `wandb 0.28`; the consumer (predict PR #9) reads with `wandb 0.21.3` — a
7-minor pre-1.0 gap. The two repos never share a process or lockfile; they exchange through the
**server-side registry**, so what must hold is a **wire-format** property (a 0.28-written artifact is
readable by a 0.21.3 reader), not library-version equality. Decision (unanimous across the round-3
review):

- **Do NOT hard-pin both repos to one wandb version.** It couples two independently-released repos'
  cadences and buys nothing without a shared resolver. Downgrading the producer to 0.21.3 would lose
  the load-bearing `link_artifact(aliases=)` API (0.28) and reintroduce the 0.25-era alias workaround.
- **Producer keeps `wandb>=0.28.0,<0.29.0`** (floor is load-bearing; cap blocks silent auto-upgrade to
  an unverified minor). **Consumer should adopt a floor-and-cap range** (minimum `>=0.21.3,<0.22.0`;
  ideally converge upward to the `0.28` band later, gated by a re-canary).
- **The canary is the real evidence:** seed representative cards with the 0.28 writer and round-trip
  them through the consumer's actual 0.21.3 `pytest -m wandb` before the full seed (the *only* true
  skew gate — the producer-side read-back runs 0.28, so it validates alias placement, not the skew).
  Make the canary **representative** (a shared-weight primary + a rice two-crown card, exercising the
  space-in-`mode` and dedup shapes) rather than a trivial soybean primary.
- **Make the point-in-time proof a durable forward contract:** record `wandb_version` in run lineage
  (forensic), **and** document the tested pair (writer 0.28.x ↔ reader 0.21.3, canary-verified) as a
  "W&B compatibility" note in the README, with the rule that **raising the producer's `<0.29` cap
  requires a re-canary + a consumer floor bump**. Report-back (task 9.3) asks predict to pin a tested
  range and add a CI marker that re-verifies on a bump.

### Module layout

```
src/sleap_roots_training/registry/
  __init__.py
  config.py    # resolve_registry_config() from env + require_api_key()          [pure/env]
  chooser.py   # load_selection_matrix(path) + parse_age_window(age_str) + vocab  [PURE]
  cards.py     # expand_rows_to_cards(rows) + card_to_metadata(card) + collection_id(card) [PURE]
  models.py    # resolve_model_dir(model_id, models_root, checksums, *, require_pinned=False,
               #   cache_root=None) — SHA256-verify + junk-free atomic unzip to a content-keyed
               #   (short, self-invalidating) cache leaf + normalize layout  [filesystem]
  lineage.py   # build_lineage(matrix_sha256) + _resolve_git_sha()                [env/subprocess]
  publish.py   # publish_card(run, card, model_dir, cfg) + resolve_all(cards, models_root,
               #   checksums) -> [(card, dir)] (validate-all, pre-network) +
               #   seed_registry(resolved, cfg, run, *, api=None, force=False) +
               #   verify_registry(cfg, expected, api=None) + _existing_collections(api, project)
               #   + _collection_has_production(api, project, coll, alias) (lazy wandb import) [NETWORK]
  data/model_selection.yaml
cli.py         # `seed-registry --models-root <dir> [--selection-matrix <path>] [--execute] [--yes]
               #   [--force] [--only <collection_id>]... [--verify]` (lazy wandb import in net paths)
```

`chooser`/`cards` (and `config`, `models`, `lineage`) are unit-tested with no network. `publish` is a
thin wandb wrapper: minimal-mock unit tests assert the artifact `type`/metadata (exactly the six
keys), `add_dir` target, the exact forward-slash link path + alias, the shared-weights→distinct-
collections property, the duplicate-collection-id abort, and the alias-based skip/`--force` paths;
the real network behavior is verified by the producer-side read-back + the consumer's gated test.

## Risks / Trade-offs

- **Alias placement:** the `production` alias must land on the *registry-linked* entry the consumer
  iterates, not only the source artifact. The `publish.py` unit test (mock) only proves the code
  *calls* `link_artifact(aliases=[alias])` — it cannot prove wandb attaches the alias where the
  consumer reads it. Mitigation: a **producer-side post-seed read-back** (task 9.1) re-runs the
  consumer's read path (`artifact_collections` → `artifacts` → assert alias present) from this repo,
  and the consumer's gated `pytest -m wandb` (task 9.2) is a **required rollout gate**, not optional.
- **wandb version skew** between this producer and predict. Mitigation: pin `wandb>=0.28.0,<0.29.0`;
  reconcile the floor with predict's pin during acceptance.
- **Real seed is an outward-facing, hard-to-undo write** to a shared registry, and `WANDB_API_KEY`
  is often already exported. Mitigation: `seed-registry` **defaults to dry-run**; `--execute` +
  confirmation is required to write (D5); re-seed is idempotent — a card whose collection already has
  the `production` alias is skipped, and moving the alias needs `--force` (D7); the real seed (task
  9.1) runs only with explicit user go-ahead.
- **git-SHA lineage from an installed wheel / dirty tree** could crash the seed or record a wrong SHA.
  Mitigation: the resolver never uses `cwd`, never raises, falls back to the package version, and
  warns on a dirty tree (D6); unit-tested offline.
- **`weights_checksum` is a whole-artifact digest** (the consumer names `artifact.digest` that way),
  so incidental non-weight file changes alter it. Mitigation: idempotency keys on the `production`
  alias, not the digest (D7); `add_dir` drops OS junk; the rerun contract says re-seeds reuse the
  identical snapshot.
- **species/mode value skew** silently breaks the consumer's `==` filter. Mitigation: vocabulary
  validation at load (D8) + acceptance check of seeded values.
- **Cross-platform path corruption:** the registry link target must use forward slashes on Windows
  CI. Mitigation: build it as a literal f-string (never `os.path.join`); the `publish.py` mock test
  asserts the exact forward-slash target; `resolve_model_dir` compares `Path` objects.
- **Lockfile drift:** adding deps without committing `uv.lock`, plus `ci.yml`'s lock-less `uv sync`,
  would only surface at release. Mitigation: commit the regenerated lock (task 0.2) and add
  `--locked` to `ci.yml`.
- **Producer/consumer wandb version skew:** the producer writes with `wandb 0.28`, but the consumer
  (predict PR #9) reads with `wandb 0.21.3` — a 7-minor skew. An artifact-format incompatibility
  would only show at read time. Mitigation: the **canary** (below) reads back one seeded card through
  the consumer's 0.21.3 gated test before seeding the rest; report-back asks predict to set a `wandb`
  floor so a future bump can't silently invalidate the proven compatibility.
- **Matrix drift** from the external xlsx. Mitigation: committed YAML is reviewed in the PR diff,
  provenance-stamped with the source URL + per-model SHA256s; each re-seed re-confirms against the
  live xlsx.

## Migration Plan

Additive, and seeded **canary-first** to de-risk the producer/consumer wandb version skew. After
merge, a maintainer: (1) seeds **one** card via `seed-registry --execute --only <collection_id>`;
(2) runs the consumer's `pytest -m wandb` (task 9.2) — if the 0.21.3 reader can `list_cards()` +
`materialize()` the canary written by the 0.28 writer, the format round-trips; (3) seeds the rest
with a full `seed-registry --execute` (the idempotent skip makes re-running free — the canary is
skipped); (4) runs `seed-registry --verify`. Rollback = remove the `production` alias from the
seeded collections (the artifacts remain as inert versions).

## Open Questions

- Env-var names settled: `WANDB_ENTITY` / `SLEAP_ROOTS_MODEL_REGISTRY` / `SLEAP_ROOTS_MODEL_ALIAS`
  (the registry var is model-scoped so it can't be confused with the `sleap-roots-labels` registry).
  Still trivially swappable to an `SRT_`-prefixed mirror of predict's `SRP_` if preferred.
- Whether a dedicated `sleap-roots-models-production` registry is wanted long-term — deferred; the
  env indirection makes it a later config change.
- Whether to promote the species/mode vocabulary into `sleap-roots-contracts` so producer and
  consumer import one definition (currently reconciled at acceptance, task 9.2) — a follow-up.
