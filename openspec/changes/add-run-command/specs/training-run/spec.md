## ADDED Requirements

### Requirement: Combined Training Run Command

The CLI SHALL provide a `run` subcommand that performs the validate → emit → train workflow in a
single invocation on a host where the optional `train` extra is installed. `run` SHALL locate the
`sleap-nn` console script by searching, in order, the running interpreter's console-script directory
(`sysconfig.get_path("scripts")`), the directory containing the interpreter itself, and then `PATH`;
and SHALL fail fast with a clear error naming the `sleap-roots-training[train]` install when none of
them yields it. `run` SHALL print the absolute path of the resolved executable before starting the
backend. `run` SHALL invoke the backend as a subprocess and SHALL NOT import `sleap-nn`'s training
entry points. `run` SHALL execute its steps in the order gate → validate → credential check →
run-name and destination checks → run-directory refusal → write artifacts → invoke, so that a
failure at any step leaves nothing written and no subprocess started. Deep `sleap-nn` validation SHALL run only when `sleap_nn` is importable by the running
interpreter — which resolving the console script does not guarantee — and `run` SHALL report the
same skip note `validate` reports when it is not, without treating the skip as a failure.

#### Scenario: Backend not installed — fail fast, change nothing

- **WHEN** a user runs `sleap-roots-training run config.yaml` on a host where the `sleap-nn` console
  script is found in none of the three searched locations
- **THEN** the command exits non-zero with a clear message naming the
  `sleap-roots-training[train]` install (not a traceback)
- **AND** no file is written anywhere
- **AND** no subprocess is started

#### Scenario: The interpreter's own environment is preferred over PATH

- **WHEN** a `sleap-nn` console script exists both in the running interpreter's console-script
  directory and elsewhere on `PATH`
- **THEN** `run` invokes the one from the interpreter's console-script directory

#### Scenario: The interpreter's own directory is searched before PATH

- **WHEN** no `sleap-nn` console script exists in the interpreter's console-script directory, but one
  exists beside the interpreter itself and another exists on `PATH`
- **THEN** `run` invokes the one beside the interpreter

#### Scenario: PATH is the fallback, not the first choice

- **WHEN** no `sleap-nn` console script exists in the interpreter's console-script directory or
  beside the interpreter, but one exists on `PATH`
- **THEN** `run` invokes the one on `PATH`

#### Scenario: The resolved backend is named before a long run starts

- **WHEN** `run` has resolved the backend and is about to invoke it
- **THEN** it prints the absolute path of the resolved `sleap-nn` executable
- **AND** it prints the path of the config the backend will be given

#### Scenario: Invalid config is rejected before anything is written

- **WHEN** a user runs `run` on a config that fails validation (an out-of-vocabulary
  `experiment.species`, a missing `trainer_config.seed`, or an unparseable file)
- **THEN** the command exits non-zero with the same field-named error `validate` reports
- **AND** no file is written anywhere
- **AND** no subprocess is started

#### Scenario: Backend resolves but sleap_nn is not importable here

- **WHEN** the `sleap-nn` console script resolves from `PATH` (an environment other than the one
  running `sleap-roots-training`) and `sleap_nn` is not importable by this interpreter
- **THEN** `run` performs the base-safe checks and prints the same "deep `sleap-nn` validation
  skipped" note `validate` prints
- **AND** the skip is not treated as a failure
- **AND** `run` proceeds to write its artifacts and invoke the backend

#### Scenario: The backend's training internals are never imported

- **WHEN** `run` executes to completion with the subprocess invocation replaced by a stub
- **THEN** `sleap_nn` is absent from `sys.modules` afterwards
- **AND** neither the CLI module nor the backend module contains an import of `sleap_nn` at any
  nesting depth

### Requirement: Run Directory Provenance Artifacts

Before invoking the backend, `run` SHALL write two files into the run directory
`<trainer_config.ckpt_dir>/<trainer_config.run_name>/`: `resolved_config.yaml`, the emitted
sleap-nn-native config with the same content `emit` produces for that input; and
`source_config.yaml`, a verbatim copy of the input config including the repo-owned `experiment`
block. Neither SHALL be a temporary file, an in-memory pipe, or a file `run` deletes afterwards.
Both SHALL be written with LF (`\n`) line endings on every platform and SHALL be written atomically,
so a failed write leaves no truncated artifact. `trainer_config.ckpt_dir` SHALL default to `"."`,
matching the backend's own default. `run` SHALL require a usable `trainer_config.run_name` — a
string that is non-empty after stripping surrounding whitespace, is not the literal `"None"` (which
the backend itself treats as unset), is not absolute, and contains no path separator — and SHALL
refuse otherwise, naming the field. `run` SHALL refuse to reuse a run directory that
already holds evidence of a previous run (a `best.ckpt`, or the `training_config.yaml` the backend
writes on completion), naming the directory and instructing the operator to choose a new
`trainer_config.run_name`; no flag SHALL override this refusal. `--resolved-config PATH` SHALL
relocate the emitted config only, and SHALL reject a path that is a directory or that is the input
config itself.

#### Scenario: Both artifacts land in the run directory

- **WHEN** `run` executes a valid config that sets `trainer_config.ckpt_dir` and a usable
  `trainer_config.run_name`
- **THEN** `<ckpt_dir>/<run_name>/resolved_config.yaml` and `<ckpt_dir>/<run_name>/source_config.yaml`
  both exist
- **AND** the backend is invoked with the absolute path of `resolved_config.yaml`

#### Scenario: The persisted configs match their sources exactly

- **WHEN** the same valid config is passed to `emit -o out.yaml` and to `run`
- **THEN** `resolved_config.yaml` and `out.yaml` hold identical bytes
- **AND** `resolved_config.yaml` omits the `experiment` block while retaining the `data_config` /
  `model_config` / `trainer_config` blocks
- **AND** `source_config.yaml` holds the input config's content, including its `experiment` block

#### Scenario: Artifacts use LF line endings on every platform

- **WHEN** `run` writes its artifacts on Windows
- **THEN** neither file contains a CR byte
- **AND** a subsequent invocation recognizes them as unchanged rather than as differing content

#### Scenario: An unset checkpoint directory follows the backend's default

- **WHEN** a valid config omits `trainer_config.ckpt_dir`
- **THEN** `run` uses `.` as the checkpoint directory, the same default the backend applies
- **AND** the artifacts land in `./<run_name>/`

#### Scenario: An unusable run name is refused, never guessed

- **WHEN** `trainer_config.run_name` is absent, empty, whitespace-only, or the literal `"None"`
- **THEN** the command exits non-zero naming `trainer_config.run_name`
- **AND** the message explains the backend would generate a timestamped name `run` cannot predict
- **AND** no file is written and the backend is not invoked

#### Scenario: A run name that escapes the run directory is refused

- **WHEN** `trainer_config.run_name` is an absolute path or contains a path separator
- **THEN** the command exits non-zero naming `trainer_config.run_name`
- **AND** no file is written outside the checkpoint directory

#### Scenario: A run directory holding a previous run is refused

- **WHEN** the run directory already contains a `best.ckpt` or a `training_config.yaml` from an
  earlier run
- **THEN** the command exits non-zero naming that directory and instructing the operator to choose a
  new `trainer_config.run_name`
- **AND** the existing directory is left byte-for-byte unchanged
- **AND** no flag overrides this refusal
- **AND** the backend is not invoked

#### Scenario: Retrying a run that never completed proceeds without a flag

- **WHEN** the run directory exists but holds neither a `best.ckpt` nor a `training_config.yaml` (a
  run that died before the backend wrote either)
- **THEN** `run` overwrites its own two artifacts and proceeds
- **AND** no flag is required

#### Scenario: Relocating the emitted config

- **WHEN** `run` is given `--resolved-config <path>`
- **THEN** the emitted config is written to `<path>`
- **AND** `source_config.yaml` is still written into the run directory
- **AND** the backend is invoked with `<path>`

#### Scenario: A destination that would destroy input or is not a file is refused

- **WHEN** `--resolved-config` names an existing directory, or names the input config itself, or
  resolves to a path inside the run directory that would collide with an artifact `run` writes
- **THEN** the command exits non-zero naming the path (not a traceback)
- **AND** the input config is left unchanged
- **AND** the backend is not invoked

#### Scenario: A failed write leaves no partial artifact

- **WHEN** writing an artifact fails partway (a full disk) or the destination is unwritable
- **THEN** the command exits non-zero with a clear message naming the path
- **AND** no truncated file is left at the destination
- **AND** the backend is not invoked

### Requirement: Backend Invocation And Exit Status

`run` SHALL invoke the backend with the argument vector
`[<resolved sleap-nn>, "train", "--config", <absolute path to the emitted config>]` — without a
shell, and forwarding no additional arguments or backend-side configuration overrides. The child
SHALL inherit this process's environment and working directory unmodified, since relative dataset
and checkpoint paths are resolved by the backend against them. The child's standard output and
standard error SHALL be inherited rather than captured, so a long run streams live. `run` SHALL exit
0 only when the backend exits 0; SHALL propagate a positive backend exit status verbatim when it is
within the range the platform can represent; and SHALL exit `128 + N` with a message naming signal
`N` where the platform reports signal termination as a negative return code. On an operator
interrupt, `run` SHALL NOT kill or signal the backend and SHALL wait for the backend's own exit
status, so the backend can shut down gracefully. `run` SHALL NOT print a success line for a failed
run, SHALL NOT emit a traceback, and SHALL NOT delete the artifacts of a failed run.

#### Scenario: The backend is invoked with exactly the documented argument vector

- **WHEN** `run` invokes the backend
- **THEN** the argument vector is `[<resolved sleap-nn>, "train", "--config", <path>]` and `<path>`
  is absolute
- **AND** no shell is used, and no additional arguments or backend-side overrides are appended

#### Scenario: The backend inherits the operator's environment and working directory

- **WHEN** `run` invokes the backend
- **THEN** the child inherits this process's environment and working directory unmodified
- **AND** `run` neither constructs nor filters either of them

#### Scenario: The backend's streams are inherited, not captured

- **WHEN** `run` creates the backend subprocess
- **THEN** it is created with no redirection of standard output or standard error
- **AND** `run` does not read, buffer, or reprint the backend's output

#### Scenario: Successful training reports where the artifacts are

- **WHEN** the backend exits 0
- **THEN** `run` exits 0
- **AND** it prints one line naming the run directory and the persisted configs

#### Scenario: Backend failure propagates its exit status

- **WHEN** the backend exits with a non-zero status such as 2
- **THEN** `run` exits with that same status
- **AND** it prints no success line and emits no traceback

#### Scenario: Signal termination is reported where the platform expresses it

- **WHEN** the backend is terminated by a signal on a platform that reports this as a negative
  return code (for example SIGKILL from the OOM killer)
- **THEN** `run` exits `128 + N` for signal number `N`
- **AND** it prints a message naming the signal

#### Scenario: A status the platform cannot represent as an exit code is still a failure

- **WHEN** the backend exits with a status outside the range a process exit code can carry (for
  example a large Windows status such as `0xC000013A`)
- **THEN** `run` exits non-zero without synthesizing a `128 + N` value
- **AND** it prints a message naming the raw status

#### Scenario: An operator interrupt is handed to the backend

- **WHEN** the operator interrupts a run (Ctrl-C, which reaches both processes)
- **THEN** `run` does not kill or signal the backend
- **AND** it waits for the backend's own exit status and reports it
- **AND** it emits no traceback

#### Scenario: A failed run keeps its provenance artifacts

- **WHEN** the backend exits non-zero after `run` has written its artifacts
- **THEN** the artifacts remain on disk as the record of what was attempted
- **AND** `run` does not delete or roll back the run directory

### Requirement: Credential Safety For Persisted Configs

Because `run` writes configs into the run directory — a directory this package uploads wholesale
when publishing a model — `run` SHALL refuse a config that carries a non-empty
`trainer_config.wandb.api_key`, naming the supported credential paths instead. When a config enables
W&B, `run` SHALL verify that a credential resolves before writing anything or starting the backend,
using the same check the registry commands use.

#### Scenario: An in-config W&B API key is refused, never persisted

- **WHEN** `run` executes a config whose `trainer_config.wandb.api_key` is set to a non-empty value
- **THEN** the command exits non-zero naming `WANDB_API_KEY` / `wandb login` as the supported ways to
  supply the credential
- **AND** no file is written and the backend is not invoked

#### Scenario: W&B is enabled but no credential resolves

- **WHEN** `run` executes a config with `trainer_config.use_wandb: true` on a host where neither
  `WANDB_API_KEY` nor a netrc entry for `api.wandb.ai` resolves
- **THEN** the command exits non-zero with the same credential message the registry commands report
- **AND** no file is written and the backend is not invoked

#### Scenario: A run with W&B disabled needs no credential

- **WHEN** `run` executes a config that leaves `trainer_config.use_wandb` absent or false
- **THEN** no credential check is performed
- **AND** the run proceeds

### Requirement: One-Command Path Is Documented

The config-driven training guide SHALL document the one-command path in a single place: the
invocation, the `[train]`-extra gate, the artifacts written into the run directory alongside those
the backend itself writes, the run-name rule, and the invocation form that does not disturb an
environment where the `train` extra was installed separately. The guide SHALL continue to document
the three-command `validate` → `emit` → `sleap-nn train` path independently of the one-command
section, since that path remains canonical for authoring on one machine and training on another.

#### Scenario: The guide documents the one-command path

- **WHEN** the training guide is read
- **THEN** it contains a fenced `sleap-roots-training run` invocation
- **AND** that section names the persisted artifacts and states that the `train` extra is required
- **AND** no unresolved placeholder (`TODO` / `TBD`) is left in the guide

#### Scenario: The canonical three-command path survives on its own

- **WHEN** the guide's fenced blocks that do not mention `run` are inspected
- **THEN** the `validate`, `emit`, and `sleap-nn train --config` commands are each still present
  among them
- **AND** the one-command section has not become the only place they appear
