"""Seed the wandb model registry from the committed selection matrix.

This subpackage turns the committed selection matrix
(:mod:`sleap_roots_training.registry.data.model_selection`) into one "card" per
**physical model** — a scalar ``root_type`` plus the (species, mode, age) selectors
that model was validated for — resolves each card's checksum-pinned model archive, and
publishes it as a wandb ``type="model"`` artifact with ``ModelCard`` selection metadata
under the configured alias (default ``production`` — the surface the
``sleap-roots-predict`` warm worker reads).
"""
