"""Opt-in owner workspace. Fixed read-only connectors; explicit subscription accounts.

Configuration contains paths and local policy only, never credentials. Model input
cannot select an endpoint or a filesystem path. All provider usage is explicit.
"""
import contextvars
import asyncio
import json
import os
import re
import sqlite3
import tomllib
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx

_profile = contextvars.ContextVar("personal_subscription_profile", default=None)
PROFILE_IDS = {"codex-me": "codex", "codex-son": "codex", "codex-kadi": "codex", "claude-main": "claude"}
READ_TOOLS = ("atlas_search", "atlas_get", "atlas_project", "controller_status")


def config() -> dict:
    location = os.environ.get("OPEN_DUET_PERSONAL_CONFIG")
    if not location:
        return {}
    path = Path(location)
    if path.stat().st_size > 32768:
        raise ValueError("Personal operations configuration too large")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Invalid personal operations configuration")
    return value


def enabled() -> bool:
    return bool(os.environ.get("OPEN_DUET_PERSONAL_CONFIG"))


def profile_for(provider: str, selected: str | None = None) -> str:
    if provider not in ("codex", "claude"):
        raise ValueError("This workspace allows subscription Codex and Claude engines only")
    selected = selected or ("codex-me" if provider == "codex" else "claude-main")
    if PROFILE_IDS.get(selected) != provider:
        raise ValueError("Account profile does not match engine")
    return selected


@contextmanager
def use_profile(provider: str, selected: str | None = None):
    token = _profile.set(profile_for(provider, selected))
    try:
        yield
    finally:
        _profile.reset(token)


def subscription_environment(source: dict) -> dict:
    if not enabled():
        return source
    # Provider and API-key routes are opt-in elsewhere upstream. This profile
    # deliberately excludes them, including casing variants and Node injection.
    excluded = ("OPENAI_", "ANTHROPIC_", "CLAUDE_CODE_USE_", "GEMINI_", "CODEX_")
    env = {k: v for k, v in source.items() if not k.upper().startswith(excluded)
           and k.upper() not in {"CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "NODE_OPTIONS", "NODE_PATH"}}
    selected = _profile.get()
    homes = config().get("account_homes", {})
    codex = selected if selected and selected.startswith("codex-") else "codex-me"
    env["CODEX_HOME"] = str(Path(homes.get(codex, str(Path.home() / f".{codex}"))).expanduser())
    env["CLAUDE_CONFIG_DIR"] = str(Path(homes.get("claude-main", str(Path.home() / ".claude"))).expanduser())
    return env


def profiles() -> list[dict]:
    homes = config().get("account_homes", {})
    return [{"id": key, "provider": provider,
             "configured": Path(homes.get(key, str(Path.home() / (".claude" if key == "claude-main" else f".{key}")))).expanduser().is_dir(),
             "quota": "unknown", "automatic_fallback": False}
            for key, provider in PROFILE_IDS.items()]


def budget_status() -> dict:
    settings = config()
    day = datetime.now(ZoneInfo(settings.get("timezone", "Europe/Tallinn"))).date().isoformat()
    result = {"day": day, "cap": settings.get("daily_call_cap", 4), "reserved": 0,
              "scope": "Open Duet only; controller has a separate budget", "accounts": {}}
    path = Path(settings["budget_path"])
    if path.exists():
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2) as db:
            rows = db.execute("SELECT account,COUNT(*) FROM reservations WHERE day=? GROUP BY account", (day,)).fetchall()
            result["accounts"] = dict(rows)
            result["reserved"] = sum(row[1] for row in rows)
    return result


async def require_subscription(provider: str) -> None:
    from app.services import cli_probe, local_claude_runner
    if provider == "codex":
        home = Path(subscription_environment({})["CODEX_HOME"])
        path = home / "config.toml"
        if path.exists():
            if path.stat().st_size > 262144:
                raise ValueError("Selected Codex configuration exceeds review limit")
            saved = tomllib.loads(path.read_text(encoding="utf-8-sig"))
            if (saved.get("model_provider", "openai") != "openai"
                    or saved.get("model_providers", {}).get("openai")
                    or saved.get("chatgpt_base_url", "https://chatgpt.com/backend-api").rstrip("/") != "https://chatgpt.com/backend-api"):
                raise ValueError("Selected Codex profile has a custom provider endpoint; subscription-only admission refused")
        from app.services.codex_adapter import resolve_codex_executable
        exe = resolve_codex_executable()
        args = [str(exe), "--no-daemon", "login", "status"]
    else:
        exe = local_claude_runner.resolve_claude_executable()
        args = [str(exe), "auth", "status"]
    if exe is None:
        raise ValueError("Subscription CLI unavailable")
    result = await cli_probe.run(args, timeout=8)
    if provider == "codex":
        confirmed = bool(re.search(r"^Logged in using ChatGPT\s*$", result.stdout + "\n" + result.stderr, re.M))
    else:
        try:
            data = json.loads(result.stdout)
            confirmed = data.get("loggedIn") is True and data.get("authMethod") == "claude.ai" and data.get("apiProvider") == "firstParty"
        except (ValueError, TypeError):
            confirmed = False
    if not result.ok or not confirmed:
        raise ValueError("Selected subscription login is not confirmed; no API or other-account fallback")


def codex_command(executable) -> list[str]:
    if not enabled():
        return [str(executable), "app-server"]
    return [str(executable), "--no-daemon", "-c", 'model_provider="openai"',
            "-c", 'forced_login_method="chatgpt"', "app-server"]


def reserve_call(key: str, account_id: str) -> None:
    settings = config()
    path = Path(settings["budget_path"]).expanduser()
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")) or "onedrive" in str(path).lower():
        raise ValueError("Budget database needs local non-synced storage")
    path.parent.mkdir(parents=True, exist_ok=True)
    day = datetime.now(ZoneInfo(settings.get("timezone", "Europe/Tallinn"))).date().isoformat()
    cap = settings.get("daily_call_cap", 4)
    if type(cap) is not int or not 1 <= cap <= 20:
        raise ValueError("Invalid local daily call cap")
    with sqlite3.connect(path, timeout=5) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS reservations(key TEXT PRIMARY KEY,day TEXT,account TEXT)")
        db.execute("BEGIN IMMEDIATE")
        # A reservation is never refunded on failure or spent twice after replay.
        if db.execute("SELECT 1 FROM reservations WHERE key=?", (key,)).fetchone():
            raise ValueError("This turn already reserved a model call; inspect it before a new turn")
        if db.execute("SELECT COUNT(*) FROM reservations WHERE day=?", (day,)).fetchone()[0] >= cap:
            raise ValueError("Local daily model-call cap reached; no account rotation")
        db.execute("INSERT INTO reservations VALUES(?,?,?)", (key, day, account_id))


def _endpoint(source: str) -> str:
    value = config().get(f"{source}_url", "http://127.0.0.1:4317" if source == "atlas" else "http://127.0.0.1:4321")
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Only a configured numeric loopback source is allowed")
    return value.rstrip("/")


async def read_source(source: str, path: str, params: dict | None = None) -> dict | list:
    async with asyncio.timeout(10), httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
        async with client.stream("GET", _endpoint(source) + path, params=params) as response:
            if response.status_code != 200:
                raise ValueError("Source did not return a successful response")
            response.raise_for_status()
            chunks, size = [], 0
            async for part in response.aiter_bytes():
                size += len(part)
                if size > 512000:
                    raise ValueError("Source response exceeds size cap")
                chunks.append(part)
            return json.loads(b"".join(chunks))


async def read_tool(name: str, arguments: dict) -> dict | list:
    if not enabled() or name not in READ_TOOLS:
        raise ValueError("Read-only personal tool unavailable")
    if name == "atlas_search":
        if set(arguments) != {"query"} or not isinstance(arguments["query"], str) or not 1 <= len(arguments["query"]) <= 200:
            raise ValueError("A bounded search query is required")
        value = await read_source("atlas", "/api/search", {"q": arguments["query"], "type": "entry"})
        return {"query": value["query"], "hits": value["hits"][:8], "source": "Personal Atlas", "read_only": True}
    if name in ("atlas_get", "atlas_project"):
        if set(arguments) != {"id"} or not isinstance(arguments["id"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", arguments["id"]):
            raise ValueError("A canonical identifier is required")
        return await read_source("atlas", f"/api/{'entry' if name == 'atlas_get' else 'project'}/{arguments['id']}")
    if arguments:
        raise ValueError("Controller status takes no arguments")
    value = await read_source("controller", "/api/view")
    return {key: value.get(key) for key in ("observedAt", "paused", "runtime", "summary", "tasks", "budget", "goals", "accounts")}


async def overview() -> dict:
    output = {"enabled": enabled(), "profiles": profiles() if enabled() else [], "sources": {}, "ownership": {
        "atlas": "Canonical knowledge and project context", "controller": "Existing bounded execution and evidence", "company_os": "Company task authority; no new write connector"}}
    if not enabled():
        return output
    output["budget"] = budget_status()
    for name, path in (("atlas", "/api/projects"), ("controller", "/api/view")):
        try:
            data = await read_source(name, path)
            output["sources"][name] = {"state": "connected", "observed_at": datetime.now().astimezone().isoformat(), "data": data}
        except (httpx.HTTPError, ValueError, OSError):
            output["sources"][name] = {"state": "unavailable", "data": None, "message": "Source unavailable; do not infer an empty project list or idle worker"}
    return output
