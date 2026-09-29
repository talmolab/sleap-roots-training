"""Training task 6.3: retire the 13 flat collections by unlinking their `production` link.

Decision 0.4 ("retire them. Approved"), gated on the upgraded predict being deployed (C2,
predict#34). For each collection in the 6.0(a) baseline this fetches the registry link at
`<registry>/<collection>:production`, asserts `is_link`, and calls `unlink()` — the drop
rehearsed on the canary in 6.0(b). It never calls `save()` on anything (verified failure mode:
on the source artifact it aliases the source collection and reports success), and it never
deletes a collection (not recoverable).

Phases, all logged per collection:
  1. Pre-flight (always, read-only): every one of the 13 must resolve to a link whose version
     equals the baseline's, carries `production`, and whose source artifact resolves. Any
     mismatch stops before anything is touched. The captured source qualified names and
     digests are the rollback anchor, so they are written to the record first.
  2. Retire (only with --execute): per collection, re-fetch the link, assert `is_link`,
     `unlink()`, then confirm with a fresh Api that `:production` no longer resolves and the
     source still does. Stops on the first failure.
  3. Rollback (only with --rollback --execute): for each named collection (or all 13),
     `Artifact.link(<registry target>, aliases=["production"])` on the recorded source
     version — the 6.0(e) rehearsal.

Default is a dry run (phase 1 only). Single operator: announce the window first.
Run from the sleap-roots-training worktree:
    uv run python <this> [--execute] [--rollback [COLLECTION ...]]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import wandb

from sleap_roots_training.registry.config import resolve_registry_config

HERE = Path(__file__).parent
BASELINE = HERE / "2026-09-22-pre-reseed-baseline.json"
OUT = HERE / "2026-09-29-retire-flat-collections-record.json"


def now():
    """UTC timestamp for the record."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolves(path):
    """Fresh-Api read of ``path``; return the artifact, or the error text if it fails."""
    try:
        return wandb.Api().artifact(path, type="model"), None
    except Exception as e:  # wandb raises CommError/ValueError depending on version
        return None, f"{type(e).__name__}: {e}"


def preflight(registry, entry):
    """Read one collection's production link and check it against the baseline."""
    link, err = resolves(f"{registry}/{entry['collection']}:production")
    if link is None:
        return None, f":production does not resolve ({err})"
    state = {
        "collection": entry["collection"],
        "version": link.version,
        "aliases": sorted(link.aliases),
        "digest": link.digest,
        "is_link": link.is_link,
        "source_qualified_name": link.source_qualified_name,
    }
    if not link.is_link:
        return state, "not the registry link"
    if link.version != entry["version"]:
        return state, f"version {link.version} != baseline {entry['version']}"
    if "production" not in link.aliases:
        return state, "link does not carry production"
    source, err = resolves(link.source_qualified_name)
    if source is None:
        return state, f"source does not resolve ({err})"
    if source.digest != link.digest:
        return state, f"source digest {source.digest} != link digest {link.digest}"
    return state, None


def write(record):
    """Persist the record after every step, so a stop leaves an accurate trail."""
    OUT.write_text(json.dumps(record, indent=2) + "\n")


def retire(registry, state):
    """Unlink one collection's production link; return an error string or None."""
    link, err = resolves(f"{registry}/{state['collection']}:production")
    if link is None:
        return f"re-fetch failed ({err})"
    if not link.is_link:
        return "refusing: re-fetched artifact is not the registry link"
    if link.source_qualified_name != state["source_qualified_name"]:
        return "refusing: link source changed since pre-flight"
    link.unlink()
    gone, _ = resolves(f"{registry}/{state['collection']}:production")
    if gone is not None:
        return f":production still resolves after unlink ({gone.version})"
    source, err = resolves(state["source_qualified_name"])
    if source is None:
        return f"source no longer resolves after unlink ({err})"
    return None


def rollback(registry, state):
    """Re-link the recorded source version with production; return an error or None."""
    source, err = resolves(state["source_qualified_name"])
    if source is None:
        return f"source does not resolve ({err})"
    if source.digest != state["digest"]:
        return f"source digest {source.digest} != recorded {state['digest']}"
    source.link(f"{registry}/{state['collection']}", aliases=["production"])
    link, err = resolves(f"{registry}/{state['collection']}:production")
    if link is None:
        return f":production does not resolve after link ({err})"
    if not link.is_link or link.digest != state["digest"]:
        return f"restored link mismatch (is_link={link.is_link}, digest={link.digest})"
    print(f"  restored {link.version} aliases={sorted(link.aliases)}")
    return None


def main():
    """Pre-flight, then retire (``--execute``) or roll back (``--rollback --execute``)."""
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true", help="write to W&B")
    p.add_argument("--rollback", nargs="*", metavar="COLLECTION")
    args = p.parse_args()
    baseline = json.loads(BASELINE.read_text())
    registry = resolve_registry_config().registry_project()
    assert registry == baseline["registry"], f"{registry} != {baseline['registry']}"
    assert baseline["count"] == len(baseline["collections"]) == 13

    if args.rollback is not None:
        record = json.loads(OUT.read_text())
        states = {s["collection"]: s for s in record["preflight"]}
        names = args.rollback or sorted(states)
        for name in names:
            print(f"rollback {name} <- {states[name]['source_qualified_name']}")
            if not args.execute:
                continue
            err = rollback(registry, states[name])
            record.setdefault("rollback", []).append(
                {"collection": name, "utc": now(), "error": err}
            )
            write(record)
            if err:
                print(f"  FAIL: {err}")
                return 1
        return 0

    record = {"started_utc": now(), "registry": registry, "execute": args.execute}
    states, failed = [], False
    for entry in baseline["collections"]:
        state, err = preflight(registry, entry)
        print(f"preflight {entry['collection']}: {'FAIL: ' + err if err else 'ok'}")
        if state:
            print(
                f"  {state['version']} {state['aliases']} <- {state['source_qualified_name']}"
            )
        states.append({**(state or {"collection": entry["collection"]}), "error": err})
        failed = failed or bool(err)
    record["preflight"] = states
    write(record)
    if failed:
        print("STOP: pre-flight failed; nothing was touched.")
        return 1
    if not args.execute:
        print(
            f"dry run: would unlink {len(states)} production links; nothing was touched."
        )
        return 0

    record["retired"] = []
    for state in states:
        err = retire(registry, state)
        record["retired"].append(
            {"collection": state["collection"], "utc": now(), "error": err}
        )
        write(record)
        print(f"retire {state['collection']}: {'FAIL: ' + err if err else 'unlinked'}")
        if err:
            print("STOP on first failure; see the record for what was retired.")
            return 1
    record["finished_utc"] = now()
    write(record)
    print(f"retired {len(states)} of {len(states)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
