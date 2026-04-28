"""FastAPI entry point for the Embr Control-Plane MCP server.

Exposes:
- ``GET /health`` — health probe for Embr's readiness check.
- ``GET /`` — landing page describing the MCP server and how to connect.
- ``/mcp/`` — MCP streamable-HTTP server (mount path) — the main surface.
"""

from __future__ import annotations

import contextlib
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from . import embr_client
from .mcp_server import mcp

load_dotenv()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Embr Control-Plane MCP",
    description=(
        "An MCP server that exposes Embr Global API operations as tools so a "
        "Foundry / Claude / VS Code agent can drive Embr by name. Built for "
        "the Embr × Foundry POC."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config", tags=["meta"])
async def config() -> dict[str, object]:
    """Useful for the README/landing-page to show whether the server is
    actually wired up to a real Embr API + token."""
    token_set = bool(os.environ.get("EMBR_TOKEN", "").strip())
    return {
        "shape": "Embr-driving MCP (Scenario D)",
        "embr_api_url": embr_client.get_api_url(),
        "token_configured": token_set,
        "mcp_endpoint": "/mcp/",
    }


_LANDING_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Embr Control-Plane MCP</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
         background: #0d1117; color: #c9d1d9; margin: 0; padding: 2rem;
         max-width: 820px; margin-inline: auto; line-height: 1.55; }
  h1 { color: #f0f6fc; font-weight: 600; letter-spacing: -0.01em; margin-bottom: 0.25rem; }
  .lede { color: #8b949e; margin-top: 0; }
  code { background: #161b22; border: 1px solid #30363d; padding: 0.1rem 0.4rem;
         border-radius: 4px; font-size: 0.9em; }
  pre { background: #161b22; border: 1px solid #30363d; padding: 1rem;
        border-radius: 6px; overflow-x: auto; font-size: 0.85em; }
  h2 { color: #f0f6fc; margin-top: 2rem; font-size: 1.1rem; }
  ul { padding-left: 1.2rem; }
  li { margin: 0.2rem 0; }
  .pill { background: #1f6feb22; color: #58a6ff; border: 1px solid #1f6feb55;
          padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.78rem; }
  a { color: #58a6ff; }
</style>
</head>
<body>
<h1>Embr Control-Plane MCP <span class="pill">Scenario D</span></h1>
<p class="lede">An MCP server that exposes Embr Global API operations as tools, so a Foundry or Claude or VS Code agent can drive Embr by name.</p>

<h2>Connect from VS Code</h2>
<pre>// .vscode/mcp.json
{
  "servers": {
    "embr-control-plane": {
      "type": "http",
      "url": "<this-deployment-url>/mcp/"
    }
  }
}</pre>

<h2>Connect from a Foundry agent</h2>
<p>Add an MCP project connection in the Foundry portal pointing at <code>&lt;this-deployment-url&gt;/mcp/</code>, then attach it to your agent as an MCP tool.</p>

<h2>Available tools (read-only)</h2>
<ul>
  <li><code>embr_whoami</code> — verify token</li>
  <li><code>list_projects</code>, <code>get_project</code>, <code>get_project_by_repo</code></li>
  <li><code>list_environments</code>, <code>get_environment</code></li>
  <li><code>list_deployments</code>, <code>get_deployment</code></li>
  <li><code>list_builds</code>, <code>get_build</code></li>
  <li><code>list_variable_keys</code> (keys only — values are not exposed)</li>
</ul>

<h2>Why this sample exists</h2>
<p>The MCP server holds a single <code>EMBR_TOKEN</code> with the human user's full permission. There is no agent identity, no scoped token, and no per-tool authorization on Embr today. <strong>This sample is a deliberate finding-driver, not a production pattern.</strong> See the README for the platform-features ask list.</p>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, tags=["meta"])
async def landing() -> HTMLResponse:
    return HTMLResponse(content=_LANDING_HTML)


# Mount MCP streamable-HTTP app at /mcp/
app.mount("/mcp", mcp.streamable_http_app())


@app.middleware("http")
async def _mcp_trailing_slash(request, call_next):
    """Same trailing-slash workaround as embr-foundry-tool-sample."""
    if request.url.path == "/mcp":
        request.scope["path"] = "/mcp/"
        request.scope["raw_path"] = b"/mcp/"
    return await call_next(request)
