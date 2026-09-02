# Design: label-corpus inventory

## Context

Full background, the verified findings this rests on, and the resolved decisions are in
[`docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md`](../../../docs/superpowers/specs/2026-09-01-label-and-model-inventory-design.md)
(deliverables A, B and C are in scope here; D is the second change — see Change split).
This file carries the decisions that shape the spec deltas.

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
- **D3. Two derivations, reconciled — but only one of them is genuinely independent.**
  For **species** the derivations are independent: a human typed `SLEAP_wheat`, and Bloom
  records `species_name` from experiment metadata. Agreement there is real corroboration.
  For **age and date** they are not: `bloomctl` *wrote* `Day{plant_age_days}_{date_scanned}`
  from the very columns we later read back, so agreement is a **staleness check** — did the
  record change after download, through a re-key or a correction. Since age and date are the
  only per-scan facts compared, the reconciliation tally's assurance value is weaker than the
  first draft of this decision claimed. Both checks are worth running; the spec now says
  which is which rather than presenting them as one argument.
- **D4. Aggregates from agreed rows only, gated per collection.** A total computed across
  verified and unverified rows looks authoritative and is not. The gate is scoped to the
  collection rather than the run: a global halt would let one poorly-covered collection
  suppress the whole corpus, which is the opposite of the isolation rule.
- **D5. Unresolved is a state, not an error.** Legacy scans may predate Bloom ingestion or
  have been re-keyed, and an unparseable path is a third way to have no Bloom record. The
  state carries its reason so a malformed path is distinguishable from a scan Bloom has never
  seen.
- **D6. Provenance from the original version; images-embedded from the repair.** Six
  collections carry a re-embed repair that restores trainability and, in doing so, drops the
  species tags and records a temporary path. Both versions are needed and they answer
  different questions, so the spec names which value comes from which.
- **D7. Read-only is enforced by HTTP method, not by trust.** The available Bloom
  credentials belong to a person and carry write authority, so no permission boundary
  protects us and "performs no write" is unassertable. The **data plane** issues only `GET`:
  every table write and every volatile remote procedure requires another method, so a
  `GET`-only data plane cannot perform one whatever its credentials allow. The rule is scoped
  to the data plane rather than the whole client because the session token exchange is a
  `POST` — a client-wide rule would forbid logging in, which the first draft of this decision
  did, and would have contradicted its own re-authentication rule two requirements later.
  Note also that a read-only remote procedure *can* be served over `GET`; the guarantee rests
  on the gateway refusing `GET` for a volatile one, not on procedures being writes. Injected
  clients remain a regression control layered on top, mirroring `registry/publish.py`'s
  `api=None` seam rather than inventing a pattern. A dedicated non-writer Bloom account would
  be stronger still and is worth pursuing separately; it is not available now, and the design
  does not depend on it.
- **D8. Structural discovery over a maintained list.** A list encodes what is already
  remembered, which is what an audit exists to get past. A folder qualifies when it holds a
  top-level labels file; split directories are excluded because a split describes a training
  run, and reporting its frame count as the corpus's would be wrong in the direction that
  looks plausible. The walk root is a parameter so discovery is testable without the share.
- **D9. Diff the skeleton table, never read values from it.** The table is advisory and says
  so; its header states that verifying against these collections is what flips its
  `verified:` flags. Reading it to fill a value would launder an unverified assertion into an
  inventory. The `mode` gap is reported as a keying gap rather than a per-row contradiction
  because no row edit fixes a missing key.
- **D10. New module tree, away from the file two changes are queueing on.**
  `inventory/` rather than `registry/` or `labeling/`. The only shared file is `cli.py`,
  where `#48` appends a command group at end of file and
  `add-labeling-experiment-verification` adds one option mid-file; this change's group goes
  **before** the `labeling` group so it does not contest the EOF. Conflict-free in any order
  except for that additive edit.
- **D11. Artifacts are committed to `inventory/`, at a pinned path.** Reviewability in the
  PR and diffability over time are the point, and `inventory/` is not gitignored. The path is
  pinned in the docs rather than left to whoever passes `--out`, because "regenerate and
  diff" only works if everyone regenerates to the same place. W&B publishing is a follow-up
  once the shape settles.
- **D12. Emitted artifacts are redacted structurally, because the repo is public.** The
  recorded source paths carry an internal SMB hostname and a username, and
  `scripts/pull_tf_reference.py` already redacts exactly those two strings before committing
  captured payloads, for exactly this reason. But reusing its literal substitutions is not
  enough: the share holds several people's directories, so an enumerated username redacts one
  person and passes everyone else through — and a test built on the enumerated name would
  report that as clean. Redaction is therefore structural (the segment after a user-directory
  marker, whatever its value; any UNC host segment), with the existing substitutions kept as
  a compatibility floor. Person-identifying Bloom fields are not emitted at all, and the
  accession/genotype columns need an owner's call before they are committed.
  Note `src/` cannot import from `scripts/`, which has no `__init__.py`; the rule is defined
  in `inventory/redact.py` and a test loads the script by path — the way
  `tests/test_scripts.py` already does — to assert the two agree.
  Scope note: discovery is confined to the project owner's SLEAP directory, so every
  *walked* path carries one user segment. The structural rule earns its keep on **recorded**
  paths from registry metadata, which this capability does not control and cannot re-scope.
  `genotype`, `accession_id` and `experiment_name` are approved for the public repo
  (eberrigan, 2026-09-02); the excluded class is fields naming a person.
- **D13. Depend on `bloomctl`. This reverses an earlier decision, and the reversal is the
  most consequential change in this proposal.** The earlier version reached Bloom over
  `requests` to avoid ~40 transitive packages, on the stated grounds that "this capability
  needs two `GET` shapes, not a client library." That was a weight trade-off made against a
  read path whose shape was never established. The two shapes are written down nowhere — not
  here, and not in `bloomctl`, which issues no HTTP of its own and delegates to `supabase-py`
  (`auth.py` is `client.auth.sign_in_with_password(...)` over `create_client(...)`). So the
  saving was measured against work that had not been scoped.
  It also promised to specify three inherited behaviours. Two were specified (the batching
  budget, the `in.(…)` quoting rule); the third — the expired-session signal — could not be,
  because `bloomctl`'s only expiry handling is free-text matching on *storage* errors and its
  PostgREST layer has no expiry retry at all. Depending on `supabase-py` through `bloomctl`
  makes that requirement disappear rather than need specifying: its auth client refreshes on
  a timer.
  What the dependency buys: the authenticated client, session refresh, `fetch_in_batches`
  with its measured budget, the quoting rule, `CSV_COLUMNS` as an importable constant instead
  of a transcribed fixture with a drift guard, and a **plate** read path — which the
  cylinder-only view could not serve, and without which this change cannot verify the plate
  half of the `mode` keying gap that is its own headline. It resolves cleanly against
  `main`'s contracts pin.
  What it costs, stated plainly: `supabase`, `httpx`, `realtime`, `cryptography` and the rest,
  in a repo that has been careful about its dependency surface. Accepted, rather than paid in
  reimplemented production authentication.
- **D14. Emit evidence, not cards.** A `LabelCard` requires `registry_id` and `version`,
  which are meaningless for a collection that was never registered — and the unregistered
  collections outnumber the registered ones. `mode` and `root_type` have no source in scan
  metadata at all; the only available source is the collection name, which this capability
  exists to distrust. So the aggregate stops claiming to carry "the card fields". It carries
  what is evidenced, `#49` builds cards from it, and name-derived root type and mode are used
  **only** to select a skeleton row to compare against — never emitted as provenance.

## Alternatives considered

- **Read only from the registry, skip the share.** Reproducible for anyone with an API key,
  and removes the drive-mapping question. Rejected: it discards the share as an independent
  cross-check, which is what makes the digest gate meaningful rather than circular.
- **Trust matching path and size.** Cheapest. Rejected on the explicit standard set for this
  work — a same-size file with different content would pass, and the output is permanent
  provenance.
- **Derive species from the collection name.** Free, and right most of the time. Rejected:
  the exceptions are the entire question, and a name-derived answer confirms names using
  names.
- **Depend on `bloomctl` for its read path and column list.** Attractive — it already
  implements Bloom auth, batching and the expired-token retry, so we would reimplement none
  of it. Rejected on the resolution conflict in D13; the batching and retry rules are
  therefore specified here explicitly rather than inherited.
- **One change covering labels and models.** Shares the share walk. Rejected: repo convention
  is one change per PR, the two have different consumers, and `#49` is a live example of the
  cost of a large one.

## Risks

- **Production credentials with write authority.** Mitigated by D7's `GET`-only client, the
  injected-client seam, and a test asserting the method of every request. A second reviewer on
  the Bloom module is requested in the PR description rather than as a task.
- **Bloom coverage of legacy scans.** Unknown until run. Handled by D5 rather than assumed
  away — if coverage is poor the output says so per scan instead of producing confident
  aggregates from a thin join, and D4's per-collection gate means the well-covered collections
  still emit.
- **The gate could withhold most aggregates.** If most rows are unresolved, little is
  emitted. That is the correct failure: it reports that the corpus cannot yet be verified
  rather than that it has been.
- **Duplication with an existing check.** `verify-skeleton-table.yml` already diffs node
  counts weekly by downloading `:latest` — the repair version, which is why it cannot see
  species. This capability subsumes it from better inputs. Retiring it is deferred so this
  change stays additive; the overlap is recorded in Impact so the two do not silently diverge.
- **Downstream irreversibility.** If `#49` consumes a wrong aggregate and publishes
  `LabelCard`s, reverting this repo does not unpublish them, and W&B is the system of record
  for label artifacts. Hence the ordering: artifacts adjudicated and committed before `#49`'s
  publish step.
- **Scope pressure.** Everything this finds implies a fix — the `mode` key, missing species
  rows, `#3`, tip models. The non-goals list holds that line, and each is a separate change.
