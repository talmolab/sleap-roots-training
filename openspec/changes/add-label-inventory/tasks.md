## 1. Fixtures first — everything below consumes these

- [ ] 1.1 Build the labels fixture tree into `tmp_path` (never committed — `.gitignore:53` is
      `*.slp` and would silently swallow committed fixtures, passing locally and failing CI).
      Write real `.slp` files with `Video.from_filename` over generated JPEGs, reusing
      `tests/conftest.py`'s `write_jpeg`. Do **not** build videos as
      `sio.Video(filename=[...])`: that constructs and even saves without error, then raises
      `TypeError: expected str, bytes or os.PathLike object, not list` on load, inside the
      module under test — and `open_videos=False` does not avoid it. Note
      `Video.from_filename(jpg).filename` is itself a list, so a reader must not assume it is
      a string. `Skeleton-N` names must be set explicitly; an unnamed `Skeleton()` has
      `name=None`.

## 2. Enumeration and grouping

- [ ] 2.1 Create `src/sleap_roots_training/inventory/__init__.py` and `discover.py`.
- [ ] 2.2 Test the exclusion rules: a `*.predictions.slp` file outside every derived
      directory is excluded and attributed to its filename shape; files beneath `models/`,
      `predictions/` and `train_test_split*/` are excluded; an unversioned labels file is a
      candidate; an unreadable subdirectory is counted and reported, not skipped; and the
      per-rule counts plus candidates sum to the files seen.
- [ ] 2.3 Implement the walk and the exclusion rules. Pass `onerror=` so unreadable
      directories are counted rather than swallowed (`os.walk` discards them by default), and
      pin `followlinks=False` so a later change to it is a deliberate act.
- [ ] 2.4 Test the family key: all four version-suffix shapes (`.vNNN.slp`, `.vNNN.pkg.slp`,
      `.vNNN_<text>.slp`, `.<text>.vNNN.slp`) parse; identical basenames in two directories
      form two families with neither superseding the other; `labels.v001_ana.slp` and
      `labels.v001_ben.slp` stay apart with neither crowned; and `labels.vNNN.slp` versus
      `labels.vNNN.pkg.slp` stay separate but cross-referenced.
- [ ] 2.5 Implement family grouping on (directory, basename minus only the `.vNNN` token,
      full suffix chain).

## 3. Reading the labels files

- [ ] 3.1 Test: skeleton names, node names, node count, frame count, both instance counts and
      the referenced video filenames are recorded for a fixture file.
- [ ] 3.2 Test: zero skeletons and more than one are reported distinctly. Branch on
      `len(labels.skeletons)`, not on the exception — `Labels.skeleton` raises `ValueError`
      for both cases and only the message differs, which is an upstream string we do not own.
- [ ] 3.3 Test: a genuinely corrupt candidate (truncated bytes / non-HDF5 garbage) is recorded
      against its family without aborting the scan, and the handler catches broadly enough to
      survive a `TypeError` from inside `sleap_io`.
- [ ] 3.4 Implement `read.py` using `Labels.n_user_instances` and `Labels.n_pred_instances`.
      They exist in `sleap_io` 0.7.1 — only `user_instances`/`predicted_instances` do not —
      and their lazy path reads the instance store without materializing frames, which is
      worth having across ~1,450 candidates.

## 4. Digest verification

- [ ] 4.1 Test: a base64 MD5 equal to the matched entry's digest reports verified; a differing
      one reports a mismatch naming both; a candidate with no matching entry reports
      unregistered without affecting exit status; more than one matching entry reports all and
      crowns none; a reference entry whose scheme is not `file` reports unverifiable; and a
      `file://` entry logged with `checksum=False` — whose digest is an MD5 of the *path* and
      is shape-identical to a content hash — reports unverifiable rather than a false
      mismatch. Keep these as unit tests: `ArtifactManifestEntry` constructs offline and
      `wandb.sdk.lib.hashutil.md5_file_b64` computes the expected digest locally, so marking
      them `integration` would exclude them from CI and leave R4 unverified there.
- [ ] 4.2 Implement `verify.py` against the per-file `ArtifactManifestEntry.digest`, reading
      the manifest via `Artifact.manifest`. Never `Artifact.digest` — it is computed over the
      manifest. Discriminate on the reference scheme, not on `entry.ref` being set.

## 5. Keying-gap report

- [ ] 5.1 Test: two families differing only in capture mode and node count are reported as
      both selecting one `skeletons.yaml` row, with the two node counts named as the evidence.
      Assert no `wandb.Api` is constructed, reusing the `_no_api` monkeypatch idiom at
      `tests/test_registry_publish.py:201-203`.
- [ ] 5.2 Test: a derived species with no row is listed as uncovered. Inject the table via
      `lookup_skeleton(table=...)` using the `write_table` idiom in
      `tests/test_labeling_skeletons.py`, so adding a real wheat row later does not break this.
- [ ] 5.3 Test: an auto-generated `Skeleton-N` name is reported as unresolvable by the
      existing `partition("_")` check — it yields `('Skeleton-1', '', '')`, an empty root type.
- [ ] 5.4 Implement `gap.py`, deriving mode from the family's directory path and node counts
      from the files — no external service.

## 6. Redaction

- [ ] 6.1 Test: a candidate beneath the root emits with the fixed root token, and no segment
      of the root's absolute path appears anywhere in the artifacts.
- [ ] 6.2 Test: a referenced video path emits as its filename alone, for both `C:\Users\...`
      and `C:/Users/...` forms and for a UNC path. Split on both separators — the recorded
      strings are Windows-shaped whatever host runs the scan, and `PurePath` is
      `PurePosixPath` on the Ubuntu and macOS CI runners, where `Z:/a/b` has `drive=''` and
      `parts[0] == 'Z:'`. A test that passes on Windows can leak on POSIX.
- [ ] 6.3 Test: a candidate that cannot be expressed relative to the root — including a
      relative path and a `..`-rooted one — is reported by filename with the reason recorded.
- [ ] 6.4 Test: `genotype`, `accession_id` and `experiment_name` survive unchanged.
- [ ] 6.5 Implement `redact.py` as root-relativization plus basename extraction. Do not port
      `scripts/pull_tf_reference.py`'s `_REDACTIONS` as a floor: it is a case-sensitive
      literal `str.replace` hardcoded to one name and protects nobody else.

## 7. Emission and the human stop

- [ ] 7.1 Test: two runs over an unchanged tree emit byte-identical artifacts under
      `inventory/`, with the registry side stubbed so identity does not depend on live state,
      and no wall-clock timestamp, duration or hostname in either artifact.
- [ ] 7.2 Test: rows sort by emitted path, and an unresolvable group is listed as candidates
      with no collection membership asserted.
- [ ] 7.3 Test: the only files written are the table and the report; the only files read are
      labels files, `skeletons.yaml` and registry manifests.
- [ ] 7.4 Test: a name-derived species is labelled name-derived and stated not to be evidence.
- [ ] 7.5 Test: a scan recording mismatches and unregistered families exits zero; a missing or
      unreadable root exits non-zero without emitting a partial table.
- [ ] 7.6 Implement `emit.py` — one table, one report, under `inventory/`.

## 8. CLI

- [ ] 8.1 Test: `inventory labels` over the fixture tree produces both artifacts and the
      documented exit statuses.
- [ ] 8.2 Add the `inventory` group and its `labels` command to `cli.py` after
      `seed-registry` (body ends `:221`) and before `validate` (`:224`). Clear of all four of
      #48's hunks (old ranges 4-11, 16-23, 275-281, 642-646); the module import merges clean
      in either placement, but if #48's rewritten `main()` docstring enumerates subcommands,
      adding `inventory` there is a separate one-line edit.

## 9. Docs and validation

- [ ] 9.1 Add a `docs/CHANGELOG.md` `### Added` entry under `[Unreleased]` and a one-line
      README pointer beside the existing `seed-registry` section — every feature merge in this
      repo has done both. #48 also appends under `### Added`, so expect a trivial conflict
      whichever lands second.
- [ ] 9.2 Run the first real scan. **Before committing, grep the artifacts for both known
      colleague names and for any surviving absolute path** — a leak survives `git revert`,
      which removes the blob from the tree and not from history. Commit the artifacts as their
      own commit, and push it together with 9.1 so the PR's final head is CI-verified
      (`inventory/**` is outside the paths filter and does not trigger CI on its own).
- [ ] 9.3 Run CI's own gate, not a looser local one:
      `uv run black --check src/sleap_roots_training tests && uv run ruff check
      src/sleap_roots_training tests && uv run pytest -m "not integration"
      --cov=src/sleap_roots_training --cov-fail-under=95`. Headroom is ~129 uncovered lines
      repo-wide, so every implementation commit must carry its own tests.
- [ ] 9.4 Validate strict on **both** pinned CLIs — 1.5.0 and 1.11.0 — and paste both
      `--version` outputs into the PR body, since no workflow enforces this. 1.5.0 rejects a
      `SHALL` that wraps past a requirement's first body line; later versions accept it
      silently.
- [ ] 9.5 Flip `docs/superpowers/specs/2026-09-15-label-inventory-v2-scope.md`'s header from
      scaffolding-to-be-deleted to a superseded banner, and keep the file. It holds the hard
      limits, the nine verified facts and the governing principle, and `proposal.md` cites it
      as where the reasoning lives; deleting it would strand that. Same treatment the v1
      design doc got, for the same reason.
