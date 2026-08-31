"""Locate and drive the ``sleap-nn`` training backend as a subprocess.

The backend is consumed through its **console script**, never by importing its training
entry points: ``openspec/project.md`` consumes ``sleap-nn`` / ``sleap-io`` as pinned
libraries, and a subprocess additionally keeps Lightning's process-level side effects
(signal handlers, CUDA init, ``sys.exit``) out of this CLI's process while handing us the
backend's exit status for free.

Nothing here imports ``sleap_nn``. The module is base-install safe and stdlib-only, so the
cross-platform CI matrix -- which never installs the ``train`` extra -- exercises every
path in it through stub executables.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import NamedTuple, Optional

from omegaconf import OmegaConf
from omegaconf.errors import OmegaConfBaseException

from sleap_roots_training import config as training_config

#: The console script the ``train`` extra installs. Bare name on purpose: ``shutil.which``
#: applies ``PATHEXT`` itself on Windows, so we never spell an extension here.
SCRIPT_NAME = "sleap-nn"

_MISSING_BACKEND = (
    f"the {SCRIPT_NAME!r} training backend is not installed (or is not on PATH).\n"
    'Install it with:  uv pip install "sleap-roots-training[train]"\n'
    'or, for an isolated run:  uvx --from "sleap-roots-training[train]" '
    "sleap-roots-training run <config.yaml>\n"
    "See docs/training-backend.md for the GPU install."
)


class BackendError(RuntimeError):
    """The ``sleap-nn`` backend could not be located, staged for, or driven."""


def _interpreter_scripts_dir() -> str:
    r"""Return the console-script directory of the interpreter running this process.

    ``sysconfig.get_path("scripts")`` rather than ``Path(sys.executable).parent`` is
    load-bearing: the two agree for a POSIX venv, but for a base Windows install
    (``C:\\Python311\\python.exe`` vs ``C:\\Python311\\Scripts\\``), a conda environment on
    Windows, or a Linux ``pip install --user``, they do not -- and the documented GPU box
    is native Windows. Isolated as a function so tests can drive the lookup.

    Returns:
        The path to this environment's console-script directory.
    """
    return sysconfig.get_path("scripts")


def resolve_sleap_nn() -> Path:
    """Locate the ``sleap-nn`` console script, preferring this interpreter's environment.

    Searched in order: this environment's console-script directory, the directory holding
    the interpreter itself (belt-and-braces for a relocated scheme), then ``PATH``. The
    interpreter-first order matters because the GPU box is routinely driven by an absolute
    path into a venv, where a bare ``PATH`` lookup can miss a backend that *is* installed
    -- or find an unrelated one built against different pins.

    That order is not unconditionally safer: if this package is installed in a pipx/uvx
    environment while the operator has activated a venv holding the pinned ``sleap-nn``,
    the sibling wins. The mitigation is visibility, not a different order -- callers echo
    the returned path before starting a run.

    Returns:
        The path to the resolved ``sleap-nn`` console script.

    Raises:
        BackendError: No console script was found in any of the three locations.
    """
    candidate_dirs = (_interpreter_scripts_dir(), str(Path(sys.executable).parent))
    for directory in candidate_dirs:
        found = shutil.which(SCRIPT_NAME, path=directory)
        # Confirm the hit actually came from the directory we asked about. On win32 + Python
        # 3.11 -- the version build.yml pins, on the OS that trains -- `shutil.which` prepends
        # `os.curdir` to the search *even when `path=` is given*, mimicking cmd.exe, and returns
        # a relative match. Without this check a stray `sleap-nn.exe` in the invocation
        # directory beats the interpreter's Scripts\, defeating the whole ordering below, and
        # the relative path would print as a bare filename -- so the "visibility, not a
        # different order" mitigation would fail exactly when the hazard fires. 3.12+ honour
        # `path=`, which makes this version-scoped rather than universal.
        if found and Path(found).resolve().parent == Path(directory).resolve():
            return Path(found).resolve()
    found = shutil.which(SCRIPT_NAME)
    if found:
        # Absolute so the echoed path is always actionable, wherever PATH found it.
        return Path(found).resolve()
    raise BackendError(_MISSING_BACKEND)


#: The emitted, sleap-nn-native config `run` hands to the backend.
EMITTED_CONFIG_NAME = "emitted_config.yaml"

#: A verbatim copy of the config the operator authored. This is the artifact the backend
#: cannot write: every config it sees has the repo-owned ``experiment`` block stripped by
#: construction, so nothing else in the run directory records species / mode / root_type /
#: dataset identity.
SOURCE_CONFIG_NAME = "source_config.yaml"

#: Evidence that a run already happened in a directory. ``best.ckpt`` is the backend's own
#: auto-suffix trigger (``training/model_trainer.py:522``); ``training_config.yaml`` is
#: what it writes on completion (``:1313``) and catches the ``save_ckpt: false`` case,
#: where no checkpoint is ever written and the backend silently reuses the directory.
RUN_EVIDENCE = ("best.ckpt", "training_config.yaml")


#: Characters Windows forbids in a path component. ``/`` and ``\\`` are already excluded by the
#: single-component check; ``:`` is listed because a bare ``C:foo`` is *drive-relative*, not
#: absolute, and joining it discards everything to its left.
_WINDOWS_RESERVED_CHARS = frozenset('<>:"|?*')

#: Windows device names, which cannot be used as a directory component regardless of extension.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{digit}" for digit in range(1, 10)}
    | {f"LPT{digit}" for digit in range(1, 10)}
)


def _check_single_component(run_name: str) -> None:
    r"""Reject a ``run_name`` that is anything other than one plain directory name.

    The gate is applied under **both** POSIX and Windows path semantics, so the same config is
    accepted or rejected identically on the laptop that authors it and the box that trains it --
    a rule that only fired on Windows would let a bad name reach the GPU box unnoticed.

    ``PurePath.is_absolute()`` plus a separator scan is *not* sufficient, and the gap is not
    theoretical: ``PureWindowsPath("C:foo")`` is drive-**relative**, so it reports
    ``is_absolute() == False`` and contains no separator, yet
    ``PureWindowsPath("ckpt") / "C:foo"`` evaluates to ``C:foo`` -- pathlib discards the
    left-hand side once the right-hand side carries a drive. The artifacts would then land
    outside the run directory this whole design guards, with no error. Counting path components
    catches that, and catches a backslash on POSIX as a bonus (``PurePosixPath("a\\b")`` is one
    component, ``PureWindowsPath("a\\b")`` is two).

    Args:
        run_name: The candidate ``trainer_config.run_name``.

    Raises:
        BackendError: The name is not a single, portable path component.
    """
    for flavour in (PurePosixPath, PureWindowsPath):
        if len(flavour(run_name).parts) != 1:
            raise BackendError(
                f"trainer_config.run_name must be a single directory name, got {run_name!r} "
                "(a separator, an absolute path, or a Windows drive-relative name like 'C:foo' "
                "would place the run outside ckpt_dir)"
            )
    # `..` (and `...`) survive the component count -- one component under both flavours -- yet
    # `<ckpt_dir>/..` climbs out of the very directory the refusal machinery guards, so the run's
    # provenance lands beside `ckpt_dir` rather than inside it, on every platform. This also
    # covers the Windows trailing-dot/space rule: Win32 strips those when creating a path, so
    # `run_name: "r1 "` and `run_name: "r1"` name ONE directory there and TWO here -- which makes
    # the reuse refusal answer differently on the authoring host and the training host, and lets
    # `NUL ` walk past the device-name check below. Rejecting rather than silently normalizing
    # keeps the name the operator wrote and the directory they get identical everywhere.
    if run_name.rstrip(". ") != run_name or not run_name.rstrip(". "):
        raise BackendError(
            f"trainer_config.run_name must not be a relative directory reference or end in a "
            f"dot or space, got {run_name!r} (Windows strips trailing dots and spaces, so the "
            "same name would identify a different directory there than here)"
        )
    control = sorted(char for char in run_name if ord(char) < 32)
    if control:
        raise BackendError(
            f"trainer_config.run_name contains control character(s) {control!r}; "
            f"got {run_name!r}"
        )
    bad_chars = sorted(set(run_name) & _WINDOWS_RESERVED_CHARS)
    if bad_chars:
        raise BackendError(
            f"trainer_config.run_name contains character(s) Windows forbids in a path: "
            f"{''.join(bad_chars)!r} (got {run_name!r})"
        )
    # Rejected on every platform, not only Windows: the GPU box is Windows, so a name that is
    # legal on the authoring Mac but illegal there would fail at the worst possible moment.
    if run_name.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        raise BackendError(
            f"trainer_config.run_name is a Windows reserved device name ({run_name!r}); "
            "it cannot be a directory on the training box"
        )


def _select(cfg, key: str, default=None):
    """Read ``key`` off ``cfg``, turning an interpolation failure into a named error.

    ``OmegaConf.select`` **resolves**, so a field carrying ``${oc.env:UNSET}`` or a dangling
    reference raises an ``OmegaConfBaseException`` from deep inside OmegaConf. Unwrapped, that
    escapes the CLI's ``except BackendError`` and reaches the operator as a traceback -- which
    the spec explicitly forbids, and which `validate` and `emit` never do because neither
    resolves anything.

    Args:
        cfg: A loaded training config.
        key: A dotted key path.
        default: Value to return when the key is absent.

    Returns:
        The resolved value, or ``default``.

    Raises:
        BackendError: The key exists but its interpolation could not be resolved.
    """
    try:
        return OmegaConf.select(cfg, key, default=default)
    except OmegaConfBaseException as error:
        raise BackendError(f"{key} could not be resolved: {error}") from error


def check_emitted_config_resolvable(cfg) -> None:
    """Refuse a config whose emitted form the backend could not load.

    Two different things are true at once and they have to be reconciled *before* anything is
    staged. The gates here read through ``OmegaConf.select``, which resolves against the **full**
    config; the emitted file is written with ``resolve=False`` and with the ``experiment`` block
    **stripped**. So ``run_name: ${experiment.species}_v1`` resolves cleanly for every check,
    stages the artifacts under ``arabidopsis_v1``, and then hands the backend a config that
    cannot be reloaded at all -- gated, staged and reported against a value the backend never
    sees. That is exactly the "artifact describing a run other than the one beside it" this
    design exists to prevent, and the schema invites it: the examples duplicate the dataset path
    by hand and tell authors to keep a ``run_name`` suffix in step with ``seed``.

    This resolves a throwaway copy purely as a check. The emitted file itself stays unresolved on
    purpose -- that is what keeps ``${oc.env:WANDB_API_KEY}`` a literal interpolation in the
    artifact instead of a baked secret.

    Args:
        cfg: A loaded, validated training config.

    Raises:
        BackendError: The emitted config carries an interpolation that cannot resolve without
            the repo-owned blocks the backend never receives.
    """
    try:
        OmegaConf.to_container(
            training_config.to_sleap_nn_config(cfg), resolve=True, throw_on_missing=True
        )
    except OmegaConfBaseException as error:
        raise BackendError(
            "the emitted sleap-nn config cannot be resolved on its own: "
            f"{error}. An interpolation most likely points at the repo-owned 'experiment' "
            "block, which is stripped from the config the backend receives -- write the value "
            "literally instead."
        ) from error


def run_directory(cfg) -> Path:
    """Return the directory the backend will train into, validating the run name.

    Args:
        cfg: A loaded training config.

    Returns:
        ``<trainer_config.ckpt_dir>/<trainer_config.run_name>``, with ``ckpt_dir``
        defaulting to ``"."`` -- the backend's own default
        (``config/trainer_config.py:368``), so both agree on where the run lands.

    Raises:
        BackendError: ``trainer_config.run_name`` is unusable. An unset name is not
            guessed: the backend generates ``<timestamp>.<model_type>.n=<frames>``
            (``training/model_trainer.py:513``), a directory this process cannot predict,
            so artifacts would land beside the real run rather than in it.
    """
    run_name = _select(cfg, "trainer_config.run_name")
    if not isinstance(run_name, str) or not run_name.strip():
        raise BackendError(
            "trainer_config.run_name is required by `run` (the backend would otherwise "
            "generate a timestamped directory this command cannot predict); set an "
            "explicit run name, or use the validate/emit/sleap-nn train path"
        )
    # "None" is the literal string the backend itself treats as unset (model_trainer.py:491).
    if run_name.strip() == "None":
        raise BackendError(
            "trainer_config.run_name is the literal string 'None', which the backend "
            "treats as unset; set a real run name"
        )
    _check_single_component(run_name)
    ckpt_dir = _select(cfg, "trainer_config.ckpt_dir")
    if ckpt_dir is None:
        # Absent is documented: the backend defaults to "." (config/trainer_config.py:368).
        ckpt_dir = "."
    elif not isinstance(ckpt_dir, str) or not ckpt_dir.strip():
        # Malformed is NOT absent. `or "."` used to swallow "" / false / null alike, so a
        # typo silently sent the run's provenance to ./<run_name> while the operator believed
        # it was going somewhere else; a list or int reached `Path(str(...))` and produced a
        # directory named "['a', 'b']". config.py type-checks seed, use_wandb and both
        # preprocessing flags -- this field supplies the left-hand side of every path the
        # run-directory guard rests on, so it gets the same treatment.
        raise BackendError(
            f"trainer_config.ckpt_dir must be a non-empty string, got {ckpt_dir!r}"
        )
    return Path(ckpt_dir) / run_name


def check_run_directory(run_dir: Path) -> None:
    """Refuse a run directory that already holds a run.

    The backend appends ``-1``, ``-2``, ... to the run name when the directory holds a
    ``best.ckpt`` (``training/model_trainer.py:522``), so it would train *elsewhere* while
    our artifacts landed here, describing a different run than the checkpoint beside them.
    There is deliberately no override flag: the correct remedy for a name collision is a
    new name, and overwriting a finished run's provenance is never the desired outcome.

    Args:
        run_dir: The directory the backend would train into.

    Raises:
        BackendError: The directory already contains evidence of a previous run.
    """
    if run_dir.exists() and not run_dir.is_dir():
        raise BackendError(
            f"{run_dir} exists and is not a directory, so it cannot hold this run's artifacts"
        )
    for marker in RUN_EVIDENCE:
        if (run_dir / marker).exists():
            raise BackendError(
                f"{run_dir} already holds a previous run ({marker}); the backend would "
                f"train into '{run_dir.name}-1' instead, leaving this run's config beside "
                "another run's results. Change trainer_config.run_name (there is no "
                "--force: overwriting a finished run's provenance is never wanted)."
            )


def resolved_config_path(run_dir: Path, override: Optional[Path]) -> Path:
    """Return where the emitted sleap-nn config should be staged.

    Args:
        run_dir: The directory the backend will train into.
        override: An explicit ``--resolved-config`` path, or ``None``.

    Returns:
        ``override`` when given, else ``<run_dir>/emitted_config.yaml``.
    """
    return override if override is not None else run_dir / EMITTED_CONFIG_NAME


def wandb_enabled(cfg) -> bool:
    """Whether the config turns W&B on, read through the interpolation-safe accessor.

    Args:
        cfg: A loaded training config.

    Returns:
        ``True`` when ``trainer_config.use_wandb`` is set.

    Raises:
        BackendError: The field carries an interpolation that cannot be resolved.
    """
    return bool(_select(cfg, "trainer_config.use_wandb", default=False))


def reject_inline_api_key(cfg) -> None:
    """Refuse a config carrying a literal W&B credential.

    ``run`` writes configs into the run directory, and ``registry/publish.py`` uploads that
    directory wholesale (``artifact.add_dir``), so a persisted key would ship as a registry
    artifact. The backend masks this field in both configs it writes
    (``training/model_trainer.py:997``); we cannot mask it in ours without breaking
    byte-identity with ``emit``, so we refuse it instead.

    Args:
        cfg: A loaded training config.

    Raises:
        BackendError: ``trainer_config.wandb.api_key`` is set to a non-empty value.
    """
    api_key = _select(cfg, "trainer_config.wandb.api_key")
    if isinstance(api_key, str) and api_key.strip():
        raise BackendError(
            "trainer_config.wandb.api_key is set in the config. `run` copies configs into "
            "the run directory, which is uploaded whole when a model is published, so the "
            "key would ship with it. Remove it and authenticate with WANDB_API_KEY or "
            "`wandb login` instead."
        )


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write ``payload`` to ``path`` via a temp file in the same directory.

    ``Path.write_bytes`` is not atomic: on ENOSPC it raises only after leaving a truncated
    file, which the next invocation would read as a real artifact. Writing to a sibling
    temp file and ``os.replace``-ing it into place means the destination either has the old
    content or the new one.

    Args:
        path: The destination path.
        payload: The exact bytes to write.

    Raises:
        OSError: The write or the replace failed; no temp file is left behind.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f"{path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
        os.replace(temp_path, path)
    except BaseException:
        # BaseException, not OSError: a KeyboardInterrupt between mkstemp and os.replace would
        # otherwise strand a `.tmp` sibling in the run directory -- which `add_dir` would then
        # publish as part of the model artifact.
        temp_path.unlink(missing_ok=True)
        raise


def stage_artifacts(cfg, source_path: Path, run_dir: Path, resolved_dest: Path) -> None:
    """Write the run's two provenance artifacts, before the backend is started.

    The emitted config is written with LF line endings so its bytes are host-independent
    (and identical to ``emit -o``'s). The source config is copied **verbatim** -- a
    provenance copy that rewrote the operator's bytes would not be one.

    Args:
        cfg: A loaded, validated training config.
        source_path: The config file the operator passed to ``run``.
        run_dir: The directory the backend will train into.
        resolved_dest: Where to stage the emitted config.

    Raises:
        BackendError: The destination is unusable, would destroy the source, or the write
            failed. Nothing partial is left behind.
    """
    # Re-check immediately before writing: the caller checked earlier, and a checkpoint
    # appearing in that window would otherwise strand these artifacts next to it. This narrows
    # the race, it does not close it -- a checkpoint appearing between *this* check and the
    # writes below would still slip through. Closing it properly would need a lock the backend
    # does not participate in, and the operator-facing failure (two runs sharing one name) is
    # already refused for every realistic ordering.
    check_run_directory(run_dir)

    source_copy = run_dir / SOURCE_CONFIG_NAME
    if resolved_dest.name in RUN_EVIDENCE:
        raise BackendError(
            f"--resolved-config must not name {resolved_dest.name!r}: that is how a completed "
            "run is recognized, so writing it now would fabricate the evidence the next run "
            "refuses -- and with no --force, recovery would mean deleting files by hand"
        )
    # The override is a way to move the emitted config, not a way around the reuse guard: an
    # unchecked path could drop this run's config into a *different*, finished run's directory.
    check_run_directory(resolved_dest.parent)
    if resolved_dest.is_dir():
        raise BackendError(
            f"--resolved-config must name a file, but {resolved_dest} is a directory"
        )
    if resolved_dest.resolve() == source_path.resolve():
        raise BackendError(
            f"--resolved-config would overwrite the input config {source_path}; the "
            "emitted config has the experiment block stripped, so this would destroy the "
            "run's identity"
        )
    if resolved_dest.resolve() == source_copy.resolve():
        raise BackendError(
            f"--resolved-config resolves to {source_copy}, which `run` writes itself"
        )

    try:
        # `source_config.yaml` first, deliberately: it is the only artifact carrying the
        # `experiment` block, so if the second write fails the run directory keeps the record
        # nothing else can reproduce rather than the one the backend rewrites anyway.
        _atomic_write(source_copy, source_path.read_bytes())
        _atomic_write(
            resolved_dest, training_config.to_sleap_nn_yaml(cfg).encode("utf-8")
        )
    except OSError as error:
        raise BackendError(
            f"could not write the run's config artifacts: {error}"
        ) from error


class BackendOutcome(NamedTuple):
    """What the backend did, translated into terms a CLI can exit with.

    Attributes:
        exit_code: The status this process should exit with.
        note: A line to print for the operator when the raw status needs explaining
            (a signal, or a status too large to be an exit code), else ``None``.
    """

    exit_code: int
    note: Optional[str] = None


def backend_version(binary: Path) -> Optional[str]:
    """Return what ``sleap-nn --version`` reports, or ``None`` if it cannot be asked.

    Echoed before a run so the operator's log records which backend actually ran. Deliberately
    *not* stamped into the staged config: that file must stay byte-identical to ``emit -o``'s
    output, and a version line would break the guarantee. sleap-nn writes its own version into
    ``initial_config.yaml`` -- but only once the trainer is built, which is precisely the window
    the staged config exists to cover, so for a run that dies during setup this console line is
    the only record of what would have trained it.

    Args:
        binary: The resolved ``sleap-nn`` console script.

    Returns:
        The reported version string, or ``None`` when the probe fails for any reason. It is a
        diagnostic, never a gate -- a backend that cannot report a version still runs.
    """
    try:
        completed = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    reported = (completed.stdout or completed.stderr).strip()
    return reported or None


def build_argv(binary: Path, resolved_config: Path) -> list[str]:
    """Return the exact argument vector the backend is invoked with.

    Pure and public so the argv contract can be asserted without a subprocess, and so the
    plumbing in :func:`run_backend` can be exercised against a different executable.

    The config path is absolutized because the backend hands it to Hydra, which resolves
    it itself (``sleap_nn/cli.py``'s ``split_config_path``); passing it absolute keeps the
    two from ever disagreeing about what a relative path meant.

    Args:
        binary: The resolved ``sleap-nn`` console script.
        resolved_config: The staged, sleap-nn-native config.

    Returns:
        ``[<binary>, "train", "--config", <absolute config path>]`` -- nothing appended.
        In particular no Hydra-style ``key=value`` overrides: ``run`` passes one config and
        nothing else, so the staged file is always a complete description of the run.
    """
    return [str(binary), "train", "--config", str(Path(resolved_config).resolve())]


#: `STATUS_CONTROL_C_EXIT` (0xC000013A) -- what a Windows console Ctrl-C produces.
_STATUS_CONTROL_C_EXIT = 3221225786


def _translate_status(returncode: int) -> BackendOutcome:
    """Turn a child's return code into an exit code this process can actually exit with.

    Args:
        returncode: The value reported by ``Popen.wait``.

    Returns:
        The translated outcome. A negative code is POSIX signal termination and becomes
        ``128 + N``; a code too large for an exit status (Windows reports e.g.
        ``0xC000013A`` for Ctrl-C, and POSIX truncates a real status to 8 bits) becomes a
        plain failure naming the raw value, rather than a number that would wrap to 0.
    """
    if returncode == 0:
        return BackendOutcome(0)
    if returncode < 0:
        signal_number = -returncode
        return BackendOutcome(
            128 + signal_number,
            f"sleap-nn train was terminated by signal {signal_number}",
        )
    if returncode == _STATUS_CONTROL_C_EXIT:
        # Windows never reports POSIX-style negative codes, so a console Ctrl-C arrives as this
        # NTSTATUS. Reporting it raw gave exit 1 and a 10-digit number no operator recognizes,
        # for the same event that yields 130 on POSIX.
        return BackendOutcome(130, "sleap-nn train was interrupted (Ctrl-C)")
    if returncode > 255:
        return BackendOutcome(
            1, f"sleap-nn train exited with status {returncode} (reported as-is)"
        )
    return BackendOutcome(returncode)


def run_backend(argv: list[str]) -> BackendOutcome:
    """Run the backend to completion and translate its exit status.

    Streams are inherited (no redirection), so a multi-hour run shows live progress and
    nothing is buffered here. The environment and working directory are inherited too:
    ``WANDB_API_KEY`` / ``CUDA_VISIBLE_DEVICES`` are how an operator steers a run, and every
    committed example uses relative dataset and checkpoint paths that the backend resolves
    against the cwd it inherits.

    ``Popen`` plus an explicit wait loop rather than ``subprocess.run``: Ctrl-C signals the
    whole foreground process group, so this process takes SIGINT too, and ``run()`` responds
    by killing the child and re-raising. That would SIGKILL a trainer that had just been
    asked to stop -- destroying Lightning's checkpoint-on-interrupt -- and would make the
    signal branch below unreachable. Instead the interrupt is swallowed here and the child,
    which already received it, is left to shut down and report its own status.

    Args:
        argv: The argument vector, as built by :func:`build_argv`.

    Returns:
        The translated :class:`BackendOutcome`. This function never exits the process; the
        CLI owns that.
    """
    try:
        process = subprocess.Popen(argv)
    except OSError as error:
        # A truncated wheel, or a PATHEXT hit on something that is not executable, raises here --
        # after the artifacts are staged, so an unwrapped OSError would land on the operator as a
        # traceback on top of a half-finished run.
        raise BackendError(f"could not start {argv[0]}: {error}") from error

    interrupts = 0
    while True:
        try:
            returncode = process.wait()
            break
        except KeyboardInterrupt:
            interrupts += 1
            if interrupts == 1:
                # The child already received the same SIGINT; let it shut down gracefully,
                # which is the whole reason this is not `subprocess.run`.
                print(
                    "interrupt forwarded to sleap-nn; press Ctrl-C again to terminate it",
                    file=sys.stderr,
                    flush=True,
                )
            elif interrupts == 2:
                # There has to be a ceiling. Every further Ctrl-C used to hit the same
                # `continue`, so a child that ignores SIGINT could not be aborted at all --
                # design.md claimed an escape hatch that did not exist. Escalating only on an
                # explicit second request keeps the graceful path for the ordinary case.
                print("terminating sleap-nn", file=sys.stderr, flush=True)
                process.terminate()
            else:
                print("killing sleap-nn", file=sys.stderr, flush=True)
                process.kill()
    return _translate_status(returncode)
