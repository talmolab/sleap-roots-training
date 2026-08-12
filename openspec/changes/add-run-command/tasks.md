# Tasks

TDD throughout: within each task group the loop is **write every failing test → confirm red →
implement → confirm green → `black --check` + `ruff check`**. That red→green loop is *local*; the
**committed** unit is always green (tests land with their implementation, per the Tier 0.5 /
`add-config-schema` precedent — never push a red commit). No task group adds a test after its own
"confirm green" step. See the Commit Plan at the bottom.

Conventions that keep the cross-platform base matrix green:

- Every task is base-install safe (no `train` extra) except those marked **[integration]**. CI never
  installs the backend, so unit tests assert the contract through two seams —
  `backend.resolve_sleap_nn` and `backend._interpreter_scripts_dir` — plus
  `monkeypatch.setattr(backend.subprocess, "Popen", fake)`, following
  `tests/test_registry_lineage.py:29`. **No private `_subprocess_run` wrapper:** a wrapper launders
  the call, so a kwargs assertion against it proves nothing about what reaches `subprocess`.
- New test files are `tests/test_backend_invoke.py` and `tests/test_cli_run.py` — *not*
  `test_backend.py`, which would read as a sibling of the existing `test_backend_docs.py` (a docs
  test, not a module test). Neither may have a module-top `sleap_nn` / `torch` import.
- **Every `run` test MUST sandbox the checkpoint tree.** `tests/conftest.py::VALID_CONFIG` ships
  `ckpt_dir: models` (relative), and `CliRunner` does not change directory — so an unmodified
  `write_config()` would write into the repo checkout, where `.gitignore`'s `/models/` hides it and
  the "nothing was written" assertions become unfalsifiable. Use
  `write_config(overrides={"trainer_config": {"ckpt_dir": str(tmp_path / "ckpt")}})` **and**
  `monkeypatch.chdir(tmp_path)`. `conftest.py` itself needs no change — the existing factory already
  takes arbitrary overrides.
- "Nothing was written" is asserted as a **snapshot diff**, not emptiness (`tmp_path` already holds
  the input config): capture `{p.relative_to(tmp_path) for p in tmp_path.rglob("*")}` before and
  after, and assert equality plus `not (tmp_path / "ckpt").exists()`.
- "No traceback" is asserted as `result.exception is None or isinstance(result.exception, SystemExit)`.
  The `"Traceback" not in result.output` idiom inherited from `tests/test_cli_validate.py:53` passes
  even when the command crashed — `CliRunner` stores the exception instead of printing it.
- Paths are compared as `Path` objects, never their `str()`.

## 1. Emit line endings (prerequisite — must land first)

Ordering is load-bearing, not cosmetic: group 3's byte-identity tests compare `run`'s artifact
against `emit -o`'s file, and today `emit` inherits `newline=None` and writes CRLF on Windows. Any
commit that adds those tests *before* this fix is red on `windows-latest`, which runs on every
commit.

- [ ] 1.1 Write the failing test: `emit -o out.yaml` produces a file containing no CR byte, and its
      bytes are the UTF-8 encoding of `config.to_sleap_nn_yaml(cfg)` exactly.
- [ ] 1.2 Confirm red on Windows (and green elsewhere — note in the test's docstring that this is a
      Windows-only failure before the fix, so a green local run is not evidence).
- [ ] 1.3 Implement: `output.write_text(sleap_nn_yaml, encoding="utf-8", newline="\n")` in `cli.py`'s
      `emit` (design D10).
- [ ] 1.4 Confirm green; `black --check` + `ruff check` clean.

## 2. Backend executable resolution (TDD)

- [ ] 2.1 Write the failing tests (`tests/test_backend_invoke.py`). Helper: `_make_stub(dir_)`
      writing `"sleap-nn.exe" if os.name == "nt" else "sleap-nn"` (Windows `shutil.which` on Python
      **3.11** only tries `cmd + ext` for each `PATHEXT` entry — the bare extensionless name is
      never tried, so an unsuffixed stub is invisible on that leg) and `chmod(0o755)` on POSIX.
      Cover **all three tiers**, including the middle one, which the first draft left untested:
      (a) stub in the interpreter's scripts dir **and** on `PATH` → scripts-dir wins;
      (b) stub beside the interpreter **and** on `PATH`, none in the scripts dir → the
      beside-the-interpreter one wins (the belt-and-braces tier D2 justifies for relocated schemes);
      (c) only on `PATH` → that one; (d) none → `BackendError`.
      Drive tiers (a)/(b) via `monkeypatch.setattr(backend, "_interpreter_scripts_dir", …)` and a
      patched `sys.executable`; drive `PATH` with `monkeypatch.setenv`.
      `monkeypatch.chdir(tmp_path)` in every case: Python 3.11's `shutil.which` prepends `os.curdir`
      on win32 **even when `path=` is passed**.
- [ ] 2.2 Write the failing test for the error text: it names `sleap-roots-training[train]`, gives
      the `uvx --from` form, and points at `docs/training-backend.md`.
- [ ] 2.3 Write the failing test that `_interpreter_scripts_dir()` really is this environment's
      console-script directory: assert it equals `Path(shutil.which("black")).parent` when `black`
      resolves (a dev-group dependency, present on every CI leg), else skip. This is the only test
      that would catch a regression back to `Path(sys.executable).parent`.
- [ ] 2.4 Confirm red (module does not exist).
- [ ] 2.5 Implement `src/sleap_roots_training/backend.py`: `BackendError(RuntimeError)`, the seam
      `_interpreter_scripts_dir() -> str` returning **`sysconfig.get_path("scripts")`** (design D2 —
      *not* `Path(sys.executable).parent`, which is the env root rather than `Scripts\` for conda and
      base Windows installs), and `resolve_sleap_nn() -> Path` searching scripts dir → interpreter
      dir → `PATH`. Stdlib only; no `sleap_nn` import.
- [ ] 2.6 Confirm green; lint clean.

## 3. Destination policy and provenance artifacts (TDD)

- [ ] 3.1 Write the failing destination tests: artifacts land in `<ckpt_dir>/<run_name>/`; an unset
      `ckpt_dir` resolves to `.` (the backend's own default); `--resolved-config` relocates the
      emitted config while `source_config.yaml` still lands in the run directory; a relative
      `ckpt_dir` resolves against the process cwd (assert explicitly with `monkeypatch.chdir` —
      `VALID_CONFIG` ships a relative one).
- [ ] 3.2 Write the failing `run_name` tests: absent, empty, **whitespace-only**, and the literal
      `"None"` are each refused naming `trainer_config.run_name` (the backend treats `"None"` as
      unset and would generate a timestamped directory we cannot predict); a `run_name` containing a
      path separator or an absolute path is refused — `Path("ckpt") / "/tmp/x"` evaluates to
      `/tmp/x`, so an absolute value escapes the run tree entirely. Add a long / non-ASCII
      `run_name` case: on Windows the resulting path can exceed `MAX_PATH`, which must surface as
      the clean `OSError` path of 3.5, never a traceback.
- [ ] 3.3 Write the failing run-directory-refusal tests (design D4): a run directory holding
      `best.ckpt` **or** `training_config.yaml` is refused, naming the directory and a new
      `run_name`, leaving the directory unchanged (verify with a before/after hash) and starting no
      subprocess; **no flag overrides it**; a directory holding neither is the retry case and
      proceeds, overwriting only our two artifacts. Include the TOCTOU case: if the refusal
      condition appears *between* the check and the write, the write must still not clobber a
      checkpoint — assert the artifact write refuses to overwrite anything it did not expect.
- [ ] 3.4 Write the failing content tests: `resolved_config.yaml` equals `emit -o`'s output
      **file-for-file** (compare artifact bytes to artifact bytes, never bytes to
      `to_sleap_nn_yaml(cfg).encode()` — `Path.write_text` translates `\n` to `os.linesep`, so the
      latter is red on Windows by construction; group 1 has already made both sides LF);
      `resolved_config.yaml` has no `experiment` block and retains the three sleap-nn blocks;
      `source_config.yaml` matches the input file's content including `experiment`; neither file
      contains a CR byte on any platform.
- [ ] 3.5 Write the failing write-robustness tests: missing parents are created; a destination whose
      parent is a file is refused cleanly (portable — `chmod(0o555)` does not deny writes on Windows
      or for root); `--resolved-config` naming a directory is refused (`dir_okay=False`);
      `--resolved-config` naming the input config is refused, since overwriting the source with its
      `experiment`-stripped form destroys the run's identity; a **relative** `--resolved-config`
      that resolves to one of the run directory's own artifact names is refused (it would collide
      with what `run` writes); a write that fails partway leaves no truncated file.
- [ ] 3.6 Write the failing credential tests (design D9): a non-empty `trainer_config.wandb.api_key`
      is refused before any write, naming `WANDB_API_KEY` / `wandb login`.
- [ ] 3.7 Confirm red.
- [ ] 3.8 Implement in `backend.py`: `run_directory(cfg)`, `resolved_config_path(cfg, override)`,
      and `stage_artifacts(cfg, source_path, dest)` writing atomically (temp file in the destination
      directory + `os.replace`) with `newline="\n"`.
- [ ] 3.9 Confirm green; lint clean.

## 4. Invocation and exit-status translation (TDD)

- [ ] 4.1 Write the failing argv test: `build_argv(binary, dest)` (pure, public — kept separate from
      `run_backend` so the plumbing can be exercised with a different argv, see 7.1) returns exactly
      `[str(binary), "train", "--config", str(dest)]` with `dest` absolute — nothing appended, no
      Hydra-style `key=value` overrides forwarded.
- [ ] 4.2 Write the failing invocation-shape test: the subprocess is created exactly once, with no
      `shell=`, no `env=`, no `cwd=`, and no `stdout` / `stderr` redirection. Assert the kwargs *set*
      is bounded (`set(kwargs) <= {…}`) so a later `text=True` or `PIPE` fails the test. This asserts
      **call shape**; behavioral proof of stream inheritance is 7.1.
- [ ] 4.3 Write the failing exit-status tests with fabricated return codes: `0` → 0; `2` → 2; `-9` →
      `137` with a message naming signal 9; a large Windows-style status (`3221225786`) → non-zero
      without `128 + N` synthesis, naming the raw status; and a boundary case above 255 → non-zero,
      with the contract stated (POSIX truncates a real exit status to 8 bits, so `run` must not hand
      `sys.exit` a value it cannot represent).
- [ ] 4.4 Write the failing interrupt test (design D5): when the wait raises `KeyboardInterrupt`,
      `run_backend` does **not** kill the child, waits again, and returns the child's own status.
      This is what really happens on Ctrl-C — SIGINT reaches the parent too — and it is why
      `subprocess.run` is unusable here (it SIGKILLs the child and re-raises).
- [ ] 4.5 Confirm red.
- [ ] 4.6 Implement `backend.run_backend(argv)` on `subprocess.Popen` with the wait loop, returning a
      translated status (no `sys.exit` inside `backend.py` — the CLI owns process exit).
- [ ] 4.7 Confirm green; lint clean.

## 5. CLI `run` subcommand (TDD)

All tests in this group are written before 5.8's implementation; nothing is appended after the green
gate.

- [ ] 5.1 Write the failing CLI tests (`tests/test_cli_run.py`, Click `CliRunner`, following
      `tests/test_cli_validate.py`): happy path exits 0, prints the resolved absolute backend path
      before invoking, and prints one success line naming the run directory and both artifacts;
      backend missing exits non-zero with the install message; invalid config exits non-zero with
      the field-named error; malformed YAML and a nonexistent path exit non-zero without a
      traceback.
- [ ] 5.2 Write the failing **ordering** tests (design D6 — the contract that matters most). For
      each cheap-failure case, in the order the requirement lists them — backend unresolvable,
      invalid config, in-config `api_key`, W&B enabled with no resolvable credential, unusable
      `run_name`, occupied run directory — assert the subprocess seam recorded **zero** calls,
      `(tmp_path / "ckpt")` was never created, and the `rglob` snapshot is unchanged.
- [ ] 5.3 Write the failing exit-propagation CLI tests: backend status `2` → CLI exit 2 with no
      success line; `-9` → CLI exit 137; interrupt → the backend's status is reported, with
      `result.exception` never a `KeyboardInterrupt` and no `Aborted!`.
- [ ] 5.4 Write the failing gate/importability test: with `resolve_sleap_nn` stubbed to a path and
      `config._deep_validation_available` stubbed to `False` (a `PATH` hit from another environment
      — design D2 deliberately does not gate on `find_spec`), `run` proceeds **and echoes the skip
      note**, so an operator knows a multi-hour run was not deeply validated.
- [ ] 5.5 Write the failing failed-run-retention test: after a non-zero backend status, both
      artifacts remain on disk and the run directory is not rolled back.
- [ ] 5.6 Write the failing base-install lock tests, in two parts, because
      `assert "sleap_nn" not in sys.modules` alone is **vacuous** where the extra is not installed
      (i.e. on every CI leg): (a) a tripwire — install a fake `sleap_nn` module whose `__getattr__`
      raises, then drive a full stubbed `run` and assert it completes; this is the part that catches
      a dynamic `importlib.import_module("sleap_nn")`; (b) a static lock — `ast.parse` `backend.py`
      and `cli.py` and assert no `Import` / `ImportFrom` node names `sleap_nn` at any nesting depth.
      (b) is belt-and-suspenders against the obvious spelling, **not** a guarantee — only (a) covers
      dynamic imports. Follow `tests/test_config.py:195`'s
      `monkeypatch.delitem(sys.modules, "sleap_nn", raising=False)` so both are valid on the
      co-installed GPU box too.
- [ ] 5.7 Write the failing regression test that the new gate did not leak into the base-safe
      commands: with `resolve_sleap_nn` stubbed to raise, `validate <good>` still exits 0 and
      `emit <good>` still writes its output. Confirm red for the whole group.
- [ ] 5.8 Implement `run` in `cli.py`: `@main.command(name="run")`, `config_path` argument
      (`exists=True, dir_okay=False, path_type=Path`), `--resolved-config`
      (`dir_okay=False, path_type=Path`); compose gate → `load_config` → `validate_config` (echoing
      notes) → `_require_api_key()` when `use_wandb` → run-name and destination checks →
      run-directory refusal → stage → invoke → `ctx.exit(status)`; map `BackendError` /
      `ConfigError` to `click.ClickException`. Extend the CLI group docstring so `--help`
      distinguishes the base-safe `validate` / `emit` from the `[train]`-gated `run`.
- [ ] 5.9 Confirm green; run the full suite + lint.

## 6. Documentation

- [ ] 6.1 Write the failing doc-contract tests first (`tests/test_training_docs.py`): a fenced
      `sleap-roots-training run` command exists **inside** the new section (section-scoped, following
      `test_backend_docs.py`'s `_arch_findings_section` precedent); the section names
      `resolved_config.yaml`, `source_config.yaml`, and `[train]`; and — the assertion that actually
      matters — the `validate` / `emit` / `sleap-nn train --config` commands are each still present
      among the fenced blocks that do **not** mention `run`. The three existing whole-document
      assertions would otherwise be satisfied from inside an "equivalent to…" comment in the `run`
      block, letting the canonical sections be deleted while the suite stays green.
- [ ] 6.2 Confirm red (the section does not exist yet).
- [ ] 6.3 Write the `docs/training.md` section as a `###` at the end of `## 3. Train` (a new `##`
      would break the guide's 1–5 narrative, which both later sections depend on from either path).
      It must carry: the `uv run --no-sync` form with its reason (a bare `uv run` re-syncs and
      uninstalls the `[train]` extra installed by `uv pip install ".[train]"` — the same rule
      `scripts/clean_pkg.py` documents); the run-directory inventory, explicitly qualified **"as of
      `sleap-nn` 0.2.0"** with the file:line citation, matching how `docs/training-backend.md`
      version-qualifies its backend findings so this does not silently rot at the Tier 6 bump
      (`initial_config.yaml` and `training_config.yaml` written by the backend,
      `resolved_config.yaml` and `source_config.yaml` written by `run`); the one-`run_name`-per-run
      rule and why; the note that the three-command path stays canonical for the author-here /
      train-there workflow; and the unchanged #10/#11 provenance caveat. No `TODO` / `TBD` (a doc
      test forbids them) and no `**range**` token (the baseline test parses the first line containing
      it); use an untagged fence for any directory listing, since `_yaml_blocks` parses every
      ```yaml``` fence.
- [ ] 6.4 Confirm green.
- [ ] 6.5 `README.md`: extend the pointer paragraph (`README.md:25-28`) with one line for the
      one-command shortcut. There is no command list in the README to add to — `emit` is not
      mentioned there at all.
- [ ] 6.6 `docs/CHANGELOG.md`: add to the top of the existing `### Added` list under `[Unreleased]`,
      in this repo's voice — the command, the gate, the artifacts, the exit-status contract, then a
      **`For config authors:`** paragraph covering what does *not* change, the reused-`run_name`
      rule, the refused in-config `api_key`, and `emit -o`'s Windows line-ending change. (That
      bolded audience lead-in currently appears only under `### Changed`; using it under `### Added`
      is a deliberate first, since this entry has real caveats for authors.)
- [ ] 6.7 `openspec/project.md`: update the Architecture Patterns line for the new consumption mode
      (`sleap-nn` is consumed as a pinned library **and**, for `run` only, as a console script
      invoked as a subprocess), mirroring how `add-config-schema` updated the same line. While in
      that file, fix the Git Workflow line's "archived with the code on merge" — it contradicts
      `openspec/AGENTS.md` Stage 3 and all five archive PRs (#5, #18, #19, #42, #45), which archive
      in a separate follow-up PR.

## 7. Backend verification

- [ ] 7.1 Add the **real-`Popen` plumbing test** (`tests/test_backend_invoke.py`), no seams patched,
      running on **every** platform including Windows: call `backend.run_backend([sys.executable,
      "-c", <script>])` — `sys.executable` is a real executable everywhere — with a script that
      writes to stdout and stderr and exits with a chosen code. Assert with `capfd`
      (file-descriptor capture; `capsys` cannot see a child) that both streams reach the operator's
      fds (the behavioral proof of inheritance that 4.2 cannot give), and that `0` → 0 and `2` → 2
      survive a real process. This is the only automated coverage of the `Popen` path on the OS the
      GPU box actually runs.
- [ ] 7.2 Add the **stub console script** end-to-end test (`tests/test_cli_run.py`),
      `skipif(os.name == "nt")` (a shell stub is not executable there, and `CreateProcess` cannot
      launch a `.bat` without a shell — 7.1 is the Windows-side mitigation): write
      `tmp_path/bin/sleap-nn` as a `#!/bin/sh` script recording `"$@"` to a sentinel file, point
      `PATH` at it, and assert the stub received exactly `["train", "--config", <abs dest>]` through
      the full CLI path, plus a stub that `kill -9 $$`es itself → 137.
- [ ] 7.3 **[integration]** Add a `sleap-nn train --help` probe asserting `--config` is accepted —
      the upstream-compatibility check the argv contract test cannot perform, and the test that
      fails first at the Tier 6 bump to the 0.3.0 mask line. Body-level
      `pytest.importorskip("sleap_nn")`; inert in CI.
      *(No `.slp`-backed end-to-end test is proposed: `.gitignore` blocks `*.slp` and `/data/`, and
      `openspec/project.md` makes W&B the system of record, so a committed fixture is prohibited and
      a test gated on one would be a permanent skip masquerading as coverage — design D8.)*
- [ ] 7.4 On the RTX A5000 box (`[train]` installed), copy `examples/baseline_bottomup_v000_os4.yaml`
      to a **scratch** config with `run_name: runcmd_verify_<date>` and `ckpt_dir: models_scratch` —
      never the published baseline's name or directory, whose run directory exists on that box and
      whose numbers are in `docs/training.md` — and run `sleap-roots-training run` on it against the
      real v000 split. Confirm exit 0, the four configs in the run directory, and
      `resolved_config.yaml` byte-identical to `emit`'s output. Paste the console output, including
      the echoed resolved backend path, into the PR.
- [ ] 7.5 On the same box, re-run against a `run_name` whose directory already holds a `best.ckpt`
      and confirm `run` **refuses**, leaving that directory unchanged (checksum before/after). This
      is the regression that matters most — assert it against the real backend, not only the seam.
- [ ] 7.6 On the same box, interrupt a run with Ctrl-C and **record what was observed** — the exit
      code, and whether any traceback appeared. The box is native Windows, where exit codes are
      unsigned and `128 + N` does not apply, so the check there is "non-zero, no traceback, no
      success line"; the POSIX `128 + N` mapping is covered by 4.3 and 7.2.
- [ ] 7.7 Backfill the verification into `docs/training.md`'s status banner (dated, like the
      2026-07-23 entry), as its own commit after 7.4–7.6 — mirroring how `add-config-schema`
      backfilled its GPU evidence.

## 8. Verification (before requesting review of the implementation)

- [ ] 8.1 `uv run pytest --cov=src/sleap_roots_training -m "not integration" tests/` green — CI's
      actual selection, not a bare `pytest`.
- [ ] 8.2 `uv run pytest --collect-only -m integration` collects cleanly on a base install (a
      collection error in an integration test is invisible to CI's deselection).
- [ ] 8.3 `uv run black --check src/sleap_roots_training tests` and
      `uv run ruff check src/sleap_roots_training` clean — CI's scoping, not `.`.
- [ ] 8.4 Confirm `backend.py` has no uncovered branch in `resolve_sleap_nn` / `stage_artifacts` /
      `run_backend` under the base-install run.
- [ ] 8.5 `uv build`; then `uv run --isolated --with dist/*.whl sleap-roots-training run --help`
      exits 0, and `run` on a valid config **without** the extra fails with the install message and
      no traceback (`build.yml`'s existing entry-point step is the natural home for this — consider
      adding it there rather than leaving it manual).
- [ ] 8.6 `npx --yes @fission-ai/openspec@latest validate add-run-command --strict` passes. (The
      `openspec` binary is not installed globally; `openspec/**` is outside CI's paths filter, so
      this gate is manual by construction.)
- [ ] 8.7 Update this checklist to `- [x]` only once every item above is actually done.

## Commit Plan

One PR, matching the repo's precedent (#4, #15, #20 each carried proposal **and** implementation).
Those PRs interleaved proposal, implementation, and review-fix commits rather than landing in one
burst, and this one will too — the grouping below is the intended shape, not a promise that no
review-fix commit lands between them. Implementation goes out as **two visible pushes**: commits
1–5 (the command), then 6–9 (docs and verification), so each is reviewable on its own.

CI is green after every commit — `black --check src/sleap_roots_training tests`,
`ruff check src/sleap_roots_training`, `pytest -m "not integration" tests/`, on all six matrix cells.
(`ruff` selects only `D`, so a partially-built module raises no unused-code or completeness finding.)

0. `docs(openspec): propose the combined run command (#34)` — `openspec/changes/add-run-command/**`.
   Triggers no CI: `openspec/**` is outside the paths filter, and `main` has no branch protection or
   required checks (verified 2026-08-11), so nothing is left pending.
1. `fix(cli): write emitted configs with LF line endings on every platform` — group 1. **First**,
   because group 3's byte-identity tests are red on Windows until it lands; also the one change to
   existing behavior, so it stays independently revertible.
2. `feat(backend): resolve the sleap-nn console script from the interpreter env, then PATH` — group 2.
3. `feat(backend): stage the run's provenance configs; refuse to reuse a run directory` — group 3.
4. `feat(backend): invoke sleap-nn train and translate its exit status` — group 4.
5. `feat(cli): add the combined run command (validate → emit → sleap-nn train)` — group 5.
6. `docs: document the one-command run path and the run directory's contents` — group 6.
7. `test: exercise the real subprocess path on every platform` — 7.1–7.3.
8. `docs(training): record the GPU-box verification of the run command` — 7.7.

Then `chore(openspec): archive add-run-command` as its own follow-up PR on branch
`chore/archive-add-run-command`, via `openspec archive add-run-command --yes` (**not**
`--skip-specs` — this change has real deltas to promote). That matches `openspec/AGENTS.md` Stage 3
and all five archive PRs in this repo (#5, #18, #19, #42, #45); task 6.7 fixes the
`openspec/project.md` line that contradicts them.
