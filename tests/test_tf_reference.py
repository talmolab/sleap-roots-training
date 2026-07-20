"""Lock the documented TensorFlow reference against the committed fixtures.

Guards `docs/tf-reference.md` and the committed W&B payloads under
`tests/fixtures/tf_reference/` against silent drift: the sweep structure, the two
same-stride `dist_avg` ranges, the broken `oks_map`, and the two missing-summary runs
must all remain true of the data — and the documentation must keep stating them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "tf_reference"
DOC = Path(__file__).parent.parent / "docs" / "tf-reference.md"
SCRIPT = Path(__file__).parent.parent / "scripts" / "pull_tf_reference.py"

#: The seven canonical run ids of the receptive-field sweep.
RUN_IDS = (
    "ijn85j6w",
    "nxe8xgsd",
    "v7rdm7cd",
    "qilbptpp",
    "1tryadtu",
    "yenwgpjq",
    "26ryyfu2",
)

#: Runs that logged no summary metrics (only the `_wandb` bookkeeping key).
NO_SUMMARY_RUNS = {"ijn85j6w", "26ryyfu2"}

#: Documented same-stride `dist_avg` ranges (the doc rounds to 3 decimals).
DOC_DIST_AVG_RANGES = {16: (0.989, 1.710), 32: (1.383, 2.078)}

#: The `oks_map` broken-metric ceiling — every summarized run reads below this.
OKS_MAP_CEILING = 0.05


def _load(run_id: str, kind: str) -> dict:
    return json.loads((FIXTURES / f"{run_id}.{kind}.json").read_text())


def _max_stride(config: dict) -> int:
    flat = config["model.backbone.unet.max_stride"]
    nested = config["model"]["backbone"]["unet"]["max_stride"]
    assert flat == nested, "flat and nested max_stride disagree"
    return flat


def test_all_payloads_and_provenance_present():
    for run_id in RUN_IDS:
        assert (FIXTURES / f"{run_id}.config.json").is_file()
        assert (FIXTURES / f"{run_id}.summary.json").is_file()
    # Exactly the 14 payloads + the manifest, and the capture script.
    payloads = sorted(p.name for p in FIXTURES.glob("*.json"))
    assert len(payloads) == 14
    assert (FIXTURES / "README.md").is_file()
    assert SCRIPT.is_file()


def test_fixtures_have_no_secrets():
    # A wandb API key is 40 lowercase hex chars; no fixture file should contain one.
    key_re = re.compile(r"\b[0-9a-f]{40}\b")
    for path in sorted(FIXTURES.iterdir()):
        assert not key_re.search(path.read_text()), f"possible API key in {path.name}"
    # No payload should carry a credential-bearing key with a non-empty value.
    for run_id in RUN_IDS:
        for kind in ("config", "summary"):
            blob = json.dumps(_load(run_id, kind)).lower()
            for marker in ("api_key", "wandb_api_key", "password", "secret", "token"):
                assert f'"{marker}"' not in blob, f"{marker} in {run_id}.{kind}.json"


def test_stride_multiset_is_a_sweep():
    strides = sorted(_max_stride(_load(run_id, "config")) for run_id in RUN_IDS)
    # Two runs each at 16/32/64 and a single run at stride 8 — seven runs, a sweep.
    assert strides == [8, 16, 16, 32, 32, 64, 64]


def test_missing_summary_runs_have_no_metrics():
    for run_id in NO_SUMMARY_RUNS:
        summary = _load(run_id, "summary")
        assert set(summary) <= {"_wandb"}, f"{run_id} unexpectedly has metrics"
    for run_id in set(RUN_IDS) - NO_SUMMARY_RUNS:
        assert "dist_avg" in _load(run_id, "summary")


def test_oks_map_is_broken():
    for run_id in set(RUN_IDS) - NO_SUMMARY_RUNS:
        oks_map = _load(run_id, "summary")["oks_map"]
        assert 0 < oks_map < OKS_MAP_CEILING, f"{run_id} oks_map={oks_map}"


def test_same_stride_dist_avg_ranges_match_doc():
    by_stride: dict[int, list[float]] = {}
    for run_id in RUN_IDS:
        summary = _load(run_id, "summary")
        if "dist_avg" not in summary:
            continue
        stride = _max_stride(_load(run_id, "config"))
        by_stride.setdefault(stride, []).append(summary["dist_avg"])
    for stride, (lo, hi) in DOC_DIST_AVG_RANGES.items():
        values = by_stride[stride]
        assert len(values) == 2, f"stride{stride} is not a genuine same-stride pair"
        assert min(values) == pytest.approx(lo, abs=1e-3)
        assert max(values) == pytest.approx(hi, abs=1e-3)


def test_doc_locks_the_documented_claims():
    doc = DOC.read_text()
    assert "sweep" in doc.lower()
    # The two same-stride ranges (rounded values) must appear in the doc.
    for value in ("0.989", "1.710", "1.383", "2.078"):
        assert value in doc, f"{value} missing from docs/tf-reference.md"
    # oks_map is excluded, with both missing-summary runs named.
    assert "oks_map" in doc
    assert re.search(r"exclud", doc, re.IGNORECASE)
    assert "ijn85j6w" in doc and "26ryyfu2" in doc
    # The observability gap is recorded.
    assert "scan_history" in doc
