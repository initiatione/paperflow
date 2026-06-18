# MCP Runtime Health

Use this reference when a Paper Source MCP server is missing, cannot initialize, lists no tools, times out, or appears shadowed by user-level Codex MCP config.

## Prefer Built-In Doctor

Start with:

```powershell
python scripts\orchestrator.py doctor --vault <vault> --json
```

The built-in doctor is the source of truth for plugin MCP self-registration, installed launcher shape, user-level static MCP shadowing, runtime command paths, and provider readiness.

## Layers To Separate

1. Plugin `.mcp.json`: marketplace-visible server declarations and launcher commands.
2. Codex registration: whether the installed plugin exposes the MCP servers to the current Codex session.
3. Outer launcher: plugin root `cwd`, wrapper command, and runtime.json loading.
4. Inner server command: user-configured `paper-search-mcp` or `grok-search-rs` process.
5. Provider runtime: env files, API keys, base URLs, model, proxy, DNS, TLS, and upstream service behavior.

Do not collapse all failures into "MCP broken". Name the lowest failing layer that evidence supports.

## Stdio Probe

When doctor output is insufficient and the server uses line-delimited JSON over stdio, run:

```powershell
python skills\health-doctor\scripts\mcp_stdio_probe.py --command <cmd> --arg <arg1> --arg <arg2>
```

The probe sends `initialize`, `notifications/initialized`, and `tools/list`. It prints tool names and stderr tail, redacting secret-looking args. If the server uses `Content-Length` framing or a custom wrapper, use its native client or the plugin doctor instead of forcing this probe.

## Common Symptoms

- Launch failed: command not installed, wrong interpreter, bad `cwd`, missing executable bit, or path unavailable from the installed plugin.
- Initialize timeout: server started but did not speak the expected stdio protocol, is waiting on user input, or is blocked importing dependencies.
- Tools list error: protocol handshake works but server-side dependency/provider setup failed.
- No tools: wrong package/module, incompatible server version, or command launches a different program.
- Works in source checkout but not Codex: installed cache stale, marketplace not refreshed, current thread loaded old skill/MCP metadata, or user-level config shadows plugin self-registration.

## Reporting

Report:

- server name;
- failing layer;
- sanitized command shape;
- whether env files exist, not their contents;
- first actionable next step;
- whether the check was run against source checkout or installed cache.

