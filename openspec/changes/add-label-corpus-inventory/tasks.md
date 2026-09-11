# Tasks

**TDD, as separate commits.** `(RED)` lands the tests and is **expected to be red**;
`(GREEN)` lands the implementation that turns it green. Subjects use
`test(inventory): … [RED]` / `feat(inventory): … [GREEN]`, keeping the subsystem in the
scope slot as every commit in this repo does. Confirm each RED fails for the right reason —
`ImportError`, `AttributeError` or `AssertionError`, not an unexpected error, per
`.claude/commands/tdd.md` Phase 2.

The convention itself is **not amended here**. It lands in its own change first, covering the
five places the green-every-commit rule is written; see `design.md` Prerequisites. Note
honestly what it buys: because PRs here are squash-merged, the pair collapses on merge, so
the labels serve *branch* review, not `main`'s history.

**Push discipline.** The unit is the **group**, not a pair: groups 1, 3, 4 and 6 fan several
REDs into one implementation commit. Push each group's REDs together with that group's GREEN
in one `git push`, so CI evaluates the pushed head and not an intermediate red state. A RED
pushed alone against an open PR produces a genuine red run — permitted, but noisy. There is
no branch protection on `main`, so a red run cannot block a merge.

**No CI on the proposal commit.** `openspec/**` and `.claude/**` are outside `ci.yml`'s paths
filter — absence of signal, not green. `README.md`, `scripts/**` and `inventory/**` are
outside it too, which task 0.4 fixes because groups 6, 8 and 9 depend on all three.

**Approval gate.** No implementation task starts until the proposal is approved.

## 0. Before any code

- [ ] 0.1 **Rebase onto `origin/main`**, then `uv sync`. The branch is 3 behind, including
      the breaking registry reshape and the root-type vocabulary collapse, and `main` carries
      the design doc and the RED/GREEN convention from the two prerequisite PRs. This is a
      **hard prerequisite of 0.2**, not housekeeping: `bloomctl 0.1.0a5` requires
      `sleap-roots-contracts>=0.1.0a7` and is **unsatisfiable** against this branch's current
      `==0.1.0a6`. Re-measure the resolution against `main`'s `==0.1.0a8` after the rebase —
      any measurement taken before it was against an unsatisfiable pin. Re-verify that the
      name-derived root-type and mode selectors in group 5 key against the post-rebase
      contract-owned `RootType`/`Mode`, not the pre-collapse local vocabulary.
- [ ] 0.2 Add `bloomctl` as a dependency and re-lock **in the same commit** — `ci.yml` runs
      `uv sync --locked`, which fails on a stale `uv.lock`. Pin
      `bloomctl>=0.1.0a5,<0.1.0b1`: the lower bound must be the pre-release literal, because
      `bloomctl>=0.1.0` resolves to nothing (only `0.1.0aN` is published; the local `0.1.0a6`
      is changelogged but never released), and the cap is tight because the symbols used are
      private internals of a pre-release CLI. Record in `pyproject.toml`, beside the pin,
      that it can re-floor this repo's exact `sleap-roots-contracts` pin.
- [ ] 0.3 Record the placement decision in a comment on the pin: **core, not an extra**, on
      two grounds — `pyproject.toml`'s stated rule that extras are for heavy or
      platform-specific *backends*, and the fact that `ci.yml` runs
      `uv sync --locked --group dev` with no `--extra`, so an extra would leave every
      inventory test failing on import in all six matrix legs. State the accepted cost:
      +25 transitive packages over the core set, including compiled `cryptography`/`cffi`.
- [ ] 0.4 **Its own commit, and it self-tests.** Add `inventory/**`, `README.md` and
      `.claude/commands/**` to **both** the `pull_request` and `push` paths filters in
      `.github/workflows/ci.yml`, and add `inventory/** text eol=lf` to `.gitattributes`.
      Without the first, the artifact commit in group 9 and the doc-locks in group 8 report a
      green check meaning nothing ran. Without the second, `* text=auto` plus
      `core.autocrlf=true` checks the committed artifacts out with CRLF on the
      `windows-latest` leg and breaks the byte-identity guarantee. `ci.yml` is itself inside
      its own paths filter, so this commit gets a real run.
- [ ] 0.5 Confirm `#48` has merged, or keep the `inventory` group **after the
      `seed-registry` command and before the `validate` command** in `cli.py` — a location
      none of `#48`'s four `cli.py` hunks touches. Reconcile with `#48`'s amendment moving
      archiving to a separate follow-up PR, which contradicts task 10.3.
- [ ] 0.6 **(RED)** Test `inventory/vocab.py`: each of the **five** closed vocabularies is a
      non-empty frozen collection with the members the spec enumerates, the resolution
      outcomes and the defect set are separate fields, and the module imports with `wandb`
      and `bloomctl` blocked by a `meta_path` finder — spec scenario *The vocabularies import
      without client libraries*, which had no test in the previous draft. Mirror
      `registry/chooser.py`'s `_vocab_from_contract_literal` shape guard.
- [ ] 0.7 **(GREEN)** Define the five closed vocabularies as constants in a leaf
      `inventory/vocab.py`, importable without the registry or scan-metadata clients:
      per-scan status, unresolved reason, per-field confidence, file classification, and the
      collection resolution/defect pair. First because groups 1-6 assert vocabulary members,
      and defining it later means several modules carry local literals and a refactor.

## 1. Resolution, digest verification, containment

- [ ] 1.1 **(RED)** Test the recorded-path→share mapping against **the prefix table the spec
      enumerates**, in both the backslash and the forward-slash rendering plus the
      drive-relative form, with an unrecognized prefix reported. Include a doubled separator,
      a trailing separator and a `.` segment: `sleap_io`'s filename sanitiser normalises those
      three differently on Windows and POSIX, so assert the mapping renormalises through
      `PureWindowsPath` **unconditionally, with no `os.name` branch**. Assert identical
      results under both semantics; `labeling/copy_images.py`'s docstring records this scar
      twice.
- [ ] 1.2 **(RED)** Test that the digest compared is the **manifest entry's** per-file
      base64 MD5, not the artifact-level digest, and that a **same-size** file with different
      content is excluded. Prefer `base64.b64encode(hashlib.md5(...).digest())` in
      `inventory/` over `wandb.sdk.lib.hashutil.md5_file_b64`, which is a private path, and
      assert the two agree so a wandb change is caught.
- [ ] 1.3 **(RED)** Test that a manifest entry carrying an external store's ETag is reported
      **unverifiable**, distinctly from failing verification — an ETag over a multipart
      upload is not an MD5 of the bytes, and the eight legacy collections' upload paths are
      not all known.
- [ ] 1.4 **(RED)** Test that verification invokes no download: the injected registry double
      records zero `download` / `checkout` / `file` calls.
- [ ] 1.5 **(RED)** Test that a directory is refused and an I/O error is reported as
      unreadable, distinctly from a mismatch.
- [ ] 1.6 **(RED)** Test that the registry client is **injected** and the double is
      **strict** — raising on any attribute outside an enumerated read allowlist. Enumerate
      that allowlist explicitly: in wandb 0.28.0 the entries live at
      `Artifact.manifest.entries` (there is no `Artifact.entries`), and touching `.manifest`
      is itself a network read. Note `tests/test_registry_cli.py`'s `_no_wandb` is two
      `monkeypatch.setattr(..., boom)` calls, not an allowlisted double, so this harness is
      new work.
- [ ] 1.7 **(RED)** Test with `isolate_wandb_env` that **with an injected registry client the
      run consults no ambient credential** — no `WANDB_API_KEY` / `WANDB_ENTITY` / `NETRC`
      read, no netrc under the repointed `HOME` — so a host-configured key can neither
      authorise nor mask a failure. Absent-registry behaviour is 1.9, not this task.
- [ ] 1.8 **(RED)** Test that a promoted collection with **no registry counterpart** is
      inventoried, reported `unregistered` with `share_only` fields, distinctly from a digest
      mismatch.
- [ ] 1.9 **(RED)** Test that an absent registry or absent share exits `3` naming the missing
      source and emits nothing, and that an unreachable registry is **never** reported as
      `unregistered`.
- [ ] 1.10 **(RED)** Test that two collections resolving to the same share file are both
      reported, naming the shared path and marking the pair as sharing bytes; and that
      differing recorded species for identical bytes is reported as a contradiction.
- [ ] 1.11 **(RED)** Test containment: a collection failing verification, and a collection
      whose fields are withheld, each leave the others emitted, and the run exits `4`.
- [ ] 1.12 **(RED)** Test provenance is read from the original version and images-embedded
      from the repair, on a two-version collection where the two answers differ; and that a
      single-version collection reads both from that version. The version-enumeration
      mechanism is `Artifact.manifest` over the collection's versions and belongs to the
      registry adapter, not to labels-file reading — add it to 1.6's allowlist.
- [ ] 1.13 **(GREEN)** Implement `inventory/resolve.py` and the registry read adapter.

## 2. Reading the labels file

- [ ] 2.1 **(RED)** Test that skeleton name, node names and node count are read from a labels
      file **round-tripped through a synthetic `.slp` written with `sio.save_slp` and loaded
      with `sio.load_slp`**, using `open_videos=False` — a host without the share cannot
      resolve video backends, and `scripts/clean_pkg.py` documents that resolving them raises
      `PermissionError`.
- [ ] 2.2 **(RED)** Test the counts distinguish user labels, predictions and **confirmed
      absences**: assert user-instance and predicted-instance counts, frames carrying a user
      instance, frames marked as a confirmed absence, and their sum — the frame set the
      backend exports. `sleap_io` 0.7.1 has **no `Labels`-level** `user_instances` /
      `predicted_instances`, so sum over `LabeledFrame.user_instances` /
      `.predicted_instances`; `len(labels.user_labeled_frames)` is the exported set and
      counts negative frames, while `Labels.n_user_frames` does not.
      `tests/test_labeling_package.py` asserts such empty frames really occur, and
      `labeling/build_package.py` documents them as ground truth.
- [ ] 2.3 **(RED)** Test the four recorded-path shapes: a **referenced** path yielding code,
      age, date and device; an **embedded** package whose code comes from the embedded source
      rather than the package's own filename, including the list form and the deliberately
      cleared form; a **generated** package whose scan identifier comes from the sample
      manifest beside it; and a **plate** path yielding no key, unresolved with
      `no_identifying_code`. Build the generated fixture with `sio.Video.from_filename([...])`
      over real JPEGs from `conftest.write_jpeg` — the backend must open for the list form to
      serialise as `backend.filenames`; `sio.Video(filename=[...], open_backend=False)`
      round-trips to `TypeError: … not list` in `slp.py`, which is a fixture defect, not a
      code defect.
- [ ] 2.4 **(RED)** Test that a file carrying more than one skeleton is reported as such
      **and that a file carrying none is reported distinctly** — `Labels.skeleton` raises
      `ValueError` for both in 0.7.1 ("There are no skeletons in the labels." versus the
      single-skeleton message), so one `try/except ValueError` would conflate them and hide an
      empty file.
- [ ] 2.5 **(RED)** Test that a labels file with zero videos, and one with a video carrying
      no labeled frames, each yield a recorded entry with the unresolved reason
      `nothing_comparable` rather than a crash or a silent skip.
- [ ] 2.6 **(GREEN)** Implement `inventory/read.py`.

## 3. Bloom resolution (cylinder only)

- [ ] 3.1 **(RED)** Test that only the enumerated `bloomctl` read symbols are called, that
      the client is injected, and that the double is strict.
- [ ] 3.2 **(RED)** Test at the transport level that every data-plane request used `GET`, and
      that any other method fails the run; the session exchange is the permitted `POST`.
      **Name the mechanism**: 3.1's strict double issues no HTTP, so this needs a real
      transport — verify `bloomctl`'s client construction accepts an injected `httpx`
      transport, or add `respx` to the dev group in 0.2. If interception proves infeasible,
      say so here, mark the test `integration`, and record in `design.md` that D7's primary
      mitigation is absent from default CI.
- [ ] 3.3 **(RED)** Test **at source level** that no module in `inventory/` names a
      `bloomctl` ingest symbol. Record in the test why this is a source assertion and not an
      import-graph one: `bloomctl/cyl/__init__.py` does `from .ingest import
      batch_ingest_result`, so `bloomctl.cyl.ingest` is in `sys.modules` after any read
      import — verified against `bloomctl==0.1.0a5`.
- [ ] 3.4 **(RED)** Test the drift guard: each enumerated upstream symbol
      (`_postgrest.fetch_in_batches`, `_postgrest.ID_FILTER_BUDGET_CHARS`,
      `cyl.download.CSV_COLUMNS`, `auth.make_authed_client`) is present in the installed
      client, and a missing one fails naming the symbol.
- [ ] 3.5 **(RED)** Test the scan lookup returns species identity, plant identity, age and
      experiment for a known key, against a fake speaking the **row keys** while the emitter
      uses the **export column names** — they differ for the code (`qr_code` versus
      `plant_qr_code`), and conflating them breaks the join. Import the cylinder column names
      from `bloomctl.cyl.download.CSV_COLUMNS` **by name**, since `bloomctl/download.py`
      holds a duplicate list and `plate/download.py` a different one.
- [ ] 3.6 **(RED)** Test that a scan is keyed by **plant code plus age plus device**, or by
      the manifest's scan identifier, and that a plant code alone never selects a single row —
      one plant has two rows at Day 11, from the Fast and Slow scanners.
- [ ] 3.7 **(RED)** Test batching via `bloomctl`'s `fetch_in_batches`: a collection larger
      than one filter resolves every scan, **each request's rendered percent-encoded URL is
      under the measured budget** (assert the length, not just the split), and a code
      containing a character the filter grammar reserves is quoted so the request selects
      that code and no other. The quoting rule is specified here, not inherited: every
      `in_()` in `bloomctl` filters on numeric bigints.
- [ ] 3.8 **(RED)** Test that a code absent from Bloom yields `unresolved` with
      `no_bloom_record`, distinct from `no_identifying_code` and `no_recoverable_path`.
- [ ] 3.9 **(RED)** Test that loaded credentials appear in no repr, log line, exception
      message or emitted artifact.
- [ ] 3.10 **(GREEN)** Implement `inventory/bloom.py` over `bloomctl`'s cylinder read
      surface, keeping credential loading, client construction and every upstream import in
      one thin adapter.

## 4. Reconciliation and adjudication

- [ ] 4.1 **(RED)** Test the three-state classification with **one of the five reasons**
      recorded on every unresolved row, and the conflicting **field** recorded on every
      disagreed row.
- [ ] 4.2 **(RED)** Test that an **unparseable or ambiguous date** yields `unresolved` with
      `unparseable_date` and never `disagreed` — the recorded form is ambiguous between
      day-first and month-first and may carry a two-digit year, and a parse failure reported
      as a disagreement would withhold a field on a formatting convention.
- [ ] 4.3 **(RED)** Test the adjudication gate: on a collection with agreed **and disagreed**
      scans, the fields the conflicting field feeds carry `awaiting_adjudication` with the
      pending count while every other field is emitted from the agreed scans with its
      contributing and excluded counts; and a collection with agreed **and unresolved** scans
      withholds nothing. This is the mixed case D4 turns on and the previous draft tested only
      at the all-unresolved extreme.
- [ ] 4.4 **(RED)** Test the verdict's two forms and its guards: **accept** clears the
      withholding for that scan and field alone; **exclude** removes the scan from that field's
      contributing scans, records it excluded with its reason, and likewise unblocks the field.
      Assert an adjudicated scan is classified `adjudicated` and **never** `agreed`, that a
      field built from one carries the confidence `adjudicated` and never `verified`, and that
      it stays in the queue carrying both observed values and the verdict.
- [ ] 4.4a **(RED)** Test **stale-verdict detection**: a verdict whose recorded pair of
      observed values no longer matches the pair the run observes is **not applied** — the
      field stays `awaiting_adjudication` and the scan re-enters the queue naming both pairs —
      and a verdict whose disagreement has vanished is reported as no longer needed. Without
      this the run emits a value neither source carries, marked as if it were corroborated.
- [ ] 4.4b **(RED)** Test that a verdict keyed on plant code, device and **path-derived age**
      applies to every promoted collection containing that scan, and that each aggregate entry
      names the verdicts it consumed.
- [ ] 4.5 **(RED)** Test that species comes from Bloom when the name says otherwise, that
      comparison is on the **species identifier** rather than the common name, and that two
      identifiers sharing a genus and species are one taxon and not mixed — `medicago` and
      `alfalfa` both denote *Medicago sativa*. Where a common name is rendered, assert
      agreement with the contract library's `params._normalize_species` (private in
      `0.1.0a8`, with an empty alias map, so it is strip-and-lowercase); do **not** normalise
      via `resolve_params`, which fixes `mode="cylinder"` and raises when an age is absent.
- [ ] 4.6 **(RED)** Test that a collection resolving to more than one species is reported a
      **defect blocking its card**, that the experiment-to-species mapping is emitted **with
      a scan count per species**, and that detection considers every scan carrying a Bloom
      row — an agreed-only check would let a thin join hide a pooling.
- [ ] 4.7 **(RED)** Test scan/plant counting: scan count is file-derived and survives a Bloom
      failure; plant count is distinct Bloom plant identity, not the filename code.
- [ ] 4.8 **(RED)** Test that the scan≥plant guard applies to **cylinder only** — a cylinder
      inversion withholds that collection's Bloom-derived counts as `count_inconsistent`
      while its file-derived fields still emit — and that a **plate** collection emits **no
      plant count at all**, neither a zero nor a filename-derived substitute, since it reads
      no scan metadata.
- [ ] 4.9 **(RED)** Test that the age window is emitted as an **observed** range labelled as
      such, carrying the observed age set and the upstream field; that the epoch is keyed on
      the **epoch token in the collection's name** and marked `convention`, with `DAG`, `DAP`
      and `DO` all occurring in the corpus and `DAP` on a cylinder collection, so a per-mode
      constant would contradict a collection's own name; that a name with no token reports the
      epoch unstated; and that a gapped age set is `age_set_non_contiguous`, since
      `LabelCard`'s window is contiguous and cannot express one.
- [ ] 4.9a **(RED)** Test the plate age sources: `video_ages.csv` beside the labels file,
      joined on the **basename** of the recorded video path (its paths are share paths, the
      labels file records another machine's), marked `share_only`; a basename matching two
      rows with different ages reported as a disagreement, not resolved; the collection name
      as the fallback, marked `name_derived` and supplying a range only; and the file's
      absence reported rather than treated as an error, since it covers roughly three of the
      plate collections.
- [ ] 4.10 **(GREEN)** Implement `inventory/reconcile.py`.

## 5. Discovery, promotion, and the skeleton diff

- [ ] 5.1 **(RED)** Test that the walk root is a parameter, by walking a `tmp_path` tree with
      no share present; that labels files are found **at any depth** beneath the root, since
      the real parent directories hold none at their own top level; that a directory with no
      labels file is reported skipped with a reason; and that discovery does not ascend above
      the root.
- [ ] 5.2 **(RED)** Test that derived files are excluded **by shape, not by directory**: a
      `*.predictions.slp` outside any `train_test_split` / `models` / `predictions` directory
      is still excluded, a split's frame count is never reported as the corpus's, and a
      directory of derived files is reported as a count rather than one entry per file.
      Thirteen thousand of the share's eighteen thousand labels files are inference outputs,
      so a directory-shaped rule does not bound the aggregate.
- [ ] 5.3 **(RED)** Test **version families** against the grammar the spec states: the key is
      (containing directory, basename minus `.v<digits>`, extension); `.slp` and `.pkg.slp`
      are separate families; free text before or after the version is not part of it; the
      highest version is current and earlier ones are `superseded_version` without being read
      or digested; two files at one version are a **version collision** with no current file;
      the same basename and version in different directories are distinct files each naming
      the others; and an unversioned file is `unclassified`, **not** `scratch`. Use a fixture
      shaped like `SLEAP_sorghum/primary_6nodes` plus a second directory reusing a basename —
      `labels.vNNN.slp` really occurs 57 times in 23 directories, and the worked example's
      own file exists three times at one version, so both cases are load-bearing rather than
      hypothetical.
- [ ] 5.4 **(RED)** Test **promotion**: an enumerated file absent from the decision file is
      `unclassified` and not read; a promoted file is read and reconciled; a file marked out
      of scope is reported and not inventoried; and every enumerated file receives an
      aggregate entry recording its classification, path and family. Include a directory
      holding promoted files of three different species, all inventoried; and a promoted file
      since superseded by a higher version, which stays `promoted`, is read, and has its entry
      name the newer version.
- [ ] 5.4a **(RED)** Test the **decision file's shape and mechanics**: `--decisions` accepts a
      file or a directory, and a directory's `*.yaml` files are merged in path order; a file
      is identified by its walk-root-relative path with forward slashes and that identifier
      matches what the aggregate reports; a `walk_root` mismatch exits `3` naming both; an
      entry matching nothing is `decision_unmatched` at exit `4`; a duplicate identifier
      within or across files exits `4` rather than last-one-wins; an absent file is treated as
      empty and reported; an unparseable file exits `3`; and the run leaves the decision
      content byte-unchanged. Assert `rationale` and the deciding person are read as **data**
      and appear in no emitted artifact.
- [ ] 5.5 **(RED)** Test the diff's five outcomes and that nothing is written back.
- [ ] 5.6 **(RED)** Test the selectors: species, root type, mode and age are derived from the
      collection's name and the file's observed ages, used for selection only, and appear in
      no emitted evidence; `seminal` / `sr` / `seminal_root` select the `crown` row; and a
      root type outside the contract vocabulary (`tertiary`, `adventitious`) is reported
      `root_type_out_of_vocabulary` rather than as a missing row.
- [ ] 5.7 **(RED)** Test that a mode-dependent node count is a **keying gap**, not a
      contradiction on either row, and likewise for an age-dependent one.
- [ ] 5.8 **(RED)** Test that the diff is emitted with Bloom unavailable, using name-derived
      selectors and file-derived node counts — this is the half of the check that survives a
      Bloom outage, and the previous draft's selector rule made it impossible.
- [ ] 5.9 **(GREEN)** Implement `inventory/discover.py` and `inventory/promote.py`.
- [ ] 5.10 **(GREEN)** Implement `inventory/skeleton_diff.py`.

## 6. Redaction, emission, determinism

- [ ] 6.1 **(RED)** Test that redaction is **structural**: a user segment appearing in no
      enumerated substitution is still redacted, any network-path host segment is redacted,
      and the marker set covers the share's user-directory marker **and** the
      temp-directory shape a repair version's recorded path takes.
- [ ] 6.2 **(RED)** Test the rule still covers `scripts/pull_tf_reference.py`'s `_REDACTIONS`
      as a floor — three substitutions over two entities — loading that script **by path** as
      `tests/test_scripts.py` does, since `scripts/` has no `__init__.py`.
- [ ] 6.3 **(RED)** Test that person-identifying fields are absent while genotype, accession
      and experiment name are present — approved for the public repo (eberrigan, 2026-09-02).
- [ ] 6.4 **(RED)** Test confidence is **per field**: file-derived facts are emitted even when
      every scan is unresolved, marked `file_only`, while reconciliation-derived fields are
      withheld; and that each field's confidence comes from the closed vocabulary.
- [ ] 6.5 **(RED)** Test that a collection with no agreed scan is emitted as an entry
      recording that, not as a verified zero, and that a withheld field never removes an
      entry.
- [ ] 6.5a **(RED)** Test that a de-promoted collection's per-scan table is removed from the
      output directory on the next run, while the decision content is left untouched — a stale
      table makes "regenerate and diff" show a clean diff over data no longer produced. Assert
      the aggregate records the digest of the decision content the run read, since CI cannot
      regenerate the artifacts to check them.
- [ ] 6.6 **(RED)** Test determinism and idempotence: no timestamp, hostname or run
      identifier; the spec's declared sort order; `LF` line endings; **every emitted path
      rendered with forward slashes whatever the host**; two runs identical; a new promoted
      collection leaves the others byte-identical; and the decision file counted as an input,
      so an unchanged verdict set reproduces the bytes.
- [ ] 6.7 **(RED)** Test byte-identity **across operating systems** against a **committed
      golden** in `tests/fixtures/inventory/`, so every matrix leg compares the same bytes,
      and give the fixture a `.csv`/`.yaml` extension so `.gitattributes`' explicit `eol=lf`
      covers it — a `text=auto` extension is checked out CRLF on Windows under
      `core.autocrlf`. Assert the emitter writes `LF` explicitly: `csv.writer`'s default
      `lineterminator` is `\r\n`, which is what `bloomctl/cyl/download.py` uses.
- [ ] 6.8 **(RED)** Test atomic emission **over an existing destination**, which is the normal
      case for a committed artifact: use `os.replace`, not `Path.rename`, which raises
      `FileExistsError` (WinError 183) on Windows when the destination exists —
      `labeling/copy_images.py` carries the sibling scar. Assert a raised failure leaves the
      previous artifact byte-unchanged and removes the staging file, an orphaned staging file
      is overwritten, and a second emission replaces a non-empty destination.
- [ ] 6.9 **(GREEN)** Implement `inventory/redact.py`.
- [ ] 6.10 **(GREEN)** Implement `inventory/emit.py`.

## 7. CLI

- [ ] 7.1 **(RED)** Test `inventory labels` end to end against injected clients, passing a
      `tmp_path` walk root and applying `isolate_wandb_env`. The option surface is
      `--walk-root` (required), `--out` (default `inventory/`), `--decisions` (default
      `inventory/decisions.yaml`) and `--bloom-profile` — `--decisions` accepting a file or a
      directory — with the entity read from `WANDB_ENTITY` as `seed-registry` does. Include a
      first run that promotes nothing: an aggregate with an entry per enumerated file, no
      per-scan table, an empty skeleton diff, exit `0`.
- [ ] 7.2 **(RED)** Test the exit codes: `0` on completion, `3` when the registry or share is
      absent (naming it, emitting nothing), `4` when the run completed with a failing
      collection; and that absent Bloom emits the per-scan tables, the diff, and file-derived
      aggregate fields while withholding reconciled ones.
- [ ] 7.3 **(GREEN)** Implement the `inventory` group in `cli.py`, after the `seed-registry`
      command and before the `validate` command.

## 8. Docs

- [ ] 8.1 `README.md`: an "Inventorying the label corpus" section following the
      `seed-registry` pattern, showing the **full option surface in a fenced command line** —
      the doc-lock reads fences only, so the `seed-registry` section's prose env-var table
      would not satisfy it. Add a link to `docs/labeling-packages.md` from the Status
      section's doc links, which currently omit that guide entirely.
- [ ] 8.2 `docs/labeling-packages.md`: a "Reading the corpus inventory" section carrying
      **all three** artifact schemas — the per-scan CSV's columns grouped by source, the
      aggregate's shape, and the skeleton diff's shape and format — plus the decision file's
      shape, which exists in no document today and must be written from the requirement rather
      than migrated: the background design doc contains no decision-file shape at all.
- [ ] 8.3 In the same section, define **all five** closed vocabularies, each as its own
      Markdown table under a stable `#### <Vocabulary name>` heading, first column the literal
      member value, second column whether rows carrying it contribute to
      reconciliation-derived fields. The doc-lock parses these tables; prose alone cannot be
      locked.
- [ ] 8.4 State that species comes from Bloom and may fall outside `SPECIES_VOCAB`; that the
      age window is **observed**, not approved, and carries its upstream field and a per-mode
      epoch convention; that plate ages are share-derived because Bloom has none; that plant
      count is distinct Bloom plant records, not a botanical count under multiplant modes; and
      that `inventory/` is the **pinned** output path, because regenerating elsewhere breaks
      the diff workflow.
- [ ] 8.5 State that the capability writes nothing, issues only reads, and never writes the
      decision file.
- [ ] 8.6 `openspec/project.md`: extend Purpose to cover corpus inventory, and qualify the
      source-of-record split in **Important Constraints**, where the constraint actually
      lives — W&B remains the system of record for label **artifacts**; Bloom is authoritative
      for **scan metadata** and nothing else. Add the same qualification to
      `.claude/commands/review-pr.md`, which restates it as "(not Bloom)" inside the reviewer
      prompt and would otherwise flag this capability's Bloom reads on every future PR.
- [ ] 8.7 `src/sleap_roots_training/labeling/data/skeletons.yaml` header, comment only so the
      change stays additive: the corpus inventory's skeleton diff is now the evidence that
      flips `verified:`; the table cannot express a mode-dependent node count, which the diff
      reports as a keying gap; and fix the stale "Source of truth" citation to
      `build-labeling-package.md`'s skeleton table, which no longer exists there and now
      points back here. Add a one-line pointer in
      `.github/workflows/verify-skeleton-table.yml`'s header recording the overlap.
- [ ] 8.8 `docs/roadmap.md`: correct Tier 2.7's stated blocker — node counts and node names
      are readable from the labels files, so the spacing measurement no longer waits on
      `#11`'s backfill, though `#11` still owns the card backfill itself. Note that "the
      existing 8 label collections" is the registry count, not the corpus. Note explicitly
      that `#46` must not derive an approved age window from this change's observed range,
      and that `#23`'s mask inventory is a different artifact this change does not produce.
      As a new dated revision entry — earlier entries are historical and are not edited. The
      Tier 2 Tracking reconciliation and the dead-`data_path` correction already landed in
      `62d1dc9`.
- [ ] 8.9 `docs/CHANGELOG.md`: entry under `[Unreleased]` → `### Added`. While in the file,
      fix the garbled sentence at the `labeling validate` entry ("`labeling validate` **and
      ignores** operating-system sidecars").
- [ ] 8.10 `tests/test_inventory_docs.py`: doc-lock binding `README.md` (command lines) and
      `docs/labeling-packages.md` (schemas and vocabularies). Command and option locks follow
      `tests/test_labeling_docs.py`; the vocabulary lock follows
      `tests/test_training_docs.py`, **strengthened from that precedent's subset check to set
      equality in both directions**. Add a fourth lock: for each reconciliation status, the
      documented statement about whether it contributes to reconciliation-derived fields is
      asserted against the emitter. Note this is the first test in the repo to read the root
      `README.md`, which 0.4 brings inside the paths filter.

## 9. The worked example

- [ ] 9.1 Promote the registered wheat superset in `inventory/decisions.yaml` and adjudicate
      its disagreements, recording each verdict with its reasoning.
- [ ] 9.2 Run the capability credentialed against the real share, registry and Bloom, and
      commit `inventory/decisions.yaml` plus the three artifacts. This proves before merge
      that the manifest digest matches the share file, that the join returns rows, and that
      redaction strips the host and user segments — the checks that only real data can make.
- [ ] 9.3 Promote the committed per-scan table and aggregate to the golden fixture 6.7
      compares against, so the cross-operating-system assertion runs on real bytes.

## 10. Gate

- [ ] 10.1 Mirror CI — `uv run pytest --cov=src/sleap_roots_training --cov-report=xml
      --cov-fail-under=95 --durations=20 -m "not integration" tests/`, `uv run black --check
      src/sleap_roots_training tests`, `uv run ruff check src/sleap_roots_training`,
      `uv sync --locked --group dev` — plus `openspec validate add-label-corpus-inventory
      --strict` on **1.5.0 and the newest cached CLI**, since 1.5.0 rejects a requirement
      whose `SHALL` wraps past the first line and later versions accept it silently.
- [ ] 10.2 Re-measure coverage **after the rebase**. The gate is `round(total, 0) < 95` with
      no `--cov-precision`, so the real threshold is `misses/statements < 0.055`, not `0.05`.
      At the pre-rebase baseline of 1545 statements / 39 misses that allows `≈46 + 0.055·N`
      new misses for `N` new statements. **Compute the floor rather than quoting a band**:
      required new-module coverage is `1 − (46 + 0.055N)/N`, which is 83% at `N=400`, 88% at
      `N=700` and 89.9% at `N=1000` — so a fixed "87-89%" budget goes red once the new tree
      passes ~840 statements. Expect ~3 uncovered statements per lazily-constructed client.
- [ ] 10.3 Run the unfiltered suite separately as a credentialed step, and add the
      `integration` tier this change otherwise lacks: tests that resolve and digest-verify one
      real collection against the real share, and issue one real Bloom read asserting the
      documented columns. Each must skip cleanly without credentials or the share — there is
      no `addopts`, and both `.claude/commands/coverage.md` and `.claude/commands/tdd.md` run
      the suite unfiltered. Follow `verify-skeleton-table.yml`'s credentials-check pattern.
- [ ] 10.4 Archive with `@fission-ai/openspec` **≥ 1.7.0** — an explicit upgrade, since the
      CLI on `PATH` is 0.13.0 — and confirm the live spec's `Purpose` is the real text, not
      the `TBD` stub. Verified by bisection: 1.5.0 and 1.6.0 clobber it; 1.7.0+ preserve it.
      Check `openspec --version` before running archive. Reconcile with `#48`'s amendment
      moving archiving to a separate follow-up PR.
- [ ] 10.5 Reconcile implementation against this proposal per `/new-feature` step 9. Record
      any deviation with a `### Why N instead of M?` note.

## 11. Follow-ups — deliberately not tasks of this change

Excluded from the checklist: none can be a commit in this PR, and leaving them unchecked
would keep the change out of the archive, as it has for three other changes on `main`.

- **Adjudicating and committing the remaining collections** → its own follow-up PR, using the
  worked example's decision file as the pattern.
- **A scheduled run** → optionally a workflow following `verify-skeleton-table.yml`. If that
  route is taken, wire the trigger in the same PR — that workflow's header records a gated
  check nothing ever triggered. Note a hosted runner has no `Z:` share, so this needs a
  self-hosted runner or it cannot run at all.
- **A second reviewer on `inventory/bloom.py`** → a PR-description request. The read-method,
  source-level ingest and symbol-drift tests are the mechanical backstop.
- **Reconciling plate scan metadata** → separate change, better scoped once Bloom carries a
  plate age column. File the upstream request.
- **A public `normalize_species` in `sleap-roots-contracts`** → upstream request, so this
  repo stops importing a private symbol.
- **Splitting the pooled multi-species files** → separate change, informed by this change's
  experiment-to-species mapping with its per-species scan counts.
- **Retiring `verify-skeleton-table.yml`** → separate change. This capability does *not*
  subsume it: that check needs only W&B and runs unattended in CI, which this cannot.
- **Posting the aggregate to `#49`** → better as a small PR against `#49`'s branch striking
  its §2 in favour of consuming this artifact, and resolving whether
  `wheat_5-14DAG_seminal_6nodes_labels` is the wheat half of the pooled wheat+rice file.
