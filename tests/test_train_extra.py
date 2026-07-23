"""Contract tests for the optional ``train`` backend dependency extra.

These tests are CI-safe: they only parse ``pyproject.toml`` (no network, no install), so
they run on every leg of the matrix and lock the Phase-1 pin declaration in place. They
guard the load-bearing properties of the ``[project.optional-dependencies].train`` extra:
release specifiers only (no VCS/URL/commit refs), the floor *and* the caps that block the
unverified v0.3.0 / sleap-io 0.8.0 mask line, and a lean base install.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
BACKENDS = ("sleap-nn", "sleap-io", "torch")


def _load_pyproject() -> dict:
    with open(PYPROJECT, "rb") as fh:  # tomllib requires binary mode
        return tomllib.load(fh)


def _extract_train_extra(project: dict) -> list[str]:
    train = project.get("optional-dependencies", {}).get("train")
    assert train, (
        "pyproject.toml [project.optional-dependencies].train must exist and be non-empty "
        "(the Phase-1 sleap-nn backend extra)"
    )
    assert isinstance(train, list), (
        "the `train` extra must be a TOML array of requirement strings, got "
        f"{type(train).__name__}"
    )
    for entry in train:
        assert isinstance(entry, str), (
            "each `train` entry must be a requirement string, got "
            f"{type(entry).__name__}: {entry!r}"
        )
    return train


def _train_extra() -> list[str]:
    return _extract_train_extra(_load_pyproject()["project"])


def _requirements() -> list[Requirement]:
    return [Requirement(entry) for entry in _train_extra()]


def _specifier_for(name: str):
    target = canonicalize_name(name)
    for req in _requirements():
        if canonicalize_name(req.name) == target:
            return req.specifier
    raise AssertionError(f"{name} not found in the train extra")


def test_train_extra_declares_full_backend_with_release_specifiers():
    reqs = _requirements()
    names = {canonicalize_name(req.name) for req in reqs}
    for backend in BACKENDS:
        assert (
            canonicalize_name(backend) in names
        ), f"{backend} missing from train extra"
    for req in reqs:
        assert req.url is None, f"{req.name} uses a direct URL/VCS reference: {req}"


def test_sleap_nn_pinned_to_released_v020_line():
    spec = _specifier_for("sleap-nn")
    assert spec.contains(Version("0.2.0")), f"sleap-nn must admit 0.2.0: {spec}"
    assert not spec.contains(Version("0.1.0")), f"sleap-nn must reject 0.1.0: {spec}"


def test_version_caps_exclude_unverified_mask_line():
    nn = _specifier_for("sleap-nn")
    io = _specifier_for("sleap-io")
    assert not nn.contains(
        Version("0.3.0")
    ), f"sleap-nn must reject 0.3.0 (mask line): {nn}"
    assert io.contains(Version("0.7.1")), f"sleap-io must admit 0.7.1: {io}"
    assert not io.contains(
        Version("0.8.0")
    ), f"sleap-io must reject 0.8.0 (mask line): {io}"


def test_base_install_stays_lean():
    base = {
        canonicalize_name(Requirement(entry).name)
        for entry in _load_pyproject()["project"]["dependencies"]
    }
    for backend in BACKENDS:
        assert (
            canonicalize_name(backend) not in base
        ), f"{backend} must not be a base dependency (train extra only)"


def test_torch_has_release_floor():
    # torch is intentionally floor-only (no upper cap); still lock the floor so an accidental
    # edit to a bare, unpinned `torch` fails here the way the sleap-nn/sleap-io caps do.
    spec = _specifier_for("torch")
    assert spec.contains(Version("2.5.0")), f"torch must admit 2.5.0: {spec}"
    assert not spec.contains(
        Version("2.4.0")
    ), f"torch must keep a >=2.5 floor (not left unpinned): {spec}"


def test_specifier_for_unknown_name_raises():
    with pytest.raises(AssertionError):
        _specifier_for("definitely-not-in-the-extra")


def test_extract_train_extra_rejects_non_list():
    # A bare string (forgotten [...] brackets) must fail clearly, not iterate char-by-char.
    with pytest.raises(AssertionError):
        _extract_train_extra(
            {"optional-dependencies": {"train": "sleap-nn>=0.2.0,<0.3.0"}}
        )


def test_extract_train_extra_rejects_non_string_entry():
    # A non-string entry (e.g. an accidental inline table) must fail clearly, not TypeError.
    with pytest.raises(AssertionError):
        _extract_train_extra(
            {"optional-dependencies": {"train": [{"name": "sleap-nn"}]}}
        )
