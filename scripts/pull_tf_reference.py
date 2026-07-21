"""Capture the canonical TensorFlow reference W&B run payloads as committed fixtures.

Pulls the ``config`` and ``summary`` of the seven canonical runs of the
``20250625_cyl_arabidopsis_primary_receptive_field`` group (run-name suffix
``_training_v000``) and writes each as pretty-printed, key-sorted JSON under
``tests/fixtures/tf_reference/``. These committed payloads are the TF reference baseline
(see ``docs/tf-reference.md``) and let the registry code be exercised against realistic
W&B payload shapes without network access.

Only ``config``/``summary`` data is written -- never a W&B API key or netrc. The script
relies on an existing ``wandb login`` session (a netrc entry for ``api.wandb.ai``) or
``WANDB_API_KEY`` in the environment.

The raw payloads embed an internal SMB host and user in their path strings; those two
segments are redacted (see ``_redact``) before writing, keeping the audit-relevant
run-name/timestamps/group intact. Redaction is applied on every pull, so re-running still
reproduces byte-identical files.

Writes are deterministic (LF newlines, ``sort_keys``, ``ensure_ascii``, single trailing
newline) so re-running reproduces byte-identical files on every platform.

Usage:
    uv run python scripts/pull_tf_reference.py
"""

from __future__ import annotations

import json
from pathlib import Path

#: The W&B entity and project the canonical runs live in.
ENTITY = "eberrigan-salk-institute-for-biological-studies"
PROJECT = "sleap-roots"

#: The seven canonical run ids of the receptive-field sweep, in stride order.
RUN_IDS = (
    "ijn85j6w",  # stride 8  (no summary metrics)
    "nxe8xgsd",  # stride 16
    "v7rdm7cd",  # stride 16
    "qilbptpp",  # stride 32
    "1tryadtu",  # stride 32
    "yenwgpjq",  # stride 64
    "26ryyfu2",  # stride 64 (no summary metrics)
)

#: Where the committed fixtures live, relative to the repo root.
OUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "tf_reference"

#: Internal path segments scrubbed from every payload before it is committed. The
#: hostname reveals internal network topology; the user segment is redacted with it.
#: The audit-relevant run-name/timestamps/group are deliberately left intact.
_REDACTIONS = (
    ("multilab-na.ad.salk.edu", "REDACTED-HOST"),
    ("users/eberrigan", "users/REDACTED-USER"),  # forward-slash UNC form
    ("users\\eberrigan", "users\\REDACTED-USER"),  # backslash UNC form
)


def _redact(payload):
    """Return ``payload`` with the internal host/user redacted from every string value.

    Args:
        payload: A JSON-serializable value (dict, list, str, or scalar).

    Returns:
        The same structure with :data:`_REDACTIONS` applied to every string leaf.
    """
    if isinstance(payload, dict):
        return {key: _redact(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_redact(item) for item in payload]
    if isinstance(payload, str):
        for old, new in _REDACTIONS:
            payload = payload.replace(old, new)
        return payload
    return payload


def _write_json(path: Path, payload: dict) -> None:
    """Write ``payload`` as deterministic, byte-stable JSON.

    Args:
        path: The destination file.
        payload: The JSON-serializable mapping to write.
    """
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")


def main() -> int:
    """Pull every canonical run and write its ``config``/``summary`` fixtures.

    Returns:
        Process exit code (``0`` on success).
    """
    import wandb  # lazy: only this network path needs wandb.

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    api = wandb.Api()
    for run_id in RUN_IDS:
        run = api.run(f"{ENTITY}/{PROJECT}/{run_id}")
        _write_json(OUT_DIR / f"{run_id}.config.json", _redact(dict(run.config)))
        _write_json(
            OUT_DIR / f"{run_id}.summary.json",
            _redact(dict(run.summary._json_dict)),
        )
        print(f"{run_id} {run.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
