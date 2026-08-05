## Context

`sleap-roots-training` pins `sleap-roots-contracts==0.1.0a3` as a runtime dependency. It imports
exactly one name from it — `ModelCard` — in tests, and records the installed contract version in
seed-run lineage (`registry/lineage.py`). The producer writes flat `ModelCard` metadata onto wandb
model artifacts; `sleap-roots-predict` is the consumer that matches on it.

`chooser.MODE_VOCAB` has **two** consumers in this package, not one:

1. `chooser.load_selection_matrix` — validates each row of the committed `model_selection.yaml`,
   which is repo-owned data that only ever reaches wandb artifact metadata.
2. `config._validate_experiment` (`config.py`, added by Tier 1 / #20) — validates
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

**Decision: a rejected vocabulary value gets a "did you mean" hint, and the hint is not a
normalization.** Added during review, and recorded here rather than only in `tasks.md` because it is
one of the two places this change alters what a user sees (the other being the `seed-registry` error
packaging in the spec delta). Exact matching (above) is only defensible if the
rejection *tells you what to write*; `difflib.get_close_matches` on the allowed values costs
+1.6 ms of import and turns `mode: Cylinder` from a bare rejection into a fix. It stays strictly a
hint — the value is never corrected, never written back, and the error is still raised — so it does
not encroach on the normalization decision deferred above. That deferral is about `validate`
*accepting* a non-canonical value; this is about the error message it prints when it does not.

Two sub-decisions worth stating, both of which look arbitrary in the code otherwise:
- **Cutoff `0.5`, named, not `difflib`'s implicit `0.6`.** `cyl` → `cylinder` scores **0.545**, so
  at the default the one shorthand this whole vocabulary collapse exists to close would get no hint
  at all. Everything else clears either threshold comfortably (`Cylinder` 1.0,
  `multiplant-cylinder` 0.947, `cylnder` 0.933, `plaet` 0.800) and `teacup` correctly gets nothing.
- **`ascii()` rendering when it differs from `repr()`.** `repr` escapes non-printables but leaves
  printable non-ASCII alone, so a homoglyph paste (`'сylinder'`, Cyrillic `с`) would be displayed
  identically to the `'cylinder'` it suggests — an error a user cannot act on. Applied only when
  the two differ, so `'Cylinder'` and `' cylinder'` are untouched.

**Scope note:** `_check_vocab` is shared by `experiment.species`, `experiment.mode` **and**
`experiment.root_type`, so the hint and the `ascii()` rendering changed the error text for all three
fields, not only for `mode`. That is wider than this change's stated subject, and is called out
because a reader arriving from the title would not expect it. Accepted rather than narrowed: making
the hint mode-only would mean either duplicating `_check_vocab` or branching on the field name, both
worse than the disclosure. One known wart, left alone: `mode: lateral` suggests `'plate'`, because
`difflib` has no idea `lateral` is a valid *root_type* pasted into the wrong field. Species synonyms
(`rapeseed` → `canola`, `Oryza sativa` → `rice`) score below any sane cutoff and get no hint; a
synonym map would serve config authors better than `difflib` there, and is not attempted here.

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
- **Two exact pins to different versions are unsatisfiable.** → A consequence of `==` on a *runtime*
  dependency, not just a dev one (`uv pip compile` confirms the conflict): if a combined
  producer/consumer environment ever exists, this repo and `sleap-roots-predict` become lockstep-bump
  partners. Not a risk today — `predict` is not a dependency here, and the producer/consumer boundary
  is decoupled through W&B artifact metadata rather than a shared import — but it is the cost of the
  pin and belongs on the list. `==` remains the right call for the reasons in the first decision.
- **A future contract release changes `Mode` from a `Literal` to something else.** → `get_args()`
  does not raise on a shape it cannot destructure; it *degrades*, in two different directions:

  | upstream `Mode` becomes | `get_args` returns | `MODE_VOCAB` |
  |---|---|---|
  | `Enum` / plain `str` alias | `()` | empty |
  | `Annotated[Literal[...], Field(...)]` | `(Literal[...], FieldInfo)` | typing objects |
  | `Optional[Literal[...]]` | `(Literal[...], NoneType)` | typing objects |
  | `Union[Literal[...], Literal[...]]` | `(Literal[...], Literal[...])` | typing objects |

  In every one, no real mode is in the vocabulary and the `frozenset[str]` annotation becomes a
  runtime falsehood; the failure then surfaces far from its cause, as every real mode being
  rejected — or, worse, as a `TypeError` thrown from inside the *error-reporting* path (`sorted()`
  over mixed types) at pytest collection time. `chooser` therefore raises at import when the derived
  vocabulary is empty **or contains a non-string**, naming what changed.

  The type half matters and was missed once: a first pass guarded only emptiness, which catches the
  first row and none of the other three — and `Annotated[..., Field(...)]` is the *idiomatic* shape
  for a pydantic-first contracts package, so it is the likeliest of the four. The guard's own
  discrimination is now tested against all four shapes plus a plain-`Literal` negative control
  (`tasks.md` 3.6). Note also the two tests named for this invariant cannot catch it on their own:
  `test_mode_vocab_is_the_contract_vocabulary_unforked` re-derives the set exactly as production
  does, so both sides degrade together and it still passes, and a `MODE_VOCAB`-parametrized test
  degrades to a *skip*, not a failure. Both now carry an independent literal witness alongside the
  re-derivation.
- **A future contract narrowing invalidates hand-written configs, not just matrix rows.**
  → `MODE_VOCAB` also backs `validate`'s check on `experiment.mode`, so the contract now governs a
  user-authoring surface. The committed matrix and `examples/` were already guarded; `docs/training.md`
  is the third authoring surface and nothing read it, so a test now asserts every `mode:` the guide
  tells users to write stays contract-valid. Flagged in the CHANGELOG for downstream config authors.

  **The guard is scoped to the `experiment:` block, and that scope is the point.** A config is the
  repo-owned `experiment` block **plus** `sleap-nn`'s own `data_config` / `model_config` /
  `trainer_config` consumed as-is — and those carry `mode` keys of their own that this vocabulary
  has no claim on (`ReduceLROnPlateau(mode='min'|'max')` is a standard Lightning field, and the
  guide is meant to document it). Two earlier versions of this guard fired on *correct* docs edits:
  first by splitting on `:` (so quoting the value broke it), then by walking every `mode` key at any
  depth (so documenting a scheduler broke it). In a repo whose rule is "`main` stays green", a guard
  that goes red on a correct change is a defect, and a guard is this change's whole value — so the
  extraction reads `experiment.mode` and nothing else, pinned by
  `test_mode_guard_reads_only_the_experiment_block`.
- **A rejected selection matrix reaches the operator as a traceback.**
  → Wrapped into a `ClickException` in `seed-registry` (`tasks.md` 2.6), then found to cover only
  the out-of-vocabulary path while the "unreadable file" half the CHANGELOG named as fixed still
  crashed (`tasks.md` 2.8). Normalization now lives in `chooser._parse_matrix` rather than in the
  `except` clause: the loader is where the set of possible failures is known, and a call site that
  re-derives that set is a call site that will miss a member — which is exactly what happened. The
  documented `Raises: ValueError` on `load_selection_matrix` is therefore the whole contract, and
  every caller (including future ones) wraps one type.
- **Eager import cost.** `from sleap_roots_contracts import Mode` at `chooser` module scope is the
  first place this package actually imports the contract (and transitively pydantic) — `lineage.py`
  only read its version via `importlib.metadata`. Since `config.py` imports `chooser` eagerly, this
  lands on the CLI's import path.

  **Corrected after review.** An earlier draft recorded "~183 ms added (~199 ms vs ~16 ms), ~124 ms
  of which is the contract/pydantic import". That is the *total* cost of importing `chooser`, not
  what this change *adds*: `chooser` already imported `omegaconf` before this PR, and omegaconf and
  the contract share `yaml`, `importlib.metadata` and `re`, so the marginal cost is much smaller.
  A true A/B — reverting only `chooser`'s contract import to the previous local frozenset via an
  editable install, median of 15, restored byte-for-byte — gives:

  | case | pre-PR | this change | delta |
  |---|---|---|---|
  | bare interpreter | 15.4 ms | 15.1 ms | noise |
  | CLI `--version` | 118.7 ms | 191.1 ms | **+72.4 ms** |
  | CLI `--help` | 116.7 ms | 194.0 ms | **+77.3 ms** |
  | `import ...config` | 90.9 ms | 178.0 ms | +87.1 ms |
  | `import ...registry.chooser` | 88.6 ms | 175.9 ms | +87.3 ms |

  So ~72–87 ms, not ~183 ms. (An independent reviewer measured +53–77 ms on other hardware; the
  absolute numbers are machine-dependent, the correction is not.) The direction favours the change,
  but the recorded figure was wrong in a way that would mislead whoever revisits this.

  It is also **not** "a one-time cold-start cost" as previously written. `cli.py:10` imports
  `chooser` at module scope, so `--help`, `--version` and every shell TAB-completion press pay it,
  not only `train` / `seed-registry`. Still accepted — immaterial next to training runtime — but it
  does cut against this repo's lazy-import convention for heavy dependencies (`wandb`, `sleap-nn`),
  so it is recorded rather than silent.

  **Why it is not deferred** — also corrected; the previous reason ("making `MODE_VOCAB` a function,
  which trades a public constant two modules consume") is simply false. A PEP 562 module-level
  `__getattr__` in `chooser` keeps `MODE_VOCAB` a public constant that both `chooser.MODE_VOCAB` and
  `from ...chooser import MODE_VOCAB` still resolve. The public constant was never the obstacle.
  Two things are:
  - `config.py` does `from ...chooser import MODE_VOCAB`, and a from-import binds *eagerly*, so it
    fires `__getattr__` at import time. Deferring in `chooser` alone therefore recovers **0 ms** —
    measured, not estimated: an arm with `chooser` lazy and `config.py` untouched times identically
    to the eager arm. Only deferring in *both* recovers anything, and then it recovers essentially
    the whole marginal cost (~82–85 ms), not part of it.
  - The real cost, and the actual reason to decline: the import-time guard above would have to move
    into the accessor, becoming a **first-use** error instead of failing at the seam. Demonstrated
    against a deliberately broken stub (`Mode = str`): eager, `--version` fails immediately with the
    intended `RuntimeError`; fully deferred, `--version` *succeeds silently* against a broken
    contract and the error only appears on first attribute access inside `validate_config`. That is
    exactly the regression the guard exists to prevent, and it is worth more than the ~85 ms.

  If anyone does implement it later, two traps: `_parse_matrix`'s global reference to `MODE_VOCAB`
  does **not** route through module `__getattr__` (a function's global lookup hits `globals()`
  directly) and must call the accessor or it `NameError`s; and `functools.cached_property` is a
  non-starter on a module — it is a descriptor needing a class instance, so `functools.cache` on a
  module-level function is the equivalent.

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

**Provenance covers the seed path only, and this change adds a surface it does not cover.**
`build_lineage()` is called once, in `seed-registry`, so the paragraph above answers provenance for
published artifacts. It does not answer it for training: `emit` strips the whole `experiment` block
(`config.py:_strip_experiment`, because sleap-nn's struct-mode config rejects the key), so the config
that actually reaches `sleap-nn train` carries no mode, no species and no contract version. That
matters more after this change than before it: previously a repo commit fully determined which modes
were valid, so the commit *was* the provenance; now validity also depends on an installed package
version, and the training path records neither. Recoverable in practice via the `==` pin plus the
lockfile, but not recorded anywhere on that path. The unprovenanced training path is pre-existing
(#20); what is new is an external dependency on it. Tracked as a follow-up — the cheap fix is a
provenance comment (contract version + repo SHA) written into the emitted YAML, which is the artifact
that survives to the GPU box.

Rollback is reverting the pin and the lockfile; the chooser change is inert without it (the import
would fail, which is the correct loud failure rather than a silent vocabulary fork).

## Open Questions

None.
