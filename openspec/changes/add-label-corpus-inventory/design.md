# Design: label-corpus inventory

## Context

Full background, the verified findings this rests on, and the resolved decisions are in
[`docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md`](../../../docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md).
This file carries only the decisions that shape the spec deltas.

Three sources describe one corpus and none has been reconciled against the others. The
registry holds 8 collections against an expected 25–30; `skeletons.yaml` cannot express
two of the eight; and `#49` records the share paths as unusable because it reads the repair
version rather than the original.

## Decisions

- **D1. ADDED, not MODIFIED.** No live spec covers label provenance. `label-registry`
  belongs to in-flight `#49` and is not on `main`, so a MODIFIED block would re-paste a
  spec that does not exist yet and permanently bake a base that was never merged.
  Precedent: `add-tf-reference-fixtures` added `tf-reference` the same way. This also makes
  the change order-independent with respect to `#49`.
- **D2. A capability, not a script.** The corpus grows, so a one-time pass is stale the
  day a further collection is published. Idempotence is specified normatively so the
  artifacts can be regenerated and diffed instead of hand-audited — and so the eventual
  ninth collection is a re-run, not a rediscovery.
- **D3. Two derivations, reconciled — not one source preferred.** Filenames give a guess
  at species (a folder named `SLEAP_wheat`) and a proxy for plants (deduped QR codes);
  Bloom gives `species_name` and `plant_id` from the system of record. Computing both and
  requiring agreement is what makes a reported value evidence rather than an assumption.
  Preferring Bloom silently would produce the same numbers with none of the assurance, and
  would hide the cases worth looking at.
- **D4. Aggregates from agreed rows only, and exceptions gate emission.** A total computed
  across verified and unverified rows looks authoritative and is not. "170 scans, 12
  unresolved" forces a decision; "170 scans" with a footnote does not. The gate is a
  requirement rather than a report because a report is skimmable.
- **D5. Unresolved is a state, not an error.** Legacy scans may predate Bloom ingestion or
  have been re-keyed. A run that aborts on the first one cannot inventory the corpus that
  motivated it, so the classification carries three states and only digest failure is
  fatal — and then only to its own collection.
- **D6. Provenance from the original version; images-embedded from the repair.** Six
  collections carry a re-embed repair that restores trainability and, in doing so, drops
  the species tags and records a temporary path. Both versions are needed and they answer
  different questions, so the spec names which value comes from which rather than treating
  "the artifact" as one thing.
- **D7. Read-only is specified as an effect, not a call site.** The credentials can write
  and Bloom's own CLI exposes `ingest`, so nothing in the environment prevents a later edit
  from mutating production data. Requiring injected clients makes an unintended write fail
  a test instead of surfacing in production. This mirrors `registry/publish.py`'s existing
  `api=None` seam rather than inventing a pattern.
- **D8. Structural discovery over a maintained list.** A list encodes what is already
  remembered, which is precisely what an audit exists to get past. A folder qualifies when
  it holds a top-level labels file; split directories are excluded because a split
  describes a training run and reporting its frame count as the corpus's would be wrong in
  the direction that looks plausible.
- **D9. Diff the skeleton table, never read from it.** `skeletons.yaml` is advisory and
  says so; its header states that verifying against these collections is what flips its
  `verified:` flags. Reading it to fill a value would launder an unverified assertion into
  an inventory. The `mode` gap is reported as a keying gap rather than a per-row
  contradiction because no row edit fixes a missing key.
- **D10. New module tree, away from in-flight work.** `inventory/` rather than `registry/`
  or `labeling/`, both of which have in-flight changes (`labeling-package` ×2, plus `#49`).
  Keeps this change conflict-free on merge in any order.

## Alternatives considered

- **Read only from the registry, skip the share.** Reproducible for anyone with an API
  key, and removes the drive-mapping question. Rejected: it costs ~2 GB of downloads and
  discards the share as an independent cross-check, which is the thing that makes the
  digest gate meaningful rather than circular.
- **Trust matching path and size.** Cheapest, no downloads. Rejected on the explicit
  standard set for this work — a same-size file with different content would pass, and the
  output is permanent provenance.
- **Derive species from the collection name.** Free, and right seven times out of eight.
  Rejected: the eighth is the entire question, and a name-derived answer confirms names
  using names.
- **One change covering labels and models.** Shares the share walk. Rejected: repo
  convention is one change per PR, the two have different consumers (`#49` versus `#3` and
  the roadmap), and `#49` is a live example of the cost of a large one.

## Risks

- **Production credentials.** The capability reads prod Bloom. Read paths only, injected
  clients, and a spec requirement that a write fails a test. Worth a second reader on the
  client module before the first run.
- **Bloom coverage of legacy scans.** Unknown until run. Handled by D5 rather than
  assumed away — if coverage is poor the output says so per scan instead of producing
  confident aggregates from a thin join.
- **The gate could stall the run.** If most rows are unresolved, D4's gate means little
  is emitted. That is the correct failure: it reports that the corpus cannot yet be
  verified, rather than that it has been.
- **Scope pressure.** Everything this finds implies a fix — the `mode` key, missing species
  rows, `#3`, tip models. The non-goals list exists to hold that line, and each is a
  separate change.
