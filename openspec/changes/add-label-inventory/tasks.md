## 1. Enumeration and grouping

- [ ] 1.1 Create `src/sleap_roots_training/inventory/__init__.py` and `discover.py`.
- [ ] 1.2 Test the exclusion rules: a `*.predictions.slp` file outside every derived
      directory is excluded and attributed to its filename shape; files beneath `models/`,
      `predictions/` and `train_test_split*/` are excluded; an unversioned labels file is a
      candidate.
- [ ] 1.3 Implement the walk and the exclusion rules; report per-rule counts.
- [ ] 1.4 Test the family key: all four version-suffix shapes (`.vNNN.slp`,
      `.vNNN.pkg.slp`, `.vNNN_<text>.slp`, `.<text>.vNNN.slp`) parse; identical basenames
      in two directories form two families with neither superseding the other; one basename
      in three directories yields three families.
- [ ] 1.5 Test: `labels.vNNN.slp` and `labels.vNNN.pkg.slp` in one directory stay separate
      families and are cross-referenced as one labeling effort in two representations.
- [ ] 1.6 Implement family grouping on (directory, basename minus version, extension).

## 2. Reading the labels files

- [ ] 2.1 Test: skeleton names, node names, node count, frame count and the two instance
      counts are recorded for a fixture file.
- [ ] 2.2 Test: zero skeletons and more than one skeleton are reported distinctly —
      `Labels.skeleton` raises on both with different messages.
- [ ] 2.3 Test: the confirmed-absence count is recorded as unreadable, not zero.
- [ ] 2.4 Test: one unreadable candidate is recorded against its family without aborting
      the scan.
- [ ] 2.5 Implement `read.py`, summing user and predicted instances over `LabeledFrame` —
      `sleap_io` 0.7.1 has no `Labels`-level accessor.

## 3. Digest verification

- [ ] 3.1 Test: a base64 MD5 equal to the manifest entry's digest reports verified; a
      differing one reports a mismatch naming both digests.
- [ ] 3.2 Test: a candidate with no registry artifact reports unregistered without
      affecting exit status; a manifest entry carrying a reference store's ETag reports
      unverifiable rather than mismatching.
- [ ] 3.3 Implement `verify.py` against the per-file `ArtifactManifestEntry.digest`, reading
      the manifest via `Artifact.manifest` (GraphQL, no download). Never `Artifact.digest`.

## 4. Keying-gap report

- [ ] 4.1 Test: two families differing only in capture mode and node count are reported as
      both selecting one `skeletons.yaml` row.
- [ ] 4.2 Test: a derived species with no row is listed as uncovered.
- [ ] 4.3 Test: an auto-generated `Skeleton-N` name is reported as unresolvable by the
      existing `partition("_")` check.
- [ ] 4.4 Implement `gap.py`, deriving mode from the family name and node counts from the
      files — no external service.

## 5. Redaction

- [ ] 5.1 Test: `users/`, `Users/` and `home/` markers redact the following segment in any
      casing; a drive-rooted or UNC path with no marker redacts its first segment instead.
- [ ] 5.2 Test: the two known real video paths emit with no colleague's name remaining.
- [ ] 5.3 Test: `genotype`, `accession_id` and `experiment_name` survive untouched.
- [ ] 5.4 Implement `redact.py`, taking `scripts/pull_tf_reference.py`'s `_REDACTIONS` as
      the floor.

## 6. Emission and the human stop

- [ ] 6.1 Test: two runs over an unchanged tree emit identical artifacts; rows sort by
      redacted path.
- [ ] 6.2 Test: an unresolvable group is listed as candidates with no collection membership
      asserted.
- [ ] 6.3 Test: the command reads and writes no file recording a human determination.
- [ ] 6.4 Test: a name-derived species is labelled name-derived and stated not to be
      evidence.
- [ ] 6.5 Implement `emit.py` — one table, one report, under `inventory/`.

## 7. CLI

- [ ] 7.1 Add the `inventory` group and its `labels` command to `cli.py`, positioned after
      `seed-registry` and before `validate` (clear of #48's four hunks).
- [ ] 7.2 Test: `inventory labels` on a fixture tree exits zero with findings present, and
      non-zero only on an unusable root.
- [ ] 7.3 Build the fixture tree from real `.slp` files written with
      `Video.from_filename` over real JPEGs — `sio.Video(filename=[...], open_backend=False)`
      round-trips to a `TypeError`.

## 8. Docs and validation

- [ ] 8.1 Update `docs/roadmap.md` Tier 2: drop the Bloom-joined description of the
      inventory and replace the `add-label-corpus-inventory` change id with this one.
- [ ] 8.2 Run the first real scan; commit the resulting `inventory/` artifacts.
- [ ] 8.3 `uv run black --check . && uv run ruff check . && uv run pytest`.
- [ ] 8.4 Validate strict on **both** pinned CLIs — 1.5.0 and 1.11.0. 1.5.0 rejects a
      `SHALL` that wraps past a requirement's first body line; later versions accept it
      silently.
- [ ] 8.5 Delete `docs/superpowers/specs/2026-09-15-label-inventory-v2-scope.md` once this
      proposal is approved — it is scaffolding and says so.
