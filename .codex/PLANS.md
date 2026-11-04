# Personal operations fork

2026-11-04 owner explicitly approved forking/customizing Open Duet and integrating Personal Atlas, controller and existing projects. Fork: Tormiuss/open-duet; upstream base21fa1e71932f5eee32b9888885437471252a9c70. Local source/runtime remain outside synced storage. Do not copy private knowledge, credentials or runtime databases into Git.

1. Create/verify fork and isolated build environment; retain upstream license and sync remote.
2. Add an opt-in personal-operations profile: isolated named subscription accounts, pinned conversation account, no account fallback, bounded turn admission and automatic background AI off.
3. Add bounded read-only Atlas search/full-entry/project tools and controller status. Atlas is canonical knowledge; ctl owns its existing task execution; Company OS retains business task authority.
4. Add an operator workspace showing source project cards, canonical knowledge search, account choices and controller state; reuse existing agent/team/chat features.
5. Test narrow boundaries first, then relevant backend regressions, frontend validation/build and real browser flows with disposable local data. Verify actual account/model behavior without launching unbounded work.
6. Document actual status, limitations, launch/stop/recovery and next steps; publish only reviewed source changes to the user's fork branch. No production installation or private content publication.

## Delivered 2026-11-04

Fork and opt-in local workspace implemented; Atlas/ctl remain read-only connectors with separate authority. Three subscription logins confirmed; two actual Codex-account conversations completed. The first exposed a transient search failure, high context usage and upstream model-catalog shape mismatch; the follow-up search passed after protocol/isolation fixes. Effort preservation was subsequently corrected and tested. Exact evidence and incomplete acceptance: docs/PERSONAL-OPERATIONS-VERIFIED.md. Windows selected backend checks274/99/final49 passed; frontend341 passed and static build passed. Whole backend suite stops at Linux-only collection APIs; no claim of full-suite, Claude/team/remote/unattended acceptance. No token-efficiency claim. Source publication is limited to this reviewed branch; private data stays outside Git.
