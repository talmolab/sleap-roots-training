"""Lock the documented TensorFlow reference against the committed fixtures.

Guards `docs/tf-reference.md` and the committed W&B payloads under
`tests/fixtures/tf_reference/` against silent drift: the sweep structure, every cell of
the per-stride metrics table, the two same-stride `dist_avg` ranges, the broken
`oks_map`, and the two missing-summary runs must all remain true of the data -- and the
documentation must keep stating them.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from conftest import NO_SUMMARY_RUNS, TF_RUN_IDS as RUN_IDS

FIXTURES = Path(__file__).parent / "fixtures" / "tf_reference"
DOC = Path(__file__).parent.parent / "docs" / "tf-reference.md"
SCRIPT = Path(__file__).parent.parent / "scripts" / "pull_tf_reference.py"

#: Documented same-stride `dist_avg` ranges (the doc rounds to 3 decimals).
DOC_DIST_AVG_RANGES = {16: (0.989, 1.710), 32: (1.383, 2.078)}

#: The `oks_map` broken-metric ceiling — every summarized run reads below this.
OKS_MAP_CEILING = 0.05

#: Metric columns of the per-stride table in `docs/tf-reference.md`, left to right after
#: the run-id and `max_stride` columns.
DOC_METRIC_COLUMNS = ("dist_avg", "dist_p50", "dist_p90", "vis_recall")


def _load(run_id: str, kind: str) -> dict:
    return json.loads((FIXTURES / f"{run_id}.{kind}.json").read_text())


def _max_stride(config: dict) -> int:
    flat = config["model.backbone.unet.max_stride"]
    nested = config["model"]["backbone"]["unet"]["max_stride"]
    assert flat == nested, "flat and nested max_stride disagree"
    return flat


def _load_capture_script():
    """Import `scripts/pull_tf_reference.py` as a module (its wandb import is lazy)."""
    spec = importlib.util.spec_from_file_location("pull_tf_reference", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_doc_metric_table() -> dict[str, dict]:
    """Parse the per-stride metrics table out of `docs/tf-reference.md`.

    Returns a mapping of run id -> {"max_stride": int, "cells": {column: text}} for every
    table row that names a canonical run. A missing metric keeps its literal "—" text.
    """
    rows: dict[str, dict] = {}
    for line in DOC.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip().strip("`").strip() for c in stripped.strip("|").split("|")]
        run_id = cells[0]
        if run_id not in RUN_IDS:
            continue
        rows[run_id] = {
            "max_stride": int(cells[1]),
            "cells": dict(zip(DOC_METRIC_COLUMNS, cells[2:6])),
        }
    return rows


def test_all_payloads_and_provenance_present():
    for run_id in RUN_IDS:
        assert (FIXTURES / f"{run_id}.config.json").is_file()
        assert (FIXTURES / f"{run_id}.summary.json").is_file()
    # Exactly the 14 payloads + the manifest, and the capture script.
    payloads = sorted(p.name for p in FIXTURES.glob("*.json"))
    assert len(payloads) == 14
    assert (FIXTURES / "README.md").is_file()
    assert SCRIPT.is_file()


def test_capture_script_run_ids_match_shared_constant():
    # The standalone capture script keeps its own RUN_IDS copy (it must not import the
    # test package); guard it against drifting from the shared conftest tuple.
    module = _load_capture_script()
    assert (
        module.RUN_IDS == RUN_IDS
    ), "scripts/pull_tf_reference.py RUN_IDS drifted from tests/conftest.py TF_RUN_IDS"


def test_fixtures_have_no_secrets():
    # A wandb API key is 40 hex chars. Match a 40+-hex run bounded by non-hex characters,
    # case-insensitively, so a key cannot slip through by casing, extra length, or being
    # glued to underscores/adjacent word characters (which a `\b`-anchored regex missed).
    key_re = re.compile(r"(?<![0-9a-f])[0-9a-f]{40,}(?![0-9a-f])", re.IGNORECASE)
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
        # abs=5e-4 is half the doc's 3-decimal rounding unit: a fixture that would round
        # to a different 3-decimal string than the doc cannot stay inside tolerance.
        assert min(values) == pytest.approx(lo, abs=5e-4)
        assert max(values) == pytest.approx(hi, abs=5e-4)


def test_doc_table_matches_every_fixture_cell():
    # Lock EVERY cell of the per-stride table -- including the stride-8/64 singleton rows,
    # not just the two paired ranges -- to the committed fixture value rounded to the
    # doc's 3 decimals. This is what catches a single silently-wrong number.
    rows = _parse_doc_metric_table()
    assert set(rows) == set(RUN_IDS), "doc table must list exactly the seven runs"
    for run_id, row in rows.items():
        assert row["max_stride"] == _max_stride(
            _load(run_id, "config")
        ), f"{run_id}: doc max_stride disagrees with the fixture config"
        if run_id in NO_SUMMARY_RUNS:
            for column, cell in row["cells"].items():
                assert (
                    cell == "—"
                ), f"{run_id}: doc {column}={cell!r}, expected '—' (no metrics logged)"
            continue
        summary = _load(run_id, "summary")
        for column, cell in row["cells"].items():
            expected = f"{summary[column]:.3f}"
            assert cell == expected, (
                f"{run_id}: doc {column}={cell!r} but fixture {summary[column]!r} "
                f"rounds to {expected}"
            )


def test_doc_locks_the_documented_claims():
    doc = DOC.read_text()
    assert "sweep" in doc.lower(), "the doc must frame the group as a sweep"
    # The two same-stride ranges (rounded values) must appear in the doc.
    for value in ("0.989", "1.710", "1.383", "2.078"):
        assert value in doc, f"{value} missing from docs/tf-reference.md"
    # oks_map is excluded, with both missing-summary runs named.
    assert "oks_map" in doc, "the doc must discuss the excluded oks_map metric"
    assert re.search(
        r"exclud", doc, re.IGNORECASE
    ), "the doc must say oks_map is excluded"
    assert (
        "ijn85j6w" in doc and "26ryyfu2" in doc
    ), "both missing-summary run ids must be named in the doc"
    # The observability gap is recorded.
    assert (
        "scan_history" in doc
    ), "the doc must record the scan_history observability gap"
