"""The names Decision 3's package layout is made of.

Extracted during the blocking review of #40. These constants and the project-filename rule
lived in :mod:`sleap_roots_training.labeling.validate`, which inverted the dependency: the
modules that *write* a package — :mod:`package`, :mod:`build_package`,
:mod:`render_readme` — had to import the module that *checks* it in order to know where to
put things. That inversion is also how the duplication got in. ``project_filename``'s
docstring says the builder's naming is "stated once so validation looks for the same file
the builder wrote", while ``build_package`` re-typed the same f-string a few lines from its
own ``save_slp`` call — two copies of a rule that is load-bearing on both sides of the
package boundary.

Decision 3 makes the package directory a named contract. This module is that contract's
vocabulary, and it depends on nothing but :mod:`metadata`, so writers and checkers can both
import it without importing each other.
"""

from __future__ import annotations

from sleap_roots_training.labeling.metadata import PackageMetadata, PackageRecord

#: The manifest's name inside a package. Part of Decision 3's layout contract.
MANIFEST_FILENAME = "sample_manifest.csv"

#: The curated images directory. Task 5.5 keeps it in the package: the spec's one-to-one
#: requirement is checked against it, and ``output_filename`` resolves to nothing without it.
IMAGES_DIRNAME = "images"

#: The package's rendered README.
README_FILENAME = "README.md"

#: Files a file manager or an archive tool drops beside real content. They are not curated
#: images and must not be counted as any (blocking review of #40): packages ship via Box and
#: are opened on macOS, so one Finder visit adds a ``.DS_Store`` to ``images/`` — which used
#: to make ``labeling validate`` reject a perfectly good package, blaming the manifest for a
#: file the manifest has nothing to do with. ``tests/test_registry_models.py`` already
#: filters exactly these two names for the same reason.
SIDECAR_FILENAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


def is_sidecar(name: str) -> bool:
    """Return whether a filename is an operating-system sidecar rather than content.

    Args:
        name: The bare filename.

    Returns:
        ``True`` for a known sidecar name, or any AppleDouble ``._`` resource fork — which
        is what a macOS copy onto a non-native filesystem leaves beside every file.
    """
    return name in SIDECAR_FILENAMES or name.startswith("._")


def project_filename(metadata: PackageMetadata, root_type: str, version: str) -> str:
    """Return the ``.slp`` filename a package's root type is written under.

    The naming rule, stated once, so the builder writes and validation looks for the same
    name rather than a glob that would accept a near-miss. It follows the command doc's
    ``<crop>_<experiment>_<root_type>_labels.<version>.slp``.

    Takes the identity and the version rather than a whole :class:`PackageRecord`, because
    the builder names its files before it has a record to build — a frame count it has not
    finished computing is not a prerequisite for knowing what to call the output. Callers
    holding a record use :func:`project_filename_for`.

    Args:
        metadata: The package identity.
        root_type: The root type.
        version: The package version string.

    Returns:
        The filename, e.g. ``soybean_weep_primary_labels.v000.slp``.
    """
    return (
        f"{metadata.species}_{metadata.experiment}_{root_type}" f"_labels.{version}.slp"
    )


def project_filename_for(record: PackageRecord, root_type: str) -> str:
    """Return the ``.slp`` filename for a root type of an already-built package.

    Args:
        record: The package record.
        root_type: The root type.

    Returns:
        The filename.
    """
    return project_filename(record.metadata, root_type, record.version)
