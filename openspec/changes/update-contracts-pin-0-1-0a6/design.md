## Context

`sleap-roots-training` pins `sleap-roots-contracts==0.1.0a3` as a runtime dependency. It imports
exactly one name from it — `ModelCard` — in tests, and records the installed contract version in
seed-run lineage (`registry/lineage.py`). The producer writes flat `ModelCard` metadata onto wandb
model artifacts; `sleap-roots-predict` is the consumer that matches on it.

`chooser.MODE_VOCAB` has **two** consumers in this package, not one:

1. `chooser.load_selection_matrix` — validates each row of the committed `model_selection.yaml`,
   which is repo-owned data that only ever reaches wandb artifact metadata.
2. `config._validate_experiment` (`config.py:200`, added by Tier 1 / #20) — validates
   `experiment.mode` in a **hand-written user training config**.

The second is the consequential one: after this change, the contract governs a user-facing config
field, not merely published metadata. That is intended (one vocabulary, one owner), but it means a
future narrowing of `Mode` upstream would reject configs people have already written, not just
matrix rows we control. Recorded here so the next bump review knows to look at both.

`0.1.0a6` is on PyPI. This design records the delta review that justifies taking the bump as a
non-migration, and the two decisions the change turns on.

## a3 → a6 delta review

Only **one already-released contract** changed across the three releases: `ModelCard`. Everything
else is new surface this repo does not import.

| Release | Change | Impact here |
| --- | --- | --- |
| `0.1.0a4` | `resolve_params` oracle promoted in; sentinel hardening; schema `$id` restamp | **None** — not imported; no vendored schema |
| `0.1.0a5` | `PredictionArtifact` / `PredictionManifest` added; schema `$id` restamp | **None** — consumer-side (`predict` → `bloomctl`) |
| `0.1.0a6` | `LabelCard` + `Mode` added | **None yet** — `LabelCard` is #10 |
| `0.1.0a6` | **BREAKING (validation):** `ModelCard.mode` is `Mode`, not free `str`; matched exactly, no case/whitespace normalization | **The substance of this change** (below) |
| `0.1.0a6` | **BREAKING (validation):** `age_min`/`age_max` reject `bool` / `numpy.bool_` | **None** — ages come from `_parse_age_window` over a YAML comma-list and are already `int` |

The `ModelCard.mode` tightening is compatible with every value this repo produces:

- Contract `Mode` = `Literal["cylinder", "multiplant cylinder", "plate"]`.
- `chooser.MODE_VOCAB` = `frozenset({"cylinder", "multiplant cylinder", "plate"})`.

Set-identical. The committed `model_selection.yaml` uses only `cylinder` (6 rows) and
`multiplant cylinder` (1 row) — both in vocabulary, with the space preserved rather than the
hyphenated collection-id slug. The `cyl` shorthand the contract changelog calls out belongs to the
**label** registry, which this repo does not yet write.

So there is no RED test to write for a behavior change, because there is no behavior change. The
tests this change adds are regression guards on an invariant that currently holds by coincidence of
two lists agreeing.

## Goals / Non-Goals

- **Goals:** one source of truth for the mode vocabulary; the pin advanced to `0.1.0a6`; the
  producer/consumer agreement asserted by a test rather than by two lists happening to match.
- **Non-Goals:** adopting `LabelCard` (#10); changing the selection matrix; changing what metadata
  the producer writes.

## Decisions

**Decision: keep the exact `==` pin rather than relaxing to a compatible range.**
The archived `seed-production-model-registry` design chose `==` deliberately — this is a schema
contract that must byte-match a consumer, and the library is in `0.1.0a*`, where a patch-level
release has already shipped a breaking validation tightening (`0.1.0a6` itself is the proof). A
range would let a future alpha narrow `Mode` underneath a green lockfile. Bumping deliberately, and
reviewing the delta each time as above, is the intended cost.
*Alternatives considered:* `>=0.1.0a6,<0.2` — rejected; it converts a reviewed bump into an
unreviewed one, on a dependency whose whole job is agreement with another repo.

**Decision: derive `MODE_VOCAB` from the contract with `get_args(Mode)`; keep the name.**
`Mode` is a `Literal` alias, so `frozenset(get_args(Mode))` is the vocabulary as a set. Keeping the
`MODE_VOCAB` name preserves the loader's existing error message (`expected one of {sorted(...)}`)
and any importer, so the diff is confined to where the values come from.
*Alternatives considered:* (a) validating the row through `ModelCard` itself — rejected, it would
require inventing placeholder `registry_id`/`version`/`weights_checksum` at load time and would
report a pydantic error where the loader promises a row-numbered one; (b) annotating
`SelectionRow.mode` as `Mode` — rejected, the dataclass is not validated at runtime, so the
annotation would document the constraint without enforcing it, and the loader check would still be
the real gate.

**Decision: modes are matched exactly at every surface — no case or whitespace normalization.**
This was already the behavior (`MODE_VOCAB` is an exact-match set; `_check_vocab` uses `in`), so
this change neither introduces nor removes it. It is promoted to a stated decision here because the
contract now owns the vocabulary and the question is live: `Cylinder` in a hand-written
`experiment.mode` is rejected, and stays rejected. The contract's `ModelCard.mode` does not
normalize either — upstream is explicit that canonicalizing a *requested* mode is `resolve_params`'
job on the consumer side, not the card's. So accepting `Cylinder` at `validate` time **without**
canonicalizing it would be strictly worse than rejecting it: the value would flow onward and fail at
publish or silently match no model, instead of failing in front of the person who typed it.
*Alternatives considered:* (a) normalize-then-check in `_validate_experiment`, writing the canonical
value back — a defensible kindness for a hand-typed field, but it is a behavior change to the
`validate` CLI, belongs to the config capability rather than `model-registry`, and that capability's
spec is still unarchived in `add-config-schema`; deferred rather than rejected. (b) accept cased
input without canonicalizing — rejected outright, per above.

**Decision: `SPECIES_VOCAB` stays local.**
The contract models `RootType` and `Mode` but no species vocabulary — species is a free `str` on
`ModelCard`. Nothing to collapse into; inventing a contract-side species enum is out of scope and
belongs upstream if it is wanted.

## Risks / Trade-offs

- **A future contract release narrows `Mode` and silently invalidates a matrix row.** → The added
  test asserts every mode in the *committed matrix* validates against the real `ModelCard`, so the
  narrowing fails in this repo's CI at bump time, which is the moment it can still be handled.
- **A future contract release widens `Mode` with a value the consumer cannot match.** → Widening is
  permissive, so nothing fails here; it is also the safe direction (the loader accepts more, the
  matrix still contains only what we ship). Accepted.
- **The exact pin means this repo must be bumped by hand for every contract release.** → Accepted;
  that is the point of the first decision above.
- **A future contract release changes `Mode` from a `Literal` to something else.** → `get_args()`
  returns `()` for a non-parameterized type *without raising*, so `MODE_VOCAB` would degrade to the
  empty set — "no mode is valid" — and the failure would surface far from its cause, as every real
  mode being rejected. `chooser` therefore raises at import when the derived vocabulary is empty,
  naming what changed. Note the two tests named for this invariant cannot catch it on their own:
  `test_mode_vocab_is_the_contract_vocabulary_unforked` re-derives the set exactly as production
  does, so both sides degrade together and it still passes, and a `MODE_VOCAB`-parametrized test
  degrades to a *skip*, not a failure. Both now carry an independent literal witness alongside the
  re-derivation.
- **A future contract narrowing invalidates hand-written configs, not just matrix rows.**
  → `MODE_VOCAB` also backs `validate`'s check on `experiment.mode`, so the contract now governs a
  user-authoring surface. The committed matrix and `examples/` were already guarded; `docs/training.md`
  is the third authoring surface and nothing read it, so a test now asserts every `mode:` the guide
  tells users to write stays contract-valid. Flagged in the CHANGELOG for downstream config authors.
- **Eager import cost.** `from sleap_roots_contracts import Mode` at `chooser` module scope is the
  first place this package actually imports the contract (and transitively pydantic) — `lineage.py`
  only read its version via `importlib.metadata`. Since `config.py` imports `chooser` eagerly, this
  lands on the CLI's import path: measured here at ~183 ms added to a bare-interpreter start (~199 ms
  vs ~16 ms), ~124 ms of which is the contract/pydantic import itself. Accepted — a one-time
  cold-start cost, immaterial next to training runtime — but it does cut against this repo's lazy-
  import convention for heavy dependencies (`wandb`, `sleap-nn`), so it is recorded rather than
  silent. Deferring it would mean making `MODE_VOCAB` a function, which trades a public constant two
  modules consume for a cost nobody has felt.

**Deliberate scope boundary: `root_type` is not collapsed.** `config.ROOT_TYPE_VOCAB` and
`cards._ROOT_SLOTS` are still hand-maintained local copies of what is now a contract-owned
`RootType` (`('primary', 'lateral', 'crown')`, verified against `0.1.0a6`) — the identical
duplication this change removes for `mode`, and `get_args(<contract Literal>)` is now the
established pattern for fixing it. Left out on purpose so the bump stays one reviewable change with
one behavior claim; it is an oversight only if nobody writes it down, so this is the note. Tracked
in #38, which also records the wrinkle that makes it more than a find-and-replace: `_ROOT_SLOTS` is
an *ordered* tuple driving card emission order, while `ROOT_TYPE_VOCAB` is an unordered membership
set, so deriving both from `get_args(RootType)` would couple emission order to the contract's
declaration order.

## Migration Plan

None required. No published artifact, no committed matrix row, and no producer output changes. The
lineage record `sleap_roots_contracts_version` follows `importlib.metadata` automatically and will
read `0.1.0a6` on the next seed run.

Rollback is reverting the pin and the lockfile; the chooser change is inert without it (the import
would fail, which is the correct loud failure rather than a silent vocabulary fork).

## Open Questions

None.
