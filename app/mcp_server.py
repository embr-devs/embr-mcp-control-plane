"""MCP server surface — exposes Embr control-plane operations as MCP tools.

Connect a Foundry agent / Claude Desktop / VS Code MCP client to:
    https://<this-deployment-host>/mcp/

and the model gains the ability to read your Embr projects, environments,
deployments, and builds.

Read-only by design (v1). Mutating operations (create deployment, set env
var, delete project) are intentionally NOT exposed — adding them is trivial,
but the *finding* this sample surfaces is that there's no scoping primitive
on the token, so a write tool would inherit the human's full permission. A
real production MCP server backed by Embr would need server-side scoping
(see the README "Embr platform findings" section).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import embr_client

mcp = FastMCP(
    "Embr Control Plane",
    host="0.0.0.0",
    json_response=True,
    stateless_http=True,
    streamable_http_path="/",
)


# ---------------------------------------------------------------------------
# Identity / config
# ---------------------------------------------------------------------------

@mcp.tool()
def embr_whoami() -> dict:
    """Sanity-check the configured Embr token. Returns the API URL and a
    confirmation that the token is valid.

    Call this first if you suspect auth issues. Does NOT return the token.
    """
    return embr_client.whoami()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@mcp.tool()
def list_projects(limit: int = 50) -> list[dict]:
    """List Embr projects accessible to the current user. Returns id, name,
    owner, repository, defaultBranch, isActive, isSuspended, createdAt.

    Use this first to discover the project_id you'll need for environment
    and deployment lookups."""
    return embr_client.list_projects(limit=limit)


@mcp.tool()
def get_project(project_id: str) -> dict:
    """Get full details of a single Embr project by id. Returns the same
    fields as list_projects plus settings, triggerMode, and installationId."""
    return embr_client.get_project(project_id)


@mcp.tool()
def get_project_by_repo(owner: str, repo: str) -> dict:
    """Look up an Embr project by GitHub owner/repo (e.g. owner='embr-devs',
    repo='embr-foundry-chat-sample'). Useful when you know the repo but not
    the project id."""
    return embr_client.get_project_by_repo(owner, repo)


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------

@mcp.tool()
def list_environments(project_id: str) -> list[dict]:
    """List environments for a given project. Each environment has id, name,
    branch, isProduction, isActive, url, createdAt."""
    return embr_client.list_environments(project_id)


@mcp.tool()
def get_environment(project_id: str, environment_id: str) -> dict:
    """Get full details of a single environment, including settings and
    activeDeploymentId."""
    return embr_client.get_environment(project_id, environment_id)


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------

@mcp.tool()
def list_deployments(project_id: str, environment_id: str, limit: int = 20) -> list[dict]:
    """List recent deployments for an environment. Each deployment has id,
    status, buildId, commitSha, branch, createdAt, activatedAt."""
    return embr_client.list_deployments(project_id, environment_id, limit=limit)


@mcp.tool()
def get_deployment(project_id: str, environment_id: str, deployment_id: str) -> dict:
    """Get full details of a deployment, including the public url and any
    error message if it failed."""
    return embr_client.get_deployment(project_id, environment_id, deployment_id)


# ---------------------------------------------------------------------------
# Builds
# ---------------------------------------------------------------------------

@mcp.tool()
def list_builds(project_id: str, environment_id: str, limit: int = 20) -> list[dict]:
    """List recent builds for an environment. Each build has id, status,
    commitSha, branch, createdAt, completedAt."""
    return embr_client.list_builds(project_id, environment_id, limit=limit)


@mcp.tool()
def get_build(project_id: str, environment_id: str, build_id: str) -> dict:
    """Get full details of a build, including the build error if it failed
    and the imageRef if it succeeded."""
    return embr_client.get_build(project_id, environment_id, build_id)


# ---------------------------------------------------------------------------
# Variables (keys only — values are not exposed)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_variable_keys(project_id: str, environment_id: str) -> list[dict]:
    """List environment variable keys for an environment. Returns key,
    isSecret, updatedAt for each variable. **Values are NOT returned** —
    this is read-only metadata for diagnosing config drift."""
    return embr_client.list_variable_keys(project_id, environment_id)
