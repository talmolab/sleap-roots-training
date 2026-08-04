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
#: Captures the info string (group 1) as well as the body (group 2). The tag matters:
#: the mode guard below must read *only* YAML blocks, or a `python` fence containing
#: `mode: str = "cylinder"` and a `bash` fence containing `mode: $MODE` contaminate it.
_FENCE = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)

#: The exact reserved-baseline marker the follow-up baseline PR replaces with real numbers.
#: Asserted present so the reservation can't be silently deleted; kept free of TODO/TBD.
_RESERVED_MARKER = "**Reserved** — the PyTorch baseline numbers are established by the follow-up baseline PR"


def _read() -> str:
    return GUIDE.read_text(encoding="utf-8").replace("\r\n", "\n")


def _fenced_blocks(text: str) -> list[str]:
    return [body for _tag, body in _FENCE.findall(text)]


def _yaml_blocks(text: str) -> list[str]:
    return [
        body
        for tag, body in _FENCE.findall(text)
        if tag.strip().lower() in {"yaml", "yml"}
    ]


def _collect_modes(node) -> list[str]:
    """Every value under a ``mode`` key, at any depth, in a parsed YAML document."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "mode" and not isinstance(value, (dict, list)):
                found.append(value)
            found.extend(_collect_modes(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_modes(item))
    return found


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


def test_documented_experiment_modes_stay_contract_valid():
    """Every ``mode:`` the guide tells a user to write must still be accepted.

    ``MODE_VOCAB`` now comes from ``sleap_roots_contracts.Mode``, so the contract governs
    a **user-authoring** surface, not only published card metadata. An upstream narrowing
    of ``Mode`` would therefore invalidate configs people have already written by copying
    this guide. The shipped ``examples/`` are covered by ``test_examples_validate``; this
    is the other authoring surface, and nothing else reads it.

    Parsed as YAML rather than split on ``:``. A guard that fires on a *correct* docs edit
    is a defect in a repo whose rule is "main stays green", and naive splitting has three
    of them: quoting the value (`mode: "multiplant cylinder"` — and that is the one
    multi-word mode, so quoting it is exactly what a YAML style guide advises) yields
    ``'"multiplant cylinder"'``; a nested or flow-mapping form is missed; and a `python`
    or `bash` fence contributes junk. Worse, the message then blames the contract for a
    bug in the test. ``yaml.safe_load`` handles quoting, nesting, flow mappings and
    comments for free (PyYAML is already present — omegaconf requires it).
    """
    import yaml

    from sleap_roots_training.registry.chooser import MODE_VOCAB

    documented = []
    for block in _yaml_blocks(_read()):
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            continue  # a deliberate fragment, not a config a user would copy
        documented.extend(_collect_modes(parsed))

    assert documented, "guide documents no `mode:` value — did the example block move?"
    for mode in documented:
        assert mode in MODE_VOCAB, (
            f"docs/training.md tells users to write mode: {mode!r}, which the contract "
            f"vocabulary no longer accepts (allowed: {sorted(MODE_VOCAB)})"
        )
