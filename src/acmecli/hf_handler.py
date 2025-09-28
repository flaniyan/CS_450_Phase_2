import requests
import logging

class HFHandler:
    def fetch_meta(self, url: str) -> dict:
        # Example: https://huggingface.co/google/gemma-3-270m
        try:
            parts = url.split("/")
            # huggingface.co/<username_or_org>/<model_name>
            org, model = parts[3], parts[4]
            api_url = f"https://huggingface.co/api/models/{org}/{model}"
            resp = requests.get(api_url)
            resp.raise_for_status()
            meta = resp.json()
            # Add typical fields for metrics:
            meta['downloads'] = meta.get('downloads', 0)
            meta['likes'] = meta.get('likes', 0)
            meta['modelId'] = meta.get('modelId', f"{org}/{model}")
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