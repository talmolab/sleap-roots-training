"""Training task 6.5 probe: does re-logging byte-identical weights with NEW metadata refresh
the production-aliased artifact's metadata?

Mirrors `publish_card` exactly (same Artifact name/type, same add_dir of the same resolved
model dir, log_artifact -> wait -> link_artifact with the production alias), except that the
metadata carries ONE extra top-level key, `probe_6_5`, which every consumer ignores
(contracts `ModelCard` is extra="ignore"; training's shape test only looks at `selectors` and
the four legacy keys). Selection is therefore unchanged whatever happens.

Phase 1 (observe) reports: the logged version (new vN, or the existing v0 = no-op), the
digest, and whether the SERVER's view of `:production` carries `probe_6_5`.
Phase 2 (restore) runs only with --restore: sets the production link's metadata back to the
exact pre-probe metadata via `Artifact.save()` (the requirement's remedy path) and re-reads
the server's view to confirm `probe_6_5` is gone and the metadata equals the snapshot.
Run from the sleap-roots-training worktree: `uv run python <this> [--restore]`.
"""

import argparse
import json
import sys
from pathlib import Path

import wandb

from sleap_roots_training.registry import cards as cards_mod
from sleap_roots_training.registry import chooser, publish
from sleap_roots_training.registry.config import resolve_registry_config

COLLECTION = "rice-younger-primary-230104_182346.multi_instance.n-720"
MODELS_ROOT = Path("C:/repos/models-downloader/tests/data/models_downloader_input/20250204_models")
PROBE_KEY = "probe_6_5"
OUT = Path(__file__).with_name("probe_6_5_record.json")


def server_view(api, target):
    """Fresh read of the production-aliased link (new Api: no process cache)."""
    a = api.artifact(f"{target}:production", type="model")
    return {"version": a.version, "digest": a.digest, "aliases": list(a.aliases),
            "is_link": a.is_link, "source": a.source_qualified_name,
            "metadata": dict(a.metadata)}, a


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--restore", action="store_true")
    args = p.parse_args()
    cfg = resolve_registry_config()
    target = f"{cfg.registry_project()}/{COLLECTION}"
    record = json.loads(OUT.read_text()) if OUT.exists() else {}

    if args.restore:
        before = record["before"]["metadata"]
        _, link = server_view(wandb.Api(), target)
        assert link.is_link, "refusing: not the registry link"
        link.metadata = before
        link.save()
        after, _ = server_view(wandb.Api(), target)
        record["restored"] = after
        OUT.write_text(json.dumps(record, indent=2))
        ok = PROBE_KEY not in after["metadata"] and after["metadata"] == before
        print(json.dumps({"restored_equals_snapshot": ok, "probe_key_present": PROBE_KEY in after["metadata"]}, indent=2))
        return 0 if ok else 1

    (card,) = [c for c in cards_mod.expand_rows_to_cards(chooser.load_selection_matrix().rows)
               if cards_mod.collection_id(c) == COLLECTION]
    matrix = chooser.load_selection_matrix()
    ((_, model_dir),) = publish.resolve_all([card], MODELS_ROOT, matrix.checksums)
    before, _ = server_view(wandb.Api(), target)
    record = {"collection": COLLECTION, "before": before}
    OUT.write_text(json.dumps(record, indent=2))

    metadata = cards_mod.card_to_metadata(card)
    assert {k: v for k, v in before["metadata"].items()} == metadata, "live metadata != builder metadata; stop"
    probed = {**metadata, PROBE_KEY: "2026-09-24 metadata-refresh probe (training 6.5)"}

    run = wandb.init(project="migrate-model-card-selectors", job_type="probe_6_5")
    art = wandb.Artifact(name=COLLECTION, type="model", metadata=probed)
    art.add_dir(str(model_dir))
    logged = run.log_artifact(art)
    logged.wait()
    linked = run.link_artifact(logged, target, aliases=[cfg.alias])
    run.finish()

    after, _ = server_view(wandb.Api(), target)
    record.update(logged_version=logged.version, logged_digest=logged.digest, after=after,
                  probe_visible_on_production=PROBE_KEY in after["metadata"],
                  new_version_created=after["version"] != before["version"])
    OUT.write_text(json.dumps(record, indent=2))
    print(json.dumps({k: record[k] for k in ("logged_version", "logged_digest",
                      "new_version_created", "probe_visible_on_production")}, indent=2))
    print("before:", before["version"], before["digest"], "| after:", after["version"], after["digest"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
