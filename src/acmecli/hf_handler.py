import logging
from urllib.parse import urlparse

import requests


class HFHandler:
    def fetch_meta(self, url: str) -> dict:
        # Example: https://huggingface.co/google/gemma-3-270m or https://huggingface.co/gpt2
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            if not path_parts:
                logging.error(f"Invalid HuggingFace URL format: {url}")
                return {}

            # Handle URLs that omit the namespace (e.g. https://huggingface.co/gpt2)
            namespace_segments = [segment for segment in path_parts if segment not in {"blob", "resolve", "tree"}]
            if not namespace_segments:
                logging.error(f"Unsupported HuggingFace URL format: {url}")
                return {}

            if namespace_segments[0] == "datasets":
                logging.debug("Skipping dataset URL: %s", url)
                return {}

            if len(namespace_segments) == 1:
                model_id = namespace_segments[0]
            else:
                model_id = f"{namespace_segments[0]}/{namespace_segments[1]}"

            api_url = f"https://huggingface.co/api/models/{model_id}"
            resp = requests.get(api_url)
            resp.raise_for_status()
            meta = resp.json()
            # Add typical fields for metrics:
            meta['downloads'] = meta.get('downloads', 0)
            meta['likes'] = meta.get('likes', 0)
            meta['modelId'] = meta.get('modelId', model_id)
            meta['lastModified'] = meta.get('lastModified', "")
            meta['files'] = meta.get('siblings', [])
            # For license, try to extract from cardData if present
            meta['license'] = meta.get('cardData', {}).get('license', "")
            return meta
        except Exception as e:
            logging.error(f"Failed to fetch metadata for {url}: {e}")
            return {}


def fetch_hf_metadata(url: str) -> dict:
    """Module-level function to fetch HuggingFace metadata."""
    handler = HFHandler()
    return handler.fetch_meta(url)
