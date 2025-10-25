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
        return meta


def fetch_hf_metadata(url: str) -> dict:
    """Module-level function to fetch HuggingFace metadata."""
    handler = HFHandler()
    return handler.fetch_meta(url)
