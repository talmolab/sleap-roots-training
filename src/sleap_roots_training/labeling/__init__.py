"""Build the labeling packages that seed ``wandb-registry-sleap-roots-labels``.

This subpackage is the in-repo home of the ``/build-labeling-package`` workflow that
previously existed only in a personal vault repo (talmolab/sleap-roots-training#26): it
selects frames from a downloaded Bloom experiment, gathers their images under curated
names, and writes a self-contained SLEAP labeling package a labeler can open directly.

Two properties are load-bearing and are enforced here rather than assumed. Selection is
**deterministic**, and a frame's curated ``output_filename`` names the *view* rather than
its position in the selection — so the same view of the same plant is the same file at
every ``views_per_plant``, which is what makes the "re-derive and republish" path for
adding frames to an already-published scan safe to merge. (Widening ``plants_per_group``
also yields a superset; widening ``views_per_plant`` re-spaces the views and does not, on
purpose — see design.md "F3 revisited".) And the built ``.slp`` **embeds its images**, so a
package never depends on source scan paths that outlive it; six of the eight collections
published before this port carry ``repaired_from: "v0"`` because an external reference
broke and had to be hand-patched into a package after the fact.

The package layout and the validation entry point are what ``#10``'s ``publish-labels``
path checks before upload, mirroring how :mod:`sleap_roots_training.registry` publishes
model artifacts.
"""
