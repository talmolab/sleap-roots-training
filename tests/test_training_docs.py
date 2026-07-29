"""Structural contract test for the config-driven training guide.

CI-safe: reads ``docs/training.md`` from disk and asserts it documents the workflow — a fenced
``sleap-roots-training validate`` command, a fenced ``sleap-nn train --config`` command, the
empirical ``scan_history()`` per-epoch-W&B check, a pointer to the backend runbook, and the
**established** PyTorch baseline (real headline metrics present, the reserved placeholder gone) —
while forbidding any ``TODO`` / ``TBD`` placeholder. The command assertions are scoped to
**fenced code blocks** so a mutated command fails rather than passing on an unrelated prose mention.

Reads with explicit ``utf-8`` and normalizes ``\\r\\n`` so the assertions hold on the Windows CI
leg regardless of checkout line endings.
"""

from __future__ import annotations

import re
from pathlib import Path

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "training.md"
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

#: The reserved-baseline placeholder the baseline PR replaced with real numbers. Asserted ABSENT
#: now, so a regression that reintroduces a placeholder instead of real numbers fails.
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


def test_guide_documents_established_baseline():
    text = _read()
    # The reserved placeholder must be gone — replaced by real established-baseline numbers.
    assert (
        _RESERVED_MARKER not in text
    ), "baseline section still shows the reserved placeholder"
    # The section reports the real accuracy headline (localization distance + visibility recall).
    for token in ("PyTorch baseline", "dist_avg", "vis_recall"):
        assert token in text, f"baseline section missing {token!r}"
    # The TF reference is cited as context only, not a gate.
    assert (
        "tf-reference.md" in text
    ), "baseline should cite the TF reference (context only)"


def test_guide_has_no_placeholders():
    text = _read()
    for placeholder in ("TODO", "TBD"):
        assert placeholder not in text, f"guide still has a {placeholder} placeholder"
