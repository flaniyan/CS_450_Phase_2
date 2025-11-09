import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class HFHandler:
    def __init__(self) -> None:
        self._headers = {"User-Agent": "ACME-CLI/1.0"}

    def _get_json(self, url: str) -> dict:
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

    def fetch_meta(self, url: str) -> dict:
        # Example: https://huggingface.co/google/gemma-3-270m or https://huggingface.co/gpt2
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if not path_parts:
            logging.error("Invalid HuggingFace URL format: %s", url)
            return {}

        namespace_segments = [
            segment
            for segment in path_parts
            if segment not in {"blob", "resolve", "tree"}
        ]
        if not namespace_segments:
            logging.error("Unsupported HuggingFace URL format: %s", url)
            return {}

        if namespace_segments[0] == "datasets":
            logging.debug("Skipping dataset URL: %s", url)
            return {}

        model_id = (
            namespace_segments[0]
            if len(namespace_segments) == 1
            else f"{namespace_segments[0]}/{namespace_segments[1]}"
        )
        api_url = f"https://huggingface.co/api/models/{model_id}"
        meta = self._get_json(api_url)
        if not meta:
            return {}

        meta["downloads"] = meta.get("downloads", 0)
        meta["likes"] = meta.get("likes", 0)
        meta["modelId"] = meta.get("modelId", model_id)
        meta["lastModified"] = meta.get("lastModified", "")
        meta["files"] = meta.get("siblings", [])
        meta["license"] = meta.get("cardData", {}).get("license", "")
        
        # Also try to fetch the model page HTML to extract GitHub link from the page
        try:
            page_url = f"https://huggingface.co/{model_id}"
            request = Request(page_url, headers=self._headers)
            with urlopen(request, timeout=10) as response:
                html_content = response.read().decode("utf-8", errors="ignore")
                # Look for GitHub links in the HTML
                import re
                github_patterns = [
                    r'href=["\'](https?://github\.com/[\w\-\.]+/[\w\-\.]+)["\']',
                    r'github\.com/([\w\-\.]+)/([\w\-\.]+)',
                ]
                for pattern in github_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    if matches:
                        if isinstance(matches[0], tuple):
                            owner, repo = matches[0]
                            github_url = f"https://github.com/{owner}/{repo}"
                        else:
                            github_url = matches[0]
                        if github_url and "github.com" in github_url:
                            if "github" not in meta:
                                meta["github"] = github_url
                            elif not meta.get("github"):
                                meta["github"] = github_url
                            break
        except Exception as e:
            logging.debug("Could not fetch model page HTML for GitHub link: %s", e)
        
        return meta


def fetch_hf_metadata(url: str) -> dict:
    """Module-level function to fetch HuggingFace metadata."""
    handler = HFHandler()
    return handler.fetch_meta(url)
