# Design: add-wheat-sorghum-production-cards

## Context

The selection matrix was built as a row-for-row mirror of one file: the models-downloader
`model_chooser_table.xlsx` in the 2025-02-04 snapshot. That assumption is written into three places:

- the yaml header ("Source of truth", "8 physical models");
- `lineage.py`'s `SELECTION_MATRIX_SOURCE` / `SELECTION_MATRIX_DATE` / `MODELS_SNAPSHOT`, which are
  written into every seed run;
- the *Seed Run Lineage* requirement.

Both new rows break it, measured on hpi_dev on 2026-10-03:

| row | zip in the 2025-02-04 snapshot? | row in its chooser xlsx? | what pinned the model |
|---|---|---|---|
| sorghum | yes, under `20250204_models/20250204_sorghum_experimental/` | **no** (the xlsx has the 7 committed rows + the omitted plate row) | the July 2024 sorghum diversity screen's `models_downloader_output/model_paths.csv`; byte-identical copies in BSB vs Torin2 EXP1 and WEEP June 2025 |
| wheat | **no**; it is in the EDPIE Feb 2025 run directory | **no** | EDPIE's `models_downloader_output/model_paths.csv` (crown; its unused primary is dropped) |

The windows (wheat 5–14, sorghum 3–14) are the owner's 2026-10-02 decision (pipeline#118).

**Species spelling**, verified in code:

- Predict compares `s.species == species` (`sleap_roots_predict/model_selection.py:85`) against
  Bloom's `species.common_name`. Bloom stores "Wheat" and "Sorghum"; bloomctl's `resolve_params`
  lowercases them (`params.py:110`).
- The traits chooser does the same (`pipeline_chooser.py:147-149`). sleap-roots#276 proposes
  lowercase rows with these windows.

**Registry probe** (read-only, 2026-10-03):

- None of the three collection ids below exists among 108 model collections.
- `production` is on exactly the 8 existing collections; `candidate` is on none.
- Predict raises on two matching cards (`model_selection.py:182-187`). No existing card has species
  wheat or sorghum, so no selector collides.

**Collection ids** (`collection_id`: `/` and `=` to `-`). This is the one place they are written out:

- `20250401_wheat_models-250328_095645.multi_instance.n-1658` (57 chars)
- `20250204_sorghum_experimental-sorghum_soybean_primary_6nodes-250203_181521.multi_instance.n-1689` (96)
- `20250204_sorghum_experimental-sorghum_soybean_lateral_4nodes-250203_214033.multi_instance.n-590` (95)

## Goals / non-goals

- **Goal:** every seed run says truthfully where its rows and weights came from, and no row can be
  added without saying so.
- **Goal:** the three cards reach the registry under `candidate`, with `production` untouched. No
  single typo and no routine re-seed can make them `production`.
- **Non-goal:** per-artifact provenance. Artifact metadata stays exactly the contract keys.
- **Non-goal:** step 6's mechanism (re-linking the candidate versions with no new versions). This
  change only makes step 6 require `--promote`.

## Decisions

### D1. Two provenance fields, because there are two provenance questions

*Why does this row exist with this window?* belongs to the **row**. *Where did these bytes come
from?* belongs to the **physical model**. The generalist primary backs four rows and has one origin.

```yaml
models:
  - species: wheat
    mode: cylinder
    age: "5, 6, 7, 8, 9, 10, 11, 12, 13, 14"
    primary_model_id: null
    lateral_model_id: null
    crown_model_id: 20250401_wheat_models/250328_095645.multi_instance.n=1658
    source: "owner decision 2026-10-02 (talmolab/sleap-roots-pipeline#118), matching past production runs"

origins:   # keyed exactly like checksums; covers exactly the referenced models
  <model_id>: {snapshot: <"YYYYMMDD" | null>, location: <str>, pinned_by: <str>}
```

`location` is the directory under which `<model_id>.zip` sits. It is relative to a run or a
snapshot, never a share or machine path. All three keys are required, and `snapshot: null` must be
explicit, so that an omitted key cannot claim "ships in no snapshot" silently.

The committed strings:

| models | `snapshot` | `location` | `pinned_by` |
|---|---|---|---|
| the 8 existing | `"20250204"` | `models-downloader 20250204_models/` | `model_chooser_table.xlsx (snapshot 20250204)` |
| sorghum primary, lateral | `"20250204"` | `models-downloader 20250204_models/` | `July 2024 sorghum diversity screen run: models_downloader_output/model_paths.csv (same bytes in the BSB vs Torin2 EXP1 and WEEP June 2025 runs)` |
| wheat crown | `null` | `EDPIE Feb 2025 run directory` | `EDPIE Feb 2025 run: models_downloader_output/model_paths.csv` |

Row `source` strings:

- the 7 existing rows: `models-downloader model_chooser_table.xlsx, snapshot 20250204 (verified 2026-07-04)`;
- the 2 new rows: as in the example above.

The models-downloader repo URL moves into the rewritten header once.

The wheat run directory's on-disk name includes a collaborator's full name. The location uses
"EDPIE Feb 2025 run" and stays within the owner's run-relative decision without publishing it.

### D2. Loader order and coverage

The check order, each failure a `ValueError` naming the row or model and the key:

1. required keys;
2. species/mode vocabulary;
3. model-id types;
4. per-row `source` (a non-empty `str`);
5. after all rows are read, `origins`:
   - it must be a mapping, and an absent or `null` map is reported as the first uncovered model;
   - each referenced id needs a mapping entry, with `location` and `pinned_by` as non-empty `str`
     and a `snapshot` key that is a `str` or `null`;
   - no entry may exist for an unreferenced id.

Existing tests that assert earlier failures keep their own message. Checking coverage after all rows
means a later row's missing `source` is reported before an earlier row's missing origin.

The coverage check is stricter than `checksums`, which tolerates extras. That is deliberate: an orphan
origin is a stale claim. `SelectionRow` gains `source: str`; `SelectionMatrix` gains
`origins: dict[str, ModelOrigin]`.

The run-relative rule is a property **of the committed file**, checked by a test. It is not a loader
rule. The loader cannot know which paths are sensitive. The test rejects a `location` that starts with
`/`, or contains `:\`, `\\`, `hpi` or `users/`.

### D3. Lineage: lists of records, scoped to the seed's cards

`build_lineage(matrix_sha256, cards, matrix)` keeps `git_sha`, `git_dirty`, `matrix_content_sha256` and
the three versions. It adds:

- `row_sources`: one `{species, mode, age, source}` per row that **backs** an in-scope card, in file
  order. A row backs a card when it contributes one of that card's selectors, that is, the row names
  the card's model in the card's root-type slot. `age` is the row's raw string.
- `model_origins`: one `{model_id, snapshot, location, pinned_by}` per in-scope card's model, sorted
  by `model_id`;
- `registry_target`: `{entity, registry, alias}`. Added after the pre-PR review: without it a
  candidate run and its later `--promote` run have the same shape, and aliases move.

They are lists because model ids contain `/`, `=` and `.`, so ids stay values, not config keys. They
are scoped to the invocation's scope, published or skipped, because a run under `--only` touches only
those collections. Reading them back through the Api may wrap values (`{"value": …}`); task 14.4 reads
accordingly.

### D4. Guard 1: a non-default alias under `--execute` requires `--only`

The guard sits after the dry-run return and before `_require_api_key()`, so it costs no credential,
prompt or network. `--force` doesn't bypass it. A dry run and `--verify` are unaffected. Without it,
the per-alias idempotency read finds nothing under the new alias and re-publishes every card.

### D5. Guard 2: a first-time `production` link requires `--promote`

Guard 1 can't stop the two paths reviewers found to `production`:

- (a) **The candidate command with its alias prefix lost.** A PowerShell `$env:…=""` *deletes* the
  variable, and `--yes` hides the only prompt that names the alias.
- (b) **After merge, any routine default-alias `--execute` without `--only`.** The skip check is
  per-alias, so a `candidate`-only collection is re-published and gains `production`.

The rule: under the default alias, `--execute` first computes
`publish.unpromoted_collections(cfg, cards, api=None)`: the in-scope collections that are absent or
have no version carrying the alias. If that list is non-empty and `--promote` is not given, the command
exits 1 with a `ClickException` naming them, and nothing is published.

- **Existence first.** A collection missing from `_existing_collections` is unpromoted **without**
  calling `_aliased_artifact`.
  - In wandb 0.28, `api.artifacts(type_name, name)` for an absent collection raises
    `ValueError("Unable to parse 'Artifacts' response data")` (`wandb/apis/public/artifacts.py:918-924`).
  - `seed_registry:237-241` already guards this the same way.
  - The shared test fake is made to raise the same way, so a missing check fails a test.
- **Lazy `wandb.Api()`.** It is built inside `unpromoted_collections` when `api is None`, as
  `seed_registry` and `verify_registry` do. Constructing `wandb.Api()` validates the key over the
  network, so the CLI never builds it on the guard path.
- **Placement.** The pre-pass runs after `_require_api_key()`, and before the confirm prompt,
  `resolve_all` and `wandb.init`. So no run is minted, and the prompt never offers something that would
  be refused.
- **`--force`.** The pre-pass runs even though `--force` skips the idempotency read.
- **API errors** in the pre-pass become a `ClickException` (fail closed, no traceback).
- **`--promote` is valid only with `--execute`, under the default alias, and with `--only`.** It is
  checked before the `--verify` branch and the dry-run return (so earlier than guard 1, which sits after
  the dry-run return). Misuse is therefore a usage error (exit 2) in every mode, and a promotion always
  names its collections.
- **Re-seeds of already-`production` collections** are unaffected: the list is empty.
- **Step 6** becomes `… --only <3 ids> --promote`.
  - Its "no new versions" outcome relies on `log_artifact` deduplicating to the candidate source
    version. That holds only with the same `WANDB_ENTITY`, `SLEAP_ROOTS_SEED_PROJECT` and staged zips
    (`publish.py:39-42`).
  - Adding a second alias to an existing membership is server behaviour this change does not test, so
    step 6 confirms "no new `:vN`" on read-back.
- **First-time seeding of any future species** needs `--promote` too. That is the intent: it is a
  production deploy.
- **Accepted residual risk.** `seed_registry` re-reads the registry itself. If someone unlinks
  `production` from a collection between the pre-pass and the publish, that run re-links it without
  `--promote`.
  - The window is seconds, or minutes at an unanswered prompt.
  - Hitting it takes a concurrent operator, and the result restores the state that was just removed.
  - Closing it would move the check into the public `seed_registry`, which is out of scope.

### D6. Alias normalization and visibility

`resolve_registry_config` strips `SLEAP_ROOTS_MODEL_ALIAS`:

- **Unset** gives `production`.
- **Set but blank** gives `""`, never `production`, and does **not** raise there.
  `inventory/verify.py:249` calls the same function only for the entity, so raising would break
  `inventory labels` over an unrelated variable. `seed-registry` rejects an empty alias as a CLI error
  in every mode, before any wandb call.
- **`" production "`** is therefore the default alias, and guard 2 applies.

Every `seed-registry` invocation, `--verify` included, prints this as its first output once the alias
resolves:
`target: <entity>/<registry> alias <ascii(alias)> (from SLEAP_ROOTS_MODEL_ALIAS | default) seed project <seed_project>`.

- `ascii()` shows hidden characters that `str.strip()` keeps (U+200B). Unlike `repr()`, it also
  escapes printable non-Latin text, which a cp1252 console cannot encode when output is redirected.
- The seed project is shown because step 6's outcome depends on it.
- `--verify` echoes too, because D7.6 reads verify output under two aliases.
- `WANDB_API_KEY` is never on this path.

### D7. Operator procedure

The README becomes the canonical, generic runbook: non-default alias, `--only`, `--promote`, verify
interpretation, and unlink rollback. This section keeps only what is change-specific. Groups 13 and 14
in `tasks.md` tick these steps and record their outputs; they do not restate them.

**Before merge, on the branch** (no writes, no lineage recorded):

- **D7.1 Stage.** Put a scratch `--models-root` outside every worktree, holding the three zips at their
  `<source_model_id>.zip` paths, copied from hpi_dev. Record `sha256sum` of each against the spec
  values.
- **D7.2 Dry-run** under `candidate` with `--only <3 ids>`. It prints the target line with
  `alias 'candidate' (from SLEAP_ROOTS_MODEL_ALIAS)` and three `[ok]`, none `UNPINNED`.
- **D7.3 Credential-less guard checks.** Run them through the Bash tool as
  `env -u WANDB_API_KEY NETRC=/nonexistent uv run --locked sleap-roots-training seed-registry …`.
  - A set `NETRC` that names no file counts as no credential (`config._resolve_netrc_path`), and the
    real `_netrc` is not touched.
  - Each check uses `--models-root <empty scratch dir>`, so even a broken guard plus a broken
    credential check stops at `resolve_all`.

  Expected:
  - `SLEAP_ROOTS_MODEL_ALIAS=candidate … --execute --yes` (no `--only`) exits 2, with output containing
    `candidate` and `--only`.
  - `… --execute --yes --promote` (no `--only`, default alias) exits 2, with output containing
    `--promote`.

  A credential error instead of either means the guard did not fire.

**After the squash-merge:**

- **D7.4 Prepare.**
  1. `git fetch origin && git worktree add --detach <path> <squash-sha>`.
  2. `uv sync --locked`.
  3. Check that `git status --porcelain` is empty.
  4. Check that `env | grep -E '^(WANDB_|SLEAP_ROOTS_|NETRC)'` shows only intended values. In
     particular `SLEAP_ROOTS_TRAINING_GIT_SHA`, `SLEAP_ROOTS_SEED_PROJECT`, `WANDB_ENTITY`, `WANDB_MODE`
     and `WANDB_SWEEP_ID` must be unset.

  Every command runs through the Bash tool (POSIX env prefix) with `uv run --locked`. Then:
  - **Read-only probe:** none of the 3 ids exists, `production` is on exactly 8, and `candidate` is on
    0.
  - **Live guard-2 check that cannot write:**
    `… seed-registry --models-root <empty dir> --only <3 ids> --execute --yes` under the default alias
    exits 1 with the `--promote` refusal. A broken guard would fail at `resolve_all` before
    `wandb.init`. This also exercises the absent-collection path against real wandb.
- **D7.5 Publish.** Ask the owner, then run
  `SLEAP_ROOTS_MODEL_ALIAS=candidate uv run --locked sleap-roots-training seed-registry --models-root
  <dir> --only <3 ids> --execute --yes`.
  - `--yes` replaces the prompt with the owner's explicit go-ahead, because the shell is
    non-interactive.
  - If the alias prefix is lost, guard 2 refuses the run.
- **D7.6 Verify** (read-only):
  - `SLEAP_ROOTS_MODEL_ALIAS=candidate … --verify --only <3 ids>` gives 3 present, 0 legacy.
  - A plain `… --verify` gives 8 present, exactly the 3 ids missing, 0 orphans, 0 legacy. It exits 1
    on those 3, which is the evidence none is `production`.
  - Read back each artifact with a fresh `Api()`: `:vN`, digest, aliases (never `production`), and
    metadata equal to `card_to_metadata`.
  - In the seed run config, `git_sha` equals the squash SHA, `git_dirty` is false, and
    `model_origins` / `row_sources` hold exactly 3 models / 2 rows.
- **D7.7 Record.**
  - A follow-up `docs(registry)` PR ticks group 14 with dated notes; the archive PR comes after it.
  - After the owner sees the text, post on #72 and #118: the collection names and versions, the
    `SRP_WANDB_MODEL_ALIAS=candidate` read instruction, and the step-6 command shape.
  - `git worktree remove` the detached worktree.

**Undo D7.5** if a card is wrong. For each collection: fetch the registry link, assert `is_link`, call
`unlink()` (never `save()`), and re-read with a fresh `Api()`. `is_link` and `unlink()` exist in the
pinned wandb 0.28.0 (`artifact.py:720, 2551`).

## Risks

- **Merge opens nothing.** With guard 2, the post-merge window reviewers flagged needs `--promote` to
  cross.
- **Until step 6, a full default-alias `--execute` without `--only` is refused**, because the 3 new
  collections are unpromoted. That is intended.
  - To re-seed the 8, pass `--only <8 ids>`.
  - A re-run after a partial promote repeats `--only … --promote`.

  The README states both.
- **A training config may now say `species: wheat`.** That is legitimate. The labeling path still
  fails at `lookup_skeleton` before staging (`package.py:225` → `skeletons.py:405-412`), and a test
  pins it.
- **Custom matrices without provenance stop loading.** This is intended and marked BREAKING. The
  failure names the row or model.
- **`--verify` exits 1 on `main` until step 6.** This is expected. The README says so, so operators
  read the missing list rather than ignore the exit code.
- **`models.py`'s rejection message says "NOT snapshot-pinned".** It becomes "NOT checksum-pinned" to
  match the modified *Legacy Model Directory Resolution*.
