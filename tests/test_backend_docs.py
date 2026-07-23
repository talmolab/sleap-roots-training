"""Structural contract test for the training-backend runbook.

CI-safe: reads ``docs/training-backend.md`` from disk and asserts it documents the verified
backend workflow — the install token, a fenced ``sleap-nn train`` command, a fenced
``sleap-nn track`` inference command, and a real GPU arch-findings section. The command and
arch assertions are scoped to **fenced code blocks** / the **arch-findings section** (not the
whole doc), so mutating the real commands or the recorded arch list fails the test rather than
passing on an unrelated mention elsewhere in prose. The arch *content* itself is verified by the
manual A5000 spike (change tasks.md task 4); this locks it in.

Reads with an explicit ``utf-8`` encoding and normalizes ``\\r\\n`` so the assertions hold on
the Windows CI leg regardless of checkout line endings.
"""

from __future__ import annotations

import re
from pathlib import Path

RUNBOOK = Path(__file__).resolve().parents[1] / "docs" / "training-backend.md"
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def _read() -> str:
    return RUNBOOK.read_text(encoding="utf-8").replace("\r\n", "\n")


def _fenced_blocks(text: str) -> list[str]:
    return _FENCE.findall(text)


def _arch_findings_section(text: str) -> str:
    match = re.search(
        r"## GPU / CUDA arch findings\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    assert match, "runbook missing a '## GPU / CUDA arch findings' section"
    return match.group(1)


def test_runbook_exists():
    assert RUNBOOK.is_file(), f"missing training-backend runbook: {RUNBOOK}"


def test_runbook_documents_install_token():
    assert (
        "sleap-roots-training[train]" in _read()
    ), "runbook missing the `sleap-roots-training[train]` install token"


def test_runbook_train_command_in_fenced_block():
    blocks = _fenced_blocks(_read())
    assert any(
        "sleap-nn train --config" in block for block in blocks
    ), "no fenced `sleap-nn train --config ...` command in the runbook"


def test_runbook_inference_command_in_fenced_block():
    # 0.2.0 checkpoint inference is `sleap-nn track` (predict is the ONNX-export path).
    blocks = _fenced_blocks(_read())
    assert any(
        re.search(r"sleap-nn track\b[^\n]*--model_paths", block) for block in blocks
    ), "no fenced `sleap-nn track ... --model_paths ...` inference command in the runbook"


def test_runbook_records_real_arch_list():
    text = _read()
    section = _arch_findings_section(text)
    assert (
        "get_arch_list" in section
    ), "arch-findings section missing get_arch_list output"
    sm_tokens = set(re.findall(r"sm_\d+", section))
    assert "sm_86" in sm_tokens and len(sm_tokens) >= 3, (
        "arch-findings section lacks a concrete multi-entry arch list including sm_86 "
        f"(found {sorted(sm_tokens)})"
    )
    for placeholder in ("TODO", "TBD"):
        assert placeholder not in text, f"runbook still has a {placeholder} placeholder"
