"""Isolated local launcher. Run using the backend's locked uv environment.

No credentials are copied from CLI accounts. The encryption key belongs only
to this fresh Open Duet database and is never printed or committed.
"""
import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify", action="store_true", help="Read connector and subscription status without a model call")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = args.data_dir.expanduser().resolve()
    if not args.data_dir.is_absolute() or str(data).startswith(("\\\\", "//")) or "onedrive" in str(data).lower() or data == root or root in data.parents:
        parser.error("Use an absolute, local, non-synced data directory outside the repository")
    data.mkdir(parents=True, exist_ok=True)
    key = data / "encryption.key"
    if not key.exists():
        if (data / "open-duet.sqlite").exists():
            parser.error("Database exists without its encryption key; restore the key from backup")
        with key.open("x", encoding="ascii") as output:
            output.write(base64.urlsafe_b64encode(os.urandom(32)).decode())
    config = data / "personal-operations.json"
    if not config.exists():
        with config.open("x", encoding="utf-8") as output:
            json.dump({"budget_path": str(data / "model-call-budget.sqlite"), "daily_call_cap": 4,
                       "timezone": "Europe/Tallinn", "atlas_url": "http://127.0.0.1:4317",
                       "controller_url": "http://127.0.0.1:4321"}, output, indent=2)
    # A fixed profile, not inherited cloud-provider or desktop authentication.
    for name in list(os.environ):
        if name.startswith(("OPENAI_", "ANTHROPIC_", "BOAT_", "COMPOSIO_", "GEMINI_", "TELEGRAM_", "OPEN_DOTS_", "OPEN_DUET_DESKTOP")):
            os.environ.pop(name)
    os.environ.update({
        "OPEN_DUET_PERSONAL_CONFIG": str(config), "DATABASE_BACKEND": "sqlite",
        "SQLITE_PATH": str(data / "open-duet.sqlite"), "TOKEN_ENCRYPTION_KEYS": key.read_text().strip(),
        "LOCAL_EXECUTION_ENABLED": "true", "LOCAL_TOOLS_ENABLED": "false",
        "LOCAL_WORKSPACE_ROOT": str(data / "workspace"), "DECISION_LOG_DIR": str(data / "decisions"),
        "ATTACHMENTS_DIR": str(data / "attachments"), "LOOPBACK_TRUST": "off",
        "FRONTEND_ORIGINS": f"http://127.0.0.1:{args.port}", "TRUSTED_HOSTS": "127.0.0.1",
        "MEMORY_CAPTURE_QUIET_SECONDS": "0", "COMPACTION_MODEL_SUMMARY": "false",
        "MEMORY_TIDY_HOUR": "24", "HELPER_ENGINE": "", "TEAM_MAX_DEPTH": "2",
        "TEAM_MAX_JOBS_PER_ROOT": "4", "TEAM_MAX_EXECUTIONS_PER_ROOT": "6", "TEAM_MAX_PARALLEL": "1",
        "TEAM_MAX_CREATED_PER_TURN": "2", "TEAM_LEAD_AUTO": "false", "OPEN_DOTS_PRESET_ENGINES": "",
    })
    if sys.platform == "win32":
        # Windows cannot execute an npm .cmd shim with asyncio's exec API.
        # Select only the current npm package's native binary, not an old cache.
        package = Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@openai/codex/node_modules/@openai"
        binaries = sorted(package.glob("codex-win32-*/vendor/*/bin/codex.exe"))
        if len(binaries) == 1:
            os.environ["LOCAL_CODEX_CLI_PATH"] = str(binaries[0])
    os.chdir(root / "backend")
    sys.path.insert(0, str(root / "backend"))
    from app.server.entry import main as server
    if args.check or args.verify:
        from app.services import personal_operations
        print(json.dumps({"profiles": personal_operations.profiles(), "data_directory": str(data),
                          "automatic_memory_calls": False, "daily_call_cap": 4,
                          "url": f"http://127.0.0.1:{args.port}/operations/"}, indent=2))
        if args.verify:
            async def verify():
                overview = await personal_operations.overview()
                results = {"sources": {key: {"state": value["state"], "items": len(value["data"]) if isinstance(value["data"], list) else None} for key, value in overview["sources"].items()}, "subscription_login": {}}
                for profile in personal_operations.profiles():
                    if not profile["configured"]:
                        results["subscription_login"][profile["id"]] = "not configured"
                        continue
                    try:
                        with personal_operations.use_profile(profile["provider"], profile["id"]):
                            await personal_operations.require_subscription(profile["provider"])
                        results["subscription_login"][profile["id"]] = "confirmed"
                    except (ValueError, OSError):
                        results["subscription_login"][profile["id"]] = "not confirmed"
                results["model_calls"] = 0
                results["atlas_read_tools"] = {}
                for tool, arguments in (("atlas_search", {"query": "AI Controller"}), ("atlas_get", {"id": "ai-controller-operations-pilot"})):
                    try:
                        value = await personal_operations.read_tool(tool, arguments)
                        results["atlas_read_tools"][tool] = {"state": "ok", "response_bytes": len(json.dumps(value).encode())}
                    except Exception as exc:
                        results["atlas_read_tools"][tool] = {"state": "failed", "error_type": type(exc).__name__}
                print(json.dumps(results, indent=2))
            asyncio.run(verify())
        return 0
    if not (root / "frontend/out/index.html").is_file():
        parser.error("Build the static frontend first: OD_STATIC_EXPORT=1 NEXT_PUBLIC_API_BASE_URL=/api/v1 npm run build")
    result = server(["migrate"])
    if result:
        return result
    return server(["--ui-dir", str(root / "frontend/out"), "--host", "127.0.0.1", "--port", str(args.port)])


if __name__ == "__main__":
    raise SystemExit(main())
