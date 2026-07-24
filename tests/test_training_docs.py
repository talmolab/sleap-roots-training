"""Structural contract test for the config-driven training guide.

CI-safe: reads ``docs/training.md`` from disk and asserts it documents the workflow — a fenced
``sleap-roots-training validate`` command, a fenced ``sleap-nn train --config`` command, the
empirical ``scan_history()`` per-epoch-W&B check, a pointer to the backend runbook, and the
reserved-baseline marker (present, so it can't be silently dropped) — while forbidding any
``TODO`` / ``TBD`` placeholder. The command assertions are scoped to **fenced code blocks** so a
mutated command fails rather than passing on an unrelated prose mention.

Reads with explicit ``utf-8`` and normalizes ``\\r\\n`` so the assertions hold on the Windows CI
leg regardless of checkout line endings.
"""

from __future__ import annotations

import re
from pathlib import Path

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "training.md"
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

#: The exact reserved-baseline marker the follow-up baseline PR replaces with real numbers.
#: Asserted present so the reservation can't be silently deleted; kept free of TODO/TBD.
_RESERVED_MARKER = "**Reserved** — the PyTorch baseline numbers are established by the follow-up baseline PR"


def _read() -> str:
    return GUIDE.read_text(encoding="utf-8").replace("\r\n", "\n")


def _fenced_blocks(text: str) -> list[str]:
    return _FENCE.findall(text)


def test_guide_exists():
    assert GUIDE.is_file(), f"missing training guide: {GUIDE}"


def test_guide_validate_command_in_fenced_block():
    blocks = _fenced_blocks(_read())
    assert any(
        "sleap-roots-training validate" in block for block in blocks
    ), "no fenced `sleap-roots-training validate ...` command in the guide"


def test_guide_emit_command_in_fenced_block():
    blocks = _fenced_blocks(_read())
    assert any(
        "sleap-roots-training emit" in block for block in blocks
    ), "no fenced `sleap-roots-training emit ...` command in the guide"


def test_guide_train_command_in_fenced_block():
    blocks = _fenced_blocks(_read())
    assert any(
        "sleap-nn train --config" in block for block in blocks
    ), "no fenced `sleap-nn train --config ...` command in the guide"


def test_guide_documents_scan_history_check():
    assert (
        "scan_history()" in _read()
    ), "guide missing the empirical per-epoch `scan_history()` verification"


def test_guide_points_to_backend_runbook():
    assert (
        "training-backend.md" in _read()
    ), "guide should point to the backend runbook (docs/training-backend.md)"


def test_guide_reserves_baseline_section():
    assert (
        _RESERVED_MARKER in _read()
    ), "guide missing the reserved PyTorch-baseline marker"


def test_guide_has_no_placeholders():
    text = _read()
    for placeholder in ("TODO", "TBD"):
        assert placeholder not in text, f"guide still has a {placeholder} placeholder"
