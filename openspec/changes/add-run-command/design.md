# Design: combined `run` command

## Context

`validate` and `emit` were built base-install safe so a config can be authored and checked on a
laptop and trained on an isolated GPU box. That split stays. This change adds one command for the
*other* case — both installed on one host — where the split buys nothing and costs an
operator-managed intermediate file whose staleness is invisible.

Everything below is grounded in `sleap-nn` 0.2.0 as actually installed (the version the `train`
extra pins; source read from the uv cache), because the first draft of this proposal got three
run-directory facts wrong by reasoning from the docs instead. The load-bearing ones:

| Fact | Source |
| --- | --- |
| The backend writes `initial_config.yaml` **and** `training_config.yaml` into `<ckpt_dir>/<run_name>/`, stamped with `sleap_nn_version` | `training/model_trainer.py:1266,1269,1313` |
| It auto-suffixes the run dir to `<run_name>-1` when the dir exists **and** holds `best.ckpt` | `training/model_trainer.py:522-533` |
| With no `run_name` it generates `<timestamp>.<model_type>.n=<frames>` — never writes into `<ckpt_dir>` itself | `training/model_trainer.py:513` |
| `ckpt_dir` defaults to `"."`, not to unset | `config/trainer_config.py:368`, `model_trainer.py:486` |
| It masks `trainer_config.wandb.api_key` in both configs it saves | `training/model_trainer.py:997-999` |
| `sleap-nn train --config X` feeds X to Hydra as `initialize_config_dir(X.parent)` + `compose(X.name)` | `cli.py:290-296,375-408` |

The constraint that shapes the rest: a run is long, expensive to repeat, and the artifact later
write-ups point at is `<ckpt_dir>/<run_name>/`. Anything `run` does must leave that directory *more*
self-describing, and must never leave an artifact describing a run other than the one beside it.

## Goals / Non-Goals

- **Goals:** one command for the co-installed case; the `experiment` identity recorded next to the
  run; the backend's own failure surfaced verbatim; zero change to `validate` / `emit` semantics or
  to the base install.
- **Non-Goals:** flag or override proxying, sweeps, W&B orchestration, resume, device selection,
  replacing the three-command path, in-process use of the backend, config hashing (#10/#11).

## Decisions

### D1 — Shell out to `sleap-nn train`, never import its training internals

Calling `run_training(...)` in-process would couple us to a call signature across the 0.2.x → 0.3.x
mask-line bump the roadmap already plans, and would put Lightning's process-level side effects
(signal handlers, CUDA init, `sys.exit`) inside our CLI process. A subprocess gives us the exit
status for free and keeps the coupling at the documented CLI surface.

This is a **new consumption mode** for this repo, not an application of an existing rule:
`openspec/project.md` says `sleap-nn` / `sleap-io` are consumed as pinned libraries and their
internals are not modified — it says nothing about invoking their console scripts. The architecture
line gets updated to name the exception (tasks group 5).

It also does not contradict `validate`'s deep check, which imports
`sleap_nn.config.training_job_config.verify_training_cfg` — a config-validation API, not the training
entry point, and unchanged here.

### D2 — Resolve the executable from this interpreter's environment first, then `PATH`

1. `shutil.which("sleap-nn", path=sysconfig.get_path("scripts"))`
2. `shutil.which("sleap-nn", path=str(Path(sys.executable).parent))`
3. `shutil.which("sleap-nn")`
4. none → `ClickException` naming `uv pip install "sleap-roots-training[train]"` (and the
   `uvx --from "sleap-roots-training[train]" …` form), pointing at `docs/training-backend.md`.

`sysconfig.get_path("scripts")` rather than `Path(sys.executable).parent` is load-bearing, not
style: on POSIX venvs they agree, but for a base Windows install (`C:\Python311\python.exe` vs
`…\Scripts\`), a conda env on Windows, or a Linux `pip install --user`, they do not — and the
documented GPU box is **native Windows** (`docs/training-backend.md` §1), escaping this only because
`uv venv` happens to put `python.exe` inside `Scripts\`. Getting it wrong produces the worst possible
diagnostic: "install the `[train]` extra" on a box where it is installed. Step 2 stays as
belt-and-braces for relocated schemes. `shutil.which` (rather than probing a filename) also handles
Windows `PATHEXT` — but its result is **verified against the directory we asked about** before being
accepted. On win32 + Python 3.11 (the version `build.yml` pins, on the OS that trains) `which`
prepends `os.curdir` to the search *even when `path=` is given*, mimicking cmd.exe, and returns a
relative match. Without that check, a stray `sleap-nn.exe` in the invocation directory would beat
the interpreter's `Scripts\` — defeating this ordering entirely — and would print as a bare
filename, so the visibility mitigation below would fail exactly when the hazard fires. 3.12+ honour
`path=`, which makes this version-scoped rather than universal, and therefore easy to miss.

The interpreter-first rule is **not unconditionally safer**, and we accept that knowingly: if this
package is installed in a pipx/uvx env while the operator has *activated* a venv holding the pinned
`sleap-nn`, step 1 picks the stale sibling. The mitigation is visibility, not a different order —
`run` echoes the absolute resolved path before starting, so a wrong pick sits one line above the log
instead of surfacing days later as "the numbers came out wrong".

`importlib.util.find_spec("sleap_nn")` is deliberately not the gate — the failure to prevent is
"cannot execute the trainer". The consequence is that the gate can pass while `sleap_nn` is *not*
importable here (a `PATH` hit from another environment), in which case `validate`'s deep check is
skipped; `run` echoes that skip note rather than claiming a deep validation it did not do.

### D3 — Write the artifacts the backend cannot, into the run directory

The backend already persists the resolved config twice (table above), so a third copy must justify
itself. **Decision: both artifacts are written** — this is settled here rather than left to review,
because the spec's destination and refusal scenarios are built on it.

The decisive argument is that the emitted config is not an optional keepsake: `run` invokes the
backend as `sleap-nn train --config <path>`, so that file **must exist on disk** for the command to
work at all. The only real question is where it lands and whether `run` deletes it afterwards, and
#34 answers that explicitly ("rather than piping it to `sleap-nn train` purely in-memory/via a
throwaway temp file"). Keeping it in the run directory therefore costs one already-required write
and no extra machinery. The alternative considered and rejected — stage it outside the run directory
and rely on the backend's `initial_config.yaml` — buys one fewer file in exchange for losing the
pre-start guarantee below, and leaves the staged input orphaned somewhere less discoverable.

Two artifacts, each with a distinct reason:

- **`source_config.yaml`** — a verbatim copy of the input, carrying the `experiment` block
  (species / mode / root_type / dataset). Every config the backend sees has that block stripped by
  construction, so this is the one piece of provenance no sleap-nn artifact can hold. This is the
  part of the change with genuinely new information.
- **`emitted_config.yaml`** — the emitted sleap-nn-native config, which #34 asks for explicitly. It
  earns its place on two counts the backend's files cannot cover: it exists **before** the backend
  starts (sleap-nn writes its two only after trainer construction and only on `global_rank == 0`, so
  a run that dies on a bad `.slp` path or at model init otherwise leaves a directory with no config
  at all), and it is the **input**, whereas `training_config.yaml` is post-mutation (the backend
  rewrites `run_name`, `in_channels`, `cache_img_path`, `wandb.current_run_id` into it). Of these,
  only the first is unique against `initial_config.yaml`, which is also a pre-mutation copy — the
  honest weight of this artifact rests on pre-start existence plus the fact that it has to be
  written anyway.

The filename is settled, not open: `training_config.yaml` **must not** be used — the backend writes
that exact name into the same directory and would silently overwrite ours at the end of every
successful run. Extra dots are also avoided (`emitted_config.yaml`, not `<run>.resolved.yaml`) since
the name is handed to Hydra as a config name.

It is `emitted_config.yaml` rather than `resolved_config.yaml` because the earlier name was actively
misleading: this file is written with `resolve=False`, while sleap-nn's neighbouring
`training_config.yaml` *is* the config after its own resolution. Two files side by side, and the one
labelled "resolved" being the unresolved one, is the kind of detail a reader trusts and should not.

The backend's reported version is echoed before the run rather than stamped into the artifact —
stamping would break the byte-identity-with-`emit` guarantee. sleap-nn writes its version into
`initial_config.yaml`, but only once the trainer is built, which is precisely the window this
artifact exists to cover, so for a run that dies during setup the console line is the only record of
what would have trained it.

Destination: `<ckpt_dir>/<run_name>/`, with `ckpt_dir` defaulting to `"."` to match the backend.
`--emitted-config PATH` relocates the emitted config only (`dir_okay=False`, and refused when it
names the input config — overwriting the source with its `experiment`-stripped form would destroy
the only copy of the run's identity). Writes are atomic (temp file in the destination directory +
`os.replace`) because `Path.write_text` on ENOSPC leaves a truncated file behind, and LF-normalized
(`newline="\n"`) because the GPU box is Windows and CRLF would break byte-comparison of artifacts
that #10/#11 will eventually hash.

### D4 — Refuse to reuse a run directory; there is no `--force`

`run` fails when `<ckpt_dir>/<run_name>/` already holds a `best.ckpt` or a `training_config.yaml`,
naming the directory and telling the operator to change `trainer_config.run_name`.

The reason is the auto-suffix: with `best.ckpt` present the backend trains into `<run_name>-1`, so
anything we write under `<run_name>/` would describe a *different* run than the one beside it. The
first draft's answer — refuse on differing content, offer `--force` — was actively harmful: taking
the offered flag rewrote run A's provenance in place while run B trained into `-1`, leaving one
directory whose config contradicts its own checkpoint and another with no config at all. Strictly
worse than doing nothing. So the flag is gone; a name collision's correct remedy is a new name.

Checking `training_config.yaml` as well as `best.ckpt` is deliberately *stricter* than the backend's
own trigger: a `save_ckpt: false` run never writes `best.ckpt`, so the backend reuses that directory
in place and silently mixes two runs' outputs. That is the one case where a repo-side guard is the
only protection.

A directory holding neither (a run that died before the backend wrote anything) is the retry case:
`run` overwrites its own two artifacts and proceeds, no flag needed.

`run_name` must be usable — non-empty, not the literal `"None"` (which the backend treats as
unset), and **exactly one path component under both POSIX and Windows semantics**, carrying no
character or device name Windows forbids. The component count is deliberate, not decoration:
`is_absolute()` plus a separator scan reports `C:foo` as safe, yet `PureWindowsPath("ckpt") /
"C:foo"` evaluates to `C:foo`, because pathlib discards the left-hand side once the right carries a
drive. That would put the artifacts outside the very directory D4 guards, on the one OS this command
exists for. Applying the rule under both flavours on every platform means a name that would escape
on the box is rejected on the laptop that authored it.

The component count is necessary but **not sufficient**, which review established one shape at a
time and is worth stating as a rule instead of a list. `".."` is exactly one component under both
flavours, so it cleared the count while `<ckpt_dir>/..` resolved *above* the checkpoint directory —
the same escape, one shape over. Windows also silently strips a trailing dot or space, so `"r1 "`
and `"r1"` name **one** directory there and **two** here, which made the reuse refusal answer
differently on the authoring host and the training host (and let `"NUL "` walk past the device-name
check). Hence the extra gates: no relative directory reference, no trailing dot or space, no control
characters. The general lesson lives in the test rather than the code — the invariant is now asserted
as *containment of the resolved run directory inside the resolved `ckpt_dir`*, which no future shape
can satisfy while escaping, rather than as an enumerated list of bad names.

`trainer_config.ckpt_dir` is validated for the same reason: it supplies the left-hand side of every
path this design guards, and `or "."` used to swallow `""`, `false` and `null` alike, so a typo
silently redirected the run's provenance while reporting success. With none of those, the backend generates a timestamped name we
cannot predict; dropping artifacts in `<ckpt_dir>` instead would place them one level above the real
run, next to every other run sharing that directory (every committed example uses `ckpt_dir: models`).
Refusing costs one config line.

### D5 — Inherit environment, cwd, and streams; let the backend own the interrupt

`subprocess.Popen([bin, "train", "--config", str(dest.resolve())])` — a vector, never a shell string,
with no `env=`, no `cwd=`, and no stream redirection:

- **Environment** inherited unmodified: `WANDB_API_KEY`, `CUDA_VISIBLE_DEVICES`, `WANDB_MODE`, and
  proxy settings are how the operator steers a run, and `run` proxies no flags of its own.
- **Working directory** inherited: every committed example uses relative `ckpt_dir` and
  `train_labels_path`, resolved by the backend against *its* cwd, which must agree with the
  destination we computed. The `--config` argument is absolutized so the argv is correct regardless.
- **Streams** inherited: a multi-hour run streams live and nothing is buffered in memory.

Exit status:

- `0` → one success line naming the run directory and the artifacts.
- positive and representable → propagated verbatim, no success line, no traceback.
- negative (POSIX: killed by signal `N`) → `128 + N` with the signal named. Passing `-9` to
  `sys.exit` would surface as an unrelated `247`.
- a status outside what an exit code can carry (Windows `0xC000013A` from Ctrl-C) → exit non-zero
  naming the raw status, with no `128 + N` synthesis. The `128 + N` convention is POSIX-only, which
  matters because the GPU box is Windows.

**Ctrl-C needs explicit handling.** `subprocess.run` is wrong here: SIGINT reaches the whole
foreground group, so the parent takes it too, and CPython's `run()` responds by `process.kill()`
(SIGKILL) and re-raising — which makes the signal branch unreachable, surfaces as Click's `Aborted!`
at exit 1, and SIGKILLs a trainer that had just been asked to stop gracefully, destroying Lightning's
checkpoint-on-interrupt. So `run` uses `Popen` and waits in a loop that swallows the parent's
`KeyboardInterrupt` and lets the child own the signal:

```python
proc = subprocess.Popen(argv)          # streams inherited; no shell
while True:
    try:
        returncode = proc.wait()
        break
    except KeyboardInterrupt:
        continue                        # the child already got SIGINT; let it shut down
```

The loop has **no timeout**, deliberately — force-killing a trainer after N seconds would
reintroduce exactly the lost-checkpoint failure this decision exists to prevent. It does have a
ceiling, on a counter rather than a clock. An earlier draft of this section claimed the operator
"keeps the real escape hatch (a second interrupt…)", which was **false**: every further Ctrl-C hit
the same `continue`, so a child ignoring SIGINT could not be aborted at all. A documented safety
property that is not true is worse than an undocumented gap, because it stops the next reviewer
looking. The ladder is now: the first interrupt is forwarded and says so, the second terminates the
backend, the third kills it. Escalating only on an explicit repeat keeps the graceful path for the
ordinary case, where the first interrupt is all it takes.

One honest limit on the automated coverage: the parent-side `KeyboardInterrupt` is exercised with a
stubbed `wait()` that raises it, because a genuine SIGINT would have to be delivered to the whole
foreground process group and would take the test runner with it. The real signal path is covered on
POSIX by a stub that `kill -9`s itself, and on Windows by the recorded manual verification (which
showed Lightning's own graceful shutdown running, then a clean non-zero exit).

### D5a — Interpolation: the gates resolve, the artifact does not

`backend.py` reads every gated field through `OmegaConf.select`, which **resolves**, while
`to_sleap_nn_yaml` writes with `resolve=False` and with the `experiment` block stripped. Those two
facts are individually right and jointly dangerous, in both directions:

- **Unresolvable references reached the operator as tracebacks.** `${oc.env:UNSET}` in `run_name`,
  `ckpt_dir` or `wandb.api_key` raised an OmegaConf exception straight past the CLI's
  `except BackendError` — and `${oc.env:WANDB_API_KEY}` is the pattern the credential guidance
  points operators toward, so an unexported variable is an ordinary mistake, not an exotic one.
  Every read now goes through a wrapper that names the field.
- **References that resolve *here* gated on a value the backend can never see.**
  `run_name: ${experiment.species}_v1` resolves against the full config, so every gate validated
  `arabidopsis_v1` and staged the artifacts there — while the emitted file kept the interpolation
  *and* lost the block it points at, so the backend could not load it at all. `run` therefore
  pre-flights `to_container(to_sleap_nn_config(cfg), resolve=True, throw_on_missing=True)` as a
  **check only**, before anything is staged.

The emitted file stays unresolved on purpose: that is what keeps `${oc.env:WANDB_API_KEY}` a literal
interpolation in the artifact rather than a baked secret, and it is a stronger reason than
byte-identity for D9 refusing an inline key rather than masking one.

### D6 — Step order is a contract, not an implementation detail

`gate → validate → credential check → run-name and destination checks → run-directory refusal →
write artifacts → invoke` — the same seven steps, in the same words, as the spec requirement, so the
two cannot drift. Every cheap failure precedes every side effect: no backend, invalid config, missing W&B
credential, unusable `run_name`, or occupied run directory all fail with **nothing written and no
subprocess started**. This is asserted in tests, not merely documented, because the failure it
prevents — a stale artifact beside a run that never happened — is indistinguishable later from a
real one. Conversely, a failure *after* the backend starts leaves the artifacts in place: they are
the record of what was attempted, and rolling them back would destroy the evidence.

### D7 — A small `backend.py`, not more logic in `cli.py`

`cli.py` is a thin command surface; `config.py` holds config-domain logic and is untouched.
Executable resolution, destination policy, artifact staging, argv construction, and exit-status
translation are domain logic with distinct failure modes worth unit-testing directly, so they land
in a new `sleap_roots_training/backend.py` (stdlib only). `backend.py` performs no process exit of
its own — it returns a translated status and the CLI owns `ctx.exit`, mirroring how `seed-registry`
composes `registry.*`.

### D8 — Testable in CI, which cannot install the backend

CI never selects the `train` extra, so the unit tests assert the contract through two seams —
`backend.resolve_sleap_nn` and `backend._interpreter_scripts_dir` — plus module-attribute patching of
`backend.subprocess`, following the existing `tests/test_registry_lineage.py:29` precedent. No
private `_subprocess_run` wrapper: a wrapper launders the call, so asserting "no redirection kwargs"
against it would prove nothing about what reaches `subprocess`.

Two things the seams cannot prove — that streams really are inherited, and that exit statuses
survive a real process — are covered by driving the real `Popen` path twice:

- **Every platform, including Windows:** `run_backend` takes an argv, so a test can hand it
  `[sys.executable, "-c", <script>]`. `sys.executable` is a real executable everywhere, so the
  plumbing (inherited fds asserted with `capfd`, exit-status propagation, the interrupt wait loop)
  is exercised on the Windows leg too — the OS the GPU box actually runs. This is why `build_argv`
  is a separate pure function rather than something `run_backend` does internally.
- **POSIX only:** a `#!/bin/sh` **stub console script** on a temp `PATH`, which additionally covers
  resolution-through-`PATH` and the exact argv the backend receives, plus a `kill -9` self-signal
  for the `128 + N` mapping. Skipped on Windows, where a shell stub is not executable and `.bat`
  cannot be launched by `CreateProcess` without a shell.

Neither needs the extra or a `.slp`, so both run in CI.

An `.slp`-backed end-to-end test is **not** proposed: `.gitignore` blocks `*.slp` and `/data/`, and
`openspec/project.md` makes W&B the system of record, so a committed fixture is prohibited — a test
gated on one would be a permanent skip masquerading as coverage. Real-backend confidence comes from
an integration-marked `sleap-nn train --help` probe (the compatibility check the argv test cannot
perform; it is what fails first at the Tier 6 bump) plus manual GPU-box verification recorded in the
PR, the same evidence standard Tier 0.5 and the Tier 1 baseline used.

### D9 — Refuse an in-config W&B credential

`trainer_config.wandb.api_key` is a real backend field, and the backend masks it in both configs it
writes ("Mask API key in both configs to prevent saving to disk"). Meanwhile `registry/publish.py:42`
uploads the entire model directory via `artifact.add_dir`. Persisting an unmasked config there would
publish the key as a registry artifact. Masking it in our copy instead would break the
byte-identity-with-`emit` contract, so `run` refuses a non-empty value and names the paths this repo
already uses (`WANDB_API_KEY`, `wandb login` — see the archived `update-wandb-credential-guard`
change). `emit`'s existing behavior is unchanged; only `run`, which places files in the published
directory, is stricter.

Relatedly, since every committed baseline example sets `use_wandb: true`, `run` reuses
`cli._require_api_key()` before writing anything — a missing credential otherwise kills the run hours
in, at `wandb.init()`.

### D10 — LF line endings for both `run` and `emit`

`Path.write_text` opens with `newline=None`, translating `\n` to `\r\n` on Windows. Left alone, the
artifact `run` writes and the file `emit -o` writes would differ byte-wise from their Linux
equivalents on the one host that actually trains, and any byte-comparison (including the retry
check) would misfire there. Both write with `newline="\n"`. This changes `emit`'s output on Windows
— the only behavior change to an existing command in this proposal — and is a strict improvement for
a YAML artifact that #10/#11 will want to hash.

## Risks / Trade-offs

- **Two documented ways to train.** → The guide keeps the three-command path canonical and presents
  `run` as the co-installed shortcut; the contract test asserts the canonical commands survive
  *outside* the `run` section, so the shortcut cannot quietly replace them.
- **`sleap-nn`'s CLI surface is now a coupling point.** → No runtime version assertion (the `<0.3.0`
  cap already bounds it, and a check would fire on every legitimate bump). The argv test is a
  change-detector on our side only — it cannot see an upstream rename — so the real guard is the
  integration `--help` probe, which runs exactly where it matters: the Tier 6 mask re-verify.
- **`uv run` re-syncs and would uninstall the `[train]` extra** installed by `uv pip install
  ".[train]"`, making the gate fire on a box where the backend *was* installed. → The guide documents
  `uv run --no-sync` (or the absolute venv path), the same rule `scripts/clean_pkg.py` and
  `scripts/dump_val_metrics.py` already carry.
- **The interpreter-first resolution can pick a stale backend.** → Accepted with the echoed absolute
  path as mitigation (D2).
- **A third and fourth config file in the run directory.** → Named distinctly, each justified in D3,
  and the guide gains an inventory of what lands there and who wrote it. Open question 1 invites
  trimming to one.

## Migration Plan

None required — additive CLI surface, no dependency change, no semantic change to `validate` /
`emit` / `seed-registry`. Rollback is deleting the subcommand and `backend.py`; nothing else imports
them. The `emit` newline fix is independently revertible.

## Open Questions

Question 1 of the first draft — "both artifacts, or only `source_config.yaml`?" — is **closed**, and
the answer is in D3: the emitted config has to be written for the backend to be invoked at all, and
#34 rules out a throwaway temp, so it stays in the run directory. It is a decision, not a deferral,
because the destination and refusal scenarios are written on top of it.

The remaining three change no spec text whichever way they go:

1. **Is the run-directory refusal too strict?** It is stricter than the backend's own trigger (D4),
   on purpose — a `save_ckpt: false` run leaves no `best.ckpt`, so the backend would silently reuse
   the directory. The cost is that reusing a name means deleting a directory by hand.
2. **`run` vs `train` as the verb.** Recommendation: keep `run`. `sleap-roots-training train` and
   `sleap-nn train` would be near-homographs in adjacent fenced blocks that take *different* inputs
   (source vs emitted), and getting them backwards reproduces the exact `ConfigKeyError` the guide
   already documents.
3. **Refuse an in-config `wandb.api_key`, or mask it?** Refusal is specified (D9) because masking
   breaks byte-identity with `emit`. Masking only in `source_config.yaml` is the alternative.
