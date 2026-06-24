# sleap-roots-training

Config-driven training and evaluation of [SLEAP](https://sleap.ai) root models on the
[`sleap-nn`](https://github.com/talmolab/sleap-nn) backend, with
[Weights & Biases](https://wandb.ai) experiment tracking and Run:AI for compute.

This package replaces the notebook-based `eberrigan/sleap-roots-training` workflow with a
reproducible, tested, OmegaConf-driven pipeline. It is built out tier by tier following the
program roadmap (generalist + per-crop keypoint models → segmentation masks).

## Status

Early scaffold (alpha). The pipeline is being implemented incrementally — see
`openspec/` for in-progress changes and `docs/CHANGELOG.md` for releases.

## Install (development)

```bash
uv sync --group dev
uv run sleap-roots-training --help
```

## Development

This repo follows the Talmo lab conventions (uv, ruff/black/pytest, OpenSpec, GitHub
Actions CI). Common tasks are available as Claude Code dev commands in `.claude/commands/`.

```bash
uv run black --check src/sleap_roots_training tests
uv run ruff check src/sleap_roots_training
uv run pytest
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
