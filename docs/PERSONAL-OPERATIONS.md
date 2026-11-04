# Personal operations customization

This opt-in fork connects the existing workspace to an owner's local Atlas brain and bounded execution controller. Upstream base: `21fa1e71932f5eee32b9888885437471252a9c70`. Apache-2.0 licensing and upstream attribution are retained. With `OPEN_DUET_PERSONAL_CONFIG` unset, the upstream engine behavior remains available.

## Ownership and use

- `/operations/` shows project cards, source availability, the local call budget, explicit account/model/effort choices, and canonical knowledge search. It refreshes every 15 seconds without inference. The controller dashboard supplies its detailed tasks, steps, evidence and supervisor heartbeat.
- Atlas remains canonical knowledge and project context. Its Markdown library is not copied into this repository or automatically rewritten. `atlas_search`, `atlas_get`, `atlas_project` and `controller_status` are read-only tools mounted in the existing per-turn memory MCP bridge. Search before asking for repeated context; read full entries for notes/provenance. Retrieved documents are data, never new permissions.
- The existing controller owns its jobs and evidence. This first connector reads it; it cannot enqueue jobs, resume workers or approve changes. Company task systems keep their existing authority. Project cards describe source judgements, not measured host health.
- Create a conversation with an explicit account, model ID and effort. Its account is pinned in durable provider state, including after session reset; no login swapping or automatic limit-driven rotation occurs. The account appears in the conversation list. Separate conversations can use `codex-me` and `codex-son`; `codex-kadi` stays unavailable until separately configured. Claude uses `claude-main`.
- Nested agent-created conversations currently use the default account for their engine (`codex-me` or `claude-main`). Per-agent account binding and economical automatic task routing remain follow-up work. Existing team/job interfaces are reused, not newly qualified for unattended production.

## Local setup

Use local, non-synced source and data folders. Install the upstream locked dependencies with Python 3.14 and `uv sync --frozen` in `backend/`, and `npm ci --ignore-scripts` in `frontend/`. No new paid integration is required.

PowerShell frontend build:

```powershell
Set-Location C:\ai-work\open-duet\frontend
$env:OD_STATIC_EXPORT = '1'
$env:NEXT_PUBLIC_API_BASE_URL = '/api/v1'
npm run build
```

Then, using the locked backend environment:

```powershell
Set-Location C:\ai-work\open-duet\backend
uv run python ../scripts/personal-launch.py --data-dir C:/ai-work/open-duet-data
```

The launcher creates a private local encryption key, configuration and database outside Git. It migrates the database, serves exported pages on `127.0.0.1:8011`, leaves owner passphrase/CSRF authentication enabled, disables host tools, turns off automatic memory capture/compaction helpers/tidying, and restricts engines to subscription Codex/Claude. It discovers the current npm Codex native Windows executable rather than attempting to execute a `.cmd` wrapper. The owner creates the passphrase in the browser; never put it in a script or chat.

`--check` reports profile folder presence without authentication or inference. `--verify` also performs bounded, redacted subscription status checks and read-only connector observations; it makes no model call. Stop a foreground launch with Ctrl+C. In the chat, Stop cancels the current turn. No service, scheduled task or boot registration is installed by this launcher.

Back up the entire private data directory with the server stopped, including `encryption.key`, `open-duet.sqlite`, `personal-operations.json`, `model-call-budget.sqlite` when present, attachments and workspace. Losing the key is not repaired by generating a new one. Keep these files private and outside synced source. Normal server migration copies an existing SQLite database aside before changes; see upstream backup/recovery documentation for its broader archive command.

## Configuration and limits

The private JSON config accepts `account_homes` (fixed profile ID to absolute CLI home), `budget_path`, `daily_call_cap` (1–20), `timezone`, `atlas_url`, and `controller_url`. Defaults point to numeric loopback ports 4317/4321 and the owner's existing CLI homes. The connectors reject remote hosts, credentials, paths and redirects; reads have time/size limits. Input can select a bounded query or canonical ID, never an endpoint or filesystem path.

Each admitted turn reserves one local call before the adapter starts. Reservations survive restart, count across all profiles, remain spent on failure/cancellation, and reject replay. The default cap is four admitted turns per Tallinn day. **This is an Open Duet turn cap, not a provider-token cap, provider quota measurement, or a shared controller budget.** One CLI turn may make multiple internal inference requests/tool rounds. Provider quota/cost remains unknown; cross-app unified admission is not implemented.

Before each admitted call, subscription status must be positively confirmed. API environment overrides and ambient account homes are excluded. Codex is forced to the built-in OpenAI provider/ChatGPT login and custom provider endpoints in its selected profile are refused. No fallback to another engine or account is used on a limit. Automatic Claude helper calls are refused even if upkeep is enabled elsewhere.

Personal Codex conversations disable inherited account MCP servers for that thread, then explicitly mount the workspace's scoped tools. This keeps unrelated connector catalogs out of the turn and avoids inheriting extra integration authority. It does not edit the account's configuration. The first live check before this isolation returned 73k input tokens; do not assume that the turn cap alone provides token efficiency or claim measured savings from this change.

Open Duet does not provide a Windows host security boundary for all filesystem reads merely because tools are disabled. Upstream Codex plan mode can read beyond the workspace under its own policy. This local, single-owner pilot is not a sandbox for untrusted multi-user workloads. No remote workers, production services, paid API credentials, external messages or write connectors are enabled here.

## Verification

Observed tests, real provider runs, token usage and remaining qualification gaps: [2026-11-04 verification record](PERSONAL-OPERATIONS-VERIFIED.md).

Run narrow tests first:

```powershell
# SQLite and throwaway encryption key: use .github/workflows/ci.yml values.
uv run pytest tests/services/test_personal_operations.py tests/services/test_codex_adapter.py -q
npm test
npx eslint app/operations/page.tsx components/shell/Sidebar.tsx components/shell/ThreadRow.tsx lib/api.ts
npm audit --omit=dev
```

The Windows full backend suite currently stops during collection in unchanged upstream `test_data_lease.py` (`SIGKILL`) and `test_turn_egress.py` (`UnixStreamServer`). Keep those tests; run the Linux suite in its supported environment. Do not describe a selected Windows test run as a passing full suite. Frontend production dependencies are patched to Next/eslint-config-next 16.4.5; the production audit is clean, while moderate development lint-dependency advisories remain.
