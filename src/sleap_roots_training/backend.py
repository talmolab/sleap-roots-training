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
from pathlib import Path
from typing import NamedTuple, Optional

from omegaconf import OmegaConf

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
        if found:
            return Path(found)
    found = shutil.which(SCRIPT_NAME)
    if found:
        return Path(found)
    raise BackendError(_MISSING_BACKEND)


#: The emitted, sleap-nn-native config `run` hands to the backend.
RESOLVED_CONFIG_NAME = "resolved_config.yaml"

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
    run_name = OmegaConf.select(cfg, "trainer_config.run_name", default=None)
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
    if Path(run_name).is_absolute() or any(sep in run_name for sep in ("/", "\\")):
        raise BackendError(
            f"trainer_config.run_name must be a single directory name, got {run_name!r} "
            "(a separator or absolute path would place the run outside ckpt_dir)"
        )
    ckpt_dir = OmegaConf.select(cfg, "trainer_config.ckpt_dir", default=None) or "."
    return Path(str(ckpt_dir)) / run_name


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
        ``override`` when given, else ``<run_dir>/resolved_config.yaml``.
    """
    return override if override is not None else run_dir / RESOLVED_CONFIG_NAME


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
    api_key = OmegaConf.select(cfg, "trainer_config.wandb.api_key", default=None)
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
    except OSError:
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
    # appearing in that window would otherwise strand these artifacts next to it.
    check_run_directory(run_dir)

    source_copy = run_dir / SOURCE_CONFIG_NAME
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
        _atomic_write(
            resolved_dest, training_config.to_sleap_nn_yaml(cfg).encode("utf-8")
        )
        _atomic_write(source_copy, source_path.read_bytes())
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
    process = subprocess.Popen(argv)
    while True:
        try:
            returncode = process.wait()
            break
        except KeyboardInterrupt:
            continue
    return _translate_status(returncode)
