# embr-mcp-control-plane

> **Scenario D** of the Embr × Foundry POC. The first sample where **Embr is the thing being driven**, not the thing hosting the driver.

An MCP server hosted on Embr that exposes Embr Global API operations as tools, so a Foundry / Claude Desktop / VS Code agent can answer questions like:

- "What's deployed in my `embr-foundry-chat-sample` production environment right now?"
- "Show me the last failed build for the `embr-multiservice-api` project."
- "List all environment variables on my staging environment."

…by calling Embr's own control-plane.

This is the inverse of every other sample in this POC. Other samples ask "how does an Embr-hosted app talk to Foundry?" — this one asks "how does a Foundry agent talk to Embr?"

---

## What's inside

```
embr-mcp-control-plane/
├── app/
│   ├── embr_client.py     # thin httpx wrapper around the Embr Global API
│   ├── mcp_server.py      # FastMCP server registering the tools
│   └── main.py            # FastAPI shell that mounts MCP under /mcp/
├── embr.yaml
├── requirements.txt
└── README.md
```

### Tools exposed (all read-only in v1)

| Tool | Purpose |
|------|---------|
| `embr_whoami` | Confirm the token is valid; returns API URL and a probe result |
| `list_projects` | Enumerate projects the user has access to |
| `get_project` | Project details by id |
| `get_project_by_repo` | Project details by GitHub owner/repo |
| `list_environments` | Environments under a project |
| `get_environment` | Environment details (incl. activeDeploymentId) |
| `list_deployments` | Recent deployments for an environment |
| `get_deployment` | Deployment details (status, url, error) |
| `list_builds` | Recent builds for an environment |
| `get_build` | Build details (status, error, imageRef) |
| `list_variable_keys` | Variable keys (NOT values — values may be secret) |

Mutating tools (create deployment, set env var, delete env) are intentionally **not** exposed in v1 — adding them is trivial code-wise, but the auth-scoping problem (see Findings below) means a write tool would inherit the human's full Embr permission. We surface that as a finding rather than ship the unsafe pattern.

---

## Quickstart — local

1. Install deps

   ```bash
   pip install -r requirements.txt
   ```

2. Get an Embr token. The MCP server uses the **same** bearer token your `embr` CLI uses.

   ```bash
   # find it in ~/.config/embr-cli/config.json (or %APPDATA%\embr-cli\config.json on Windows)
   cat ~/.config/embr-cli/config.json | jq -r '.token'
   ```

3. Set env vars (`.env` works thanks to python-dotenv)

   ```bash
   export EMBR_TOKEN="<that token>"
   export EMBR_API_URL="https://api.embr.azure/api"   # default; override for local API
   ```

4. Run

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. Smoke-test the MCP handshake

   ```bash
   curl -s -X POST http://localhost:8000/mcp/ \
        -H 'Content-Type: application/json' \
        -H 'Accept: application/json, text/event-stream' \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"0.0"}}}'
   ```

6. Or point Claude Desktop / VS Code at it

   ```jsonc
   // .vscode/mcp.json
   {
     "servers": {
       "embr-control-plane": {
         "type": "http",
         "url": "http://localhost:8000/mcp/"
       }
     }
   }
   ```

---

## Deploy to Embr

```bash
embr quickstart deploy embr-devs/embr-mcp-control-plane -i 120233234
```

After deploy:

```bash
embr config context -p prj_<id> -e env_<id>
embr variables set EMBR_TOKEN=<token> --secret
embr variables set EMBR_API_URL=https://api.embr.azure/api
```

Then the MCP endpoint is at `https://<deployment-url>/mcp/`.

To register from a Foundry agent: add an MCP **project connection** in the Foundry portal pointing at that URL, attach it as an MCP tool to your agent.

---

## Embr platform findings

**This sample exists to surface platform gaps, not to ship a production pattern.** Specifically:

### 1. No agent identity / no scoped tokens
- The MCP server holds **one** `EMBR_TOKEN`. That token is the human user's full bearer credential — same one the `embr` CLI uses.
- Anyone (or any agent) with that token can: list every project, create / cancel / delete deployments, set env vars (including secrets), delete environments, delete projects.
- There is **no** way today to mint a token scoped to:
  - a single project (`scope: project:prj_xxx`)
  - read-only operations (`scope: read`)
  - specific resource verbs (`scope: deployments:read environments:read`)
  - a time window (`expires: 1h`)
- The agent runs with the human's full permission, and the human has no way to constrain that.

**Platform feature ask:** scoped, short-lived tokens with an MCP-friendly minting flow — `embr tokens issue --scope read --project prj_xxx --ttl 24h` returning a token the agent can use.

### 2. No agent-driven token rotation
- A real agent caller can't rotate its own token. If the human revokes, the agent silently 401s. There's no "heartbeat token" pattern.
- **Platform ask:** distinct credential class for agents with a refresh-token flow.

### 3. No control-plane MCP primitive
- There's no `embr.yaml: expose_as: control-plane-mcp` or `embr mcp publish` to make this kind of MCP server a first-class affordance.
- Today the developer has to hand-write the `httpx` wrapper, the `FastMCP` registration, the `embr.yaml`, and the deploy + variable-setting dance for every control-plane MCP they want.
- **Platform ask:** an `embr` subcommand or curated template that scaffolds a control-plane MCP server with a chosen subset of read/write capabilities.

### 4. No request-level audit log entry for "who called this?"
- Embr's audit/activity log records the user that owns the token, not "this token was used by an agent named X via MCP server Y."
- For the "agent driving Embr" pattern to be a viable production posture, audit needs to record the *agent identity* alongside the user identity (think AWS IAM "AssumedRole" identity).
- **Platform ask:** agent identity threaded through to activity log entries.

### 5. Trailing-slash redirect leaks internal hostname (already filed)
- Same MCP-mount-path trailing-slash bug as `embr-foundry-tool-sample`: the in-app middleware works around it, but the underlying ingress 307 leak (per `FINDINGS.md`) is unchanged.

### 6. No way for an agent to know what scopes its token has
- An agent can call `embr_whoami` to see *who* it is, but there's no scopes-introspection endpoint (`/auth/scopes`, `/.well-known/oauth-authorization-server`, etc.).
- **Platform ask:** an introspection endpoint so an agent can self-report capabilities to its model in-context.

---

## Why this matters

A platform that wants to be the answer to "where do AI agents do their work?" has to be operable *by* agents, not just operable to host them. Today Embr is highly operable to host. The control-plane gaps above are exactly what a customer would hit the moment they ask "can my Foundry agent run a deploy when CI is green?" — and the answer is "yes, but you'd be giving it your full personal token."

That's the central finding this sample makes concrete.
