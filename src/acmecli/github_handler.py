import json
import logging
from base64 import b64decode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any, Dict


class GitHubHandler:
    """Handler for GitHub repository metadata fetching using stdlib HTTP."""

    def __init__(self):
        self._headers = {
            "User-Agent": "ACME-CLI/1.0",
            "Accept": "application/vnd.github.v3+json",
        }

    def _get_json(self, url: str) -> Dict[str, Any]:
        request = Request(url, headers=self._headers)
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as http_err:
            logging.error("HTTP error fetching %s: %s", url, http_err)
        except URLError as url_err:
            logging.error("Network error fetching %s: %s", url, url_err)
        except Exception as exc:
            logging.error("Unexpected error fetching %s: %s", url, exc)
        return {}

    def fetch_meta(self, url: str) -> Dict[str, Any]:
        """Fetch repository metadata from GitHub API."""
        parts = url.rstrip("/").split("/")
        if len(parts) < 5 or "github.com" not in parts[2]:
            logging.error("Invalid GitHub URL format: %s", url)
            return {}

        owner, repo = parts[3], parts[4]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_data = self._get_json(api_url)
        if not repo_data:
            return {}

        meta = {
            "name": repo_data.get("name", ""),
            "full_name": repo_data.get("full_name", ""),
            "description": repo_data.get("description", ""),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "watchers": repo_data.get("watchers_count", 0),
            "size": repo_data.get("size", 0),
            "language": repo_data.get("language", ""),
            "topics": repo_data.get("topics", []),
            "license": (
                repo_data.get("license", {}).get("spdx_id", "")
                if repo_data.get("license") else ""
            ),
            "created_at": repo_data.get("created_at", ""),
            "updated_at": repo_data.get("updated_at", ""),
            "pushed_at": repo_data.get("pushed_at", ""),
            "default_branch": repo_data.get("default_branch", "main"),
            "open_issues_count": repo_data.get("open_issues_count", 0),
            "has_wiki": repo_data.get("has_wiki", False),
            "has_pages": repo_data.get("has_pages", False),
            "archived": repo_data.get("archived", False),
            "disabled": repo_data.get("disabled", False),
        }

        contributors_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
        contributors = self._get_json(contributors_url)
        meta["contributors"] = {
            contrib.get("login", "unknown"): contrib.get("contributions", 0)
            for contrib in contributors[:10]
        } if isinstance(contributors, list) else {}

        readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        readme_data = self._get_json(readme_url)
        if readme_data:
            try:
                content = readme_data.get("content", "")
                meta["readme_text"] = (
                    b64decode(content).decode("utf-8", errors="ignore")
                    if content else ""
                )
            except Exception as exc:
                logging.warning("Failed to decode README for %s: %s", url, exc)
                meta["readme_text"] = ""
        else:
            meta["readme_text"] = ""

        return meta


def fetch_github_metadata(url: str) -> Dict[str, Any]:
    """Module-level function to fetch GitHub metadata."""
    handler = GitHubHandler()
    return handler.fetch_meta(url)

