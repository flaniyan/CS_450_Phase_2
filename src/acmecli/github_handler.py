import json
import logging
import os
from base64 import b64decode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any, Dict


class GitHubHandler:
    """Handler for GitHub repository metadata fetching using stdlib HTTP."""

    def __init__(self):
        github_token = os.environ.get("GITHUB_TOKEN")
        self._has_token = bool(
            github_token and github_token != "ghp_test_token_placeholder"
        )
        self._headers = {
            "User-Agent": "ACME-CLI/1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if github_token and github_token != "ghp_test_token_placeholder":
            if github_token.startswith("ghp_") or github_token.startswith(
                "github_pat_"
            ):
                self._headers["Authorization"] = f"Bearer {github_token}"
            else:
                self._headers["Authorization"] = f"token {github_token}"
            logging.info(
                "GitHub token found in environment variable - using authenticated requests (5000 req/hour)"
            )
        else:
            logging.warning(
                "GITHUB_TOKEN not set - using unauthenticated requests (60 req/hour). Set GITHUB_TOKEN environment variable for higher rate limits."
            )

    def _get_json(self, url: str) -> Dict[str, Any]:
        request = Request(url, headers=self._headers)
        try:
            with urlopen(request, timeout=10) as response:
                remaining = response.headers.get("X-RateLimit-Remaining")
                if remaining:
                    remaining_int = int(remaining)
                    if remaining_int < 10:
                        logging.warning(
                            "GitHub API rate limit low: %s requests remaining",
                            remaining_int,
                        )
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as http_err:
            if http_err.code == 403:
                rate_limit_reset = http_err.headers.get("X-RateLimit-Reset")
                if rate_limit_reset:
                    logging.error(
                        "GitHub API rate limit exceeded. Reset at: %s", rate_limit_reset
                    )
                else:
                    logging.error(
                        "GitHub API forbidden (403) for %s: %s. Check GITHUB_TOKEN environment variable.",
                        url,
                        http_err,
                    )
            elif http_err.code == 401:
                # 401 is expected when no token is set - log at debug level
                # Only log as error if token was set but is invalid
                if self._has_token:
                    logging.error(
                        "GitHub API unauthorized (401) for %s. GITHUB_TOKEN appears to be invalid.",
                        url,
                    )
                else:
                    logging.debug(
                        "GitHub API unauthorized (401) for %s. GITHUB_TOKEN not set - this is expected for unauthenticated requests.",
                        url,
                    )
            else:
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
                if repo_data.get("license")
                else ""
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
        meta["contributors"] = (
            {
                contrib.get("login", "unknown"): contrib.get("contributions", 0)
                for contrib in contributors[:10]
            }
            if isinstance(contributors, list)
            else {}
        )

        # Extract repo files list for reproducibility metric (optimized - only top-level + key directories)
        try:
            contents_url = (
                f"https://api.github.com/repos/{owner}/{repo}/contents?per_page=100"
            )
            contents_data = self._get_json(contents_url)
            repo_files = set()
            if isinstance(contents_data, list):
                # Only extract files from top-level and key directories (examples, scripts, demo) to reduce API calls
                key_dirs = [
                    "examples",
                    "scripts",
                    "demo",
                    "demos",
                    "src",
                    "tests",
                    "test",
                ]
                for item in contents_data:
                    if item.get("type") == "file":
                        file_path = item.get("path", "")
                        if file_path:
                            repo_files.add(file_path)
                    elif item.get("type") == "dir":
                        dir_name = item.get("name", "").lower()
                        if dir_name in key_dirs:
                            dir_path = item.get("path", "")
                            if dir_path:
                                dir_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{dir_path}?per_page=100"
                                dir_data = self._get_json(dir_url)
                                if isinstance(dir_data, list):
                                    for file_item in dir_data:
                                        if file_item.get("type") == "file":
                                            file_path = file_item.get("path", "")
                                            if file_path:
                                                repo_files.add(file_path)
            meta["repo_files"] = repo_files
        except Exception as files_error:
            logging.warning("Failed to fetch repo files for %s: %s", url, files_error)
            meta["repo_files"] = set()

        readme_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        readme_data = self._get_json(readme_url)
        if readme_data:
            try:
                content = readme_data.get("content", "")
                meta["readme_text"] = (
                    b64decode(content).decode("utf-8", errors="ignore")
                    if content
                    else ""
                )
            except Exception as exc:
                logging.warning("Failed to decode README for %s: %s", url, exc)
                meta["readme_text"] = ""
        else:
            meta["readme_text"] = ""
        try:
            # Limit to 10 PRs to reduce API calls and speed up ingestion
            prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=10&sort=updated"
            prs_data = self._get_json(prs_url)
            prs = []
            if isinstance(prs_data, list):
                for pr in prs_data[:10]:
                    # More reliable merged detection: check merged_at field (None for open, timestamp for merged)
                    # Also check state field: "closed" with merged_at set means merged
                    merged_at = pr.get("merged_at")
                    state = pr.get("state", "open")
                    is_merged = merged_at is not None and state == "closed"

                    pr_info = {
                        "merged": is_merged,
                        "approved": False,
                        "review_count": 0,
                        "additions": pr.get("additions", 0),
                        "files": [],
                    }
                    pr_number = pr.get("number")
                    if pr_number:
                        reviews_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
                        reviews = self._get_json(reviews_url)
                        if isinstance(reviews, list):
                            approved_reviews = [
                                r for r in reviews if r.get("state") == "APPROVED"
                            ]
                            pr_info["review_count"] = len(reviews)
                            pr_info["approved"] = len(approved_reviews) > 0
                        files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
                        files_data = self._get_json(files_url)
                        if isinstance(files_data, list):
                            pr_info["files"] = [
                                {
                                    "filename": f.get("filename", ""),
                                    "additions": f.get("additions", 0),
                                }
                                for f in files_data
                            ]
                    prs.append(pr_info)
            meta["github"] = {"prs": prs}
            # Limit to 5 commits to reduce API calls and speed up ingestion
            commits_url = (
                f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=5"
            )
            commits_data = self._get_json(commits_url)
            direct_commits = []
            if isinstance(commits_data, list):
                # Limit to fewer commits to avoid rate limits, and handle errors gracefully
                rate_limit_hit = False
                for commit in commits_data[:5]:  # Reduced to 5 for faster ingestion
                    commit_info = {"additions": 0, "files": []}
                    commit_sha = commit.get("sha")

                    # If we've hit rate limits, skip detailed fetches and use summary data
                    if rate_limit_hit:
                        stats = commit.get("stats", {})
                        if stats:
                            commit_info["additions"] = stats.get("additions", 0)
                        direct_commits.append(commit_info)
                        continue

                    if commit_sha:
                        try:
                            commit_detail_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
                            commit_detail = self._get_json(commit_detail_url)
                            if isinstance(commit_detail, dict):
                                stats = commit_detail.get("stats", {})
                                commit_info["additions"] = stats.get("additions", 0)
                                files = commit_detail.get("files", [])
                                commit_info["files"] = [
                                    {
                                        "filename": f.get("filename", ""),
                                        "additions": f.get("additions", 0),
                                    }
                                    for f in files
                                ]
                        except HTTPError as http_err:
                            # Check if it's a rate limit error
                            if http_err.code == 403:
                                rate_limit_hit = True
                                logging.warning(
                                    "GitHub API rate limit hit, using summary data for remaining commits"
                                )
                                # Use summary stats from commit list if available
                                stats = commit.get("stats", {})
                                if stats:
                                    commit_info["additions"] = stats.get("additions", 0)
                            else:
                                logging.warning(
                                    "Failed to fetch commit detail for %s: %s",
                                    commit_sha[:8],
                                    http_err,
                                )
                                stats = commit.get("stats", {})
                                if stats:
                                    commit_info["additions"] = stats.get("additions", 0)
                        except Exception as commit_error:
                            # If other error, use summary stats from commit list
                            stats = commit.get("stats", {})
                            if stats:
                                commit_info["additions"] = stats.get("additions", 0)
                            logging.warning(
                                "Failed to fetch commit detail for %s: %s",
                                commit_sha[:8],
                                commit_error,
                            )
                            # Continue with partial data rather than failing completely
                    direct_commits.append(commit_info)
            if "github" not in meta:
                meta["github"] = {}
            meta["github"]["direct_commits"] = direct_commits
        except Exception as pr_error:
            logging.warning("Failed to fetch PR/commit data for %s: %s", url, pr_error)
            if "github" not in meta:
                meta["github"] = {"prs": [], "direct_commits": []}
        return meta


def fetch_github_metadata(url: str) -> Dict[str, Any]:
    """Module-level function to fetch GitHub metadata."""
    handler = GitHubHandler()
    return handler.fetch_meta(url)
