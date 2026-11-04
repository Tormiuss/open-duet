import asyncio
import json
from types import SimpleNamespace

import pytest

from app.services import personal_operations as ops


@pytest.fixture
def personal(monkeypatch, tmp_path):
    path = tmp_path / "profile.json"
    settings = {"budget_path": str(tmp_path / "budget.sqlite"), "daily_call_cap": 2}
    settings["account_homes"] = {key: str(tmp_path / f".{key}") for key in ops.PROFILE_IDS}
    path.write_text(json.dumps(settings))
    monkeypatch.setenv("OPEN_DUET_PERSONAL_CONFIG", str(path))
    return settings, path


def test_opt_in_preserves_original_environment(monkeypatch):
    monkeypatch.delenv("OPEN_DUET_PERSONAL_CONFIG", raising=False)
    source = {"OPENAI_API_KEY": "example", "PATH": "tools"}
    assert ops.subscription_environment(source) is source


async def test_concurrent_account_environment_isolation(personal):
    async def env(account):
        with ops.use_profile("codex", account):
            await asyncio.sleep(0)
            return ops.subscription_environment({"PATH": "tools", "OPENAI_API_KEY": "secret", "anthropic_api_key": "secret", "NODE_OPTIONS": "inject", "CODEX_HOME": "wrong"})
    me, son = await asyncio.gather(env("codex-me"), env("codex-son"))
    assert me["CODEX_HOME"].endswith(".codex-me")
    assert son["CODEX_HOME"].endswith(".codex-son")
    assert set(me) == {"PATH", "CODEX_HOME", "CLAUDE_CONFIG_DIR"}
    assert ops._profile.get() is None
    with pytest.raises(ValueError):
        ops.profile_for("claude", "codex-son")
    with pytest.raises(ValueError):
        ops.profile_for("openai_compat")


def test_durable_budget_counts_all_accounts_and_refuses_replays(personal):
    ops.reserve_call("first", "codex-me")
    with pytest.raises(ValueError, match="already reserved"):
        ops.reserve_call("first", "codex-son")
    ops.reserve_call("second", "claude-main")
    with pytest.raises(ValueError, match="cap reached"):
        ops.reserve_call("third", "codex-son")


@pytest.mark.parametrize("url", ["https://127.0.0.1:4317", "http://evil.test", "http://127.0.0.1:4317/other", "http://user:password@127.0.0.1:4317", "http://127.0.0.1:4317?x=1"])
def test_connector_rejects_nonfixed_sources(personal, url):
    settings, path = personal
    path.write_text(json.dumps({**settings, "atlas_url": url}))
    with pytest.raises(ValueError):
        ops._endpoint("atlas")


async def test_read_tools_bound_input_and_use_canonical_routes(personal, monkeypatch):
    calls = []
    async def source(name, path, params=None):
        calls.append((name, path, params))
        return {"query": "routing", "hits": list(range(20))}
    monkeypatch.setattr(ops, "read_source", source)
    assert len((await ops.read_tool("atlas_search", {"query": "routing"}))["hits"]) == 8
    assert calls == [("atlas", "/api/search", {"q": "routing", "type": "entry"})]
    for name, args in [("atlas_get", {"id": "../private"}), ("atlas_search", {"query": "x", "url": "http://evil"}), ("atlas_log", {}), ("controller_status", {"command": "start"})]:
        with pytest.raises(ValueError):
            await ops.read_tool(name, args)


async def test_outage_is_unknown_not_idle(personal, monkeypatch):
    async def unavailable(*args):
        raise OSError("offline")
    monkeypatch.setattr(ops, "read_source", unavailable)
    result = await ops.overview()
    assert all(source["state"] == "unavailable" and source["data"] is None for source in result["sources"].values())


async def test_auth_refuses_api_login_without_model_call(personal, monkeypatch):
    from app.services import cli_probe, codex_adapter
    monkeypatch.setattr(codex_adapter, "resolve_codex_executable", lambda: "codex")
    async def api_login(*args, **kwargs):
        return SimpleNamespace(ok=True, stdout="Logged in using an API key", stderr="")
    monkeypatch.setattr(cli_probe, "run", api_login)
    with pytest.raises(ValueError, match="not confirmed"):
        await ops.require_subscription("codex")


async def test_pinned_account_survives_reset(personal, db_session):
    from app.db.models import Thread
    from app.services import thread_store
    thread = Thread(owner_id="personal-test", provider="codex", provider_state={"account_profile": "codex-son", "effort": "medium", "thread_id": "old"})
    db_session.add(thread)
    await db_session.flush()
    reset = await thread_store.reset_session(db_session, thread.id, None, message="test reset")
    assert reset.account_profile == "codex-son"
    assert reset.provider_state == {"account_profile": "codex-son", "effort": "medium"}


async def test_runtime_admits_once_on_pinned_profile_and_preserves_native_state(personal, monkeypatch):
    from app.services.thread_runtime import ThreadRuntime
    from app.services.provider_adapter import TurnOutcome
    runtime = object.__new__(ThreadRuntime)
    runtime.owner_id = "test-owner"
    observed = []
    async def subscription(provider):
        observed.append(("login", ops._profile.get()))
    async def turn(*args):
        observed.append(("turn", ops._profile.get()))
        return TurnOutcome("succeeded", provider_state={"native_id": "session"})
    monkeypatch.setattr(ops, "require_subscription", subscription)
    run = SimpleNamespace(ctx=SimpleNamespace(provider_state={"account_profile": "codex-son", "effort": "medium"}), engine_id="codex", thread_id=10, turn_id=1, settings_snapshot={}, recorder=None, gate=None, stalled=False)
    adapter = SimpleNamespace(run_turn=turn)
    outcome = await runtime._run_adapter(run, adapter)
    assert outcome.provider_state == {"native_id": "session", "account_profile": "codex-son", "effort": "medium"}
    assert observed == [("login", "codex-son"), ("turn", "codex-son")]
    assert ops.budget_status()["reserved"] == 1
    replay = await runtime._run_adapter(run, adapter)
    assert replay.error_code == "personal_admission_refused"
    assert len([x for x in observed if x[0] == "turn"]) == 1
    assert ops._profile.get() is None


async def test_personal_runtime_cancellation_propagates(personal, monkeypatch):
    from app.services.thread_runtime import ThreadRuntime
    runtime = object.__new__(ThreadRuntime)
    runtime.owner_id = "test-owner"
    started = asyncio.Event()
    async def subscription(provider):
        pass
    async def turn(*args):
        started.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(ops, "require_subscription", subscription)
    run = SimpleNamespace(ctx=SimpleNamespace(provider_state={"account_profile": "codex-me"}), engine_id="codex", thread_id=10, turn_id=1, settings_snapshot={}, recorder=None, gate=None, stalled=False)
    task = asyncio.create_task(runtime._run_adapter(run, SimpleNamespace(run_turn=turn)))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert run.adapter_task.cancelled()
    assert ops.budget_status()["reserved"] == 1


def test_personal_routes_require_admin_scope():
    from app.auth.policy import required_scope
    assert required_scope("GET", "/api/v1/personal-operations") == "admin"


async def test_custom_codex_provider_refused_before_cli(personal, monkeypatch):
    from pathlib import Path
    settings, _ = personal
    home = Path(settings["account_homes"]["codex-me"])
    home.mkdir()
    (home / "config.toml").write_text('model_provider = "custom"')
    with pytest.raises(ValueError, match="custom provider"):
        await ops.require_subscription("codex")
    assert "forced_login_method=\"chatgpt\"" in ops.codex_command("codex")


async def test_codex_model_effort_objects_are_normalized(personal, monkeypatch):
    from pathlib import Path
    from app.services import codex_adapter
    class Rpc:
        async def request(self, method, args):
            return {"data": [{"id": "test-model", "supportedReasoningEfforts": [{"reasoningEffort": "low", "description": "fast"}, {"reasoningEffort": "medium"}], "defaultReasoningEffort": "medium"}]}
        def notify(self, *args):
            pass
        async def close(self):
            pass
    async def spawn(*args, **kwargs):
        return Rpc()
    monkeypatch.setattr(codex_adapter.StdioRpc, "spawn", spawn)
    models = await codex_adapter.CodexAdapter()._live_models(Path("codex"))
    assert models[0].supported_reasoning_efforts == ("low", "medium")
