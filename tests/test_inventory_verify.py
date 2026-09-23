"""Digest verification against the per-file manifest entry.

Covers ``Requirement: Registry Digest Verification``. These are unit tests, deliberately
not ``integration``: ``ArtifactManifestEntry`` constructs offline and
``wandb.sdk.lib.hashutil`` computes the expected digest locally, so there is nothing to
gain from the network — and marking them ``integration`` would exclude them from CI and
leave the whole requirement unverified there.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import wandb
from wandb.sdk.artifacts.artifact_manifest_entry import ArtifactManifestEntry
from wandb.sdk.lib.hashutil import md5_string

from sleap_roots_training.inventory import verify


@pytest.fixture
def candidate(tmp_path):
    """A file on disk standing in for a labels file."""
    path = tmp_path / "labels.v001.slp"
    path.write_bytes(b"the labelled bytes")
    return path


def entry(path_name, digest, ref=None):
    """Build a manifest entry offline, the way wandb records one."""
    return ArtifactManifestEntry(path=path_name, digest=digest, size=1, ref=ref)


def test_no_network_is_needed_to_verify(monkeypatch, candidate):
    """The guard the repo's own registry tests use, for the same reason."""

    def _no_api(*_args, **_kwargs):
        raise AssertionError("verification must not construct a wandb.Api")

    monkeypatch.setattr(wandb, "Api", _no_api)
    matching = entry("labels.v001.slp", verify.content_digest(candidate))
    assert verify.classify(candidate, [matching]).status == verify.VERIFIED


def test_a_digest_match_is_reported_as_verified(candidate):
    """Scenario: A digest match is reported as verified."""
    matching = entry("labels.v001.slp", verify.content_digest(candidate))
    result = verify.classify(candidate, [matching])

    assert result.status == verify.VERIFIED
    assert result.local_digest == verify.content_digest(candidate)
    assert result.matches == 1


def test_a_digest_mismatch_names_both_digests(candidate):
    """Scenario: A digest mismatch is reported as a mismatch."""
    result = verify.classify(
        candidate, [entry("labels.v001.slp", "AAAAAAAAAAAAAAAA==")]
    )

    assert result.status == verify.MISMATCH
    assert result.recorded_digests == ("AAAAAAAAAAAAAAAA==",)
    assert result.local_digest and result.local_digest != "AAAAAAAAAAAAAAAA=="


def test_an_unregistered_candidate_is_not_a_failure(candidate):
    """Scenario: An unregistered file is not a failure."""
    result = verify.classify(candidate, [])

    assert result.status == verify.UNREGISTERED
    assert result.matches == 0


@pytest.mark.parametrize(
    "ref",
    [
        "s3://bucket/key/labels.v001.slp",
        "gs://bucket/labels.v001.slp",
        "https://example.invalid/labels.v001.slp",
        "azure://container/labels.v001.slp",
    ],
)
def test_a_reference_to_another_store_is_unverifiable_not_mismatching(candidate, ref):
    """Scenario: A reference digest that is not a content hash is unverifiable.

    Those handlers record the store's ETag, or the URI itself when checksumming is off.
    Neither is a hash of these bytes, so comparing them would manufacture a mismatch.
    """
    result = verify.classify(
        candidate, [entry("labels.v001.slp", "etag-not-a-md5", ref)]
    )

    assert result.status == verify.UNVERIFIABLE
    assert result.status != verify.MISMATCH
    assert "not a content hash" in (result.detail or "")


def test_a_file_reference_logged_without_checksumming_is_unverifiable(candidate):
    """The false mismatch that is invisible by shape.

    ``local_file_handler`` stores ``md5_string(path.resolve().as_uri())`` when
    ``checksum=False``. That is a well-formed base64 MD5, so an implementation keyed on
    "does this look like a hash" reports a confident mismatch for a file that is fine.
    """
    path_digest = md5_string(Path(candidate).resolve().as_uri())
    recorded = entry("labels.v001.slp", path_digest, f"file://{candidate.as_posix()}")

    result = verify.classify(candidate, [recorded])

    assert result.status == verify.UNVERIFIABLE
    assert "checksum=False" in (result.detail or "")
    assert path_digest != verify.content_digest(candidate)


def test_a_file_reference_with_checksumming_verifies_normally(candidate):
    """The discriminator is which digest matched, not whether a reference is set."""
    recorded = entry(
        "labels.v001.slp",
        verify.content_digest(candidate),
        f"file://{candidate.as_posix()}",
    )
    assert verify.classify(candidate, [recorded]).status == verify.VERIFIED


def test_several_matching_entries_are_all_reported_and_none_crowned(candidate):
    """The registered wheat superset exists in three directories at one version.

    The tool reports every match and picks no winner — choosing is a person's call.
    """
    digest = verify.content_digest(candidate)
    result = verify.classify(
        candidate,
        [
            entry("labels.v001.slp", digest),
            entry("labels.v001.slp", digest),
            entry("labels.v001.slp", digest),
        ],
    )

    assert result.matches == 3
    assert len(result.recorded_digests) == 3
    assert result.status == verify.VERIFIED


def test_an_unreadable_candidate_is_its_own_status(tmp_path):
    """A file that cannot be digested is not a mismatch."""
    missing = tmp_path / "gone.v001.slp"
    result = verify.classify(missing, [entry("gone.v001.slp", "AAAA==")])

    assert result.status == verify.UNREADABLE


def test_statuses_maps_many_candidates(tmp_path):
    """The shape `emit.build` consumes."""
    first = tmp_path / "a.v001.slp"
    first.write_bytes(b"a")
    second = tmp_path / "b.v001.slp"
    second.write_bytes(b"b")

    index = {"a.v001.slp": [entry("a.v001.slp", verify.content_digest(first))]}
    result = verify.statuses([first, second], index)

    assert result[first] == verify.VERIFIED
    assert result[second] == verify.UNREGISTERED
