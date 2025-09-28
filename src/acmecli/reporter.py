import json
from dataclasses import asdict
from .types import ReportRow

def write_ndjson(row: ReportRow) -> None:
    print(json.dumps(asdict(row), ensure_ascii=False))


class Reporter:
    """Simple reporter class for formatting data."""
    
    def format(self, data: dict) -> str:
        """Format data as JSON string."""
        return json.dumps(data, ensure_ascii=False)
