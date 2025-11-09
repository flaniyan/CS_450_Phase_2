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
                # Look for GitHub links in the HTML using multiple patterns
                import re
                github_url = None
                
                # Pattern 1: Direct href links: <a href="https://github.com/owner/repo">
                href_pattern = r'href=["\'](https?://(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)(?:/[^\s"\']*)?)["\']'
                href_matches = re.findall(href_pattern, html_content, re.IGNORECASE)
                if href_matches:
                    for match in href_matches:
                        full_url = match[0]
                        owner, repo = match[1], match[2]
                        # Clean up the URL to just owner/repo
                        github_url = f"https://github.com/{owner}/{repo}"
                        logging.info(f"Found GitHub URL in HTML href: {github_url}")
                        break
                
                # Pattern 2: Plain GitHub URLs in text
                if not github_url:
                    plain_pattern = r'(?:https?://)?(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)'
                    plain_matches = re.findall(plain_pattern, html_content, re.IGNORECASE)
                    if plain_matches:
                        # Filter out common false positives
                        false_positives = ["github.com/", "github.com/explore", "github.com/about"]
                        for owner, repo in plain_matches:
                            potential_url = f"https://github.com/{owner}/{repo}"
                            if potential_url.lower() not in [fp.lower() for fp in false_positives]:
                                github_url = potential_url
                                logging.info(f"Found GitHub URL in HTML text: {github_url}")
                                break
                
                if github_url and "github.com" in github_url:
                    # Clean up the URL (remove trailing slashes, fragments, etc.)
                    github_url = github_url.rstrip("/").split("#")[0].split("?")[0]
                    if "github" not in meta:
                        meta["github"] = github_url
                        logging.info(f"Set GitHub URL from HTML: {github_url}")
                    elif not meta.get("github"):
                        meta["github"] = github_url
                        logging.info(f"Set GitHub URL from HTML (replacing empty): {github_url}")
        except Exception as e:
            logging.debug("Could not fetch model page HTML for GitHub link: %s", e)
        
        return meta


def fetch_hf_metadata(url: str) -> dict:
    """Module-level function to fetch HuggingFace metadata."""
    handler = HFHandler()
    return handler.fetch_meta(url)
