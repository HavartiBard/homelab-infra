"""Slim Gitea MCP server exposing only essential developer workflow tools."""

import os
import json
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

GITEA_HOST = os.environ.get("GITEA_HOST", "https://code.klsll.com")
GITEA_TOKEN = os.environ.get("GITEA_ACCESS_TOKEN", "")
PORT = int(os.environ.get("MCP_PORT", "6976"))

mcp = FastMCP("Gitea MCP", host="0.0.0.0", port=PORT)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _headers() -> dict[str, str]:
    return {
        "Authorization": f"token {GITEA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _api(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{GITEA_HOST}/api/v1{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.request(method, url, headers=_headers(), **kwargs)
        resp.raise_for_status()
        if resp.status_code == 204:
            return {"status": "ok"}
        return resp.json()


def _pick(obj: dict, keys: list[str]) -> dict:
    return {k: obj[k] for k in keys if k in obj}


# ---------------------------------------------------------------------------
# Repos
# ---------------------------------------------------------------------------

@mcp.tool()
def list_repos(limit: int = 20, page: int = 1) -> str:
    """List repositories owned by the authenticated user."""
    data = _api("GET", "/user/repos", params={"limit": limit, "page": page})
    repos = [_pick(r, ["full_name", "description", "html_url", "default_branch",
                        "open_issues_count", "open_pr_counter", "private"]) for r in data]
    return json.dumps(repos, indent=2)


@mcp.tool()
def search_repos(query: str, limit: int = 10) -> str:
    """Search repositories by keyword."""
    data = _api("GET", "/repos/search", params={"q": query, "limit": limit})
    repos = [_pick(r, ["full_name", "description", "html_url", "default_branch"]) for r in data.get("data", [])]
    return json.dumps(repos, indent=2)


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

@mcp.tool()
def list_issues(owner: str, repo: str, state: str = "open", labels: str = "",
                limit: int = 20, page: int = 1) -> str:
    """List issues in a repository. Filter by state (open/closed) and comma-separated label names."""
    params: dict[str, Any] = {"state": state, "limit": limit, "page": page, "type": "issues"}
    if labels:
        params["labels"] = labels
    data = _api("GET", f"/repos/{owner}/{repo}/issues", params=params)
    issues = [_pick(i, ["number", "title", "state", "body", "html_url",
                         "labels", "assignees", "milestone", "created_at"]) for i in data]
    for i in issues:
        if "labels" in i:
            i["labels"] = [lb["name"] for lb in i["labels"]]
        if "assignees" in i:
            i["assignees"] = [a["login"] for a in (i["assignees"] or [])]
        if "milestone" in i and i["milestone"]:
            i["milestone"] = i["milestone"]["title"]
    return json.dumps(issues, indent=2)


@mcp.tool()
def get_issue(owner: str, repo: str, index: int) -> str:
    """Get a single issue by number."""
    data = _api("GET", f"/repos/{owner}/{repo}/issues/{index}")
    issue = _pick(data, ["number", "title", "state", "body", "html_url",
                          "labels", "assignees", "milestone", "created_at", "updated_at"])
    if "labels" in issue:
        issue["labels"] = [lb["name"] for lb in issue["labels"]]
    if "assignees" in issue:
        issue["assignees"] = [a["login"] for a in (issue["assignees"] or [])]
    if "milestone" in issue and issue["milestone"]:
        issue["milestone"] = issue["milestone"]["title"]
    return json.dumps(issue, indent=2)


@mcp.tool()
def create_issue(owner: str, repo: str, title: str, body: str = "",
                 labels: list[str] | None = None, assignees: list[str] | None = None) -> str:
    """Create a new issue. Labels should be label IDs (numbers), assignees are usernames."""
    payload: dict[str, Any] = {"title": title}
    if body:
        payload["body"] = body
    if labels:
        payload["labels"] = [int(lb) for lb in labels]
    if assignees:
        payload["assignees"] = assignees
    data = _api("POST", f"/repos/{owner}/{repo}/issues", json=payload)
    return json.dumps(_pick(data, ["number", "title", "html_url"]), indent=2)


@mcp.tool()
def edit_issue(owner: str, repo: str, index: int, title: str = "",
               body: str = "", state: str = "") -> str:
    """Edit an existing issue. Only provided fields are updated. State: open or closed."""
    payload: dict[str, Any] = {}
    if title:
        payload["title"] = title
    if body:
        payload["body"] = body
    if state:
        payload["state"] = state
    data = _api("PATCH", f"/repos/{owner}/{repo}/issues/{index}", json=payload)
    return json.dumps(_pick(data, ["number", "title", "state", "html_url"]), indent=2)


@mcp.tool()
def create_comment(owner: str, repo: str, index: int, body: str) -> str:
    """Add a comment to an issue or pull request."""
    data = _api("POST", f"/repos/{owner}/{repo}/issues/{index}/comments", json={"body": body})
    return json.dumps(_pick(data, ["id", "body", "created_at"]), indent=2)


@mcp.tool()
def list_comments(owner: str, repo: str, index: int) -> str:
    """List comments on an issue or pull request."""
    data = _api("GET", f"/repos/{owner}/{repo}/issues/{index}/comments")
    comments = [_pick(c, ["id", "body", "created_at", "user"]) for c in data]
    for c in comments:
        if "user" in c:
            c["user"] = c["user"]["login"]
    return json.dumps(comments, indent=2)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

@mcp.tool()
def list_labels(owner: str, repo: str) -> str:
    """List all labels in a repository."""
    data = _api("GET", f"/repos/{owner}/{repo}/labels")
    labels = [_pick(lb, ["id", "name", "color", "description"]) for lb in data]
    return json.dumps(labels, indent=2)


@mcp.tool()
def add_labels(owner: str, repo: str, index: int, label_ids: list[int]) -> str:
    """Add labels to an issue by label IDs."""
    data = _api("POST", f"/repos/{owner}/{repo}/issues/{index}/labels", json={"labels": label_ids})
    labels = [_pick(lb, ["id", "name"]) for lb in data]
    return json.dumps(labels, indent=2)


# ---------------------------------------------------------------------------
# Pull Requests
# ---------------------------------------------------------------------------

@mcp.tool()
def list_pull_requests(owner: str, repo: str, state: str = "open",
                       limit: int = 20, page: int = 1) -> str:
    """List pull requests in a repository."""
    data = _api("GET", f"/repos/{owner}/{repo}/pulls",
                params={"state": state, "limit": limit, "page": page})
    prs = [_pick(p, ["number", "title", "state", "body", "html_url",
                      "head", "base", "mergeable", "created_at"]) for p in data]
    for p in prs:
        if "head" in p:
            p["head"] = p["head"].get("label", "")
        if "base" in p:
            p["base"] = p["base"].get("label", "")
    return json.dumps(prs, indent=2)


@mcp.tool()
def get_pull_request(owner: str, repo: str, index: int) -> str:
    """Get a single pull request by number."""
    data = _api("GET", f"/repos/{owner}/{repo}/pulls/{index}")
    pr = _pick(data, ["number", "title", "state", "body", "html_url",
                       "head", "base", "mergeable", "diff_url", "created_at", "updated_at"])
    if "head" in pr:
        pr["head"] = pr["head"].get("label", "")
    if "base" in pr:
        pr["base"] = pr["base"].get("label", "")
    return json.dumps(pr, indent=2)


@mcp.tool()
def create_pull_request(owner: str, repo: str, title: str, body: str,
                        head: str, base: str) -> str:
    """Create a pull request. head/base are branch names."""
    data = _api("POST", f"/repos/{owner}/{repo}/pulls",
                json={"title": title, "body": body, "head": head, "base": base})
    return json.dumps(_pick(data, ["number", "title", "html_url"]), indent=2)


@mcp.tool()
def get_pull_request_diff(owner: str, repo: str, index: int) -> str:
    """Get the diff for a pull request."""
    url = f"{GITEA_HOST}/api/v1/repos/{owner}/{repo}/pulls/{index}.diff"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.text


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------

@mcp.tool()
def list_branches(owner: str, repo: str, limit: int = 20) -> str:
    """List branches in a repository."""
    data = _api("GET", f"/repos/{owner}/{repo}/branches", params={"limit": limit})
    branches = [_pick(b, ["name", "protected"]) for b in data]
    return json.dumps(branches, indent=2)


@mcp.tool()
def create_branch(owner: str, repo: str, branch_name: str,
                  old_branch: str = "main") -> str:
    """Create a new branch from an existing branch."""
    data = _api("POST", f"/repos/{owner}/{repo}/branches",
                json={"new_branch_name": branch_name, "old_branch_name": old_branch})
    return json.dumps(_pick(data, ["name"]), indent=2)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

@mcp.tool()
def get_file_content(owner: str, repo: str, filepath: str, ref: str = "") -> str:
    """Get the content of a file in a repository. ref is optional branch/tag/commit."""
    params = {}
    if ref:
        params["ref"] = ref
    data = _api("GET", f"/repos/{owner}/{repo}/contents/{filepath}", params=params)
    if data.get("encoding") == "base64":
        import base64
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return content
    return data.get("content", "")


@mcp.tool()
def get_directory_content(owner: str, repo: str, path: str = "", ref: str = "") -> str:
    """List files in a directory of a repository."""
    params = {}
    if ref:
        params["ref"] = ref
    data = _api("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
    if isinstance(data, list):
        entries = [_pick(e, ["name", "type", "size", "path"]) for e in data]
        return json.dumps(entries, indent=2)
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

@mcp.tool()
def get_user_info() -> str:
    """Get info about the authenticated user."""
    data = _api("GET", "/user")
    return json.dumps(_pick(data, ["login", "email", "full_name", "is_admin"]), indent=2)


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

@mcp.tool()
def list_milestones(owner: str, repo: str, state: str = "open") -> str:
    """List milestones in a repository."""
    data = _api("GET", f"/repos/{owner}/{repo}/milestones", params={"state": state})
    milestones = [_pick(m, ["id", "title", "description", "state",
                             "open_issues", "closed_issues", "due_on"]) for m in data]
    return json.dumps(milestones, indent=2)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
