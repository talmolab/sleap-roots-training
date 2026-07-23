## ADDED Requirements

### Requirement: Committed TensorFlow Reference Payload Fixtures

The repository SHALL commit, under `tests/fixtures/tf_reference/`, the W&B `config` and `summary`
JSON of the seven canonical runs of the `20250625_cyl_arabidopsis_primary_receptive_field` group
(run-name suffix `_training_v000`) from `eberrigan-salk-institute-for-biological-studies/sleap-roots`
(run ids `ijn85j6w`, `nxe8xgsd`, `v7rdm7cd`, `qilbptpp`, `1tryadtu`, `yenwgpjq`, `26ryyfu2`), so the
reference and its realistic W&B payload shapes are available without network access. The fixtures
SHALL contain only `config` and `summary` data and SHALL NOT contain any W&B API key, netrc
contents, or other secret. A reproducible capture script and a provenance manifest SHALL be committed
alongside the payloads; the manifest SHALL record the entity, project, group, run-name suffix, the
seven run ids with their `max_stride`, the `sleap_version` of the runs (`1.4.1a2` — the marker that
these are the TensorFlow `sleap-train` backend), the `wandb` client version used to capture, the
capture date, a "config/summary only — no secrets" note, and refresh instructions.

#### Scenario: Payloads are committed for every canonical run

- **WHEN** the fixtures directory is inspected
- **THEN** a `config` JSON and a `summary` JSON are present for each of the seven canonical run ids
  (fourteen payload files)
- **AND** the provenance manifest and the capture script are present

#### Scenario: Fixtures carry no secrets

- **WHEN** the committed fixture files are scanned for credential markers (for example
  `WANDB_API_KEY`, a 40-hex key, `password`, `netrc`, or non-empty `api_key`/`token`/`secret` values)
- **THEN** no file matches, and the scan names any offending file if one did

### Requirement: Registry Code Exercised Against Committed Payloads

At least one registry test SHALL exercise registry code against the committed real W&B payloads in
`tests/fixtures/tf_reference/` instead of a hand-rolled dictionary, so the code is proven against
realistic payload shapes offline. Concretely, for **every** committed run `config`, the seed-run
lineage produced by `registry/lineage.py` SHALL be shown to coexist with that config: no lineage key
SHALL collide with any key of the config (compared over its full nested keyset, not just top-level),
and the combined mapping SHALL round-trip through JSON unchanged. This is an illustrative
shape-coexistence guard (the registry does not itself consume training-run configs); the documented
reference is locked separately below.

#### Scenario: Lineage keys are disjoint from every real config and round-trip through JSON

- **WHEN** the registry lineage mapping is combined with each committed real W&B run `config`
- **THEN** no lineage key equals any key present in that config's full nested keyset
- **AND** the combined mapping is unchanged after a `json.dumps` / `json.loads` round-trip

### Requirement: Documented TensorFlow Reference Baseline

The repository SHALL document the TensorFlow reference in `docs/tf-reference.md`, and a test SHALL
lock the documented claims against the committed fixtures **by reading `docs/tf-reference.md`** so the
documentation cannot silently drift from the data. The documentation and the lock test SHALL reflect
that:

- the group is a `model.backbone.unet.max_stride` **sweep** — strides 8, 16, 32, 64, with two runs
  each at strides 16/32/64 and a single run at stride 8 (**seven runs total**) — **not** a replicate
  set, so metrics MUST NOT be pooled or ranged across different strides;
- same-config spread is reported as a **range** from the two genuine same-stride pairs — stride16
  `dist_avg` 0.989–1.710 (~1.73×) and stride32 `dist_avg` 1.383–2.078 (~1.50×) — never as a single
  point (stride64's second run has no metrics, so stride64 is not a usable pair);
- `oks_map` is **excluded** as broken (it reads below ~0.05 across every run with a summary — roughly
  0.009–0.046), with the reason stated;
- the two runs with no summary metrics (`ijn85j6w` at stride8, `26ryyfu2` at stride64) are **noted**
  rather than dropped, including that `ijn85j6w` is the only stride8 run so stride8 has no usable
  result;
- the **observability gap** is recorded: these runs logged only final eval metrics
  (`scan_history()` returns zero rows — no per-epoch loss, no epoch count), which is why the Tier-0
  onboarding repro (#1) could not be compared against the original and why the Tier-1 sleap-nn
  pipeline must log per-epoch loss.

#### Scenario: Documentation reports the sweep per-stride, not pooled

- **WHEN** `docs/tf-reference.md` presents the metrics
- **THEN** it groups them by `max_stride` and states the group is a sweep of seven runs (one at
  stride8), not replicates
- **AND** it does not pool or range `dist_avg` across different strides

#### Scenario: Same-config spread is reported as same-stride ranges

- **WHEN** the documentation reports run-to-run spread
- **THEN** it reports the stride16 `dist_avg` range 0.989–1.710 and the stride32 `dist_avg` range
  1.383–2.078
- **AND** it does not quote a single run as *the* TF number

#### Scenario: Broken metric is excluded with a reason

- **WHEN** the documentation lists reported metrics
- **THEN** `oks_map` is excluded and the reason (it is broken, below ~0.05 everywhere) is stated

#### Scenario: Missing-summary runs are noted

- **WHEN** the documentation covers all seven runs
- **THEN** `ijn85j6w` (stride8) and `26ryyfu2` (stride64) are noted as having no summary metrics
- **AND** it is stated that stride8 (only `ijn85j6w`) has no usable result

#### Scenario: Documented claims are locked against the fixtures

- **WHEN** the reference-lock test runs
- **THEN** it derives each run's `max_stride` from its committed `config` and asserts the stride
  multiset is `{8: 1, 16: 2, 32: 2, 64: 2}`
- **AND** it asserts `ijn85j6w` and `26ryyfu2` have no summary metrics and every summarized run's
  `oks_map` is below the broken ceiling (~0.05)
- **AND** it derives the stride16 and stride32 `dist_avg` ranges from the fixtures and asserts they
  match the documented ranges within a stated float tolerance
- **AND** it reads `docs/tf-reference.md` and confirms it states the documented same-stride ranges,
  the sweep framing, the `oks_map` exclusion, and both missing-summary run ids
- **AND** it fails if the fixtures or the documentation no longer support the documented claims
