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

import shutil
import sys
import sysconfig
from pathlib import Path

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
