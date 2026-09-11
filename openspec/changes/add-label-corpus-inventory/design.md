# Design: label-corpus inventory

## Context

Full background, the verified findings this rests on, and the resolved decisions are in
[`docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md`](../../../docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md)
(deliverables A, B and C are in scope here; D is the second change — see Change split).
This file carries the decisions that shape the spec deltas.

That document is **not carried by this change**. It lands first in its own `docs:` PR, with
its `card:` example and its run-level human gate corrected against D4 and D14, so that the
second change can cite a merged path rather than one that resolves only because this PR
happened to carry the file. See Prerequisites.

## Prerequisites

Two changes land before this one. Neither is optional and neither is bundled here.

- **The background design doc**, as a `docs:` PR (above). This branch rebases onto it.
- **The RED/GREEN commit convention**, as its own change. It amends a repo-wide rule in
  **five** places — `openspec/project.md`'s Testing Strategy; `.claude/commands/tdd.md`
  Phase 6 *and* its Integration section, which restates the rule 74 lines later;
  `.claude/commands/review-pr.md`'s TDD-reviewer prompt; and
  `.claude/commands/review-openspec.md`'s Git Workflow reviewer prompt, which is the tooling
  that would otherwise flag every RED commit the convention permits. It also collides with
  `#48`, which rewrites the same `openspec/project.md` block and moves archiving to a
  separate follow-up PR. A repo-wide convention every future change inherits does not belong
  inside a capability addition, and bundling it would falsify this proposal's additivity
  claim.

Task 0.1's rebase therefore targets a `main` carrying the design doc, the convention, and
the `sleap-roots-contracts==0.1.0a8` pin.

## Decisions

- **D1. ADDED, not MODIFIED.** No live spec covers label provenance. `label-registry`
  belongs to in-flight `#49` and is not on `main`, so a MODIFIED block would re-paste a spec
  that does not exist yet and permanently bake a base that was never merged. Precedent:
  `add-tf-reference-fixtures` added `tf-reference` as an ADDED-only new capability. That
  precedent supports the *mechanic*; our situation differs in that a spec for the adjacent
  capability exists on an unmerged branch, which is a further reason not to MODIFY. This also
  makes the change order-independent with respect to `#49`.
- **D2. A capability, not a script.** The corpus grows, so a one-time pass is stale the day
  a further collection is published. Determinism and idempotence are specified normatively
  so the artifacts can be regenerated and diffed instead of hand-audited.
- **D3. Two derivations, reconciled — but only one of them is genuinely independent, and
  only for cylinder.** For **species** the derivations are independent: a human typed
  `SLEAP_wheat`, and Bloom records the species from experiment metadata. Agreement there is
  real corroboration. For **age and date** they are not: the download tooling *wrote*
  `Day{age}_{date}` from the very columns we later read back, so agreement is a **staleness
  check** — was the record corrected after download. Since
  age and date are the only per-scan facts compared, the reconciliation tally's assurance
  value is weaker than the first draft of this decision claimed. And it applies to cylinder
  only: plate has no reconcilable scan metadata at all (D16). The spec says which check is
  which rather than presenting them as one argument.
- **D4. Reconciliation-derived fields are computed from agreed scans and annotated;
  disagreements are adjudicated per field.** Three rules, and the distinction between the
  second and third is the whole decision:
  1. A field is computed from **agreed scans only** and carries the contributing and
     excluded counts. A total computed across verified and unverified scans looks
     authoritative and is not.
  2. An **unresolved** scan never withholds anything. It carries no comparison — a legacy
     scan predating ingestion, an unparseable path, a plate path with no key — and legacy
     coverage gaps are expected (D5). A rule that withheld on any
     unresolved scan would emit almost nothing.
  3. A **disagreed** scan means the two sources actively conflict. Since the download tooling
     wrote the directory name *from* the metadata, the only way they diverge is a correction
     made afterwards — so a disagreement is a prompt to look, not evidence that either side is
     untrustworthy. It withholds **only the fields the conflicting field feeds**, marked
     `awaiting_adjudication`, and enters an adjudication queue.

  A verdict takes **two forms — accept or exclude** (eberrigan, 2026-09-11). Exclude is the
  escape hatch that stops one scan a person distrusts on both sides from blocking a
  collection's card indefinitely. An earlier draft proposed a third, *escalate*, meaning "the
  upstream record needs fixing"; with re-keying struck (D5) that form has no case left to
  describe, because a disagreement means the record was already corrected.

  An accepted value is a person's choice, not two derivations agreeing, so the scan is
  classified `adjudicated` rather than `agreed` and the field carries the confidence
  `adjudicated` rather than `verified`. Marking a human pick `verified` would publish it under
  the label this spec reserves for corroboration, into a public repo and onward into `#49`'s
  cards. A verdict also records the pair of values observed when it was made: a verdict whose
  pair no longer matches is **not applied** and the scan re-enters the queue as stale, because
  a verdict silently applied to a conflict nobody saw emits a value neither source carries.

  This **supersedes** the background doc's "Human gate on exceptions", which stopped the
  whole run before emitting any aggregate. A global halt would let one poorly-covered
  collection suppress the corpus, which is the opposite of the isolation rule; and that
  bullet was internally inconsistent, illustrating "aggregates come only from agreed rows"
  with an example reporting all 170 scans while 12 were unresolved. The gate survives, scoped
  to the field rather than the run.
- **D5. Unresolved is a state, not an error, and it has five reasons.** Legacy scans may
  predate Bloom ingestion; an unparseable path, a cleared embedded source, an unparseable
  date and a plate path with no key are each a distinct way to have no comparison. Re-keying
  is **not** among them: an earlier draft named it in three places, the term was never defined
  anywhere in this repo or in Bloom's, and it does not happen (eberrigan, 2026-09-11). The earlier draft of this decision folded an unparseable path into "a third
  way to have no Bloom record", which conflated two reasons the spec then had to
  distinguish. The five are enumerated normatively so the closed vocabulary can be locked.
- **D6. Provenance from the original version; images-embedded from the repair.** Six
  registered collections carry a re-embed repair that restores trainability and, in doing so,
  drops the species tags and records a temporary path. Both versions are needed and they
  answer different questions, so the spec names which value comes from which. A manifest
  entry added as an external-store *reference* carries that store's ETag rather than an MD5
  of the bytes; such an entry is reported unverifiable rather than mismatching, because a
  mismatch verdict would be an accusation against an intact file.
- **D7. Read-only is enforced by HTTP method on the data plane, not by trust.** The
  available Bloom credentials belong to a person and carry write authority, so no permission
  boundary protects us and "performs no write" is unassertable. The **data plane** issues
  only `GET`: every table write and every volatile remote procedure requires another method,
  so a `GET`-only data plane cannot perform one whatever its credentials allow. The rule is
  scoped to the data plane rather than the whole client because the session token exchange is
  a `POST` — a client-wide rule would forbid logging in, which the first draft of this
  decision did. Note also that a read-only remote procedure *can* be served over `GET`; the
  guarantee rests on the gateway refusing `GET` for a volatile one, not on procedures being
  writes.

  The ingest prohibition cannot be enforced at import level, and the spec says so rather
  than requiring the impossible. `bloomctl/cyl/__init__.py` imports `.ingest`, so
  `bloomctl.cyl.ingest` is in `sys.modules` the moment any read symbol under `bloomctl.cyl`
  is imported — verified against the published wheel. The enforceable guarantee is a
  **source-level** assertion that no module here names an ingest symbol, layered on the
  data-plane method assertion, which catches an actual write whatever is imported.

  Injected clients remain a regression control on top, mirroring `registry/publish.py`'s
  `api=None` seam rather than inventing a pattern. A dedicated non-writer Bloom account would
  be stronger still and is worth pursuing separately; it is not available now, and the design
  does not depend on it.
- **D8. Enumerate every labels file; a person promotes.** The unit is the **labels file, not
  the folder**, and no structural rule decides which file is a collection.

  A maintained list encodes what is already remembered, which is what an audit exists to get
  past — so enumeration is structural and complete. But the corpus refutes the folder as the
  unit outright: `SLEAP_sorghum/primary_6nodes/` holds 28 labels files covering a sorghum
  superset, a **soybean** collection, a soybean+sorghum generalist, per-labeler inputs and
  scratch; `SLEAP_wheat/seminal/` holds the wheat superset, three per-day inputs, **two rice
  collections** and a wheat+rice generalist; `SLEAP_multiple_species/primary_roots_6_nodes/`
  holds four species and no combined file. And `SLEAP_wheat/`, `SLEAP_sorghum/` and
  `SLEAP_multiple_species/` hold no labels file at their own top level. A rule selecting one
  file per folder would have dropped soybean, rice, and every generalist.

  A finished superset, a per-day input merged into it, and a practice file are not
  distinguishable by name or structure, so the classification is a judgment recorded in a
  committed decision file (D15). Version families are keyed on **(containing directory,
  basename minus `.v<digits>`, extension)**, not on the basename alone: `labels.vNNN.slp`
  occurs 57 times in 23 directories spanning five species and both capture modes, so a
  basename-keyed family would name one rice file the current version of all of them and
  refuse to read the other fifty-six. A `.slp` and a `.pkg.slp` are separate families, since
  one references images and the other embeds them. This replaces the earlier draft's
  sibling-selection rule entirely — no such rule is needed, which removes one of the values
  that draft deferred to implementation.

  Two corollaries the corpus forces. An unversioned file is `unclassified`, never `scratch`
  by structure alone: the nine most recent plate labels files are unversioned deliberate
  merges and are the only trace of two experiments, and a structural rule may not take an
  irreversible read-or-not decision — that is the judgment D15 reserves for a person. And
  derived files are excluded **by shape rather than by directory**, because 13,164 of the
  share's 18,099 labels files are `*.predictions.slp` inference outputs and thousands sit
  outside any `predictions` directory; excluding by shape leaves ~1,450 files and ~470
  versioned promotion candidates, which is a reviewable task where 18,099 is not.

  Split directories are excluded because a split describes a training run, and reporting its
  frame count as the corpus's would be wrong in the direction that looks plausible. The walk
  root is a parameter so discovery is testable without the share.
- **D9. Diff the skeleton table, never read values from it.** The table is advisory and says
  so; its header states that verifying against these collections is what flips its
  `verified:` flags. Reading it to fill a value would launder an unverified assertion into an
  inventory.

  Selecting a row needs all three of its keys and **none of them is available from scan
  metadata** — so species and age join mode and root type as name-and-file-derived
  *selectors*, used only to choose what to compare and never emitted as evidence. The
  earlier draft authorised only mode and root type, which left the diff unable to select any
  row when Bloom was down, contradicting its own claim that file-derived evidence survives a
  Bloom failure. With selectors needing no Bloom, the diff is emitted regardless.

  The name-to-root-type mapping is stated: `seminal`, `sr` and `seminal_root` select the
  `crown` row, because the team's seminal roots are the contract's crown root type and
  `RootType` has no `seminal` member — the `wheat-cylinder-crown` decision recorded in
  `docs/roadmap.md`. A name yielding a root type outside the contract vocabulary
  (`tertiary` and `adventitious` both occur on the share) is reported out-of-vocabulary
  rather than as a missing row, because the two need different fixes. The `mode` gap is
  reported as a keying gap rather than a per-row contradiction because no row edit fixes a
  missing key; whether node counts also vary by age is a hypothesis the diff tests rather
  than the settled fact the earlier draft asserted.
- **D10. New module tree, away from the file two changes are queueing on.**
  `inventory/` rather than `registry/` or `labeling/`: `resolve.py`, `read.py`, `bloom.py`,
  `reconcile.py`, `discover.py`, `promote.py`, `skeleton_diff.py`, `emit.py`, `redact.py`,
  and the leaf `vocab.py` the vocabulary requirement mandates. The only shared file is
  `cli.py`, where `#48` appends a command group at end of file and
  `add-labeling-experiment-verification` adds one option mid-file. This change's group goes
  **after the `seed-registry` command and before the `validate` command** — a location none
  of `#48`'s four `cli.py` hunks touches. The earlier draft placed it immediately before the
  `labeling` group, two unchanged lines from one of those hunks' boundaries; conflict-free in
  practice but needlessly close.
- **D11. Artifacts are committed to `inventory/`, at a pinned path.** Reviewability in the
  PR and diffability over time are the point, and `inventory/` is not gitignored. The path is
  pinned in the docs rather than left to whoever passes `--out`, because "regenerate and
  diff" only works if everyone regenerates to the same place.

  This PR commits **one adjudicated collection** as a worked example — the registered wheat
  superset — so that D11's stated reason is true of this PR and not only of a follow-up. That
  worked example also serves as the committed golden the cross-operating-system byte-identity
  test needs, and it proves before merge that the manifest digest matches, the join returns
  rows, and redaction strips what it claims to. The remaining collections are adjudicated and
  committed in a follow-up PR. `inventory/**` is added to `ci.yml`'s paths filter in the same
  change, since a commit touching only the artifacts would otherwise report a green check
  meaning nothing ran. `.gitattributes` already pins `*.md`, `*.yaml` and `*.csv` to
  `eol=lf`, so pinning `inventory/**` is redundancy rather than a fix; the real gap is
  `tests/fixtures/inventory/**`, which `inventory/**` cannot match because a slash-bearing
  pattern is anchored to its own directory.
- **D12. Emitted artifacts are redacted structurally, because the repo is public.** The
  recorded source paths carry an internal SMB hostname and a username, and
  `scripts/pull_tf_reference.py` already redacts those before committing captured payloads,
  for exactly this reason. But reusing its literal substitutions is not enough: the share
  holds several people's directories, so an enumerated username redacts one person and
  passes everyone else through — and a test built on the enumerated name would report that as
  clean. Redaction is therefore structural (the segment after a user-directory marker,
  whatever its value; any UNC host segment), with the existing substitutions kept as a
  compatibility floor. The marker set covers the share's user-directory marker and the
  temporary-directory shape a repair version's recorded path takes.

  `src/` cannot import from `scripts/`, which has no `__init__.py`; the rule is defined in
  `inventory/redact.py` and a test loads the script by path — the way `tests/test_scripts.py`
  already does — to assert the two agree.

  Scope: the rule governs **emitted artifacts**, which carry hundreds of recorded paths.
  Prose documentation naming the share root or host once is already repository practice
  (`.claude/commands/build-labeling-package.md` does it) and is out of scope; the spec's
  prefix enumeration records prefix *shapes* with the host segment in redacted form for the
  same reason. `genotype`, `accession_id` and `experiment_name` are approved for the public
  repo (eberrigan, 2026-09-02); the excluded class is fields naming a person.
- **D13. Depend on `bloomctl`. This reverses an earlier decision, and the reversal is the
  most consequential change in this proposal.** The earlier version reached Bloom over
  `requests` to avoid transitive weight, on the stated grounds that "this capability needs
  two `GET` shapes, not a client library." That was a weight trade-off made against a read
  path whose shape was never established. The two shapes are written down nowhere — not here,
  and not in `bloomctl`, which issues no HTTP of its own and delegates to `supabase-py`
  (`auth.py` is `client.auth.sign_in_with_password(...)` over `create_client(...)`). So the
  saving was measured against work that had not been scoped. It also promised to specify the
  expired-session signal, which could not be specified, because `bloomctl`'s only expiry
  handling is free-text matching on *storage* errors and its PostgREST layer has no expiry
  retry at all. Depending on `supabase-py` through `bloomctl` makes that requirement
  disappear rather than need specifying: its auth client refreshes on a timer.

  **What the dependency actually buys**, corrected from the reversal's first draft: the
  authenticated client, session refresh, `fetch_in_batches` with its measured character
  budget, and the cylinder scan-export column names as an importable constant instead of a
  transcribed fixture with a drift guard. Two items that draft claimed are **not** benefits
  and are struck: there is no filter-quoting rule to inherit — every `in_()` in `bloomctl`
  filters on numeric bigints, and `_postgrest.py` budgets by characters precisely because
  ids are bigints, so quoting a ten-character string key has no precedent there and is
  specified here; and the plate read path is out of scope (D16), so it is no longer a
  justification for anything.

  **What it costs, stated plainly.** `supabase`, `httpx`, `realtime`, `cryptography` and the
  rest — a measured +25 packages over this repo's core set, including compiled wheels, on
  every install and every one of the six CI matrix legs. Accepted rather than paid in
  reimplemented production authentication.

  **What the dependency is not.** `bloomctl` is a command-line application, not a library:
  `__init__.py` exports only `__version__`, there is no `py.typed`, `fetch_in_batches` lives
  in the private `_postgrest.py`, and the column constants live inside command modules — of
  which there are three, with the plate list differing from the two identical cylinder ones.
  The spec therefore does not claim to call a *documented* read interface; it names the
  symbols it imports in one adapter module and guards them with a test that fails loudly when
  one moves, and the version is capped tightly because these are internals of a pre-release
  CLI.

  **Resolution, measured rather than asserted.** `bloomctl 0.1.0a5` is the highest published
  release and requires `sleap-roots-contracts>=0.1.0a7`. It resolves against `main`'s
  `==0.1.0a8` pin; it is **unsatisfiable** against this branch's current `==0.1.0a6`. So the
  rebase is a hard prerequisite of adding the dependency, not housekeeping. A
  release-numbered lower bound resolves to nothing, because only `0.1.0aN` exists: the pin
  must be `bloomctl>=0.1.0a5,<0.1.0b1`.
- **D14. Emit evidence, not cards.** A `LabelCard` requires `registry_id` and `version`,
  which are meaningless for a collection that was never registered — and the unregistered
  collections outnumber the registered ones. `mode` and `root_type` have no source in scan
  metadata at all; the only available source is the collection name, which this capability
  exists to distrust. So the aggregate stops claiming to carry "the card fields". It carries
  what is evidenced, `#49` builds cards from it, and name-derived selectors are used **only**
  to select a skeleton row to compare against — never emitted as provenance.
- **D15. Committed decisions, read and never written, with a stated shape.** Both judgments
  this capability needs — which files are collections (D8) and which disagreements are
  accepted (D4) — live in committed YAML the capability **reads** and never writes, because a
  re-run is a full re-run with no resume: a judgment written by the run would be erased by the
  next one. It is consequently an *input* to determinism, and it is committed alongside the
  artifacts so the reasoning is reviewable in the diff.

  `--decisions` takes a **file or a directory** (eberrigan, 2026-09-11). One file per
  collection is the working shape: adjudication spans several PRs by design, this repository
  squash-merges, and line-based merges collide on adjacent appends — a hand-resolved conflict
  in the record of *why* a collection was promoted is the one place a silently dropped line
  does damage nothing downstream can detect. A duplicate identifier across merged files is a
  loud failure rather than a last-one-wins merge.

  A file is identified by its **walk-root-relative path**. A basename is ambiguous — 88
  versioned basenames occur in more than one directory, the worked example's own file three
  times — and an absolute path would publish the user segment D12 exists to strip, into the
  same commit as artifacts that redact it, while breaking the only workflow a person has:
  copying an identifier out of the aggregate, whose paths are redacted.

  The reasoning is recorded **as data, not as comments**, because squash-merge makes `git
  blame` resolve every judgment to the pull request rather than to the judgment. The aggregate
  records the decision content's digest, since the share is unreachable from a hosted runner
  and CI therefore cannot regenerate the artifacts to check they match the committed
  judgments.
- **D16. Plate collections are inventoried from the file only — because Bloom is not the
  source for our plate labels, not because its schema lacks the columns** (eberrigan,
  2026-09-10 and 2026-09-11). An earlier draft of this decision grounded it on a schema claim
  that was **wrong**: it said the plate schema carries no age at all. That is true of
  `gravi_scans_extended` and false of `plates_exp`, which carries `plant_age`,
  `planting_date`, `genotype` and a filename-keyed `scan_filename`; `gravi_scans` is also
  keyed `UNIQUE (experiment_id, plate_id, capture_date)`, which is what a plate path records.
  Both were considered. The decision stands on the program fact instead, and the earlier
  draft's "a better-scoped follow-up once Bloom carries a plate age" is struck, since it
  already does.

  What follows from reading plate from the file alone: its species is name-derived and
  labelled `name_derived` rather than emitted as evidence or suppressed entirely; its ages
  come from a curated `video_ages.csv` where one exists (roughly three of the plate
  collections) and from the collection name otherwise; and it has **no plant count**, since
  that quantity only exists in scan metadata. Bloom cannot reconcile a
  plate collection, and the schema is the reason rather than a scoping preference.
  `gravi_scans_extended` carries no plant identity and **no age column at all** — only a
  capture date and a transplant date — so a Bloom-derived plate age would be days after
  transplant, a third epoch matching neither the cylinder nor the plate-name convention; the
  corpus already works around this with a curated local age file. Plate paths carry no plant
  code, no age and no device, so there is nothing to join on. And plants hang off a plate
  capture one-to-many twice, through sections and then section plants, so a plate plant count
  is a different quantity from a cylinder one.

  Plate collections are therefore discovered, promoted, digest-verified and read like any
  other, with age and species share-derived and marked as such, and their scans reported
  unresolved for want of a key. **The `mode` keying gap still lands**, because the node counts
  that demonstrate it are file-derived and the mode that selects the rows is a name-derived
  selector (D9) — so the finding this proposal leads with does not depend on plate Bloom
  access. Reconciling plate metadata is a follow-up, and would start from `plates_exp`
  rather than from the gravi view.
- **D17. A multi-species collection is a defect blocking its card, and the grounds are not
  the ones first cited.** The earlier draft claimed the "program decision" that label
  collections are single-species was scoped in `docs/roadmap.md` to the eight registered
  collections and so could not carry the rule. That was a **misreading**: the roadmap states
  it program-wide — "a `LabelCard` never represents more than one species" — and only the
  *verification* obligation, that each of the eight be checked before backfilling, is scoped
  to eight. This decision restates a standing program decision rather than substituting for
  one, and adds three mechanical grounds: `LabelCard` carries one species and cannot express two; the training backend's
  `train_labels_path` is list-valued, so combining species inside one `.slp` is unnecessary;
  and the corpus's own generalist experiments are already organised as per-species
  directories.

  The verdict concerns **card eligibility, not file integrity** — models were demonstrably
  trained from several of these files, and the aggregate says so. The evidence emitted is the
  experiment-to-species mapping **with a scan count per species**, which is what makes the
  split actionable. Detection considers every scan carrying a Bloom row, agreed or not, so a
  thin join cannot hide a pooling — the case `#49` hit, where
  `wheat_5-14DAG_seminal_6nodes_labels` may be the wheat half of a pooled wheat+rice file.

  Comparison is on Bloom's species **identifier**, not the free-text common name: the common
  name is user-writable under a case-sensitive uniqueness constraint, so one taxon can carry
  two names — `medicago` and `alfalfa` both denote *Medicago sativa* — and a name-based
  comparison would report a single-species collection as mixed. Where a common name must be
  rendered, the contract library's normalisation rule is reached directly rather than through
  its parameter-resolution entry point, which fixes the mode to cylinder and raises when an
  age is absent.

## Alternatives considered

- **Reach Bloom over `requests` and specify the two `GET` shapes here.** The earlier
  decision. Saves the transitive weight D13 accepts. Rejected in D13: the two shapes are
  written down nowhere, `bloomctl` issues no HTTP of its own to copy them from, and the
  expired-session behaviour could not be specified at all — so the saving was measured
  against unscoped work, and the alternative would have reimplemented production
  authentication.
- **Read only from the registry, skip the share.** Reproducible for anyone with an API key,
  and removes the drive-mapping question. Rejected: it discards the share as an independent
  cross-check, which is what makes the digest gate meaningful rather than circular — and it
  would inventory only the eight registered collections, which is the snapshot error this
  change exists to correct.
- **Trust matching path and size.** Cheapest. Rejected on the explicit standard set for this
  work — a same-size file with different content would pass, and the output is permanent
  provenance.
- **Derive species from the collection name.** Free, and right most of the time. Rejected:
  the exceptions are the entire question, and a name-derived answer confirms names using
  names. Retained *only* as a row selector for the skeleton diff (D9), where it is never
  emitted.
- **Take the folder as the unit, one superset per folder.** Smallest output, and closest to
  the background doc's "superset labels file per collection" phrasing. Rejected on the
  corpus evidence in D8: it drops a soybean collection, two rice collections and every
  generalist file, and three of the relevant parent directories hold no labels file at their
  own top level.
- **Report a multi-species collection as `species: multiple` with no verdict.** Neutral, and
  preserves the provenance of files models were trained from. Rejected in D17: an accidental
  pooling would then read identically to a deliberate generalist, and the accidental pooling
  is the error this capability exists to catch.
- **One change covering labels and models.** Shares the share walk. Rejected: repo convention
  is one change per PR, the two have different consumers, and `#49` is a live example of the
  cost of a large one.
- **Split this change at the Bloom seam.** A Bloom-free half is genuinely shippable now that
  the keying gap needs no Bloom (D16), and it would give the dependency and the
  write-capable credentials their own diff. Rejected: the reconciliation work is coupled to
  the emitter, and two proposals, two review rounds and two archives cost more than the
  review risk they remove. The Bloom module still gets a second reviewer, requested in the
  PR description.

## Risks

- **Production credentials with write authority.** Mitigated by D7's `GET`-only data plane,
  the injected-client seam, and a transport-level test asserting the method of every request.
  That test needs a real transport rather than the strict attribute double, since the double
  issues no HTTP at all; the mechanism is named in the tasks rather than left implicit. A
  second reviewer on the Bloom module is requested in the PR description.
- **Depending on a pre-release CLI's internals.** `fetch_in_batches`, the column constants
  and the authenticated-client helper are not a published interface (D13). Mitigated by the
  tight upper pin, the single adapter module, and the drift guard that fails loudly when a
  symbol moves. The honest residual risk is that a `0.2.0aN` release moves them and this
  capability needs a small port.
- **Bloom coverage of legacy scans.** Unknown until run. Handled by D5 rather than assumed
  away — if coverage is poor the output says so per scan, and D4 means unresolved scans
  withhold nothing, so the well-covered collections still emit.
- **The adjudication queue could be long.** If many scans disagree, many fields sit
  `awaiting_adjudication`. That is the correct failure: it reports which numbers a person has
  not yet stood behind rather than publishing them. D4's per-field scoping keeps one
  conflicting age from withholding a species.
- **Duplication with an existing check.** `verify-skeleton-table.yml` diffs node counts
  weekly by downloading `:latest` — the repair version, which is why it cannot see species.
  This capability reads the same facts from better inputs (manifest digests instead of
  gigabytes of downloads) but **does not subsume it**: that check needs only `WANDB_API_KEY`
  and runs unattended on a hosted runner, whereas this capability needs the `Z:` share and so
  cannot run in CI at all. Retiring the workflow is a separate change and is not implied
  here; the overlap is recorded in Impact so the two do not silently diverge.
- **Downstream irreversibility.** If `#49` consumes a wrong aggregate and publishes
  `LabelCard`s, reverting this repo does not unpublish them, and W&B is the system of record
  for label artifacts. Hence the ordering: artifacts adjudicated and committed before `#49`'s
  publish step. The observed-versus-approved age distinction and the non-contiguity outcome
  exist so that `#46`'s plan to derive model age windows from label cards cannot silently
  promote an observed range into an approved one.
- **Scope pressure.** Everything this finds implies a fix — the `mode` key, missing species
  rows, `#3`, tip models, splitting the pooled generalist files, a plate age column in Bloom.
  The non-goals list holds that line, and each is a separate change.
