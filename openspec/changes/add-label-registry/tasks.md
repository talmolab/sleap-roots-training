## 0. Gate on the contract

- [ ] 0.1 Confirm `sleap-roots-contracts` `add-label-selection-contract` is merged and released as
      `0.1.0a6` (this change cannot proceed before it exists). **Not `0.1.0a5`** — that version was
      taken concurrently by the prediction-manifest contract and carries no `LabelCard`/`Mode`
- [ ] 0.2 Bump the `sleap-roots-contracts` pin in `pyproject.toml` to `0.1.0a6` (from `0.1.0a3`)
- [ ] 0.3 Confirm against the live `sleap-roots-labels` registry which artifact `type` string the
      existing eight collections use (resolves the Design open question; the verify path must match)

## 1. Mode vocabulary ownership

- [ ] 1.1 (RED) Test that an unknown `mode` is still rejected with a clear error naming the row and
      value (existing behaviour must not regress), and that the accepted set equals
      `get_args(Mode)` from the contract
- [ ] 1.2 (GREEN) Replace `MODE_VOCAB` (`registry/chooser.py:23`) with `from sleap_roots_contracts
      import Mode`, checking membership via `get_args(Mode)`; delete the local frozenset
- [ ] 1.3 Confirm no other module references `MODE_VOCAB`; leave `SPECIES_VOCAB` in place (out of
      scope)

## 2. LabelCard assembly from a labeling package

- [ ] 2.1 (RED) Test building a `LabelCard` from a fixture labeling-package directory
- [ ] 2.2 (RED) Test that a missing required field raises a clear error naming the field
- [ ] 2.3 (GREEN) Implement package-metadata → `LabelCard` assembly in `registry/cards.py`
- [ ] 2.4 (RED) Test that `mode="cyl"` is rejected with an error naming the accepted vocabulary
      (contract enforces; assert the error surfaces usefully from this path)

## 3. Manifest checks

- [ ] 3.1 (RED) Test that a package with no `sample_manifest.csv` is rejected
- [ ] 3.2 (RED) Test that `n_frames` disagreeing with the manifest row count is rejected, and the
      error names both the declared count and the actual row count
- [ ] 3.3 (RED) Test that a matching count passes
- [ ] 3.4 (GREEN) Implement the manifest presence + row-count checks in the pure, pre-network stage

## 4. Publish path

- [ ] 4.1 (RED) Test that the pure validation stage runs with `wandb` unavailable
- [ ] 4.2 (RED) Test (with `wandb` faked) that publishing `add_dir`s the package, attaches the card as
      artifact metadata, and links the alias
- [ ] 4.3 (GREEN) Implement `publish_labels(...)` mirroring `publish_card` (`registry/publish.py:27`)
      — lazy `wandb` import, `add_dir`, `log_artifact`, `link_artifact`
- [ ] 4.4 (RED) Test that no upload occurs when validation fails
- [ ] 4.5 (RED) Test that the published metadata carries no `data_path`

## 5. Verification path

- [ ] 5.1 (RED) Test that verification reports alias, card validity, and manifest presence
- [ ] 5.2 (RED) Test that a legacy boolean-key-tag collection is reported as failing validation
      rather than raising
- [ ] 5.3 (GREEN) Implement verification mirroring the existing registry verification command

## 6. CLI + docs

- [ ] 6.1 Wire `publish-labels` into the CLI, following the existing seed command's confirmed-execution
      pattern
- [ ] 6.2 Update `openspec/project.md` and `docs/roadmap.md` — Tier 2 notes `LabelCard` as a
      prerequisite for the lineage oracle; record that the contract has landed
- [ ] 6.3 `openspec validate add-label-registry --strict`
- [ ] 6.4 `/pre-merge-check`

## 7. Close out

- [ ] 7.1 Publish one real labeling package end-to-end and round-trip it (issue #10 definition of
      done), confirming a dry-run sweep can resolve it
- [ ] 7.2 Confirm #11 (backfill + rename the eight legacy collections) captures anything deferred here
