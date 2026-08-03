# Design — labeling-package generator

## Context

The code being ported has produced every artifact in `wandb-registry-sleap-roots-labels`, but has
never been read by anyone but its author. Two consequences shape this design: the port must be
**faithful before it is improved**, and the one behavior we already know is wrong (`embed=False`)
must be changed **on purpose, with a test**, not quietly during translation.

## Task 0 findings (source read 2026-08-03, completed 2026-08-03)

Task 0 gates everything below. All four scripts have now been read end to end. Seven findings change
the shape of this change; they are recorded here rather than absorbed silently, per Decision 1.

### F1 — The workflow is four scripts, not two — **source now complete**

`build-labeling-package.md` Phase 2 runs four scripts. The Box onboarding bundle
(`Phenotyping_team_GH/sleap-roots-training/onboarding/`) initially carried two; the remaining two
were added to the same share and obtained 2026-08-03:

| Doc step | Script | Obtained |
| --- | --- | --- |
| 1. Stratified sampling | `select_samples.py` | 2026-07-29 |
| 2. Copy images (`:160-167`) | `copy_selected_images.py` | **2026-08-03** |
| 3. Build `.slp` | `build_slp_project.py` | 2026-07-29 |
| 4. Generate README (`:210-217`) | `generate_readme.py` | **2026-08-03** |

**Step 2 is load-bearing**, which is why its absence blocked the port. `select_samples.py:109-123`
emits `output_filename` — a *curated name* (`{accession}_{qr}_age{N}_{frame}.jpg`) — alongside
`source_image`, the real path in the scan directory. `build_slp_project.py:109` then reads
`images_dir / row["output_filename"]`. `copy_selected_images.py` is the only thing that bridges them;
`build-labeling-package.md:169` confirms it is Step 2's job.

The failure mode is quiet, which is why it matters: `build_slp_project.py:113-116` warns and
`continue`s past any scan with missing images, then still writes both `.slp` files (`:194`, `:205`)
and exits 0. Run against an unpopulated `images_dir`, it reports success and produces empty label
files. F5 shows the copy step fails the same way, so the two compose. **Characterization tests must
pin both before anything changes.**

**Status: resolved.** The port is unblocked and every step now has an original to characterize
against. The vault remains the upstream source of truth —
`c:\vaults\sleap-roots\labeling-packages\` (`build-labeling-package.md:58`, `:140`, `:264`) — and the
porting commit records the Box share and copy dates, since the vault repo's history does not survive
the copy.

### F5 — The copy step tolerates missing sources and exits 0, so the silent-empty chain has two links

`copy_selected_images.py:36-39` warns on a missing `source_image`, increments a counter, and
`continue`s; `:45-46` prints a summary warning but **never sets a non-zero exit status**. Combined
with `build_slp_project.py:113-116`, a run whose sources are entirely unreachable prints two rounds
of warnings, writes both `.slp` files, and exits 0 twice. Nothing between selection and a published
artifact treats "no images" as an error.

`:32` computes `rel_path = row["source_image"].lstrip("./")` — a *character-set* strip, not a prefix
strip. `source_image` is written by `select_samples.py:122` as `str(scan_path / image_filename)` and
inherits whatever `scan_path` holds in `scans.csv`, so an **absolute** `scan_path` would have its
leading separator eaten, resolve nowhere, and report every row missing — an empty package, exit 0,
with no data actually missing.

**Resolved 2026-08-03 (task 0.9): that cannot arise from Bloom's own output.** `bloomctl` derives
`scan_path` as `f"images/Wave{n}/Day{age}_{date}/{qr}"` (`cyl/download.py:47-51`, pinned by
`tests/test_download_metadata.py:44`) — always relative, never absolute. And `Path()` normalization
in `select_samples.py:122` strips a leading `./` before it is ever written, so `lstrip("./")` has no
`./` to remove either. **The strip is dead code guarding a latent trap** — it changes nothing on any
real input and mis-resolves the one input it was never given. The port replaces it with an explicit
resolution rule (3.4); there is no shipped absolute-path behavior to preserve as characterization.

The warn-and-continue chain above is *not* resolved by this — it is live, and F8 gives it a
first-class trigger. **The port must make an empty or partial copy a failure.** Deviation, recorded
in section 7.

The manifest also remains non-portable across platforms: `str(Path(...))` emits backslashes on
Windows and forward slashes here, so a manifest written on the vault machine does not resolve on
Linux. The port normalizes to POSIX separators on write.

### F8 — Bloom's `scan_path` is relative to `scans.csv`, but the copy step resolves it against the *parent*

Looking for F5's absolute path turned up a live off-by-one-directory instead.

`bloomctl`'s `scan_relative_dir` is documented as "relative to the output dir (where `scans.csv`
lives)" (`cyl/download.py:47-51`) and emits `images/Wave2/Day14_2026-05-11/QR-1` — **no
`images_downloader_output/` segment**. The download dir is exactly that folder
(`build-labeling-package.md:25`, `:68`). But `copy_selected_images.py:33` joins `source_image` to
`experiment_dir`, the folder that *contains* `images_downloader_output/`, and its own comment (`:31`)
documents the expected form as `./images_downloader_output/images/Wave1/...` — one segment longer,
with a `./` prefix that `bloomctl` never writes.

So the two conventions differ by exactly one path segment:

| Producer | `scan_path` written | Base it is relative to |
| --- | --- | --- |
| `bloomctl cyl download` (verified — source + test) | `images/Wave1/Day3_.../QR` | `images_downloader_output/` |
| legacy `bloom cyl download` (inferred from `copy_selected_images.py:31`) | `./images_downloader_output/images/Wave1/...` | `experiment_dir` |

Feed a `bloomctl`-generated `scans.csv` to the current copy step with the documented `experiment_dir`
argument and **every** row misses by that segment, every row warns, and the run exits 0 with an empty
`images/`. That is F5's silent-empty failure reached with correct, complete, present data — the
scenario F5 hypothesized via absolute paths, arriving through a different and much more likely door,
since `bloomctl` is the sanctioned tool going forward (`bloom-cli-setup.md:1-8`) while the historical
WEEP data came from the legacy CLI.

**Confidence is asymmetric and worth stating.** `bloomctl`'s convention is verified from source and a
test. The legacy convention is *inferred from a code comment* — the legacy Node CLI has been removed
from the `bloom` repo, so it cannot be read. The port therefore must not hardcode either base: it
should resolve `source_image` against the directory containing the `scans.csv` it was derived from,
record that base in the manifest, and fail loudly when a row does not resolve — which makes the
question moot for both producers. Deviation, recorded in section 7.

### F6 — `output_filename` is not guaranteed unique, and the copy step overwrites silently

`select_samples.py:105-111` keys its `scan_view_counter` by **`scan_id`**, but builds the filename
from `(accession_name, plant_qr_code, plant_age_days, frame_num)` — `scan_id` never appears in the
name. Uniqueness therefore holds only if each `(plant_qr_code, plant_age_days)` pair maps to exactly
one `scan_id`. Nothing checks that, and the workflow's own QC config contemplates the opposite:
`build-labeling-package.md:122` sets `columns.replicate: "scan_id"` and requires it to *differ* from
the barcode column.

If it is violated, every layer absorbs it: `copy_selected_images.py:41` uses `shutil.copy2`, which
overwrites without complaint, so N manifest rows collapse into fewer files while `copied` — a count
of copy *calls*, not of resulting files (`:42`) — still reports N. `build_slp_project.py:108-109`
then points two different scan `Video`s at the *same* image path, and one scan's predictions are
rendered over another scan's image. That is a wrong labeling package that looks entirely healthy.

**Resolved 2026-08-03 (task 0.8): a repeated `(qr, age)` is an artifact of the record, not a
legitimate replicate — it does not occur in real data.** That settles the fix in a specific
direction, and it is the opposite of what the QC config's `columns.replicate: "scan_id"` first
suggests: the collision is not a naming deficiency to be repaired by widening the key, it is a
**signal that the upstream record is wrong**.

So `scan_id` stays *out* of `output_filename`. Adding it would change every curated filename in order
to accommodate a state that should not exist, and would break comparability with the eight already-
published collections. The uniqueness assertion at manifest-write time (2.9) stays — but it is a
data-integrity check, and on collision it must **fail loudly and name the offending `scan_id`s**
rather than silently disambiguate them. Disambiguating would paper over the artifact and produce a
package built from a record nobody was told to go fix.

Because the state does not occur, no retroactive audit of the published collections is owed; this
does not become an #11 work item.

Related, and worth pinning while the tests are being written: `build_slp_project.py:105,136` derives
each frame's position by sorting on `view_index` and enumerating, and never reads the manifest's
`frame_index` column — while `output_filename` embeds `frame_num` from that same counter. The two
derivations agree today only because `selected_views` is ascending. They are independent, and a
characterization test should say which one is authoritative.

### F7 — `generate_readme.py` is where the package metadata already lives — as hand-edited prose

This sharpens F4 rather than repeating it. The metadata #10's `LabelCard` wants is not absent from
the pipeline; it is present in `generate_readme.py`, unstructured, and duplicated across sites that
must be kept in sync by hand:

| Metadata | Where it lives today | Also hardcoded at |
| --- | --- | --- |
| `bloom_experiment_id` (`10102496`) | `generate_readme.py:66`, English prose | — |
| accession id → name | `:85-89`, module-level dict of three WEEP ids | passed *again* via `select_samples.py --accession-names` |
| skeleton nodes (6 primary / 4 lateral) | `:58-60`, English prose | `build_slp_project.py:43-58` |
| output `.slp` filenames | `:31-32` | `build_slp_project.py:193`, `:204` |

So the accession map has two sources of truth and the skeleton has two; a per-crop run means editing
prose in one file and constants in another and hoping they match. Decision 3 (a real package metadata
file) and Decision 7 (a committed skeleton table) are what collapse each of those pairs to one
source — and `generate_readme.py` becomes a *renderer* of that metadata rather than a fourth place it
is typed. It is a fourth per-crop hardcode site, not merely delivery packaging.

One consequence is worth its own test. `:91` computes `image_count` by globbing `images_dir` for
`*.jpg` — counting files on disk, not manifest rows. Under F5 or F6 the README therefore reports the
*reduced* count truthfully while `sample_manifest.csv` claims more. It is the one place the
discrepancy surfaces, and it surfaces as English nobody diffs. `:96` has the same shape:
`views_per_plant = len(rows) // plant_count` is integer division that silently misreports whenever
views per plant are unequal.

### F2 — The Bloom coupling is smaller in the code and larger in the workflow

Resolves the "unknown external couplings" risk below. `select_samples.py` makes **no network calls**:
it reads `10_final_data.csv` (sleap-roots-analyze QC output) and `scans.csv` (from a prior Bloom
download), plus an optional `--accession-names` JSON passed on the command line. The re-scope
trigger in task 0.3 ("the scripts orchestrate downloads, or carry credentials handling") does **not**
fire for the scripts.

It fires for the *workflow*. `build-labeling-package.md` Phase 0 runs `bloom cyl download` and a
direct `psql` against the Bloom production database at a hardcoded IP, with credentials read from a
local `.env`, to map `accession_id` → name. Phase 1 additionally depends on a full
`sleap-roots-analyze run-all` with golden config templates.

**Decision: excluded from this change.** `--accession-names` stays a caller-supplied argument, as it
is today; `select_samples.py:99` already falls back to the numeric id as a string when it is absent,
so the generator is fully functional without it. Bringing production-database credential handling
into a change that currently touches no network is exactly the absorption task 0.3 warns against.
The workflow doc records the step as a manual prerequisite.

### F3 — A widened re-run is **not** a superset, which contradicts Decision 6

Decision 5 requires it and Decision 6's "re-derive + republish" recovery path depends on it. The
ported behavior does not provide it, in two independent ways:

- **Plants.** `select_samples.py:71-77` calls `.sample(n=min(plants_per_group, ...), random_state=seed)`.
  A fixed `random_state` makes a given `n` reproducible, but *not* nested: drawing `n=10` does not
  return the `n=5` draw plus five more. Widening re-draws.
- **Views.** `:85-87` computes `step = 72 // views_per_plant`. Three views give `[1, 25, 49]`; four
  give `[1, 19, 37, 55]` — not a superset. Six give `[1, 13, 25, 37, 49, 61]`, which is. The
  guarantee holds only for particular multiples, by coincidence rather than design.

Selection *is* deterministic for identical inputs (seeded draw, sorted group keys, stable
within-group order), so Decision 5's first half survives. Its second half — and the recovery path
built on it — does not. Making widening monotone is a **deliberate, recorded deviation** under
Decision 1, not an incidental fix, and it must come after the characterization tests pin the current
behavior.

### F4 — No script writes *structured* package metadata, and `total_views` is hardcoded

Decision 3 describes the package directory as carrying "the package metadata needed to build a
`LabelCard`". No machine-readable file exists today. The actual output is `README.md`, `images/`, two
`.slp` files, and `sample_manifest.csv` — no capture mode, no skeleton name, no
`bloom_experiment_id` in any form a consumer can parse. Decision 3 is therefore **new design, not a
port**, and its tasks should read that way. **Refined by F7:** the values themselves do exist, as
hand-edited prose in `generate_readme.py` and as constants duplicated in `build_slp_project.py`, so
the work is to give them one structured home — not to invent them.

Separately, `select_samples.py:85` hardcodes `total_views = 72` with no validation. An experiment
with a different view count silently selects wrong indices rather than failing.

## Section 2 findings (port executed 2026-08-03)

Surfaced by the characterization pass, not by reading. Both were invisible to the source read: the
first because the workflow doc routes around it, the second because it needs two runs to see.

### F9 — The multi-file glob branch cannot express the layout it was written for

`select_samples.py:47` globs `cleaned_path.parent.glob(cleaned_path.name)`, which can only match a
wildcard in the *filename*. But QC writes one `10_final_data.csv` per age-group **directory**, and
the branch's own logging (`:51`, printing `f.parent.name`) assumes exactly that — it labels each
loaded file by its parent directory, which is only informative when the files sit in different
directories. Passing `<qc_out>/*/10_final_data.csv` sets `parent` to a literal `*` directory, which
does not exist, so the branch raises `FileNotFoundError` for its intended input.

Nobody noticed because the workflow doc never exercises it: `build-labeling-package.md:128-133`
concatenates the per-age-group files with a hand-written `pd.concat` in Phase 1 and passes the
single `all_cleaned.csv` to the script. The glob branch is therefore dead code in the documented
path, and the manual concat is a workaround for a bug rather than a step with a reason.

Held as a strict `xfail` against the port; the fix and its consequence for the workflow doc belong
to the deviation pass.

### F10 — Determinism holds for identical bytes, not for identical content

Task 2.4 expected an immediate GREEN and got one for the stated property: the same `scans.csv`
selects the same frames on every run. The characterization pass then found the property is narrower
than Decision 5 needs. `.sample(random_state=seed)` draws by *position* within the group, so
re-exporting `scans.csv` with the same rows in a different order selects a different set of plants.

That matters because `scans.csv` is a Bloom export, not a committed artifact: the recovery path in
Decision 6 re-fetches it. A re-download that returns the same scans in a different order silently
produces a different label set — the same failure F3 describes, reached without changing any
parameter at all. The 2.7 fix closes both, since ordering by a content-derived key does not depend
on row order.

## Decision 1: Port first, change second — characterization tests before behavior changes

Sequence: bring each script in with its behavior preserved, pin that behavior in tests, *then* make
the embed change as its own visible commit.

The alternative — port and fix in one pass — makes every later "did the port break something?"
question unanswerable, because there is no commit where the ported code demonstrably matched the
original. That matters more than usual here: the originals are the only executable description of
how eight published artifacts came to exist, and the sample-selection logic in particular
(`select_samples.py` — which frames, in which order, per scan) has downstream consequences nobody has
written down.

**Any deviation forced during the port gets recorded in tasks.md**, not silently absorbed. If a
script reaches something unavailable here (a Windows path convention, an interactive prompt, an
unpinned import), the deviation is a task with a stated reason.

## Decision 2: Embed in the *builder*, not in `publish-labels`

Issue #26 proposes calling `save_slp(..., embed=True)` "as an explicit, tested step of the publish
pipeline." **This design puts it one layer earlier** — in the package builder — and makes
`publish-labels` *verify* embeddedness rather than perform it.

Reasoning:

- **The package directory is the handoff.** If the `.slp` inside it is only embedded once
  `publish-labels` runs, then the on-disk package is not a complete artifact: it is a thing that
  looks publishable but references a filesystem. Anyone who builds a package and inspects it before
  publishing gets the broken-reference behavior we are trying to abolish.
- **It keeps this change unblocked.** `publish-labels` belongs to #10, which cannot start until
  contracts `0.1.0a6` releases. Embedding in the builder means the fix ships with the port instead of
  waiting behind a dependency it has nothing to do with.
- **Verification is cheap and belongs at the boundary anyway.** #10's publish path should fail fast
  on a non-self-contained `.slp` regardless of who embedded it — that check is what makes the
  guarantee hold against a package built by an older tool or by hand.

Net effect is what #26 asks for — no external-reference `.slp` is ever published — reached at a layer
that does not depend on a blocked change.

**Confirmed 2026-08-03 (task 0.4): move it a layer earlier, as proposed.** This supersedes #26's
stated placement; the porting commit should say so explicitly, so the issue and this change do not
read as contradicting each other.

## Decision 3: The package directory is a named contract, not an implementation detail

A labeling package is a directory containing the embedded `.slp`, `sample_manifest.csv`, and the
package metadata. Written as a spec requirement here rather than left implicit, because two separate
changes read it: this one writes it, #10's `publish-labels` consumes it and builds a `LabelCard` from
it. An implicit layout would make that seam the place they disagree.

`sample_manifest.csv` carries one row per labeled frame with the columns #10's audit enumerated —
`scan_id`, `plant_qr_code`, `plant_age_days`, `accession_id`, `accession_name`, `wave_number`,
`view_index`, `frame_index`, `source_scan_path`, `source_image`, `output_filename`. That row-level
provenance travelling *inside* the artifact is the whole point: it is what lets a consumer recover
the exact scans, plants, and accessions without a working `Z:` mount — the failure this pipeline has
already suffered once.

## Decision 4: `sleap-io` becomes a runtime dependency

This is the first code in the repo that reads or writes `.slp` files; `sleap-io` is not currently a
dependency and there are no optional-dependency extras to slot it into.

**Decided 2026-08-03: core `dependencies`, not an extra.** Building labeling packages is first-class
repo functionality reachable from the CLI, and the project's stated convention is that `sleap-io` is
consumed as a library pinned to a release. An extra would mean the CLI has a subcommand that fails on
import for a default install — the kind of surprise that argues for extras only when the dependency
is heavy (`sleap-nn`, torch) rather than merely new.

`feat/add-train-backend-extra` does not bind this; `labeling` does not become an extra. No
import-time guard and no install hint are needed — 1.1 adds a plain pinned runtime dependency.

## Decision 5: Selection is deterministic and recorded

Whatever selection strategy the ported script uses, the same inputs must yield the same frames, and
the chosen frames must be recoverable from `sample_manifest.csv` alone. Without determinism, the
"re-derive + republish" recovery path in Decision 6 is not a recovery path — re-running produces a
different label set, and the new version is not a superset of the old one.

If the original relies on unseeded randomness or filesystem iteration order, making it deterministic
is an explicit, recorded deviation (Decision 1), not an incidental cleanup.

**Resolved by F1–F3 (2026-08-03).** Determinism holds — the draw is seeded and the group and
within-group orders are stable. **Monotone widening does not**, in both the plant and view
dimensions. Since Decision 6 depends on it, this change must make widening monotone as a stated
deviation: a stable ordering over an explicit key with the wider run taking a prefix-superset of the
narrower one, rather than a fresh `.sample()` draw per `n`. Sequenced after the characterization
tests, so the current behavior is on record first.

## Decision 6: Continue-labeling is re-derive + republish

Adding frames to an existing labeled scan is: re-fetch the raw scan via `bloomctl download
--experiment-id <id>`, re-run selection with a wider frame set, build, publish a new version.

Not edit-in-place, for two reasons that compound. `LabelCard`'s Bloom-trace fields tie a package to
the experiment it came from, so re-deriving from that experiment is the path that keeps the card
truthful. And de-embedding an existing `.pkg.slp` to widen it does not work — see the `save_slp`
truncation in proposal.md. W&B artifact versions being immutable snapshots makes this the natural
grain anyway.

This is documentation, not code: the design records it, the workflow doc states it, and no
implementation tries to prevent the alternative.

## Decision 7: Per-crop skeletons come from a committed table, and it is the *native* skeleton

`build_slp_project.py:43-58` hardcodes a 6-node `soybean_primary` and a 4-node `soybean_lateral`,
and names its outputs `soybean_weep_*` (`:193`, `:204`) — while `build-labeling-package.md:13-21`
advertises a `--crop` argument and `:45-51` tabulates five crops. The script was edited per crop by
hand. Crop parameterization is in scope for this change, and it is ours to build: there is no
parameterized original to port.

**The node counts live in a committed, provenance-stamped `labeling/data/skeletons.yaml`**, keyed by
`(species, root_type)` — mirroring `registry/data/model_selection.yaml`, which already solves this
exact problem (source URL and snapshot date in the header, SHA256 into run lineage, validated on
load with row-numbered errors). The two tables also align: the doc's skeleton table splits rice by
age (young 2–5 DAG primary + crown; old 6–10 DAG crown only), which is how `model_selection.yaml`
already keys its rice rows, so the new table can be cross-checked against the existing one rather
than only hand-transcribed.

**This is the *native* skeleton, not the unified one.** `docs/roadmap.md:422` lists "the common
skeleton / node count per root type for unification" as an open question set at **Tier 2.7**, which
itself depends on #10 (`roadmap.md:201` — node counts are today recoverable only by opening each
`.slp`). Those are different numbers serving different purposes: this table is **descriptive** (what
a labeler must label with so a new package matches the existing corpus), Tier 2.7's is
**prescriptive** (a tuned choice validated by a node-count sweep, not yet made). If someone later
folds this table into the Tier 2.7 decision, new labeling packages silently stop matching the
corpus they exist to extend. The table's header must say so.

**Sourcing: transcribe, then verify.** `build-labeling-package.md:43` calls its own table advisory —
"Query the Bloom database or check existing test data … to confirm node counts" — and it has holes:
no pennycress (which is in `SPECIES_VOCAB` and has two `model_selection.yaml` rows), and canola
lateral at 3 nodes where soybean and arabidopsis are 4. The authoritative record is the eight
published collections in `wandb-registry-sleap-roots-labels`, which is also what `#10`'s
`LabelCard.node_count` will validate against via the contract's skeleton-coherence check. So: commit
the doc's table now with a header marking it advisory and unverified, and add a test that reads the
published collections and fails on any disagreement. The audit becomes a test rather than a
prerequisite, and the port is not blocked behind a multi-gigabyte download.
*Alternatives considered:* derive the table from the artifacts up front — authoritative, and it
settles pennycress and canola outright, but it front-loads a network step and 170 MB–1.2 GB per
collection before a line of porting. Deferred into the verification test, not skipped.

**Pennycress has no row.** The table ships incomplete and its loader fails loudly on a missing
`(species, root_type)` rather than defaulting — a wrong node count produces a labeling package that
looks fine and cannot be combined with anything.

## Risks

- **The port's source is a Box copy, not the vault repo's history.** Authorship and commit context do
  not survive; the ported commit should say where the code came from and when it was copied.
- ~~**Unknown external couplings.**~~ **Resolved by F2.** `select_samples.py` makes no network calls
  at all; the Bloom coupling lives in the workflow doc's Phase 0 (a `psql` against the production
  database with credentials from a local `.env`) and is excluded from this change.
- ~~**The port is blocked on source material we do not have (F1).**~~ **Resolved 2026-08-03.** All
  four scripts are in hand; every step of the workflow now has an original to characterize against,
  and no part of this change is new code standing in for a script we could not recover.
- **A latent filename collision may already have shipped (F6).** `output_filename` omits `scan_id`
  while its counter is keyed by it, and both the copy step and the builder absorb a duplicate
  silently. Whether any published collection contains two scans mapped onto one image cannot be
  determined from the scripts — it needs the eight artifacts, which is #11's territory. This change
  makes it impossible going forward and should hand #11 the check.
- **The skeleton table ships unverified (Decision 7).** Its source calls itself advisory, it is
  missing pennycress, and one asymmetry (canola lateral at 3 nodes) is unconfirmed. The verification
  test against the published collections is what closes this; until it runs, the table is a
  hypothesis with a provenance header saying so.
- **The eight existing collections stay broken.** Nothing here repairs them, and six cannot be fully
  repaired. #11 owns that; this change only ensures the ninth is not produced the same way.
