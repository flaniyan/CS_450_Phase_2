import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from typing import Dict, List, Set


class HFHandler:
    def __init__(self) -> None:
        self._headers = {"User-Agent": "ACME-CLI/1.0"}

    def _extract_hyperlinks_from_text(self, text: str) -> Dict[str, List[str]]:
        """
        Extract all hyperlinks from README text including:
        - Markdown links: [text](url)
        - Plain URLs: https://example.com
        - HTML links: <a href="url">text</a>
        - Context-aware extraction for common phrases

        Returns a dict with categorized links:
        {
            "github": [list of GitHub URLs],
            "huggingface": [list of HuggingFace model URLs],
            "other": [list of other URLs]
        }
        """
        if not text:
            return {"github": [], "huggingface": [], "other": []}

        links = {"github": [], "huggingface": [], "other": []}
        seen_urls: Set[str] = set()

        # Pattern 1: HTML hyperlink (e.g., <a href="https://example.com">Click here</a>)
        # Using pattern: href=["'](.*?)["']
        html_href_pattern = r'href=["\'](.*?)["\']'
        for match in re.finditer(html_href_pattern, text, re.IGNORECASE):
            url = match.group(1).strip()
            # Only process if it's an HTTP/HTTPS URL
            if url.startswith(("http://", "https://")):
                # Clean up URL (remove fragments, query params, trailing slashes)
                url = url.split("#")[0].split("?")[0].rstrip("/")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    self._categorize_url(url, links)

        # Pattern 2: Markdown hyperlink (e.g., [Click here](https://example.com))
        # Using pattern: \]\((https?://[^\s)]+)\)
        markdown_pattern = r"\]\((https?://[^\s)]+)\)"
        for match in re.finditer(markdown_pattern, text, re.IGNORECASE):
            url = match.group(1).strip().rstrip("/")
            if url and url not in seen_urls:
                seen_urls.add(url)
                self._categorize_url(url, links)

        # Pattern 3: Generic URL finder (any URL in plain text)
        # Using pattern: https?://[^\s"'>)]+
        generic_url_pattern = r'https?://[^\s"\'>)]+'
        for match in re.finditer(generic_url_pattern, text, re.IGNORECASE):
            url = match.group(0).strip().rstrip("/")
            # Clean up trailing punctuation
            url = re.sub(r"[.,;:!?]+$", "", url)
            if url and url not in seen_urls:
                seen_urls.add(url)
                self._categorize_url(url, links)

        # Pattern 4: Context-aware extraction for GitHub URLs
        # Look for common phrases followed by GitHub URLs
        # Comprehensive list of keywords/phrases that might reference GitHub repositories
        github_keywords = [
            # Repository references
            r"(?:this\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)",
            r"(?:the\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)",
            r"(?:our\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)",
            r"(?:original\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)",
            r"(?:official\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)",
            r"(?:main\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)",
            r"(?:primary\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)",
            # Action verbs
            r"(?:see|check|visit|view|access|find|get|download|clone|fork|browse|open|go\s+to)",
            r"(?:available|found|located|hosted|published|released|stored|kept)",
            r"(?:can\s+be\s+found|is\s+available|is\s+located|is\s+hosted|is\s+published)",
            # Prepositions and connectors
            r"(?:available\s+)?(?:on|at|in|from|via|through|using)",
            r"(?:link|url|uri|address|location|reference)",
            r"(?:homepage|website|site|page|web\s+page)",
            # GitHub-specific
            r"(?:github|git\s+hub|gh|git\s+hub\s+repo)",
            r"(?:on\s+github|at\s+github|in\s+github|via\s+github)",
            # Source/origin references
            r"(?:source|origin|original|base|foundation)",
            r"(?:source\s+code|source\s+repository|source\s+repo)",
            # Documentation references
            r"(?:documentation|docs|readme|read\s+me)",
            r"(?:more\s+info|more\s+information|details|further\s+info)",
            # Common phrases
            r"(?:first\s+released|initially\s+released|originally\s+released)",
            r"(?:released\s+in|published\s+in|hosted\s+on)",
            r"(?:check\s+out|take\s+a\s+look|have\s+a\s+look)",
        ]

        # Pattern 4a: GitHub URLs after common phrases
        # Matches patterns like:
        # - "available on https://github.com/owner/repo"
        # - "see GitHub: https://github.com/owner/repo"
        # - "repository: https://github.com/owner/repo"
        # - "first released in https://github.com/owner/repo"
        for keyword in github_keywords:
            context_pattern = rf"(?:{keyword})[\s:]*[:=]?\s*(?:https?://)?(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)"
            for match in re.finditer(context_pattern, text, re.IGNORECASE):
                owner, repo = match.groups()
                url = f"https://github.com/{owner}/{repo}"
                if url not in seen_urls:
                    seen_urls.add(url)
                    self._categorize_url(url, links)

        # Pattern 4b: GitHub URLs before common phrases (reverse order)
        # Matches patterns like "https://github.com/owner/repo repository" or "https://github.com/owner/repo (code)"
        github_url_before_pattern = r"(?:https?://)?(?:www\.)?github\.com/([\w\-\.]+)/([\w\-\.]+)[\s,]*[:=]?\s*(?:this\s+)?(?:repository|repo|codebase|source\s+code|project|implementation|code)"
        for match in re.finditer(github_url_before_pattern, text, re.IGNORECASE):
            owner, repo = match.groups()
            url = f"https://github.com/{owner}/{repo}"
            if url not in seen_urls:
                seen_urls.add(url)
                self._categorize_url(url, links)

        # Pattern 5: HuggingFace URLs near common phrases
        hf_context_patterns = [
            r"(?:based\s+on|derived\s+from|fine[-\s]?tuned\s+from|pretrained\s+on)",
            r"(?:parent\s+model|base\s+model|foundation\s+model|backbone)",
            r"(?:model|checkpoint|weights)",
            r"(?:huggingface|hf|hugging\s+face)",
        ]

        for pattern in hf_context_patterns:
            hf_context_pattern = rf"(?:{pattern})[\s:]*[:=]?\s*(?:https?://)?(?:www\.)?huggingface\.co/([^/\s]+(?:/[^/\s]+)?)"
            for match in re.finditer(hf_context_pattern, text, re.IGNORECASE):
                model_id = match.group(1)
                if not model_id.startswith("datasets/") and not model_id.startswith(
                    "spaces/"
                ):
                    url = f"https://huggingface.co/{model_id}"
                    if url not in seen_urls:
                        seen_urls.add(url)
                        self._categorize_url(url, links)

        return links

    def _categorize_url(self, url: str, links: Dict[str, List[str]]) -> None:
        """Categorize a URL and add it to the appropriate list."""
        url_lower = url.lower()

        # GitHub URLs
        if "github.com" in url_lower:
            # Extract owner/repo and normalize
            github_match = re.search(
                r"github\.com/([\w\-\.]+)/([\w\-\.]+)", url_lower, re.IGNORECASE
            )
            if github_match:
                owner, repo = github_match.groups()
                # Filter out common false positives
                false_positives = [
                    "github.com/explore",
                    "github.com/about",
                    "github.com/pricing",
                ]
                normalized_url = f"https://github.com/{owner}/{repo}"
                if normalized_url.lower() not in [fp.lower() for fp in false_positives]:
                    if normalized_url not in links["github"]:
                        links["github"].append(normalized_url)

        # HuggingFace model URLs
        elif "huggingface.co" in url_lower:
            # Extract model ID and normalize
            hf_match = re.search(
                r"huggingface\.co/([^/\s]+(?:/[^/\s]+)?)", url_lower, re.IGNORECASE
            )
            if hf_match:
                model_id = hf_match.group(1)
                # Skip datasets and other non-model paths
                if not model_id.startswith("datasets/") and not model_id.startswith(
                    "spaces/"
                ):
                    normalized_url = f"https://huggingface.co/{model_id}"
                    if normalized_url not in links["huggingface"]:
                        links["huggingface"].append(normalized_url)

        # Other URLs
        else:
            if url not in links["other"]:
                links["other"].append(url)

    def _get_json(self, url: str) -> dict:
        request = Request(url, headers=self._headers)
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as http_err:
            # 401 errors from HuggingFace are often rate limiting or temporary - log at debug level
            if http_err.code == 401:
                logging.debug(
                    "HTTP error fetching %s: %s (401 Unauthorized - may be rate limiting)",
                    url,
                    http_err,
                )
            else:
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

        # Extract README text and hyperlinks from cardData
        card_data = meta.get("cardData", {})
        readme_text = ""
        if isinstance(card_data, dict):
            # Try to get README from various possible fields
            readme_text = (
                card_data.get("---", "")
                or card_data.get("readme", "")
                or card_data.get("README", "")
                or ""
            )
            if isinstance(readme_text, str):
                meta["readme_text"] = readme_text
            else:
                meta["readme_text"] = ""
        else:
            meta["readme_text"] = ""

        # Extract hyperlinks from README text
        if readme_text:
            links = self._extract_hyperlinks_from_text(readme_text)

            # Store GitHub URLs (prioritize first one for backward compatibility)
            if links["github"]:
                first_github_url = links["github"][0]
                if "github" not in meta or not meta.get("github"):
                    meta["github"] = first_github_url
                # Also set github_url for reviewedness metric compatibility
                if "github_url" not in meta or not meta.get("github_url"):
                    meta["github_url"] = first_github_url
                meta["github_urls"] = links["github"]  # Store all GitHub URLs
                logging.info(f"Found {len(links['github'])} GitHub URL(s) in README")

            # Store HuggingFace model URLs (potential parent models)
            if links["huggingface"]:
                meta["huggingface_links"] = links["huggingface"]
                logging.info(
                    f"Found {len(links['huggingface'])} HuggingFace model URL(s) in README"
                )

            # Store other URLs
            if links["other"]:
                meta["other_links"] = links["other"]
                logging.info(f"Found {len(links['other'])} other URL(s) in README")

        # Also try to fetch the model page HTML to extract GitHub link from the rendered page
        # This is important because hyperlinks in the rendered HTML (like "this repository")
        # may not be in the markdown README text
        try:
            page_url = f"https://huggingface.co/{model_id}"
            request = Request(page_url, headers=self._headers)
            with urlopen(request, timeout=10) as response:
                html_content = response.read().decode("utf-8", errors="ignore")

                # Extract all hyperlinks from the HTML page (including rendered README)
                html_links = self._extract_hyperlinks_from_text(html_content)

                # Store GitHub URLs found in HTML (prioritize if not already found)
                if html_links["github"]:
                    first_github_url = html_links["github"][0]
                    if "github" not in meta or not meta.get("github"):
                        meta["github"] = first_github_url
                    if "github_url" not in meta or not meta.get("github_url"):
                        meta["github_url"] = first_github_url
                    # Merge with existing github_urls
                    if "github_urls" not in meta:
                        meta["github_urls"] = []
                    for url in html_links["github"]:
                        if url not in meta["github_urls"]:
                            meta["github_urls"].append(url)
                    logging.info(
                        f"Found {len(html_links['github'])} GitHub URL(s) in HTML page"
                    )

                # Also store HuggingFace links from HTML
                if html_links["huggingface"]:
                    if "huggingface_links" not in meta:
                        meta["huggingface_links"] = []
                    for url in html_links["huggingface"]:
                        if url not in meta["huggingface_links"]:
                            meta["huggingface_links"].append(url)

                # Also store other links from HTML
                if html_links["other"]:
                    if "other_links" not in meta:
                        meta["other_links"] = []
                    for url in html_links["other"]:
                        if url not in meta["other_links"]:
                            meta["other_links"].append(url)
        except Exception as e:
            logging.debug("Could not fetch model page HTML for GitHub link: %s", e)

        return meta


def fetch_hf_metadata(url: str) -> dict:
    """Module-level function to fetch HuggingFace metadata."""
    handler = HFHandler()
    return handler.fetch_meta(url)
