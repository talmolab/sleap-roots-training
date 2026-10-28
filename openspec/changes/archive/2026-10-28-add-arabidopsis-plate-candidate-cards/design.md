# Design: arabidopsis plate candidate cards

## Context

The wheat/sorghum change (archived 2026-10-04) published cards under `candidate`, and promoted them a
day later. During that window a default `--verify` reported them `missing` and exited 1, which was
acceptable for a day.

The plate cards may stay candidate for months, until Bloom has plate dispatch and traits supports
plates (sleap-roots#252). A drift check that is red for months stops being read, and since production
reached 11 cards, exit 1 from a default `--verify` is meant to signal real drift.

## D1 — Status lives on the matrix row and defaults to production

- **Why on the row:** the matrix is already the source of truth, and provenance (`source`) is per row.
  A separate list of candidate ids would be a second thing to keep in sync.
- **Why default `production`:** every existing row, and every custom matrix, keeps its meaning.
- **The allowed values are exact strings:** `production` (the default alias) or `candidate`. Nothing
  is normalized, because the alias strip in `config.py` is for environment variables, not committed
  data. Any other value, `null` included, is an error.
- **One model, mixed status, is an error:** a single collection cannot be both expected in production
  and kept out of it.
- **Not published:** `card_to_metadata` is unchanged, so the consumer schema is untouched.
  `SelectionRow.status` and `Card.status` are trailing fields with a default, so existing constructions
  in tests are unaffected.

## D2 — Verify expects each card under its own status

**Expected set.** Without `--only`, the expected set is the cards whose status equals `cfg.alias`. A
default `--verify` therefore still checks exactly the 11 production cards. A `candidate` verify checks
the candidate cards. Before this change, it expected all cards under `candidate` and always failed.

**Empty set.** If no row has the alias as its status, verification refuses with exit 1, before any
wandb call. A mistyped alias (`candidtae`) must not produce a green check.

**Unexpected production link.** Under the default alias, every in-scope candidate collection is
"barred". Each barred collection is checked as follows:

- **Absent from the registry listing:** not linked, and its versions are not read. wandb 0.28 raises
  on the versions of a collection that does not exist, and the pre-publish verify (tasks 10.3) hits
  exactly this case.
- **Present:** its versions are read for the default alias. If it is linked, it is reported as
  `UNEXPECTED PRODUCTION LINK` and the command fails. A barred collection is never also reported as
  present or orphaned.
- **Read error:** reported as unreadable, and the command fails. This is the one safety check here,
  so it is not treated as indeterminate.
- **Under `--only`:** the barred set is the named candidate collections, and they are not expected.

**Orphan exclusion uses every card the matrix produces**, whatever its status. Otherwise a `candidate`
verify would report the promoted wheat and sorghum collections, which still carry `candidate`, as
orphans. The CLI captures the full collection set before `--only` filters `all_cards`.

**API shape.** `verify_registry` gains the keyword-only parameters `matrix_collections` and
`barred_collections`, both empty by default, plus two new report buckets:

- `unexpected_production`;
- `barred_unreadable`.

`verify_failed` includes both buckets.

## D3 — Candidate rows are skipped by default and refused when named

Under the default alias:

- **Without `--only`:** candidate cards are removed from the run's scope before the promotion check,
  and each is printed as `skipped (status: candidate)`. A routine production re-seed keeps working
  unchanged.
- **With `--only` naming a candidate collection:** the run exits 1. The error names the collections,
  and gives both remedies:
  - promoting requires a reviewed PR that changes the row's `status`;
  - a production re-seed should name only production ids.
- **No override:** neither `--promote` nor `--force` overrides this. If `--promote` could win, the
  matrix would say `candidate` while production holds the card, which is exactly the drift D2 fails on.

**Ordering.** This is a pure matrix decision. It runs after the `--promote` usage validation, and
before the credential check, the promotion check and every wandb call. The guard is conditioned on
`execute and not verify`, because `--verify` takes precedence over `--execute` in the CLI.

**Unaffected:**

- A dry run lists candidate cards marked `status: candidate`.
- `--execute` under a non-default alias is unaffected.

**Residual risk.** `publish.seed_registry`, the library function, has no status guard. Its only caller
is this CLI, and the CLI chooses the scope. This is recorded and pinned by a test, not guarded twice.

## D4 — Byte-reproducible archives, built by a committed script

`--execute` needs `<models-root>/<model_id>.zip` pinned by SHA256. Ordinary zip bytes vary with
timestamps and compressor version, so the archive itself would have to be kept forever.

`scripts/build_model_zip.py` writes:

- `ZIP_STORED` entries, with no compressor dependence;
- sorted paths;
- a fixed 1980-01-01 timestamp and fixed permission bits;
- every file under one top-level directory named after the model directory.

OS junk is excluded through the registry's own `junk_filter`, so the digest cannot depend on the
host that built it.

The same directory contents always produce the same SHA256. This was verified on 2026-10-26 with
the committed script: two builds per model gave identical digests, and both were accepted by
`resolve_model_dir(require_pinned=True)`. A 2026-10-22 prototype used different permission bits, so
its digests are superseded (see tasks 1.3).
The committed checksum can therefore be re-derived from the curated copy, and nothing has to be stored
on the share.

The published `weights_checksum` is the artifact digest over the extracted files, so it is independent
of the zip bytes anyway.

## D5 — Publish flow

The publish reuses the wheat/sorghum candidate flow (archive group 13/14), with two additions.

**A local load smoke test before publishing.** Run predict's `make_predictor` under its pinned sleap-nn
on both extracted directories.

- These are SLEAP 1.3.0 TensorFlow bottom-up models, and the primary uses
  `resize_and_pad_to_target` 1500×1616.
- A wandb version cannot be fixed in place, so an unloadable card would need a new version.

**No consumer gate.** Nothing in production reads `candidate`.

## Risks

- **Section fit.** The full-plate models may not suit GraviScan sections. sleap-nn resizes every frame
  to fit 1500×1616 and then pads it, so a section is upscaled. This is the experiment Benfica is
  running, and the doc says so.
- **Thin lateral evidence.** The lateral model rests on 38 frames from one session, with 4 validation
  frames.
- **Age clamping.** A section older than 7 DAG is matched at 7, and predict only logs a warning.
