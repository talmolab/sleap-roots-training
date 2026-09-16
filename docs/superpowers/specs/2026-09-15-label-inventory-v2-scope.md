# Label inventory — scope and constraints for a fresh start

**Status:** scaffolding. Delete once the proposal it produces is approved.
**Date:** 2026-09-15
**Author:** eberrigan (with Claude Code)
**Supersedes, for this purpose:** `2026-09-01-label-and-model-inventory-design.md` and the
twelve `add-label-corpus-inventory` commits on `feat/label-corpus-inventory`.

Read **this file only**. Do not read the background design doc or the old change
directory to "get context" — they are the thing that went wrong, and reading them reliably
reproduces it. Everything still true is written below.

---

## The job

A re-runnable command that answers: **what label collections exist on the share, and what is
in them?** Today nobody knows. The registry holds 8 collections against an expected 25-30,
and `skeletons.yaml` cannot express the corpus it claims to describe.

Six things, and nothing else:

1. **Walk** a supplied root and enumerate labels files. Exclude derived files by **shape, not
   directory** (see Facts 1).
2. **Read** each file: skeleton name, node names, node count, frames and instances,
   distinguishing user labels from model predictions.
3. **Verify** the digest against the registry manifest entry where a registry artifact
   exists; report unregistered files as unregistered, not as failures.
4. **Diff** against `skeletons.yaml` and report the **`mode` keying gap** — the headline
   finding, and it needs no Bloom (Facts 6).
5. **Redact** host and user segments from every emitted path (Facts 4 — this one has teeth).
6. **Emit** one table and one report, in a deterministic order.

Then a person reads the output and decides what matters. That is the whole capability.

---

## The governing principle

> **When the tool cannot decide something, print it and stop. Do not build a mechanism to
> capture the answer.**

eberrigan, 2026-09-15: *"i don't mind being a human in the loop for this to avoid unnecessary
complications."*

This is the most important line in the document. The previous attempt grew from 15 to 19
requirements and from 68 to 145 scenarios almost entirely by building infrastructure to avoid
asking a person — a committed decision file, an identifier scheme, merge semantics, verdict
forms, stale-verdict detection, six closed vocabularies with a set-equality lock. All of it
existed so the tool would never have to stop and say "I don't know which of these is a
collection."

The answer is: stop and say it. Print the list. The human looks at it.

Concretely forbidden unless eberrigan asks for it in so many words:

- a decision / promotion / adjudication file of any kind
- a "verdict" concept, or any per-scan human-override state
- closed vocabularies with a documented-equals-emitted locking test
- any requirement whose purpose is to make a human judgment machine-readable

---

## Verified facts — carry these forward, do not re-derive

Each was established empirically during the previous attempt. Where it says *measured*, a
command was run.

**1. Scale, measured over `Z:/users/eberrigan/SLEAP`.** 18,099 `.slp` files total. 13,164 are
`*.predictions.slp` inference outputs. 2,233 sit under a `train_test_split*/` directory, 6,320
under `models/`, 6,930 under `predictions/`. Excluding all four shapes leaves ~1,450 files, of
which **~470 carry a `.vNNN` version suffix** — those are the real candidates. Thousands of
derived files sit *outside* any `models`/`predictions`/`train_test_split` directory, which is
why the exclusion must be by filename shape.

**2. Version suffixes and families.** Four suffix shapes occur, two of them inside one
five-file family: `.vNNN.slp`, `.vNNN.pkg.slp`, `.vNNN_<text>.slp`, `.<text>.vNNN.slp`. A
`.slp` and a `.pkg.slp` at the same version are the same labeling effort in two
representations (one references images, one embeds them) — five such pairs exist. Group by
**(containing directory, basename minus the version, extension)**: `labels.vNNN.slp` alone
occurs **57 times in 23 directories** spanning five species and both capture modes, so
grouping by basename would make one rice file supersede 56 unrelated ones. 88 versioned
basenames collide across directories; the registered wheat superset
`labels_sr_5-14DAG.v004.slp` exists in **three** directories at the same version, same byte
size.

**3. A directory is not a collection.** `SLEAP_sorghum/primary_6nodes/` holds 28 labels files
— a sorghum superset, a **soybean** collection, a soybean+sorghum generalist, per-labeler
inputs, and practice files. `SLEAP_wheat/seminal/` holds the wheat superset, three per-day
inputs, **two rice collections** and a wheat+rice generalist.
`SLEAP_multiple_species/primary_roots_6_nodes/` holds four species and no combined file. And
`SLEAP_wheat/`, `SLEAP_sorghum/`, `SLEAP_multiple_species/` hold no labels file at their own
top level. Nine unversioned files under `SLEAP_medicago_plates/combined_roots/` dated
2026-02-23 are the newest labeling on the share and the only trace of the MK24 and MK31
experiments — so an unversioned filename must not mean "scratch, don't read".

**4. Redaction — real names are at risk.** Two recorded video paths defeat a
"segment-after-a-user-marker" rule: `C:/Users/<name>/OneDrive - Salk Institute…` (the marker
is not the share's) and `Z:/<name>/experiments/…` (**no marker at all** — the name is the
first segment after the drive). Both are colleagues' names, and both land in every emitted row
for their collection. The rule needs a case-insensitive marker set (`users/`, `Users/`,
`home/`) **and** a first-segment rule for drive-rooted and UNC paths.
`scripts/pull_tf_reference.py`'s `_REDACTIONS` is the existing floor: three substitutions over
two entities.

**5. Digest semantics — settled, don't re-check.** `ArtifactManifestEntry.digest` is a
base64 MD5 over the whole file for uploads and `file://` references, at any size — chunking is
an I/O detail. Compare the **manifest entry's per-file digest**, never `Artifact.digest`,
which is computed over the manifest. `Artifact.manifest` fetches metadata via GraphQL with no
download. An entry added by `add_reference` to S3/GCS/Azure/HTTP carries that store's ETag
instead and is **unverifiable**, not mismatching.

**6. The keying gap needs no Bloom.** `cyl_arabidopsis…primary_6nodes` (6 nodes) and
`plate_arabidopsis…primary_8nodes` (8 nodes) are both arabidopsis primary; verified by reading
the real files. Both select the same `(arabidopsis, primary, age: null)` row, and
`lookup_skeleton` takes no `mode` argument at all. Node counts are file-derived and the mode is
derivable from the collection name, so this lands with no scan metadata. `skeletons.yaml` also
has no row for wheat, sorghum, medicago, alfalfa or covercress, and real files carry
auto-generated skeleton names (`Skeleton-1`, `Skeleton-2`) — which is why the existing weekly
check's `skeleton.name.partition("_")` cannot see these collections.

**7. Bloom is joinable in principle and its coverage was never checked.** The background doc's
"video filenames join to Bloom" establishes only that `cyl_scans_extended` is *selectable by*
`plant_qr_code`. Nobody ever ran those 125 wheat codes and counted rows. Do not treat Bloom
coverage as established. Bloom is **not** the source for plate labels (eberrigan, 2026-09-10).

**8. `is_negative` is never set.** The confirmed-absence marker is a real persisted `.slp`
property, but no file in this corpus sets it and `labeling/build_package.py` does not set it
when it writes deliberately-empty frames. Any count of confirmed absences is unreadable, not
zero.

**9. Small gotchas.** `Labels.skeleton` raises on **zero** skeletons as well as on more than
one — different messages, so don't conflate them. `sleap_io` 0.7.1 has no `Labels`-level
`user_instances`/`predicted_instances`; sum over `LabeledFrame`. `sio.Video(filename=[...],
open_backend=False)` round-trips to a `TypeError` — use `Video.from_filename` over real JPEGs.
`species` constrains `(genus, species)` UNIQUE, so two rows cannot share a non-null binomial.
`sleap_roots_contracts.RootType` is `("primary","lateral","crown")` with no `seminal` member.

---

## Decisions already made — do not re-litigate

| decision | who, when |
|---|---|
| ADDED-only spec delta; no live spec covers label provenance | eberrigan, earlier |
| Emit **evidence, not `LabelCard`s** — `registry_id`/`version` are meaningless for unregistered collections, which outnumber registered ones | eberrigan |
| Discovery scoped to the project owner's SLEAP directory only | eberrigan |
| `genotype`, `accession_id`, `experiment_name` are fine in this public repo; fields naming a **person** are not | eberrigan, 2026-09-02 |
| Artifacts committed to `inventory/` so they diff over time | eberrigan |
| Team calls wheat's seminal roots **crown**; `seminal`/`sr` map to the `crown` row and `RootType` gains no member | eberrigan |
| A multi-species labels file is **not card-eligible** and is flagged for splitting | eberrigan, 2026-09-10 |
| Bloom is not the source for **plate** labels | eberrigan, 2026-09-10 |
| The unit is the **labels file**, not the folder | eberrigan, 2026-09-10 |

---

## Out of scope, with the reason — so it does not get rebuilt

| cut | why |
|---|---|
| **Bloom reconciliation entirely** | Coverage was never verified (Facts 7). It costs `bloomctl` + supabase/httpx/cryptography (+25 packages) and production credentials that carry **write authority**, which then needs a `GET`-only data-plane requirement, a transport-interception test nobody could specify a mechanism for, and batching and quoting rules. None of it is needed for the headline finding. Make it its own change **after** someone runs one query and confirms rows come back. |
| **Species from Bloom** | Follows from the above. Report the name-derived species labelled as name-derived, and say plainly it is not evidence. |
| **Plant counts** | Only exist in scan metadata. Report scan counts, which are file-derived. |
| **A promotion/decision file** | See the governing principle. Print the candidate list; a person reads it. |
| **Adjudication, verdicts, disagreement states** | Nothing to disagree with once Bloom is out. |
| **Closed vocabularies with a set-equality lock** | Generated four blocking findings on its own. If statuses are wanted, document them as prose and let the existing repo precedent (a subset check) apply. |
| **Byte-identity across operating systems** | A deterministic sort order is enough. The cross-OS guarantee needed a committed golden fixture, `.gitattributes` surgery, and a path-separator rule, and it protected nothing anyone asked for. |

---

## Hard limits

Stop and ask rather than exceed any of these:

- **≤ 8 requirements**, **≤ 35 scenarios**, **≤ 200 lines** of `spec.md`
- **≤ 35 tasks**
- **one** `/review-openspec` round, then approval or a conversation — not another round
- if a review finding would push past a limit, **cut something instead of specifying more**

---

## How the last attempt failed

Seven review rounds. Each found real defects. Each was answered by **specifying more**, and
each revision introduced roughly as many new defects as it fixed — round 5 produced ~23
blocking findings, round 6 produced 17 of which 14 were newly introduced. The reviews were
good; the response to them was wrong.

The rule that would have prevented it: when a review flags a contradiction in a mechanism,
the **first** question is "should this mechanism exist?", not "how do I specify it better."
Roughly two thirds of the machinery in the old spec would have failed that question.

Second failure, mechanical: four interdependent documents edited in batches, with nothing
checking the seams. Stale counts, struck claims surviving in one file after being fixed in
another, scenarios asserting behaviour the prose had replaced. Keeping the spec under 200
lines is the cheapest possible fix for this.

---

## Process

### Branches — three PRs, not one

`feat/label-corpus-inventory` is **left alone**. Nothing was ever implemented on it — no
modules, no tests — so there is nothing to clean up, and its commit messages are a useful
record.

1. **`docs/roadmap-label-backfill`** — cherry-pick `62d1dc9` and `93b743f` (`docs/roadmap.md`
   only). Independent of everything; land it.
2. **`docs/label-model-inventory-design`** — cherry-pick `96dcc26` and `72b2aba`, then redo
   `da55b8f`'s design-doc edit by hand (it is the "re-keying does not happen" strike, ~5
   lines; that commit also touched spec files, so do not cherry-pick it whole). This is the
   prerequisite the model-inventory change needs in order to cite a merged path.
3. **`feat/label-inventory`** off **updated** `main` (the branch is 3 behind) — the new
   proposal. Commit this scope doc with it, and delete it when the proposal is approved.

### Commands

```bash
# 1. scaffold the change (do NOT run /new-feature — its full workflow is what produced
#    seven review rounds; use the pieces)
/openspec:proposal

# 2. validate on BOTH pinned CLI versions after every edit.
#    The `openspec` on PATH is @fission-ai/openspec 0.13.0 — a DIFFERENT numbering series.
#    Enumerate the cached 1.x copies and call them by absolute path:
for d in "$LOCALAPPDATA"/npm-cache/_npx/*/node_modules/.bin/openspec; do
  echo "$("$d" --version) <- $d"
done
# then, always both:
"$LOCALAPPDATA/npm-cache/_npx/477927d0c39997f0/node_modules/.bin/openspec" \
  validate <change-id> --strict     # 1.5.0
"$LOCALAPPDATA/npm-cache/_npx/c8a8ff1ac926c2be/node_modules/.bin/openspec" \
  validate <change-id> --strict     # 1.11.0

# 3. ONE review round, and say in the prompt that the scope is deliberately minimal and
#    that findings should propose cuts before additions
/review-openspec <change-id>

# 4. after eberrigan approves
/tdd            # or /openspec:apply
/pre-merge-check
```

**The 1.5.0 trap:** 1.5.0 rejects a requirement whose `SHALL` wraps past the first line of the
requirement body; every later version accepts it silently. Keep `SHALL` on the first body line
of every requirement, and validate on 1.5.0 *as well as* the newest — it has caught real
defects twice.

Python is managed by `uv`: always `uv run` / `uv add` / `uv tool`, never bare `python` or
`pip`.

### Stop and ask eberrigan when

- a mechanism is needed to record something a person decided
- a review finding cannot be fixed by cutting
- any hard limit would be exceeded
- a claim about Bloom, the share, or a library cannot be verified by running something
- the answer is "it depends on how you work" — that is always a question, never a design

### Coordination

- `#48` is open and touches `cli.py` with an end-of-file append. Put the new command group
  **after the `seed-registry` command and before the `validate` command** — none of `#48`'s
  four `cli.py` hunks touches there. `#48` also rewrites `openspec/project.md:44-51` and moves
  archiving to a separate follow-up PR.
- `#49` is structurally gated on this output; its §2 is the manual version of it. It also has
  a live question this change can answer: whether
  `wheat_5-14DAG_seminal_6nodes_labels` is the wheat half of the pooled wheat+rice file.
- `ci.yml`'s paths filter omits `README.md`, `scripts/**` and `inventory/**`. If anything in
  the change depends on those paths being tested, add them in their own commit — `ci.yml` is
  inside its own filter, so that commit self-tests.
