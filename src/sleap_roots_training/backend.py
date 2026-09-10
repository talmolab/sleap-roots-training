"""Locate and drive the ``sleap-nn`` training backend as a subprocess.

The backend is consumed through its **console script**, never by importing its training
entry points: ``openspec/project.md`` consumes ``sleap-nn`` / ``sleap-io`` as pinned
libraries, and a subprocess additionally keeps Lightning's process-level side effects
(signal handlers, CUDA init, ``sys.exit``) out of this CLI's process while handing us the
backend's exit status for free.

Nothing here imports ``sleap_nn``. The module is **base-install safe** -- its only
non-stdlib imports are ``omegaconf`` and this package's own ``config`` module, both of which
the base install already provides -- so the cross-platform CI matrix, which never installs
the ``train`` extra, exercises every path in it through stub executables.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import NamedTuple, Optional

from omegaconf import DictConfig, OmegaConf
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

#: What this command records about the run *itself*, as opposed to its config. Not evidence:
#: `run` writes it, so a retry legitimately overwrites it -- but it is guarded against
#: ``--emitted-config`` for the same reason the other two are.
RUN_METADATA_NAME = "run_metadata.yaml"

#: What, found in a run directory, means a run already happened there -- each mapped to why,
#: so the refusal can say something true about the marker it actually found. Every one of
#: these is written by the backend, none by this command.
#:
#: The third was missing, and its absence was the interesting one: the first two are written
#: at or *after* success, so a run that reached trainer construction and then died left a
#: directory this guard called clean, and the retry overwrote the only record of it.
RUN_EVIDENCE = {
    "best.ckpt": (
        "the backend's own auto-suffix trigger (training/model_trainer.py:522), so it would "
        "train into a '-1' directory instead and leave this run's config beside another "
        "run's results"
    ),
    "training_config.yaml": (
        "what the backend writes on completion (training/model_trainer.py:1313), which also "
        "catches the save_ckpt: false case, where no checkpoint is ever written and the "
        "backend silently reuses the directory"
    ),
    "initial_config.yaml": (
        "what the backend writes once the trainer is constructed, so a run that died after "
        "that point -- an OOM at epoch 5, a CUDA fault -- left it behind; reusing the name "
        "would overwrite the only record of what that run was going to train"
    ),
}


def _mangled(name: str) -> str:
    r"""Return the name the filesystem would actually **create** for ``name``, folded for case.

    Two independent aliasing rules, applied together because the hosts that matter apply both.
    Win32 strips trailing dots and spaces at creation time, so ``best.ckpt.`` and ``best.ckpt``
    name one file there; NTFS and (by default) APFS compare case-insensitively, so ``Best.ckpt``
    is that file too. Folding unconditionally rather than via ``os.path.normcase`` keeps every
    rule in this module answering the same on the authoring laptop and the training box -- the
    principle already established for ``run_name``, where being marginally stricter on a
    case-sensitive filesystem costs a rename and being laxer costs a run.

    This is a *comparison* helper only. Nothing here normalizes a name on the way to disk: the
    name the operator wrote is the name that is written, or the write is refused.

    Args:
        name: A single path component.

    Returns:
        The comparison key for that component.
    """
    return name.rstrip(". ").casefold()


#: Names a run directory must never gain from ``--emitted-config``, as comparison keys. The two
#: the reuse check reads as a completed run, plus the one artifact nothing else can reproduce.
_GUARDED_RUN_DIR_NAMES = frozenset(
    _mangled(name) for name in (*RUN_EVIDENCE, SOURCE_CONFIG_NAME, RUN_METADATA_NAME)
)

#: Characters Windows forbids in a path component. ``/`` and ``\\`` are already excluded by the
#: single-component check; ``:`` is listed because a bare ``C:foo`` is *drive-relative*, not
#: absolute, and joining it discards everything to its left.
_WINDOWS_RESERVED_CHARS = frozenset('<>:"|?*')

#: The first printable code point. Everything below it is a control character, which no
#: filesystem should be asked to carry in a name and no console can render.
_FIRST_PRINTABLE_ORD = 32

#: How long to wait for ``sleap-nn --version``. Generous, because the probe imports torch on
#: some installs; bounded, because it must never be what makes a run hang.
_VERSION_PROBE_TIMEOUT_SECONDS = 60

#: POSIX convention: a process killed by signal N is reported as this plus N.
_SIGNAL_EXIT_BASE = 128

#: The largest value a process exit status can carry. Anything above wraps modulo 256, which
#: is how a large Windows NTSTATUS would otherwise be reported as success.
_MAX_EXIT_STATUS = 255

#: What a POSIX shell reports for a SIGINT-terminated process (128 + SIGINT). Used for the
#: Windows console-interrupt status too, so the same event yields the same code on both.
_INTERRUPT_EXIT_CODE = 130

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
        # An anchor check as well as a component count, because a bare root satisfies the
        # count: `PurePosixPath("/").parts` is `("/",)` -- one component -- and
        # `Path("ckpt") / "/"` is `/`. Found by the generated containment test, not by
        # enumerating another shape; `..` and `C:foo` were the same oversight one round each.
        candidate = flavour(run_name)
        if len(candidate.parts) != 1 or candidate.anchor:
            raise BackendError(
                f"trainer_config.run_name must be a single directory name, got {run_name!r} "
                "(a separator, an absolute path, or a Windows drive-relative name like 'C:foo' "
                "would place the run outside ckpt_dir)"
            )
    _check_portable_component(run_name, "trainer_config.run_name")


def _check_portable_component(value: str, field: str) -> None:
    """Apply the host-portability rules to one path component, whatever field supplies it.

    Extracted from :func:`_check_single_component` so ``--emitted-config``'s basename gets the
    same treatment: it was the only path input in this module receiving no portability check at
    all, so ``<run_dir>/CON`` reached ``argv`` pointing at a console device and ``a?b.yaml``
    surfaced as a write failure blaming the write rather than the name. The reasoning is
    unchanged from ``run_name``'s -- a config authored on a Mac must not fail only on the box
    that trains -- so the rules are, too.

    Args:
        value: The component to check.
        field: How to name the offending input in the error, e.g. ``trainer_config.run_name``.

    Raises:
        BackendError: The component would not mean the same thing on both hosts.
    """
    # `..` (and `...`) survive the component count -- one component under both flavours -- yet
    # `<ckpt_dir>/..` climbs out of the very directory the refusal machinery guards, so the run's
    # provenance lands beside `ckpt_dir` rather than inside it, on every platform. This also
    # covers the Windows trailing-dot/space rule: Win32 strips those when creating a path, so
    # `run_name: "r1 "` and `run_name: "r1"` name ONE directory there and TWO here -- which makes
    # the reuse refusal answer differently on the authoring host and the training host, and lets
    # `NUL ` walk past the device-name check below. Rejecting rather than silently normalizing
    # keeps the name the operator wrote and the name that is created identical everywhere.
    if value.rstrip(". ") != value or not value.rstrip(". "):
        raise BackendError(
            f"{field} must not be a relative directory reference or end in a "
            f"dot or space, got {value!r} (Windows strips trailing dots and spaces, so the "
            "same name would identify a different file there than here)"
        )
    control = sorted(char for char in value if ord(char) < _FIRST_PRINTABLE_ORD)
    if control:
        raise BackendError(
            f"{field} contains control character(s) {control!r}; got {value!r}"
        )
    # Category Cf is the same hazard as a control character with no visual signal whatsoever:
    # `run<ZWSP>name` and `runname` render identically and are two directories -- for a name
    # that becomes a W&B run id, so the two runs are indistinguishable in the registry too.
    invisible = sorted({char for char in value if unicodedata.category(char) == "Cf"})
    if invisible:
        raise BackendError(
            f"{field} contains invisible Unicode formatting character(s) "
            f"{[f'U+{ord(char):04X}' for char in invisible]}; got {value!r} (two names that "
            "render identically would be two different directories)"
        )
    bad_chars = sorted(set(value) & _WINDOWS_RESERVED_CHARS)
    if bad_chars:
        raise BackendError(
            f"{field} contains character(s) Windows forbids in a path: "
            f"{''.join(bad_chars)!r} (got {value!r})"
        )
    # Rejected on every platform, not only Windows: the GPU box is Windows, so a name that is
    # legal on the authoring Mac but illegal there would fail at the worst possible moment.
    if value.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        raise BackendError(
            f"{field} is a Windows reserved device name ({value!r}); it cannot name a file or "
            "a directory on the training box"
        )


def _select(cfg: DictConfig, key: str, default=None):
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


def _unresolved(cfg: DictConfig, key: str):
    """Read ``key`` without resolving an interpolation stored there.

    ``OmegaConf.select`` resolves, which is right for a value this process *acts on* and wrong
    for a value it only needs to *classify*. ``trainer_config.wandb.api_key:
    ${oc.env:WANDB_API_KEY}`` resolves to the secret while the artifact records the reference,
    so a guard against a **persisted** credential has to read what is persisted.

    Args:
        cfg: A loaded training config.
        key: A dotted key path whose last segment names the leaf to read.

    Returns:
        ``(value, is_interpolation)`` -- the raw stored value (an interpolation comes back as
        its own ``${...}`` text) and whether it is one. ``(None, False)`` when the leaf or any
        parent is absent.

    Raises:
        BackendError: A parent of the leaf is itself an interpolation that cannot resolve.
    """
    parent_key, _, leaf = key.rpartition(".")
    parent = _select(cfg, parent_key) if parent_key else cfg
    if parent is None or not OmegaConf.is_dict(parent):
        return None, False
    node = parent._get_node(leaf)
    if node is None:
        return None, False
    return node._value(), OmegaConf.is_interpolation(parent, leaf)


def check_emitted_config_resolvable(cfg: DictConfig) -> None:
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
    artifact instead of a baked secret (pinned by
    ``test_run_persists_interpolations_rather_than_the_values_behind_them``).

    Runs **after** the field reads, not before them. It resolves the entire sleap-nn portion,
    so going first meant every field-level interpolation failure -- an unexported
    ``${oc.env:...}`` in ``ckpt_dir``, say -- surfaced as this generic message instead of the
    field-named one :func:`_select` raises, and the field name is the only actionable part.

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
        # No prescribed remedy: this fires for two unrelated causes (a reference into the
        # stripped `experiment` block, and an environment variable that is not exported on this
        # host), and the one remedy that fits the first -- "write the value literally" -- is
        # exactly what the credential guard below exists to prevent when it fires on the second.
        raise BackendError(
            "the emitted sleap-nn config cannot be resolved on its own: "
            f"{error}. The backend receives this config with the repo-owned 'experiment' "
            "block removed, and `run` does not resolve interpolations into the file it "
            "writes, so every interpolation left in it has to resolve from the sleap-nn "
            "blocks and this host's environment alone."
        ) from error


def _check_portable_path(value: str, field: str) -> None:
    """Apply the host-portability rules to a *path* field (separators allowed).

    ``run_name`` must be a single component; ``ckpt_dir`` is legitimately a path. But the two
    reasons a component is unsafe apply to both fields: a Windows drive-relative prefix
    (``C:foo``) discards whatever it is joined to and resolves against a hidden per-drive
    current-directory table, and a trailing dot or space is stripped by Win32, so the same
    string names a different directory on the authoring host than on the training host.
    Checking only ``run_name`` left the field supplying the left-hand side of every guarded path
    unchecked.

    Args:
        value: The field's value.
        field: The dotted field name, for the error message.

    Raises:
        BackendError: The value is drive-relative, or a component ends in a dot or space.
    """
    windows = PureWindowsPath(value)
    if windows.drive and not windows.root:
        raise BackendError(
            f"{field} must not be a Windows drive-relative path, got {value!r} (it discards "
            "whatever it is joined to and resolves against a hidden per-drive working directory)"
        )
    for part in windows.parts:
        # `.` and `..` are legitimate components of a *path* (unlike `run_name`, where they are
        # an escape and refused there); it is a trailing dot or space on a real name that Win32
        # strips.
        if part in (".", ".."):
            continue
        if part.rstrip(". ") != part:
            raise BackendError(
                f"{field} has a component ending in a dot or space ({part!r}); Windows strips "
                f"those, so {value!r} would name a different directory there than here"
            )


def _same_file(first: Path, second: Path) -> bool:
    """Whether two paths name the same file on the hosts this project actually runs on.

    ``PosixPath.__eq__`` is case-**sensitive** while macOS ships case-insensitive APFS, so
    ``Source_Config.yaml`` compared unequal to ``source_config.yaml`` on a CI leg where the two
    are one file -- making these the only rules in the module that answered differently per
    host, which :func:`_mangled` argues at length against. ``os.path.samefile`` would answer
    correctly but needs both paths to exist, and ``source_config.yaml`` has not been written at
    check time; that is the hole ``--emitted-config <run_dir>/source_config.yaml.`` went
    through, since ``resolve()`` cannot canonicalize a file that does not exist yet.

    Args:
        first: One path.
        second: The other.

    Returns:
        Whether they resolve to the same file, comparing case-insensitively.
    """
    return str(first.resolve()).casefold() == str(second.resolve()).casefold()


def _entries(directory: Path) -> set:
    """Return the names ``directory`` currently holds, empty when it does not exist.

    Deliberately ``os.listdir`` rather than a set of paths we expected to write: the whole
    B1-B3 family is "the name passed in is not the name the filesystem created", so the only
    trustworthy source for what is there is the directory itself.

    Args:
        directory: The directory to list.

    Returns:
        The entry names, or an empty set when the directory is absent or unreadable.
    """
    try:
        return set(os.listdir(directory))
    except OSError:
        return set()


def _purge_fabricated_evidence(run_dir: Path, before: set) -> str:
    """Delete anything a staging attempt created that reads as evidence of a completed run.

    Scoped to entries that appeared *since* ``before`` and whose mangled name is one the reuse
    check reads, so the deliberate decision to keep ``source_config.yaml`` after a failed
    second write is untouched. The case this exists for is a write that materializes a file
    and then fails: on NTFS, ``--emitted-config <run_dir>/best.ckpt:x`` makes ``mkstemp``
    create the **base** file ``best.ckpt`` before ``os.replace`` fails, and
    :func:`_atomic_write`'s cleanup can only unlink the temp stream -- leaving a 0-byte
    ``best.ckpt`` that refuses the run name forever, with no ``--force``.

    Args:
        run_dir: The run directory.
        before: The entry names present before the attempt.

    Returns:
        A sentence to append to the caller's error, or ``""`` when there was nothing to do.
    """
    folded = {_mangled(marker) for marker in RUN_EVIDENCE}
    removed, stuck = [], []
    for name in sorted(_entries(run_dir) - before):
        if _mangled(name) not in folded:
            continue
        try:
            (run_dir / name).unlink()
        except OSError:
            stuck.append(name)
        else:
            removed.append(name)
    parts = []
    if removed:
        parts.append(
            f"removed {', '.join(repr(name) for name in removed)}, which the "
            "attempt created and the reuse check would have read as a completed run"
        )
    if stuck:
        parts.append(
            f"could NOT remove {', '.join(repr(name) for name in stuck)}; delete it "
            "by hand or this run name will be refused from now on"
        )
    return f" ({'; '.join(parts)})" if parts else ""


def run_directory(cfg: DictConfig) -> Path:
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
        # Malformed is NOT absent, and must not be treated as it. A falsy-but-present value
        # ("" / false / null) would otherwise send the run's provenance to ./<run_name> while
        # the operator believes it is going somewhere else; a list or int would reach
        # `Path(str(...))` and produce a directory named "['a', 'b']". config.py type-checks
        # seed, use_wandb and both preprocessing flags -- this field supplies the left-hand
        # side of every path the run-directory guard rests on, so it gets the same treatment.
        raise BackendError(
            f"trainer_config.ckpt_dir must be a non-empty string, got {ckpt_dir!r}"
        )
    else:
        _check_portable_path(ckpt_dir, "trainer_config.ckpt_dir")
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
    for marker, why in RUN_EVIDENCE.items():
        if (run_dir / marker).exists():
            raise BackendError(
                f"{run_dir} already holds a previous run ({marker}): {why}. Change "
                "trainer_config.run_name (there is no --force: overwriting a finished or a "
                "crashed run's provenance is never wanted)."
            )


def _common_ancestor(first: Path, second: Path) -> Optional[Path]:
    """Return the deepest directory both paths lie under, or ``None`` for different roots.

    Compared component-wise and case-folded, for the reason :func:`_same_file` gives: two
    components differing only in case are one directory on both hosts that matter.

    Args:
        first: One path.
        second: The other.

    Returns:
        The deepest shared ancestor, or ``None`` when the two share no root (separate Windows
        drives).
    """
    left, right = first.resolve().parts, second.resolve().parts
    shared = []
    for one, other in zip(left, right):
        if one.casefold() != other.casefold():
            break
        shared.append(one)
    return Path(*shared) if shared else None


def _check_no_run_in_ancestors(destination: Path, ckpt_dir: Path) -> None:
    """Refuse a destination sitting anywhere inside a directory that already holds a run.

    ``registry/publish.py`` uploads a model directory with a **recursive** ``add_dir``, so a
    config written into any descendant of a finished run is published as part of that run's
    artifact -- and that is true regardless of which ``ckpt_dir`` the finished run belonged to.
    The previous form bounded the walk by ``ckpt_dir`` and always checked the immediate parent,
    which left two holes: depth 2 or more *outside* the checkpoint tree was accepted
    (``ckpt_dir: models_scratch`` while the published baseline sits under ``models/`` is the
    realistic shape), and ``ckpt_dir`` **itself** was never checked, so evidence sitting
    directly in it let a plain run with no override write into a finished run's tree.

    The walk now climbs from the destination's parent to the deepest directory it shares with
    ``ckpt_dir``, inclusive. Bounding it by something the operator configured rather than by
    ``ckpt_dir`` alone covers both holes, and stops short of climbing to the filesystem root:
    a stray ``training_config.yaml`` in a home directory would otherwise refuse every run
    underneath it, with no ``--force`` and possibly nothing the operator can delete.

    Args:
        destination: The path the emitted config would be written to.
        ckpt_dir: The checkpoint directory, which bounds how far the walk climbs.

    Raises:
        BackendError: The destination's parent, or an ancestor within the bound, holds
            evidence of a previous run.
    """
    resolved = destination.resolve()
    boundary = _common_ancestor(resolved.parent, ckpt_dir)
    for ancestor in resolved.parents:
        check_run_directory(ancestor)
        if boundary is None or ancestor == boundary:
            break


def emitted_config_path(run_dir: Path, override: Optional[Path]) -> Path:
    """Return where the emitted sleap-nn config should be staged.

    Args:
        run_dir: The directory the backend will train into.
        override: An explicit ``--emitted-config`` path, or ``None``.

    Returns:
        ``override`` when given, else ``<run_dir>/emitted_config.yaml``.
    """
    return override if override is not None else run_dir / EMITTED_CONFIG_NAME


def wandb_enabled(cfg: DictConfig) -> bool:
    """Whether the config turns W&B on, read through the interpolation-safe accessor.

    Args:
        cfg: A loaded training config.

    Returns:
        ``True`` when ``trainer_config.use_wandb`` is set.

    Raises:
        BackendError: The field carries an interpolation that cannot be resolved.
    """
    return bool(_select(cfg, "trainer_config.use_wandb", default=False))


def reject_inline_api_key(cfg: DictConfig) -> None:
    """Refuse a config carrying a literal W&B credential.

    ``run`` writes configs into the run directory, and ``registry/publish.py`` uploads that
    directory wholesale (``artifact.add_dir``), so a persisted key would ship as a registry
    artifact. The backend masks this field in both configs it writes
    (``training/model_trainer.py:997``); we cannot mask it in ours without breaking
    byte-identity with ``emit``, so we refuse it instead.

    An **interpolation** is not refused. ``${oc.env:WANDB_API_KEY}`` persists as itself, so
    nothing ships: the rationale above is about a value on disk, and there is none. That
    relaxation is only safe because the emitted config is written unresolved, which is now
    pinned by a test at three levels rather than resting on a defaulted keyword.

    Args:
        cfg: A loaded training config.

    Raises:
        BackendError: ``trainer_config.wandb.api_key`` holds a non-empty literal value.
    """
    api_key, is_interpolation = _unresolved(cfg, "trainer_config.wandb.api_key")
    if is_interpolation:
        # Not a persisted credential. `to_sleap_nn_yaml` never resolves, so the artifact keeps
        # the reference verbatim and nothing this command writes carries the value -- the
        # rationale above does not apply to this input. Reading through `_select` resolved it,
        # so with the variable exported the guard refused the very pattern the credential
        # guidance points operators toward, and told them to do what they had already done.
        return
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


def _check_destination_name(destination: Path) -> None:
    """Reject a ``--emitted-config`` basename that is unportable or names an owned artifact.

    Belt-and-braces beside :func:`_verify_staging`, not a replacement for it. This is a
    *pre*-write check on a string, so it can still be beaten by a mangling rule nobody has
    written down; the post-write check reads the directory back and cannot be. It earns its
    place by producing a specific, actionable message before anything is written, instead of a
    generic "staging left something behind" afterwards.

    Args:
        destination: The resolved ``--emitted-config`` path.

    Raises:
        BackendError: The basename is empty, is not portable to the training host, or aliases
            a file the run directory must never gain this way.
    """
    name = destination.name
    if not name:
        # `--emitted-config ''` arrives here as `Path('.')`. Report the empty filename, not
        # the directory it degenerates into: "must not name a file, but . is a directory" is
        # accurate and baffling.
        raise BackendError(
            f"--emitted-config needs a filename; {str(destination)!r} names a directory"
        )
    _check_portable_component(name, "--emitted-config's filename")
    if _mangled(name) in _GUARDED_RUN_DIR_NAMES:
        raise BackendError(
            f"--emitted-config must not name {name!r}. Folded for the training host's "
            f"filesystem that is {_mangled(name)!r}, which is either how a completed run is "
            "recognized -- writing it would fabricate the evidence the next run refuses, with "
            "no --force to recover -- or the verbatim source copy, the only artifact carrying "
            "the experiment block"
        )


def _verify_staging(
    run_dir: Path, source_copy: Path, source_bytes: bytes, before: set
) -> None:
    """Assert, **after** the writes, the property every destination check exists to preserve.

    Four review rounds found the same defect with a different spelling -- ``C:foo``, ``..``, a
    trailing dot, a case variant, Win32 mangling, an NTFS stream suffix -- because each guard
    compared the string it was handed while the filesystem created a different one. A longer
    blocklist cannot win that race: the mangling rules belong to the OS, not to this module.

    Reading the directory back does not have to win it. Two things must be true once the
    writes return, and both are checked against what is actually there:

    1. **No fabricated evidence.** Nothing in the run directory is a name the reuse check
       reads as a completed run. ``run`` must not be able to create the evidence it later
       refuses, whatever the destination was spelled as.
    2. **An intact source copy.** ``source_config.yaml`` is byte-identical to the input. It is
       the only artifact carrying the ``experiment`` block, so a write landing on top of it
       destroys species / mode / root_type / dataset identity -- silently, at exit 0, with the
       success line asserting the file is there and ``publish.py`` uploading it as the run's
       lineage record.

    A violation is repaired before raising, because the alternative is leaving the operator
    with exactly the state this function exists to prevent.

    Args:
        run_dir: The directory the backend will train into.
        source_copy: Where the verbatim copy belongs.
        source_bytes: The input config's exact bytes.
        before: The run directory's entries before the writes.

    Raises:
        BackendError: Either invariant was violated; the run directory has been repaired.
    """
    folded_evidence = {_mangled(marker) for marker in RUN_EVIDENCE}
    fabricated = sorted(
        name for name in _entries(run_dir) if _mangled(name) in folded_evidence
    )
    if fabricated:
        raise BackendError(
            f"staging left {', '.join(repr(name) for name in fabricated)} in {run_dir}, which "
            "the reuse check reads as evidence of a completed run -- the destination named a "
            "file the filesystem then created under a different name than the one checked."
            f"{_purge_fabricated_evidence(run_dir, before)} Choose a different "
            "--emitted-config path."
        )
    if not source_copy.is_file() or source_copy.read_bytes() != source_bytes:
        try:
            _atomic_write(source_copy, source_bytes)
        except (
            OSError
        ) as error:  # pragma: no cover - the repair failing needs two faults
            raise BackendError(
                f"staging overwrote {source_copy}, the only artifact carrying the experiment "
                f"block, and restoring it failed: {error}"
            ) from error
        raise BackendError(
            f"staging would have overwritten {source_copy} with the emitted config, which has "
            "the experiment block stripped -- species, mode, root_type and dataset identity "
            "are recorded nowhere else. The verbatim copy has been restored and nothing was "
            "launched; choose a different --emitted-config path."
        )


def stage_artifacts(
    cfg: DictConfig, source_path: Path, run_dir: Path, resolved_dest: Path
) -> None:
    """Write the run's two provenance artifacts, before the backend is started.

    The emitted config is written with LF line endings so its bytes are host-independent
    (and identical to ``emit -o``'s). The source config is copied **verbatim** -- a
    provenance copy that rewrote the operator's bytes would not be one.

    The destination checks below are all belt-and-braces. The guarantee is
    :func:`_verify_staging`, which reads the run directory back afterwards; the pre-write
    checks exist to fail with a message naming the actual mistake.

    Args:
        cfg: A loaded, validated training config.
        source_path: The config file the operator passed to ``run``.
        run_dir: The directory the backend will train into.
        resolved_dest: Where to stage the emitted config.

    Raises:
        BackendError: The destination is unusable, would destroy the source, or the write
            failed. Nothing partial and nothing misleading is left behind.
    """
    # Re-check immediately before writing: the caller checked earlier, and a checkpoint
    # appearing in that window would otherwise strand these artifacts next to it. This narrows
    # the race, it does not close it -- a checkpoint appearing between *this* check and the
    # writes below would still slip through. Closing it properly would need a lock the backend
    # does not participate in, and the operator-facing failure (two runs sharing one name) is
    # already refused for every realistic ordering.
    check_run_directory(run_dir)

    source_copy = run_dir / SOURCE_CONFIG_NAME
    _check_destination_name(resolved_dest)
    # The override moves the emitted config; it is not a way around the reuse guard. Walk the
    # ancestors rather than checking only the immediate parent: `registry/publish.py` uploads a
    # model directory with a *recursive* add_dir, so a config written into any subdirectory of a
    # finished run would be published as part of that run's artifact.
    _check_no_run_in_ancestors(resolved_dest, run_dir.parent)
    if resolved_dest.is_dir():
        raise BackendError(
            f"--emitted-config must name a file, but {resolved_dest} is a directory"
        )
    if _same_file(resolved_dest, source_path):
        raise BackendError(
            f"--emitted-config would overwrite the input config {source_path}; the "
            "emitted config has the experiment block stripped, so this would destroy the "
            "run's identity"
        )
    if _same_file(resolved_dest, source_copy):
        raise BackendError(
            f"--emitted-config resolves to {source_copy}, which `run` writes itself"
        )

    before = _entries(run_dir)
    try:
        source_bytes = source_path.read_bytes()
        # `source_config.yaml` first, deliberately: it is the only artifact carrying the
        # `experiment` block, so if the second write fails the run directory keeps the record
        # nothing else can reproduce rather than the one the backend rewrites anyway.
        _atomic_write(source_copy, source_bytes)
        _atomic_write(
            resolved_dest, training_config.to_sleap_nn_yaml(cfg).encode("utf-8")
        )
    except OSError as error:
        # A write that fails *after* materializing a file is the B3 case: on NTFS `mkstemp`
        # creates the base file of a `name:stream` destination, and `_atomic_write`'s own
        # cleanup can only unlink the stream it opened.
        raise BackendError(
            "could not write the run's config artifacts: "
            f"{error}{_purge_fabricated_evidence(run_dir, before)}"
        ) from error
    _verify_staging(run_dir, source_copy, source_bytes, before)


def stage_run_metadata(run_dir: Path, binary: Path, version: Optional[str]) -> None:
    """Record what would have trained this run, before the backend is started.

    For a repo grading reproduce-or-beat against a PyTorch baseline the backend version is
    the single most result-determining variable, and the resolved backend *path* is the only
    thing that says which of several installed environments actually ran -- the
    interpreter-first search in :func:`resolve_sleap_nn` can pick a different one than the
    operator expects, and visibility is that function's whole stated mitigation. A console
    line does not survive the session; this does.

    The reason given for not stamping the version into the staged config -- byte-identity
    with ``emit -o`` -- binds ``emitted_config.yaml`` only, so a separate sidecar costs
    nothing. Written **before** the subprocess starts, because the window it covers is a run
    that dies during setup, which is the same window the emitted config exists for.

    With ``source_config.yaml`` already giving the config bytes verbatim, this closes the code
    and environment halves of the provenance gap tracked in #32; the dataset checksum and the
    git commit stay there.

    Args:
        run_dir: The directory the backend will train into.
        binary: The resolved ``sleap-nn`` console script.
        version: What that backend reported, or ``None`` when it could not be asked -- which
            is itself recorded, rather than the key being dropped.

    Raises:
        BackendError: The sidecar could not be written.
    """
    metadata = OmegaConf.create(
        {
            "sleap_nn_version": version,
            "sleap_nn_path": str(binary),
            "sleap_roots_training_version": _package_version(),
            # Not reproducible by construction, and deliberately not part of any
            # byte-identity guarantee -- `emitted_config.yaml` carries that one.
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    try:
        _atomic_write(
            run_dir / RUN_METADATA_NAME, OmegaConf.to_yaml(metadata).encode("utf-8")
        )
    except OSError as error:
        raise BackendError(f"could not write the run's metadata: {error}") from error


def _package_version() -> str:
    """Return this package's version, preferring the installed distribution's metadata.

    ``__version__`` is the fallback rather than the source: an editable install of a working
    tree reports the distribution version, which is what a reader trying to reproduce the run
    would go looking for.

    Returns:
        The version string.
    """
    from importlib import metadata

    try:
        return metadata.version("sleap-roots-training")
    except (
        metadata.PackageNotFoundError
    ):  # pragma: no cover - needs an uninstalled tree
        from sleap_roots_training import __version__

        return __version__


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
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        # A non-zero probe has said nothing about the version; its stdout is usage text, not
        # a version string. Since this value is recorded as the run's backend identity, a
        # wrong string is worse than none -- and the flag disappearing is exactly the future
        # bump the probe exists to notice.
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

#: How often the wait loop returns to Python while the backend runs. It has to return at all:
#: `Popen.wait()` with no timeout is a non-alertable `WaitForSingleObject(INFINITE)` on
#: Windows, so a pending interrupt is deferred until the child exits -- on the platform that
#: trains. Two wakeups a second against a multi-hour run is not a cost worth optimizing.
_WAIT_POLL_SECONDS = 0.5


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
            _SIGNAL_EXIT_BASE + signal_number,
            f"sleap-nn train was terminated by signal {signal_number}",
        )
    if returncode == _STATUS_CONTROL_C_EXIT:
        # Windows never reports POSIX-style negative codes, so a console Ctrl-C arrives as this
        # NTSTATUS. Reporting it raw gave exit 1 and a 10-digit number no operator recognizes,
        # for the same event that yields 130 on POSIX.
        return BackendOutcome(
            _INTERRUPT_EXIT_CODE, "sleap-nn train was interrupted (Ctrl-C)"
        )
    if returncode > _MAX_EXIT_STATUS:
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
    try:
        while True:
            try:
                # A bounded wait, not a blocking one. On Windows the blocking form defers a
                # pending interrupt until the child exits, so the ladder below could not run
                # at all there: the "press Ctrl-C again" line printed after the child had
                # already gone, and a child that defers the first interrupt -- which is what a
                # graceful-shutdown handler does -- could not be stopped by the second or
                # third. Measured against a 30s child interrupted at 1.0s: 30.0s blocking,
                # ~2.5s polled.
                returncode = process.wait(timeout=_WAIT_POLL_SECONDS)
                break
            except subprocess.TimeoutExpired:
                continue
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
                    # The ladder needs a ceiling, or a child that ignores SIGINT could not be
                    # aborted at all. Escalating only on an explicit second request keeps the
                    # graceful path for the ordinary case.
                    print("terminating sleap-nn", file=sys.stderr, flush=True)
                    process.terminate()
                else:
                    print("killing sleap-nn", file=sys.stderr, flush=True)
                    process.kill()
    finally:
        # Do not leave a trainer holding GPU memory if this frame unwinds for any reason the
        # ladder above did not handle. This covers exception-driven unwinding only: a
        # default-disposition SIGTERM to *this* process (an IDE stop button, a closed
        # terminal) kills the interpreter without unwinding, so no `finally` runs. Covering
        # that would need a signal handler, which is a larger change than this review asked
        # for and is noted in design.md rather than done here.
        if process.poll() is None:  # pragma: no cover - needs an unhandled unwind
            process.terminate()
    return _translate_status(returncode)
