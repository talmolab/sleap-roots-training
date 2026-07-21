"""Structural contract test for the training-backend runbook.

CI-safe: reads ``docs/training-backend.md`` from disk and asserts *structural* completeness
(presence only) — the install token, a fenced ``sleap-nn`` train command, a prediction
command, and a GPU compute-capability / arch findings section. The *content* of the arch
findings is verified by the manual spike on the A5000 (change tasks.md task 4), which then
extends this test to require a concrete arch token and no leftover placeholder.

Reads with an explicit ``utf-8`` encoding and normalizes ``\\r\\n`` so the assertions hold on
the Windows CI leg regardless of checkout line endings.
"""

from __future__ import annotations

from pathlib import Path

RUNBOOK = Path(__file__).resolve().parents[1] / "docs" / "training-backend.md"


def _read() -> str:
    return RUNBOOK.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_runbook_exists():
    assert RUNBOOK.is_file(), f"missing training-backend runbook: {RUNBOOK}"


def test_runbook_documents_install_token():
    assert "sleap-roots-training[train]" in _read()


def test_runbook_documents_train_and_predict_commands():
    text = _read()
    assert "```" in text, "runbook has no fenced command blocks"
    assert "sleap-nn train" in text, "runbook missing a sleap-nn train command"
    assert ("sleap-nn predict" in text) or (
        "sleap-nn track" in text
    ), "runbook missing a prediction command"


def test_runbook_has_arch_findings_section():
    text = _read().lower()
    assert (
        ("get_arch_list" in text)
        or ("compute capability" in text)
        or ("arch list" in text)
    ), "runbook missing a GPU compute-capability / arch findings section"
