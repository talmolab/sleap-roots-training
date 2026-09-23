"""Compare a candidate against the per-file digest the registry recorded for it.

The comparison is against ``ArtifactManifestEntry.digest`` — the *per-file* digest —
never ``Artifact.digest``, which is computed over the manifest and would never match a
file. ``Artifact.manifest`` fetches that metadata without downloading artifact files, so
a whole scan costs no transfers.

A reference entry's digest is not always a content hash, and that is where a naive
implementation reports a confident false mismatch:

* ``add_reference`` against S3, GCS, Azure or HTTP stores that backend's ETag, or the URI
  itself when checksumming is off.
* A ``file://`` reference logged with ``checksum=False`` stores an MD5 **of the resolved
  URI**, which is a well-formed base64 MD5 and indistinguishable by shape from a content
  hash.

So the discriminator cannot be "is a reference set" or "does this look like an MD5". This
module computes both the content digest and the URI digest and says *which* it matched.
Unverifiable is a separate finding from mismatching, and neither is a failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence
from urllib.parse import urlparse

from wandb.sdk.lib.hashutil import md5_file_b64, md5_string

#: The candidate's bytes match the digest the registry recorded.
VERIFIED = "verified"

#: The digests differ, and the recorded one really is a content hash.
MISMATCH = "mismatch"

#: No registry artifact holds an entry for this candidate. Not a failure: unregistered
#: files outnumber registered ones, which is the finding the inventory exists to make.
UNREGISTERED = "unregistered"

#: An entry exists, but its digest is not a content hash, so it cannot be checked.
UNVERIFIABLE = "unverifiable"

#: The candidate could not be read to digest it.
UNREADABLE = "unreadable"


@dataclass(frozen=True)
class Verification:
    """The outcome of checking one candidate against the registry.

    Attributes:
        status: One of :data:`VERIFIED`, :data:`MISMATCH`, :data:`UNREGISTERED`,
            :data:`UNVERIFIABLE` or :data:`UNREADABLE`.
        local_digest: The candidate's own base64 MD5, if it could be read.
        recorded_digests: Every digest the matching entries carry, in match order.
        matches: How many manifest entries matched the candidate's filename. More than
            one is reported rather than resolved — none is crowned.
        detail: Why, for the statuses that need a reason.
    """

    status: str
    local_digest: Optional[str] = None
    recorded_digests: tuple[str, ...] = ()
    matches: int = 0
    detail: Optional[str] = None


def content_digest(path: Path) -> str:
    """Return a file's base64 MD5, the way wandb computes it for an upload.

    Size is irrelevant: the helper mmaps the whole file and falls back to chunked
    reading only on ``OSError``, so chunking is an I/O detail and not a different digest.

    Args:
        path: The file to digest.

    Returns:
        The base64-encoded MD5 of the whole file.
    """
    return md5_file_b64(str(path))


def _uri_digest(path: Path) -> Optional[str]:
    """Return the digest a ``file://`` reference logged with ``checksum=False`` carries."""
    try:
        return md5_string(Path(path).resolve().as_uri())
    except (ValueError, OSError):
        return None


def _reference_scheme(entry: object) -> Optional[str]:
    """Return the URI scheme of an entry's reference, or ``None`` for an upload."""
    ref = getattr(entry, "ref", None)
    if not ref:
        return None
    return (urlparse(str(ref)).scheme or "").lower() or None


def classify(path: Path, entries: Sequence[object]) -> Verification:
    """Classify one candidate against the manifest entries that matched its filename.

    Args:
        path: The candidate on disk.
        entries: Manifest entries whose path basename equals the candidate's filename,
            across every registry artifact searched. Empty means unregistered.

    Returns:
        The verification outcome.
    """
    if not entries:
        return Verification(status=UNREGISTERED)

    recorded = tuple(str(getattr(entry, "digest", "")) for entry in entries)
    try:
        local = content_digest(path)
    except (OSError, ValueError) as error:
        return Verification(
            status=UNREADABLE,
            recorded_digests=recorded,
            matches=len(entries),
            detail=str(error),
        )

    if local in recorded:
        return Verification(
            status=VERIFIED,
            local_digest=local,
            recorded_digests=recorded,
            matches=len(entries),
        )

    uri = _uri_digest(path)
    for entry, digest in zip(entries, recorded):
        scheme = _reference_scheme(entry)
        if scheme is not None and scheme != "file":
            return Verification(
                status=UNVERIFIABLE,
                local_digest=local,
                recorded_digests=recorded,
                matches=len(entries),
                detail=(
                    f"reference to {scheme}: the digest is that store's ETag or the "
                    "URI, not a content hash"
                ),
            )
        if uri is not None and digest == uri:
            return Verification(
                status=UNVERIFIABLE,
                local_digest=local,
                recorded_digests=recorded,
                matches=len(entries),
                detail=(
                    "file:// reference logged with checksum=False: the digest is an "
                    "MD5 of the path, not of the contents"
                ),
            )

    return Verification(
        status=MISMATCH,
        local_digest=local,
        recorded_digests=recorded,
        matches=len(entries),
    )


def statuses(
    paths: Iterable[Path], index: dict[str, Sequence[object]]
) -> dict[Path, str]:
    """Classify many candidates against an index of manifest entries.

    Args:
        paths: Candidate paths.
        index: Filename to the manifest entries carrying that filename.

    Returns:
        Each path mapped to its status string, for the emitted table.
    """
    return {
        Path(path): classify(Path(path), index.get(Path(path).name, ())).status
        for path in paths
    }


def fetch_index(project: Optional[str] = None) -> dict[str, list[object]]:
    """Fetch every labels-registry manifest entry, keyed by filename.

    ``Artifact.manifest`` reads metadata over GraphQL plus one manifest blob; no artifact
    files are downloaded, so indexing the whole registry costs no transfers.

    Args:
        project: Registry path to index; defaults to the labels registry for the
            configured entity.

    Returns:
        Filename to the manifest entries carrying it. A filename may map to several
        entries — the registered wheat superset exists in three directories at one
        version — and every one of them is kept.

    Raises:
        RuntimeError: If the registry cannot be reached or no credential resolves.
    """
    import wandb

    from sleap_roots_training.registry.config import resolve_registry_config

    try:
        cfg = resolve_registry_config()
        path = project or f"{cfg.entity}-org/wandb-registry-sleap-roots-labels"
        api = wandb.Api()
        index: dict[str, list[object]] = {}
        for collection in api.artifact_collections(path, "model"):
            artifact = api.artifact(f"{path}/{collection.name}:latest")
            for entry_path, manifest_entry in artifact.manifest.entries.items():
                index.setdefault(Path(entry_path).name, []).append(manifest_entry)
        return index
    except Exception as error:  # noqa: BLE001 - surfaced as a clean CLI message
        raise RuntimeError(f"could not read the labels registry: {error}") from error
