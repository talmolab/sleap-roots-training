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
#: Captures the info string (group 1) as well as the body (group 2). The tag matters:
#: the mode guard below must read *only* YAML blocks, or a `python` fence containing
#: `mode: str = "cylinder"` and a `bash` fence containing `mode: $MODE` contaminate it.
_FENCE = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)

#: The reserved-baseline placeholder the baseline PR replaced with real numbers. Asserted ABSENT
#: now, so a regression that reintroduces a placeholder instead of real numbers fails.
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


def _experiment_modes(node) -> list[str]:
    """Every ``experiment.mode`` value in a parsed YAML document.

    Scoped to the ``experiment:`` block, not an unbounded walk for any ``mode`` key at
    any depth. A config is the repo-owned ``experiment`` block **plus** `sleap-nn`'s own
    ``data_config`` / ``model_config`` / ``trainer_config`` consumed as-is, and those
    carry unrelated ``mode`` keys — ``ReduceLROnPlateau(mode='min'|'max')`` is a
    completely standard Lightning field. Checking those against ``MODE_VOCAB`` turns the
    guide's own guard red the moment someone documents a scheduler correctly, and blames
    the contract for it. Only ``experiment.mode`` is the surface this guards.
    """
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "experiment" and isinstance(value, dict):
                mode = value.get("mode")
                if mode is not None and not isinstance(mode, (dict, list)):
                    found.append(mode)
            found.extend(_experiment_modes(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_experiment_modes(item))
    return found


def test_mode_guard_reads_only_the_experiment_block():
    """A `sleap-nn` ``mode:`` is not an ``experiment.mode`` and must not be guarded.

    The guide documents that a config carries `sleap-nn`'s own ``data_config`` /
    ``model_config`` / ``trainer_config`` "consumed as-is", and those have unrelated
    ``mode`` keys of their own — ``ReduceLROnPlateau(mode='min'|'max')`` is a completely
    standard Lightning field. An any-depth walk for ``mode`` collects those too and
    checks them against ``MODE_VOCAB``, so documenting a scheduler accurately turns the
    guide's own guard red and blames the contract for it. Same defect the YAML-aware
    rewrite was meant to fix, one layer down.
    """
    import yaml

    doc = yaml.safe_load(
        "experiment:\n"
        "  species: arabidopsis\n"
        "  mode: cylinder\n"
        "  root_type: primary\n"
        "trainer_config:\n"
        "  lr_scheduler:\n"
        "    reduce_lr_on_plateau:\n"
        "      mode: min\n"
        "      factor: 0.5\n"
        "model_config:\n"
        "  head_configs:\n"
        "    - name: centered_instance\n"
        "      mode: max\n"
    )
    assert _experiment_modes(doc) == ["cylinder"]


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
    comments for free (PyYAML is already present — omegaconf requires it). Collection is
    scoped to the ``experiment:`` block for the same reason — see ``_experiment_modes``.
    """
    import yaml

    from sleap_roots_training.registry.chooser import MODE_VOCAB

    documented = []
    for block in _yaml_blocks(_read()):
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            continue  # a deliberate fragment, not a config a user would copy
        documented.extend(_experiment_modes(parsed))

    assert (
        documented
    ), "guide documents no `experiment.mode:` value — did the example block move?"
    for mode in documented:
        assert mode in MODE_VOCAB, (
            f"docs/training.md tells users to write experiment.mode: {mode!r}, which "
            f"the contract vocabulary no longer accepts (allowed: {sorted(MODE_VOCAB)})"
        )


#: The one-command section's heading, matched exactly so the assertions below are scoped to
#: it rather than to the whole guide (the guide-wide command assertions above would
#: otherwise be satisfiable from inside this section alone -- see the canonical-path test).
_RUN_SECTION_HEADING = "One command (same machine)"


def _run_section(text: str) -> str:
    """Return the body of the one-command section, up to the next heading."""
    # Stops at the next level-2/3 heading, not level-4: the section's own `####`
    # subsections (the run-directory inventory, the run_name rule) are part of it.
    match = re.search(
        rf"\n#{{2,3}} {re.escape(_RUN_SECTION_HEADING)}\n(.*?)(?=\n#{{2,3}} |\Z)",
        text,
        re.DOTALL,
    )
    assert match, f"guide missing a '{_RUN_SECTION_HEADING}' section"
    return match.group(1)


def test_guide_run_command_in_fenced_block():
    blocks = _fenced_blocks(_run_section(_read()))
    assert any(
        "sleap-roots-training run" in block for block in blocks
    ), "no fenced `sleap-roots-training run ...` command in the one-command section"


def test_guide_run_section_documents_the_artifacts_and_the_gate():
    section = _run_section(_read())
    for token in ("resolved_config.yaml", "source_config.yaml", "[train]", "run_name"):
        assert token in section, f"the one-command section must mention {token}"


def test_guide_run_section_uses_no_sync():
    """A bare `uv run` re-syncs the project env and uninstalls the `[train]` extra.

    Same rule `scripts/clean_pkg.py` and `scripts/dump_val_metrics.py` already document;
    getting it wrong makes the gate fire on a box where the backend *was* installed.
    """
    assert "--no-sync" in _run_section(
        _read()
    ), "the one-command section must show the `uv run --no-sync` form"


def test_guide_keeps_the_canonical_path_outside_the_run_section():
    """The shortcut must not become the only place the three commands appear.

    ``test_guide_{validate,emit,train}_command_in_fenced_block`` scan the whole document,
    so an "equivalent to ..." comment inside the ``run`` block would satisfy all three --
    letting sections 1-3 be deleted while the suite stayed green. This scopes them to the
    blocks that do *not* mention ``run``.
    """
    blocks = [b for b in _fenced_blocks(_read()) if "sleap-roots-training run" not in b]
    for command in (
        "sleap-roots-training validate",
        "sleap-roots-training emit",
        "sleap-nn train --config",
    ):
        assert any(command in block for block in blocks), (
            f"`{command}` survives only inside the `run` block -- the canonical "
            "three-command path must stay documented in its own right"
        )
