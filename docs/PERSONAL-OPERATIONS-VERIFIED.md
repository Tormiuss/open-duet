# Verification record — 2026-11-04

Environment: Windows 11, Python 3.14.10, uv 0.13.7, Codex CLI 0.166.0, Next 16.4.5. Local owner-only server and private SQLite data; no production server change or extra paid service.

## Observed

- Fork and isolated source created from upstream `21fa1e71932f5eee32b9888885437471252a9c70`; upstream remote retained.
- Owner set the passphrase directly in the browser. Login survived backend restarts. `/operations/` loaded real project cards, controller state, account choices and budget; canonical search returned results. Source reads and status probes made no inference calls.
- Subscription status confirmed for codex-me, codex-son and claude-main; codex-kadi folder absent. Quota remains unknown.
- Real codex-son conversation completed, reported model `gpt-6.1-terra`, input 72,894 / output 190 / cached input 57,344. Full Atlas retrieval succeeded. Search returned a transient unknown-coverage error; independent read-tool checks subsequently succeeded. Connector deadlines were made bounded but less brittle under concurrent local tests; the exact initial exception was not retained, so timeout is a hypothesis, not a proven cause.
- Real codex-me conversation after inherited-MCP isolation completed, reported model `gpt-6.1-terra`, input 50,303 / output 102 / cached input 45,056. Atlas search succeeded and returned the canonical entry ID. Different prompts/context/accounts prevent a controlled savings claim.
- The UI explicitly requested medium effort for both. Inspection found provider-state replacement dropped the saved effort after completion; merge/reset preservation was corrected and regression-tested. Do not infer that a post-run missing effort meant the original request had no effort.
- A live model-catalog response used reasoning-effort objects rather than strings, causing an upstream engine-list response-validation error. Both shapes now normalize to strings; the engine selector subsequently loaded in the browser.
- Two turn reservations remain spent. No automatic helper inference, external messaging, remote worker, paid API use or production deployment was enabled. No real Claude turn or delegated-team acceptance is claimed.

## Automated checks

- Selected Windows backend run: **274 passed** covering account policy, runtime, adapters, engines, thread API and authentication. Follow-up core run after live protocol/tool fixes: **99 passed**. Final personal-policy/runtime run after effort-preservation fixes: **49 passed**.
- Frontend: **341 passed**, static export/type check succeeded. Changed-file ESLint: zero errors; one existing unused `searching` warning in Sidebar. Initial test run with a relative build API URL caused three URL-expectation failures; rerunning with the normal test environment passed all 341. No test expectations were weakened.
- `npm audit --omit=dev`: zero vulnerabilities. Sixteen moderate development dependency advisories remain in minimatch/eslint dependency chains; no forced incompatible ESLint downgrade was applied.
- Full backend suite: **not passed**. Collection stopped in unchanged upstream Linux-specific `tests/core/test_data_lease.py` (missing SIGKILL on Windows) and `tests/core/test_turn_egress.py` (UnixStreamServer). Keep Linux CI coverage and qualify that environment separately.
- `git diff --check` passed before publication. Private runtime/config/key/auth/Atlas content excluded from source changes.

## Acceptance still pending

Per-agent profile binding, unified controller/workspace admission and dispatch, actual token caps/context tuning, general decomposed-step execution, real Claude/team/Stop/recovery qualification, authenticated remote workers and unattended reboot operation. The app is a local pilot with a read-only integration boundary. See [the runbook](PERSONAL-OPERATIONS.md).
