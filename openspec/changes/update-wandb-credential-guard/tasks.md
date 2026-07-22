## 1. Tests first (TDD)

All netrc tests set `WANDB_API_KEY` and `NETRC` explicitly and point `HOME`/`USERPROFILE` at a temp
dir so they never read the developer's real `~/.netrc` and run identically on every OS.

- [x] 1.1 Keep `test_require_api_key_passes_when_set` (env var satisfies the guard) and update
      `test_require_api_key_raises_when_unset` to also isolate netrc (`HOME`/`USERPROFILE` -> empty
      temp dir, `NETRC` unset) — verifies the guard still raises `RuntimeError` when neither source
      resolves.
- [x] 1.2 Add `test_netrc_via_env_var_satisfies_guard`: `WANDB_API_KEY` unset; write a temp netrc
      with an `api.wandb.ai` machine entry and point `NETRC` at it — verifies the guard passes.
- [x] 1.3 Add `test_unix_netrc_satisfies_guard`: `WANDB_API_KEY`/`NETRC` unset; write `~/.netrc`
      (via `HOME`) with an `api.wandb.ai` entry — verifies the `~/.netrc` branch passes.
- [x] 1.4 Add `test_windows_netrc_satisfies_guard`: `WANDB_API_KEY`/`NETRC` unset; write only
      `~/_netrc` (no `~/.netrc`) via `HOME`/`USERPROFILE` — verifies the `~/_netrc` branch passes on
      any OS (covers the Windows `wandb login` location the issue calls out).
- [x] 1.5 Add `test_malformed_netrc_is_treated_as_no_credential`: `WANDB_API_KEY` unset; point
      `NETRC` at a temp file with malformed contents that make `netrc.netrc(path)` raise
      `NetrcParseError` — verifies the guard swallows it and raises the clear `RuntimeError` (does NOT
      propagate the parse error).

## 2. Implementation

- [x] 2.1 In `src/sleap_roots_training/registry/config.py`, add module-level
      `_resolve_netrc_path() -> Path | None` mirroring wandb: `NETRC` env (expanded) if set, else
      `~/.netrc` if it exists, else `~/_netrc` if it exists, else `None` (pathlib, not `os.path`).
- [x] 2.2 Add module-level `_has_wandb_credential() -> bool`: return `True` if `WANDB_API_KEY` is
      set; else resolve the netrc path (return `False` if `None`) and return
      `bool(creds and creds[2])` from `netrc.netrc(path).authenticators("api.wandb.ai")` — i.e.
      require a **non-empty password** (stdlib `netrc`, module-level import — no `import wandb`);
      return `False` on `(NetrcParseError, OSError)` (malformed/unreadable/missing).
- [x] 2.3 Update `require_api_key()` to raise `RuntimeError` only when `_has_wandb_credential()` is
      `False`, with a clear message naming both sources (e.g. set `WANDB_API_KEY` or run
      `wandb login`). Update its docstring. Keep the public function name (callers/tests unchanged).

## 3. Verification

- [x] 3.1 `uv run pytest tests/test_registry_config.py -v` (new + existing tests green).
- [x] 3.2 `uv run black --check src/sleap_roots_training tests` and
      `uv run ruff check src/sleap_roots_training`.
- [x] 3.3 `uv run pytest --cov=src/sleap_roots_training --cov-report=term-missing tests/` (coverage
      maintained).
- [x] 3.4 `openspec validate update-wandb-credential-guard --strict`.
- [x] 3.5 Add a `docs/CHANGELOG.md` Unreleased entry.

## 4. Review response (PR #13)

- [x] 4.1 Blank-password bug: `_has_wandb_credential()` requires a non-empty password
      (`creds[2]`), so a stale/partially-written netrc no longer passes the guard (mirrors
      `wandb==0.28.0` `wbnetrc.read_netrc_auth_with_source`). Regression test
      `test_blank_password_netrc_is_not_a_credential`.
- [x] 4.2 Narrow `except Exception` -> `except (netrc.NetrcParseError, OSError)`; move
      `import netrc` to module level.
- [x] 4.3 Switch `_resolve_netrc_path()` to `pathlib.Path`; fix its docstring so the `NETRC`
      branch (returned as-is) is distinguished from the existence-checked fallbacks.
- [x] 4.4 Add shared `tests/conftest.py` `isolate_netrc` fixture; use it in
      `tests/test_registry_cli.py::test_execute_without_api_key_fails_before_prompt` (was not
      netrc-isolated) and refactor `tests/test_registry_config.py` onto it.
- [x] 4.5 Add branch-coverage test `test_other_machine_netrc_is_not_a_credential`.
- [x] 4.6 Fix stale docstring in `cli.py::_require_api_key`.
- [x] 4.7 Rebase onto current `main` to drop `docs/roadmap.md` stale-branch drift.
