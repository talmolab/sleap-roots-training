# Tasks

## 1. Config schema (TDD)

- [ ] 1.1 Write the failing **oracle** test: a minimal valid config dict loads and validates,
      with defaults applied for omitted fields.
- [ ] 1.2 Write the failing test: a config missing a required field, or with a wrong-typed value,
      raises a clear error that names the offending field.
- [ ] 1.3 Run the tests to confirm they fail (schema not implemented yet).
- [ ] 1.4 Implement `sleap_roots_training/config.py`: the OmegaConf structured config (dataset,
      model/backbone, training, output/W&B), plus `load_config(path)` and `validate_config(cfg)`.
- [ ] 1.5 Run the tests to confirm they pass; `black --check` and `ruff check` clean.

## 2. CLI `validate` subcommand

- [ ] 2.1 Write the failing test: `validate <good.yaml>` exits 0 and prints a success message.
- [ ] 2.2 Write the failing test: `validate <bad.yaml>` exits non-zero and prints the error.
- [ ] 2.3 Implement the `validate` subcommand in `cli.py`, wiring `load_config` + `validate_config`.
- [ ] 2.4 Run the full test suite + lint; confirm green.

## 3. Per-epoch W&B logging (TDD)

- [ ] 3.1 Write the failing test: a config with no W&B logging cadence set resolves with per-epoch
      metric logging enabled by default.
- [ ] 3.2 Write the failing test: a config that explicitly disables per-epoch logging resolves with
      it disabled and still validates.
- [ ] 3.3 Add the W&B logging configuration (with per-epoch enabled by default) to the schema in
      `sleap_roots_training/config.py`; run the tests to confirm they pass.

## 4. Docs

- [ ] 4.1 Add an example config (`examples/`) and a README usage snippet; add a `docs/CHANGELOG.md`
      entry under `[Unreleased]`.
