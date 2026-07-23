## Why

`require_api_key()` rejects any operation unless `WANDB_API_KEY` is set, but operators who ran
`wandb login` authenticate via a netrc entry for `api.wandb.ai` that `wandb.Api()`/`wandb.init()`
read automatically — so the real network calls would succeed, yet our guard fails them. This forces
a logged-in operator to redundantly export `WANDB_API_KEY` just to run `seed-registry --execute` /
`--verify` (hit during the real seed acceptance run).

## What Changes

- Broaden the credential guard from "`WANDB_API_KEY` is set" to "a **resolvable wandb credential**
  exists" — `WANDB_API_KEY` in the environment **OR** a netrc entry for `api.wandb.ai`.
- Resolve netrc cheaply and wandb-free using the stdlib `netrc` module (no `import wandb` in
  `config.py`), mirroring wandb's own file resolution precedence so a `wandb login` session is
  detected on **every** platform: the `NETRC` env var if set, else `~/.netrc`, else `~/_netrc`
  (the file `wandb login` writes on Windows). The resolved path is passed explicitly to
  `netrc.netrc(path)`.
- Treat a malformed/unreadable netrc as "no credential" (never raise a parse error from the guard).
- Keep the fail-fast behavior and a clear error message when **no** credential is resolvable
  anywhere — that is the valuable part; only stop rejecting a valid `wandb login` session.

### Why resolve the path instead of the issue's one-line `netrc.netrc()`

The issue sketched `netrc.netrc().authenticators("api.wandb.ai")`. Verified against CPython 3.11
`netrc.py` (L70), the **no-argument** `netrc.netrc()` reads only `os.path.expanduser("~/.netrc")` —
it does not honor the `NETRC` env var and never checks `~/_netrc`. So the literal one-liner would
still reject a Windows `wandb login` session (`~/_netrc`) and any `NETRC`-overridden path — the very
papercut this change fixes, and the case the issue's testing note ("cover both `~/_netrc` and
`~/.netrc`") calls out. Passing wandb's resolved path to `netrc.netrc(path)` also sidesteps the
stdlib POSIX permission check (`_security_check`, gated on the no-arg form), so a `wandb login`
session is detected regardless of file mode. Resolution logic matches wandb
(`wandb/sdk/lib/wbauth/wbnetrc.py::_get_netrc_file_path`).

## Impact

- Affected specs: `model-registry` (MODIFIED: `Environment-Driven Registry Configuration`,
  `Registry Verification Command`, `Registry Seeding CLI with Confirmed Execution`).
- Affected code: `src/sleap_roots_training/registry/config.py` (`require_api_key`, new
  `_has_wandb_credential` helper); callers unchanged in `src/sleap_roots_training/cli.py`
  (`_require_api_key` at L26, `--verify` at L99, `--execute` at L131).
- Tests: `tests/test_registry_config.py`.
- Out of scope (follow-up): mirror the identical guard in `talmolab/sleap-roots-predict`
  (`sleap_roots_predict/model_registry.py` → `WandbRegistrySource._require_key`, L147, called from
  L173/L258) so both repos resolve credentials the same way. Not in this workspace; separate PR.
