"""Enumerate the label corpus on a share and report what is in it.

Nobody has ever enumerated what labeled data exists: the registry holds 8 collections
against an expected 25-30, and ``skeletons.yaml`` cannot express the corpus it claims to
describe. This package walks a supplied root, reads the labels files themselves, and
emits evidence for a person to read.

Where it cannot determine something it says so and makes no determination. It has no
promotion, decision, adjudication or verdict concept, and reads no record of a human
judgement.
"""

from sleap_roots_training.inventory import discover, emit, gap, read, redact

__all__ = ["discover", "emit", "gap", "read", "redact"]
