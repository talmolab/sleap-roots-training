Each numbered group is one commit: red tests and the green implementation land together, so CI
stays green on every push (`openspec/project.md`: `main` stays green before every commit). Within
a group, write the tests first and watch them fail before implementing. The exceptions are
characterization tests, which pin existing behavior and pass immediately; they are labeled so.
Every delta-spec scenario gets at least one test, named after it, and is referenced by name below
rather than restated. A scenario that lists several causes is parametrized over every cause, so no
cause goes untested.
Nothing in any group writes to W&B.

## 0. Gate

- [ ] 0.1 **Dependencies merged.** #68 is merged, and `update-model-card-selectors` is archived (its
      archive PR, including 6.6, is merged). Rebase this branch on that `main`. Then:
      - run `openspec validate add-registry-retire-restore --strict`;
      - **re-diff** this delta's `Seed Run Lineage` base text against the promoted
        `openspec/specs/model-registry/spec.md`, since `validate` does not catch a stale but valid
        full-text copy.

      **Exception, approved by Elizabeth on 2026-09-30:** group 3 and task 3.3 may land **before**
      this gate. Together they are the protection: a pinned seed project, plus a README note that
      the two existing source projects must not be deleted. They depend on nothing in the pending
      change. They are code, config, tests and README only, and change no requirement that
      `update-model-card-selectors` touches. Group 3 carries the two env-var isolation lines it needs
      from 1.2. Every other group stays gated.
- [x] 0.2 **Approval.** The proposal is reviewed (`/review-openspec`, three rounds) and approved by
      Elizabeth on 2026-09-29.
- [x] 0.3 **Draft PR.** Opened as #69 (2026-09-29), proposal only. Its body notes that an
      `openspec/**`-only diff triggers no CI, and that the PR becomes the implementation PR after
      0.1. The archive follows as its own `chore(openspec): archive ...` PR, which is the precedent
      set by #63 and #67.

## 1. `test(registry): shared offline wandb fakes`

- [ ] 1.1 Create `tests/_wandb_fakes.py` containing the three fakes below. Leave
      `tests/test_registry_publish.py`'s fakes unchanged: its `_FakeArt.save()` is a working spy
      used by 17 call sites.
      - **`FakeLink`.** Attributes `is_link`, `digest`, `version`, `aliases`, `metadata` and
        `source_qualified_name`. **Every** method call (`unlink`, `link`, `save`, `delete`) is
        appended to a shared ordered `calls` list, and nothing raises. Invariant tests assert on
        `calls`, not on a raised `AssertionError`, which a fail-closed path could swallow.
        `unlink_takes_effect=False` models an unlink that returns while the alias still resolves.
      - **`FakeCollection`.** A `name`, plus an `aliases` attribute that can be set to raise.
        `delete()` is recorded in `calls` like every other method.
      - **`FakeRegistryApi`.**
        - `artifact_collections(project_name, type_name)` returns the collections in **reverse**
          sorted order, so that the code's sorting is actually exercised.
        - `artifacts(type_name, name)`, which the reused verify logic calls for expected
          collections.
        - `artifact(path, type=None)` raises a real
          `wandb.errors.CommError("artifact membership '<c>:<alias>' not found in '<project>'")`
          when the path is absent. `CommError(msg)` constructs offline in 0.28.0.
        - `fail_on_read=N, exc=...` raises `exc` on the Nth read.
        - `FakeLink.link(target, aliases)`, called on a source, mutates this API's state so that a
          later `artifact(path)` resolves the new membership. It can be configured to land at
          another version.
        - All calls go into the same ordered `calls` list.
- [ ] 1.2 Add the test-isolation guards below.
      - A `no_network_wandb` fixture patches `wandb.Api` and `wandb.init` to raise. Every new CLI
        test uses it together with `isolate_wandb_env`.
      - Add `SLEAP_ROOTS_SEED_PROJECT`, `WANDB_PROJECT`, `WANDB_SWEEP_ID` and `WANDB_LAUNCH` to
        `tests/conftest.py`'s `_WANDB_ENV_VARS`.
      - Add `SLEAP_ROOTS_SEED_PROJECT` to `tests/test_registry_config.py`'s `_ENV_VARS`, and update
        the `isolate_wandb_env` docstring in `tests/conftest.py` (~line 129) that lists the cleared
        variables.

## 2. `refactor(cli): extract the expected-collection derivation`

- [ ] 2.1 **Characterization, then red.** Add a pinning test for today's behavior, which passes
      immediately: under `seed-registry --only`, a duplicate
      collection id **outside** the `--only` scope is not reported. The duplicate check runs after
      the filter (`cli.py` ~111-124). Add unit tests that the helper returns sorted ids and raises
      on duplicates within the cards it is given.
- [ ] 2.2 **Green.** Extract the inline logic into a helper that takes cards (after any filter) and
      returns sorted, duplicate-checked ids. `seed-registry` calls it after its `--only` filter,
      which preserves the pinned behavior. `registry retire` calls it on the full card set. All
      existing CLI tests pass unchanged.

## 3. `feat(registry): pin the seed run's wandb entity and project`

- [x] 3.1 **Red.** Done 2026-09-30: 7 new tests failed first as expected (no `seed_project`, no `project=` passed).
      - **Isolation, moved up from 1.2.** Add `SLEAP_ROOTS_SEED_PROJECT` to
        `tests/test_registry_config.py`'s `_ENV_VARS`. Add it and `WANDB_PROJECT` to
        `tests/conftest.py`'s `_WANDB_ENV_VARS`, and update that fixture's docstring. Task 1.2 keeps
        the rest.
      - Config tests: `seed_project` defaults to `sleap-roots-training`, `SLEAP_ROOTS_SEED_PROJECT`
        overrides it, and an empty value falls back to the default.
      - CLI tests, extending `fake_init` in `test_execute_yes_seeds_and_reports` to capture
        `project` and `entity`: one test for each of the scenarios `Seed run uses the default
        project`, `Seed project is overridable` and `Seed project does not depend on the working
        directory` (`monkeypatch.chdir(tmp_path/"a")`, then `"b"`).
      - For `A dropped project aborts the seed`: a fake run whose `.project` differs. Assert that
        `seed_registry` is not called, that `run.finish()` is called, and that the exit is non-zero.
      - **Existing test update.** Four fake runs in `tests/test_registry_cli.py` return a
        `SimpleNamespace` with no `.project`: `test_execute_yes_seeds_and_reports`'s `fake_init`,
        plus three `lambda **kw` fakes. The review found only the first; implementation found the
        other three. Each now reports the project it was started with; otherwise the new check
        breaks them. The guard test pinning `_WANDB_ENV_VARS`
        (`tests/test_conftest_fixtures.py`) gains the two new variables.
- [x] 3.2 **Green.** Done 2026-09-30. Add `seed_project` to `RegistryConfig` and `resolve_registry_config`. Call
      `wandb.init(entity=cfg.entity, project=cfg.seed_project, ...)` and check `run.project` inside
      the existing `try/finally` (`cli.py` ~203-213), so the stray run is still finished. Add the
      variable to the `README.md` env-var table (~lines 43-48).
- [x] 3.3 **README: protect the existing source projects.** Done 2026-09-30 (README "Do not delete these wandb projects"). In the "Seeding the production model
      registry" section, state that the wandb projects `migrate-model-card-selectors` (sources of the
      8 production links, verified live 2026-09-30) and `sleap-roots-training-talmolab` (sources of
      the 13 retired flat collections, the rollback) hold live source artifacts. Deleting either
      breaks production links or the rollback, so they must not be deleted or cleaned up. Task 9.1
      later adds the restore instructions next to this note.
- [x] 3.4 **Review hardening, done in #70 (merged 2026-09-30 as `4825f8e`).** `/review-pr` findings
      were fixed test-first, with 9 tests failing first:
      - sweep and launch refused before `wandb.init`;
      - entity compared as well as project;
      - the stray run closed with `exit_code=1`;
      - a closing error cannot mask the refusal;
      - a disabled-mode message;
      - the value stripped;
      - docs corrected: wandb names an unpinned project after the git checkout's directory, and
        the CHANGELOG notes the entity change and the expected `--force` version bump.

      The spec delta and the proposal's "Why the seed-project guard grew during review" record
      this. Group 3 and 3.3 were split out of this PR into #70 and merged there; this branch
      merged `main` and carries only the change directory.

## 4. `feat(registry): not-found-only alias reads`

- [ ] 4.1 **Red.** Write the two `Registry Alias Absence Rule` scenarios and the one
      `Registry Commands Load wandb Lazily` scenario. `Other errors propagate`
      is parametrized over `CommError("permission denied")`, `ConnectionError` and `ValueError`.
      Also cover a `CommError` for a project or entity not found, which must propagate.
      `Importing the CLI does not load wandb` runs in a subprocess, since `sys.modules` state in the
      test process is unreliable. It follows `tests/test_registry_chooser.py:303-319`, imports both
      `sleap_roots_training.cli` and `sleap_roots_training.registry.retire`, and is a
      characterization test that also guards the new module.
- [ ] 4.2 **Green.** Implement `resolve_alias(api, project, collection, alias)` in
      `registry/retire.py`, importing `CommError` inside the function and matching both
      `artifact membership` and `not found`.

## 5. `feat(registry): registry snapshot`

- [ ] 5.1 **Red.** One test per `Registry Snapshot Command` scenario.
      - For `Snapshot fails closed on an unreadable collection`, add two variants: an unreadable
        `aliases`, and an unreadable alias-carrying artifact.
      - For the determinism scenario, inject `captured_utc` and assert on `read_bytes()`:
        - there is no `b"\r\n"`;
        - it decodes as UTF-8;
        - it equals `json.dumps(obj, indent=2, sort_keys=True).encode() + b"\n"`.
- [ ] 5.2 **Green.** Implement `snapshot_registry()` and the `registry` click group with its
      `snapshot` command, including the credential check through `_require_api_key`.
      - Enumerate with `publish._existing_collections` plus `collection.aliases`.
      - Read each entry with `resolve_alias`, not `_aliased_artifact`.
      - Compute the shape with `publish._is_selectors_shape` alone: `selectors` if it passes,
        `legacy` otherwise, the same two-way rule the verify command uses.
      - Write with `open(path, "x", encoding="utf-8", newline="\n")`: the same LF handling as
        `inventory/emit.py:473`, plus mode `"x"` for exclusive creation.

## 6. `feat(registry): registry retire`

- [ ] 6.1 **Red.** One test per `Production Link Retirement Command` scenario, using `calls` for
      ordering.
      - The anchor is written before the first `unlink`.
      - `Retire refuses while replacements are unhealthy` is parametrized over missing and legacy.
      - `Retire stops on a changed target` is parametrized over absent on re-read, not a link, and
        digest mismatch.
      - The credential-check test asserts that `wandb.Api` is never constructed.
      - Add an invariant test **parametrized over every path**: success, dry run, each refusal, and
        each mid-run failure. Assert that `calls` contains no `save`, `link` or `delete`, and that
        in the refusal and dry-run paths it contains no `unlink` either.
- [ ] 6.2 **Green.** Implement `retire_orphans()` and `registry retire`. Targets come from
      `verify_registry` over the full expected set from 2.2, with orphan reporting on.

## 7. `feat(registry): registry restore`

- [ ] 7.1 **Red.** One test per `Production Link Restore Command` scenario.
      - `Restore validates before writing` is parametrized over its three causes.
      - `Restore refuses to move an alias` is parametrized over another digest and a non-link.
      - `A transient error during restore propagates` is parametrized over the alias read and the
        source read.
      - `Restore detects a mismatched link` is parametrized over version, digest and source. The
        version case uses the fake's other-version link.
      - Add the same all-paths invariant test: `calls` contains no `save`, `unlink` or `delete`,
        and no `link` in the refusal and dry-run paths.
      - The snapshot file's bytes are asserted unchanged.
      - The credential-check test asserts that `wandb.Api` is never constructed.
- [ ] 7.2 **Green.** Implement `restore_snapshot()` and `registry restore`. Add a CliRunner help test,
      modeled on `tests/test_inventory_cli.py:94`:
      - `registry` appears in `--help`;
      - each subcommand's `--help` exits 0 and shows its flags.

## 8. The 2026-09-29 anchor, in three commits

- [ ] 8.1 **`feat(scripts): convert a retire record into a snapshot`.**
      - **Red** in `tests/test_scripts.py`: the pure mapping in `scripts/convert_retire_record.py`
        turns the retire record's `preflight` entries plus per-source metadata into snapshot
        entries, and refuses on a digest mismatch or a missing field.
      - **Green:** implement the script. Its only network access is a read-only `wandb.Api()` read
        of each recorded source `v0` for `metadata`, with `import wandb` **inside** that read
        function, because `tests/test_scripts.py` loads every script at import. It has no write
        path at all.
- [ ] 8.2 **`ci: lint and trigger on scripts/`.** In `.github/workflows/ci.yml`:
      - add `"scripts/**"` to both `paths` lists;
      - extend the lint steps to `black --check src/sleap_roots_training tests scripts` and
        `ruff check src/sleap_roots_training scripts`. Both pass on today's 4 scripts, checked
        2026-09-29.
- [ ] 8.3 **`docs(migration): commit the 2026-09-29 anchor`.**
      - **Live, read-only, outside CI.** Run the script to produce
        `docs/migration/2026-09-29-retired-flat-collections-snapshot.json`. Its `captured_utc`
        records the conversion time; `design.md` says what that means. Also record the run's
        ISO-8601 UTC time in the **PR body**, since squash-merge drops branch commit messages.
      - **Offline test of the committed file.** Load it with the retire record and assert:
        - 13 entries;
        - names equal to the record's `preflight` set;
        - each digest, version and `source_qualified_name` equal to the record's;
        - `registry` and `alias` equal to the defaults;
        - LF with sorted keys, and every required field present.

        Then `registry restore <it>` in a dry run over a fake API lists all 13 collections.

## 9. `docs(registry): make registry restore the documented rollback`

- [ ] 9.1 **README.**
      - Add `registry snapshot|retire|restore` to the `### Usage` block, using the same
        `uv run sleap-roots-training ...` form as the rollback line below. The inventory section
        already uses that form.
      - Add a `### Rolling back a retirement` subsection under "Seeding the production model
        registry". It gives the exact line
        `uv run sleap-roots-training registry restore docs/migration/2026-09-29-retired-flat-collections-snapshot.json --execute`.
        It leaves out `--yes` on purpose, so the confirmation prompt stays. It also states that
        `sleap-roots-training-talmolab` and `migrate-model-card-selectors` hold live sources and
        must not be deleted.
- [ ] 9.2 **`docs/CHANGELOG.md` `[Unreleased]`.**
      - **Added:** the `registry` group.
      - **Changed:** the seed run's pinned entity and project, and `SLEAP_ROOTS_SEED_PROJECT`.
        *Landed early with group 3 (2026-09-30), since the behavior change shipped then.*
      - Follow the section's style: a bold lead phrase and issue numbers. Add a
        "**For registry operators:**" note saying new sources land in `sleap-roots-training` and
        existing sources are not moved.
      - Say that it supersedes the #68 retirement script as the rollback (#68).
- [ ] 9.3 **Superseded-script note.** Add a note to the docstring of
      `docs/migration/2026-09-29-retire-flat-collections.py` saying `registry restore` supersedes
      it, with a pointer to the README subsection. Its logic stays as it ran.

## 10. Verification and hand-off

- [ ] 10.1 Run CI's own lint commands, `uv run black --check src/sleap_roots_training tests` and
      `uv run ruff check src/sleap_roots_training`, extended to `scripts` by 8.2, plus
      `uv run pytest`. All pass. CI is green on
      3 OSes × Python 3.11 and 3.12, and coverage stays at or above CI's `--cov-fail-under=95`.
- [ ] 10.2 **Live, read-only.** Record the following, with each run's ISO-8601 UTC time, in the **PR body**.
      - `registry snapshot` lists the 8 selector-shaped cards with their `source_qualified_name`.
        This confirms or corrects `design.md`'s claim about where their sources live.
      - A dry run of `registry restore` against the committed 13-entry snapshot reports none as
        already restored.
      - Nothing runs with `--execute`.
- [ ] 10.3 `openspec validate add-registry-retire-restore --strict` passes, and `/review-pr` has run
      on the PR.
- [ ] 10.4 **After merge, with confirmation.** Post comments on #68 and predict#34 replacing the
      script command with the `registry restore` line.
