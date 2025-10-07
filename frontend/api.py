import os
from typing import Any, Dict, List, Optional, Tuple
import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8080")

def _get(url: str):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()

class APIClient:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")

    def get_all(self) -> List[Dict[str, Any]]:
        return _get(f"{self.base}/packages")

    def search(self, q: str) -> List[Dict[str, Any]]:
        return _get(f"{self.base}/packages/search?q={q}")

    def rate(self, name: str) -> Optional[Dict[str, Any]]:
        return _get(f"{self.base}/packages/rate/{name}")

    def upload(self, file_storage, debloat: bool) -> Tuple[bool, str]:
        files = {"file": (file_storage.filename, file_storage.stream, "application/zip")}
        data = {"debloat": str(debloat).lower()}
        try:
            resp = requests.post(f"{self.base}/packages/upload", files=files, data=data, timeout=60)
            if resp.ok:
                return True, "Upload successful"
            return False, f"Upload failed: {resp.text}"
        except Exception as e:
            return False, str(e)

    def reset(self) -> Tuple[bool, str]:
        try:
            resp = requests.post(f"{self.base}/reset", timeout=30)
            if resp.ok:
                return True, "Reset successful"
            return False, f"Reset failed: {resp.text}"
        except Exception as e:
            return False, str(e)

api_client = APIClient(API_BASE)


