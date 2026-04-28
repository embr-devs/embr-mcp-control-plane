"""Thin wrapper around the Embr Global API.

This is a *control-plane* MCP sample. The MCP server lets a Foundry / Claude /
VS Code agent drive Embr by calling Embr Global API endpoints.

Auth model (and the central platform finding this sample surfaces):

The MCP server holds a single ``EMBR_TOKEN`` env var — a normal user-scoped
GitHub-OAuth-derived bearer token, identical to what the ``embr`` CLI uses.

There is **no agent identity** in Embr today. There is **no scoped token**
("read only", "deployments only", "project foo only"). Whoever holds the token
can do anything that user can do — list every project, create deployments,
delete environments, set env vars, etc. An agent driving Embr therefore runs
with the human's full permission, and the human has no way to constrain that.

This file is deliberately small — every method is one HTTP call. The MCP
tool surface in ``mcp_server.py`` calls these directly.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


def get_api_url() -> str:
    return os.environ.get("EMBR_API_URL", "https://api.embr.azure/api").rstrip("/")


def get_token() -> str:
    token = os.environ.get("EMBR_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "EMBR_TOKEN env var is required. Run `embr auth login` and copy "
            "the token from your Embr CLI config (~/.config/embr-cli/config.json) "
            "into the EMBR_TOKEN env var on this app's Embr environment."
        )
    return token


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/json",
        "User-Agent": "embr-mcp-control-plane/0.1",
    }


def _client() -> httpx.Client:
    return httpx.Client(base_url=get_api_url(), headers=_headers(), timeout=30.0)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def list_projects(limit: int = 50) -> list[dict[str, Any]]:
    with _client() as c:
        r = c.get("/projects", params={"limit": limit})
        r.raise_for_status()
        body = r.json()
        items = body.get("items", body) if isinstance(body, dict) else body
    return [_project_summary(p) for p in items]


def get_project(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/projects/{project_id}")
        r.raise_for_status()
        return _project_summary(r.json(), full=True)


def get_project_by_repo(owner: str, repo: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/projects/repo/{owner}/{repo}")
        r.raise_for_status()
        return _project_summary(r.json(), full=True)


def _project_summary(p: dict[str, Any], full: bool = False) -> dict[str, Any]:
    out = {
        "id": p.get("id"),
        "name": p.get("name"),
        "owner": p.get("owner"),
        "repository": p.get("repositoryFullName") or f"{p.get('owner')}/{p.get('repositoryName')}",
        "defaultBranch": p.get("defaultBranch"),
        "isActive": p.get("isActive"),
        "isSuspended": p.get("isSuspended"),
        "createdAt": p.get("createdAt"),
    }
    if full:
        out["settings"] = p.get("settings")
        out["triggerMode"] = p.get("triggerMode")
        out["installationId"] = p.get("installationId")
    return out


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------

def list_environments(project_id: str) -> list[dict[str, Any]]:
    with _client() as c:
        r = c.get(f"/projects/{project_id}/environments")
        r.raise_for_status()
        body = r.json()
        items = body.get("items", body) if isinstance(body, dict) else body
    return [_env_summary(e) for e in items]


def get_environment(project_id: str, environment_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/projects/{project_id}/environments/{environment_id}")
        r.raise_for_status()
        return _env_summary(r.json(), full=True)


def _env_summary(e: dict[str, Any], full: bool = False) -> dict[str, Any]:
    out = {
        "id": e.get("id"),
        "name": e.get("name"),
        "branch": e.get("branch"),
        "isProduction": e.get("isProduction"),
        "isActive": e.get("isActive"),
        "url": e.get("url"),
        "createdAt": e.get("createdAt"),
    }
    if full:
        out["settings"] = e.get("settings")
        out["activeDeploymentId"] = e.get("activeDeploymentId")
    return out


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------

def list_deployments(project_id: str, environment_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with _client() as c:
        r = c.get(
            f"/projects/{project_id}/environments/{environment_id}/deployments",
            params={"limit": limit},
        )
        r.raise_for_status()
        body = r.json()
        items = body.get("items", body) if isinstance(body, dict) else body
    return [_deploy_summary(d) for d in items]


def get_deployment(project_id: str, environment_id: str, deployment_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(
            f"/projects/{project_id}/environments/{environment_id}/deployments/{deployment_id}"
        )
        r.raise_for_status()
        return _deploy_summary(r.json(), full=True)


def _deploy_summary(d: dict[str, Any], full: bool = False) -> dict[str, Any]:
    out = {
        "id": d.get("id"),
        "status": d.get("status"),
        "buildId": d.get("buildId"),
        "commitSha": (d.get("commitSha") or "")[:12] if d.get("commitSha") else None,
        "branch": d.get("branch"),
        "createdAt": d.get("createdAt"),
        "activatedAt": d.get("activatedAt"),
    }
    if full:
        out["url"] = d.get("url")
        out["error"] = d.get("error")
        out["activeRevision"] = d.get("activeRevision")
    return out


# ---------------------------------------------------------------------------
# Builds (read-only)
# ---------------------------------------------------------------------------

def list_builds(project_id: str, environment_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with _client() as c:
        r = c.get(
            f"/projects/{project_id}/environments/{environment_id}/builds",
            params={"limit": limit},
        )
        r.raise_for_status()
        body = r.json()
        items = body.get("items", body) if isinstance(body, dict) else body
    return [_build_summary(b) for b in items]


def get_build(project_id: str, environment_id: str, build_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/projects/{project_id}/environments/{environment_id}/builds/{build_id}")
        r.raise_for_status()
        return _build_summary(r.json(), full=True)


def _build_summary(b: dict[str, Any], full: bool = False) -> dict[str, Any]:
    out = {
        "id": b.get("id"),
        "status": b.get("status"),
        "commitSha": (b.get("commitSha") or "")[:12] if b.get("commitSha") else None,
        "branch": b.get("branch"),
        "createdAt": b.get("createdAt"),
        "completedAt": b.get("completedAt"),
    }
    if full:
        out["error"] = b.get("error")
        out["imageRef"] = b.get("imageRef")
    return out


# ---------------------------------------------------------------------------
# Variables (read-only — listing keys, not values, since values may be secret)
# ---------------------------------------------------------------------------

def list_variable_keys(project_id: str, environment_id: str) -> list[dict[str, Any]]:
    with _client() as c:
        r = c.get(f"/projects/{project_id}/environments/{environment_id}/variables")
        r.raise_for_status()
        body = r.json()
        variables = body.get("variables", body) if isinstance(body, dict) else body
    out = []
    for v in variables:
        out.append({
            "key": v.get("key"),
            "isSecret": v.get("isSecret", False),
            "updatedAt": v.get("updatedAt"),
        })
    return out


# ---------------------------------------------------------------------------
# Whoami — sanity-check the token works
# ---------------------------------------------------------------------------

def whoami() -> dict[str, Any]:
    with _client() as c:
        r = c.get("/auth/me")
        if r.status_code == 404:
            r = c.get("/projects", params={"limit": 1})
            r.raise_for_status()
            return {
                "ok": True,
                "note": "no /auth/me route — used /projects?limit=1 as a token-validity probe",
                "apiUrl": get_api_url(),
            }
        r.raise_for_status()
        return {"ok": True, "user": r.json(), "apiUrl": get_api_url()}
