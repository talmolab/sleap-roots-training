"""Seed the production wandb model registry from the legacy model snapshot.

This subpackage turns the committed selection matrix
(:mod:`sleap_roots_training.registry.data.model_selection`) into per-species,
per-root-type "cards", resolves each card's legacy model directory, and publishes
it as a wandb ``type="model"`` artifact with ``ModelCard`` selection metadata and
the ``production`` alias — the surface the ``sleap-roots-predict`` warm worker reads.
"""
