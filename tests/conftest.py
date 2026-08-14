"""Shared pytest fixtures for the sleap-roots-training test suite.

Centralizes the setup that was otherwise re-invented across test modules — writing a
selection-matrix YAML to a temp path, staging a stub models-root, and isolating the
wandb/registry environment (env vars + netrc/home) for hermetic tests — plus loaders for
the committed TensorFlow-reference W&B payloads under ``tests/fixtures/tf_reference/``.
"""

from __future__ import annotations

import base64
import copy
import csv
import json
import shutil
from pathlib import Path
from typing import Callable

import pytest
import numpy as np
import sleap_io as sio
from omegaconf import OmegaConf

from sleap_roots_training.labeling.build_package import build_slp_project
from sleap_roots_training.labeling.metadata import PackageMetadata
from sleap_roots_training.labeling import select_samples as ss
from sleap_roots_training.labeling.metadata import (
    PackageRecord,
    SelectionParameters,
    write_package_metadata,
)
from sleap_roots_training.labeling.package import build_labeling_package

#: Directory holding committed test data.
FIXTURES_DIR = Path(__file__).parent / "fixtures"

#: The seven canonical run ids of the TensorFlow-reference receptive-field sweep, in
#: stride order. Single source of truth for the tests that key off them (the standalone
#: capture script keeps its own copy, guarded against drift by ``test_tf_reference``).
TF_RUN_IDS = (
    "ijn85j6w",  # stride 8  (no summary metrics)
    "nxe8xgsd",  # stride 16
    "v7rdm7cd",  # stride 16
    "qilbptpp",  # stride 32
    "1tryadtu",  # stride 32
    "yenwgpjq",  # stride 64
    "26ryyfu2",  # stride 64 (no summary metrics)
)

#: The runs that logged no summary metrics (only the ``_wandb`` bookkeeping key).
NO_SUMMARY_RUNS = frozenset({"ijn85j6w", "26ryyfu2"})

#: The wandb/registry environment variables a hermetic test must clear. ``NETRC`` joins
#: the registry vars so netrc-based credential resolution is isolated too; ``HOME``/
#: ``USERPROFILE`` are *repointed* (not cleared) by ``isolate_wandb_env`` below.
_WANDB_ENV_VARS = (
    "WANDB_API_KEY",
    "WANDB_ENTITY",
    "SLEAP_ROOTS_MODEL_REGISTRY",
    "SLEAP_ROOTS_MODEL_ALIAS",
    "NETRC",
)

#: A minimal one-row selection matrix (one primary + one lateral, shared checksum).
TINY_MATRIX = """\
models:
  - species: soybean
    mode: cylinder
    age: "2, 3"
    primary_model_id: soy/p
    lateral_model_id: soy/l
    crown_model_id: null
checksums:
  soy/p: {sha}
  soy/l: {sha}
""".format(sha="0" * 64)


#: A 16x16 grayscale JPEG, committed as bytes rather than generated.
#:
#: The labeling builder opens curated images through sleap-io's ``ImageVideo`` backend,
#: which decodes them, so its fixtures need real JPEGs rather than placeholder bytes.
#: Writing them with ``imageio`` would make the tests depend on a package that is only
#: importable *transitively* via sleap-io — the same trap task 2.1 closed for ``pandas``,
#: and not worth a direct test dependency for 447 bytes of constant.
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAAQABABAREA/8QAHwAAAQUBAQEB"
    "AQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1Fh"
    "ByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZ"
    "WmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
    "x8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/9oACAEBAAA/APMfAfgP/hN/7Q/4mX2L"
    "7H5f/LDzN+/d/tDGNv60ePPAf/CEf2f/AMTL7b9s8z/lh5ezZt/2jnO79KPAfjz/AIQj+0P+Jb9t"
    "+2eX/wAt/L2bN3+yc53fpR488ef8Jv8A2f8A8S37F9j8z/lv5m/ft/2RjG39a//Z"
)


def write_jpeg(path: Path) -> Path:
    """Write :data:`TINY_JPEG` to ``path``, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(TINY_JPEG)
    return path


@pytest.fixture
def tiny_matrix(tmp_path: Path) -> Path:
    """Write the minimal selection matrix to a temp path and return it."""
    path = tmp_path / "matrix.yaml"
    path.write_text(TINY_MATRIX, encoding="utf-8")
    return path


@pytest.fixture
def stub_models_root(tmp_path: Path) -> Path:
    """A models-root with the two tiny models as already-unzipped dirs."""
    root = tmp_path / "models"
    for model_id in ("soy/p", "soy/l"):
        model_dir = root / model_id
        model_dir.mkdir(parents=True)
        (model_dir / "best_model.h5").write_bytes(b"w")
        (model_dir / "training_config.json").write_bytes(b"{}")
    return root


@pytest.fixture
def isolate_wandb_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Fully isolate wandb/registry credential resolution from the host environment.

    Clears every var in ``_WANDB_ENV_VARS`` (``WANDB_API_KEY``/``WANDB_ENTITY``/the two
    ``SLEAP_ROOTS_MODEL_*`` vars/``NETRC``) and repoints ``HOME``/``USERPROFILE`` at an
    empty temp dir, so neither an exported key, an ambient ``wandb login`` netrc, nor a
    stray registry override leaks in — on any OS.

    Returns:
        The isolated home dir, so a test can write ``.netrc``/``_netrc`` into it to
        exercise the netrc fallback branches. Tests that need the underlying
        ``monkeypatch`` (e.g. to layer further patches) can request it as a separate
        fixture param — pytest hands this fixture and the test the same instance.
    """
    home = tmp_path / "home"
    home.mkdir()
    for var in _WANDB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def tf_reference_dir() -> Path:
    """The directory of committed TensorFlow-reference W&B payload fixtures."""
    return FIXTURES_DIR / "tf_reference"


#: A canonical, fully-valid training config reused across the config + CLI tests. It is
#: *final*-valid on purpose — a valid ``experiment`` vocab, an integer ``trainer_config.seed``,
#: a backbone + head (so it also passes deep sleap-nn validation under ``[train]``), and
#: ``use_wandb`` absent (so no W&B target is required) — so that adding the seed and W&B
#: checks in later commits never turns an earlier group's "good" config red. Tests state only
#: their *deviation* from it via ``write_config(overrides=..., drop=...)``.
VALID_CONFIG: dict = {
    "experiment": {
        "species": "arabidopsis",
        "mode": "cylinder",
        "root_type": "primary",
        "dataset": {
            "name": "arabidopsis_primary_cylinder",
            "path": "data/train.pkg.slp",
            "notes": "Tier 1 baseline dataset",
        },
    },
    "data_config": {
        "train_labels_path": ["data/train.pkg.slp"],
        "val_labels_path": ["data/val.pkg.slp"],
        "preprocessing": {
            "ensure_rgb": False,
            "ensure_grayscale": False,
            "max_height": 192,
            "max_width": 192,
            "scale": 1.0,
        },
    },
    "model_config": {
        "backbone_config": {"unet": {"filters": 32, "max_stride": 16}},
        "head_configs": {"single_instance": {"confmaps": {"sigma": 5.0}}},
    },
    "trainer_config": {
        "max_epochs": 50,
        "seed": 42,
        "save_ckpt": True,
        "ckpt_dir": "models",
        "run_name": "arabidopsis_primary_cylinder",
    },
}


def _drop_key(cfg: OmegaConf, dotted: str) -> None:
    """Delete a dotted key (e.g. ``trainer_config.seed``) from an OmegaConf container."""
    parts = dotted.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]


@pytest.fixture
def write_config(tmp_path: Path) -> Callable[..., Path]:
    """Return a factory that writes a training-config YAML to a temp path and returns it.

    The factory starts from a deep copy of ``VALID_CONFIG`` so a test only states its
    deviation:

    - ``overrides``: an OmegaConf-mergeable mapping deep-merged onto the valid config
      (set a value, or add an unknown key to exercise rejection).
    - ``drop``: dotted keys to delete (e.g. ``"experiment"`` or ``"trainer_config.seed"``).

    Fixtures are self-contained (built in ``tmp_path``); tests never read ``examples/``.
    """

    def _write(
        name: str = "config.yaml",
        overrides: dict | None = None,
        drop: tuple[str, ...] = (),
    ) -> Path:
        cfg = OmegaConf.create(copy.deepcopy(VALID_CONFIG))
        if overrides:
            cfg = OmegaConf.merge(cfg, overrides)
        for dotted in drop:
            _drop_key(cfg, dotted)
        path = tmp_path / name
        path.write_text(OmegaConf.to_yaml(cfg), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def tf_config(tf_reference_dir: Path) -> Callable[[str], dict]:
    """Return a loader for a committed run ``config`` payload by run id."""

    def load(run_id: str) -> dict:
        path = tf_reference_dir / f"{run_id}.config.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return load


@pytest.fixture
def tf_summary(tf_reference_dir: Path) -> Callable[[str], dict]:
    """Return a loader for a committed run ``summary`` payload by run id."""

    def load(run_id: str) -> dict:
        path = tf_reference_dir / f"{run_id}.summary.json"
        return json.loads(path.read_text(encoding="utf-8"))

    return load


# --------------------------------------------------------------------------------------
# Labeling-package builders.
#
# Promoted here during the blocking review of #40. Four test modules used to import these
# from `test_labeling_build_package`, and two more chained off `test_labeling_validate` and
# `test_labeling_package` — test-module-to-test-module imports that work only because
# pytest's `prepend` import mode puts `tests/` on `sys.path` and there is no
# `tests/__init__.py`. Adding either would have broken six files at once, for a reason
# with nothing to do with the code under test.
#
# The fixture is deliberately small and fully specified: two scans, three selected views,
# the soybean WEEP package the vault script was hand-edited to build. Tests state only
# their deviation from it.
# --------------------------------------------------------------------------------------

#: Two scans, three selected views each. The view indices are the vault script's own
#: three-view spread, so the frame/view correspondence under test is the shipped one.
SCANS = (
    (1, "9DK8KJJEZR", 3, 12742739, "A3244"),
    (2, "8XQ2LMNPQR", 3, 12742740, "WEEP-1-4"),
)
VIEWS = (1, 25, 49)

#: The soybean WEEP package the vault script was hand-edited to build.
METADATA = PackageMetadata(
    species="soybean",
    mode="cylinder",
    experiment="weep",
    root_types=("primary", "lateral"),
)


def manifest_rows(scans=SCANS, views=VIEWS, frame_indices=None):
    """Build manifest row dicts, letting a test decouple frame_index from view order."""
    for scan_id, qr, age, acc_id, acc_name in scans:
        indices = frame_indices if frame_indices is not None else range(len(views))
        for frame_index, view_index in zip(indices, views):
            scan_path = f"images/Wave1/Day{age}_20250101/{qr}"
            yield {
                "scan_id": scan_id,
                "plant_qr_code": qr,
                "plant_age_days": age,
                "accession_id": acc_id,
                "accession_name": acc_name,
                "wave_number": 1,
                "view_index": view_index,
                "frame_index": frame_index,
                "source_scan_path": scan_path,
                "source_image": f"{scan_path}/{view_index}.jpg",
                "output_filename": f"{acc_name}_{qr}_age{age}_{frame_index}.jpg",
            }


def write_manifest(path: Path, rows) -> list[dict]:
    """Write ``sample_manifest.csv`` and return the rows written."""
    rows = list(rows)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ss.MANIFEST_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_predictions(
    predictions_dir: Path,
    scan_id: int,
    root_type: str,
    view_indices=VIEWS,
    node_count: int = 6,
    model: str = "model_a",
    all_nan: bool = False,
    nan_from: int | None = None,
    node_names: list[str] | None = None,
) -> Path:
    """Write one scan's prediction ``.slp``, as the traits pipeline emits it.

    Prediction frames are indexed over the *full* rotation (``view_index - 1``), not over
    the selected subset — the offset the builder has to translate.

    Args:
        predictions_dir: Where to write the file.
        scan_id: The scan's Bloom id.
        root_type: The root type predicted.
        view_indices: Which 1-based views the file holds frames for.
        node_count: Nodes per instance.
        model: Model name embedded in the filename.
        all_nan: Write every keypoint as NaN — a frame SLEAP tracked nothing in.
        nan_from: Write keypoints from this index on as NaN — an occluded or
            early-terminating root, which is the common real-world case and which no
            fixture produced before the blocking review of #40.
        node_names: Override the node names, to exercise a model whose skeleton does
            not match the canonical `r1..rN` base-first chain. Sets `node_count`.
    """
    predictions_dir.mkdir(parents=True, exist_ok=True)
    nodes = node_names or [f"r{i}" for i in range(1, node_count + 1)]
    node_count = len(nodes)
    skeleton = sio.Skeleton(
        nodes=nodes,
        edges=[(nodes[i], nodes[i + 1]) for i in range(node_count - 1)],
        name=f"pred_{root_type}",
    )
    # The pipeline predicts on the scan's own container, not on the curated images; it is
    # never opened here (`open_videos=False`), only its frame indices are read.
    video = sio.Video(filename=f"/scans/scan_{scan_id}.h5", open_backend=False)
    frames = []
    for view_index in view_indices:
        points = np.array(
            [[float(view_index), float(i)] for i in range(node_count)], dtype=np.float64
        )
        if all_nan:
            points[:] = np.nan
        elif nan_from is not None:
            points[nan_from:] = np.nan
        instance = sio.PredictedInstance.from_numpy(
            points_data=points,
            skeleton=skeleton,
            point_scores=np.full(node_count, 0.9),
            score=0.85,
        )
        frames.append(
            sio.LabeledFrame(
                video=video, frame_idx=view_index - 1, instances=[instance]
            )
        )
    labels = sio.Labels(labeled_frames=frames, videos=[video], skeletons=[skeleton])
    labels.update()
    path = predictions_dir / f"scan_{scan_id}.{model}.root_{root_type}.slp"
    sio.save_slp(labels, str(path), embed=False)
    return path


def build_inputs(
    tmp_path: Path,
    rows=None,
    populate_images: bool = True,
    predictions: tuple = (("primary", 6), ("lateral", 4)),
    scans=SCANS,
) -> tuple[Path, Path, Path, Path]:
    """Stage a manifest, curated images, and predictions; return the four build paths."""
    manifest_csv = tmp_path / "sample_manifest.csv"
    rows = write_manifest(manifest_csv, rows if rows is not None else manifest_rows())

    images_dir = tmp_path / "package/images"
    images_dir.mkdir(parents=True)
    if populate_images:
        for row in rows:
            write_jpeg(images_dir / row["output_filename"])

    predictions_dir = tmp_path / "sleap_roots_traits_input"
    predictions_dir.mkdir(parents=True)
    for scan_id, *_ in scans:
        for root_type, node_count in predictions:
            write_predictions(
                predictions_dir, scan_id, root_type, node_count=node_count
            )

    output_dir = tmp_path / "package"
    return manifest_csv, images_dir, predictions_dir, output_dir


def build_projects(tmp_path: Path, **kwargs) -> Path:
    """Build the ``.slp`` projects alone over the standard fixture.

    Distinct from :func:`build_package_dir`, which runs the whole orchestrated
    assembly. The two were both named ``build`` in their own modules, which only became
    a collision once they moved here.
    """
    manifest_csv, images_dir, predictions_dir, output_dir = build_inputs(
        tmp_path, **kwargs
    )
    build_slp_project(manifest_csv, images_dir, predictions_dir, output_dir, METADATA)
    return output_dir


def primary(output_dir: Path) -> sio.Labels:
    """Load the built primary project."""
    return sio.load_slp(str(output_dir / "soybean_weep_primary_labels.v000.slp"))


# A hand-assembled package that passes validation, and the record describing it.
# Hand-assembled on purpose (see `test_labeling_validate`'s module docstring): the
# guarantee has to hold for a package built by an older tool or patched together by a
# person, so a validator that only ever sees its own builder's output tests agreement
# rather than correctness.

#: The fixture's two scans x three views.
FRAME_COUNT = 6

SKELETONS = {
    "primary": ("r1", "r2", "r3", "r4", "r5", "r6"),
    "lateral": ("r1", "r2", "r3", "r4"),
}


def package_record(**overrides) -> PackageRecord:
    """Build the record describing the fixture package, stating only the deviation."""
    fields = {
        "metadata": METADATA,
        "bloom_experiment_id": 10102496,
        "accessions": {"12742739": "A3244", "12742740": "WEEP-1-4"},
        "selection": SelectionParameters(
            seed=42, plants_per_group=5, views_per_plant=3, total_views=72
        ),
        "frame_count": FRAME_COUNT,
        "skeletons": SKELETONS,
        "version": "v000",
    }
    fields.update(overrides)
    return PackageRecord(**fields)


def complete_package(tmp_path, rows=None, record=None, scans=None):
    """Hand-assemble a package that passes: images, manifest, projects, metadata.

    Mirrors what a correct build produces without going through one, so a validation test
    that fails is a statement about the validator rather than about the builder.

    ``scans`` travels through to :func:`build_inputs` so a test supplying its own ``rows``
    can have predictions written for the scans those rows actually name.
    """
    manifest_csv, images_dir, predictions_dir, package_dir = build_inputs(
        tmp_path, rows=rows, **({} if scans is None else {"scans": scans})
    )
    build_slp_project(manifest_csv, images_dir, predictions_dir, package_dir, METADATA)
    shutil.copy2(manifest_csv, package_dir / "sample_manifest.csv")
    write_package_metadata(record or package_record(), package_dir)
    return package_dir


# A full Bloom download, manifest, and predictions, assembled end to end. The source
# images live where `scans.csv` says they do, so this exercises the real resolution
# rule rather than handing the assembler a pre-populated `images/`.

TOTAL_VIEWS = 72
ACCESSIONS = {"12742739": "A3244", "12742740": "WEEP-1-4"}
SELECTION = SelectionParameters(
    seed=42, plants_per_group=5, views_per_plant=3, total_views=TOTAL_VIEWS
)


def download(tmp_path: Path, rows=None, scans=SCANS):
    """Materialize a Bloom download, a manifest, and the pipeline's predictions.

    The source images live where ``scans.csv`` says they do — the copy step resolves
    against that file's directory (task 7.2) — so this exercises the real resolution rule
    rather than handing the assembler a pre-populated ``images/``.

    ``scans`` is a parameter so a test can supply rows spanning more scans than the
    standard fixture — a plant scanned at several ages, for instance — and still get a
    download and predictions covering them.
    """
    rows = list(rows if rows is not None else manifest_rows())
    download_dir = tmp_path / "WEEP_soybean/images_downloader_output"
    download_dir.mkdir(parents=True)

    with (download_dir / "scans.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["scan_id", "plant_qr_code", "scan_path"])
        for scan_id, qr, age, *_ in scans:
            scan_path = f"images/Wave1/Day{age}_20250101/{qr}"
            writer.writerow([scan_id, qr, scan_path])
            for view in range(1, TOTAL_VIEWS + 1):
                write_jpeg(download_dir / scan_path / f"{view}.jpg")

    manifest_csv = write_manifest(tmp_path / "sample_manifest.csv", rows) and (
        tmp_path / "sample_manifest.csv"
    )
    predictions_dir = tmp_path / "sleap_roots_traits_input"
    predictions_dir.mkdir()
    for scan_id, *_ in scans:
        write_predictions(predictions_dir, scan_id, "primary", node_count=6)
        write_predictions(predictions_dir, scan_id, "lateral", node_count=4)
    return manifest_csv, download_dir / "scans.csv", predictions_dir


def build_package_dir(
    tmp_path: Path, rows=None, output_dir=None, scans=SCANS, **overrides
):
    """Assemble a complete package over the standard fixture and return its directory."""
    manifest_csv, scans_csv, predictions_dir = download(
        tmp_path, rows=rows, scans=scans
    )
    kwargs = {
        "metadata": METADATA,
        "bloom_experiment_id": 10102496,
        "accessions": ACCESSIONS,
        "selection": SELECTION,
    }
    kwargs.update(overrides)
    return build_labeling_package(
        manifest_csv,
        scans_csv,
        predictions_dir,
        output_dir or tmp_path / "soybean-weep-labeling",
        **kwargs,
    )
