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
    # The section reports the real accuracy headline and cites the TF reference (context only).
    for token in ("PyTorch baseline", "dist_avg", "vis_recall", "tf-reference.md"):
        assert token in text, f"baseline section missing {token!r}"
    # os4 is the baseline, os2 is the documented collapse — both named (guards an os4/os2 swap).
    assert "output_stride 4" in text and "output_stride 2" in text
    assert "collapsed" in text, "the os2 collapse finding must stay documented"
    # The os4 dist_avg range must parse to two sane floats (lo <= hi) — not merely be a substring.
    range_lines = [ln for ln in text.splitlines() if "**range**" in ln]
    assert range_lines, "no os4 baseline `**range**` row found"
    nums = [float(x) for x in re.findall(r"\d+\.\d+", range_lines[0])]
    assert len(nums) >= 2, f"range row has too few numbers: {range_lines[0]!r}"
    lo, hi = nums[0], nums[1]
    assert 1.0 < lo <= hi < 200.0, f"dist_avg range is not sane px: {lo}-{hi}"


def test_guide_has_no_placeholders():
    text = _read()
    for placeholder in ("TODO", "TBD"):
        assert placeholder not in text, f"guide still has a {placeholder} placeholder"
