# TensorFlow reference run fixtures

Committed W&B `config` + `summary` payloads for the canonical TensorFlow reference runs. These are
the durable form of the Tier-0 TF reference baseline (see [`docs/tf-reference.md`](../../../docs/tf-reference.md));
committing them lets the registry code be exercised against realistic W&B payload shapes without
network access, and locks the documented reference against drift.

## Provenance

- **Entity:** `eberrigan-salk-institute-for-biological-studies`
- **Project:** `sleap-roots`
- **Group:** `20250625_cyl_arabidopsis_primary_receptive_field`
- **Run-name suffix:** `_training_v000`
- **Backend:** TensorFlow `sleap-train` (`sleap_version` = `1.4.1a2` in every `config`)
- **Captured with:** `wandb` client `0.28.0`
- **Capture date:** 2026-07-20
- **Contents:** `config` and `summary` JSON only — **no** W&B API key, netrc, or other secret.
- **Redaction:** the raw payloads embed an internal SMB host and user in their path strings
  (`config_path`, `filename`, `runs_folder`, `*_labels`, `model_path`). Both segments are redacted
  to `REDACTED-HOST` / `REDACTED-USER` before committing; the audit-relevant run-name, timestamps,
  group, and split are left intact. `scripts/pull_tf_reference.py` applies the same redaction on
  every pull, so a refresh stays byte-identical.

This experiment is a `model.backbone.unet.max_stride` **sweep**, not a replicate set. Two runs each
at strides 16/32/64 and a single run at stride 8 (seven runs total). Do not pool or range metrics
across different strides. See `docs/tf-reference.md` for the full interpretation.

| run id | `max_stride` | summary metrics? |
|---|---|---|
| `ijn85j6w` | 8 | none (only stride-8 run — no usable result) |
| `nxe8xgsd` | 16 | yes |
| `v7rdm7cd` | 16 | yes |
| `qilbptpp` | 32 | yes |
| `1tryadtu` | 32 | yes |
| `yenwgpjq` | 64 | yes |
| `26ryyfu2` | 64 | none |

## Files

For each run id: `<run_id>.config.json` (the run `config`) and `<run_id>.summary.json` (the run
`summary`). Fourteen files total, pretty-printed and key-sorted.

## Refresh

Re-capture (requires a `wandb login` session or `WANDB_API_KEY`):

```bash
uv run python scripts/pull_tf_reference.py
```

The script writes deterministically (LF newlines, sorted keys), so a refresh with the same `wandb`
client version reproduces byte-identical files. A different client version may change the payload
shape — update the "Captured with" version above if so.
