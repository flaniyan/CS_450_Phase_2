from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from acmecli.cache import InMemoryCache
from acmecli.cli import classify, process_url, setup_logging
from acmecli.github_handler import GitHubHandler
from acmecli.hf_handler import HFHandler

SUPPORTED_SOURCES = {"MODEL_GITHUB", "MODEL_HF"}


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score repositories listed in a URL file and emit NDJSON records.",
    )
    parser.add_argument(
        "-i",
        "--input",
        default="urls.txt",
        help="Path to a text file containing one URL per line (default: urls.txt).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def iter_urls(path: Path) -> Iterable[str]:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        url = raw_line.strip()
        if url:
            yield url


def build_record(url: str, net_score: float, latency_ms: float, name: str) -> dict[str, object]:
    return {
        "model": name,
        "urls": [url],
        "NET_SCORE": round(net_score * 100.0, 1),
        "LATENCY": round(float(latency_ms), 1),
    }


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging()

    urls_path = Path(args.input)
    if not urls_path.exists():
        print(f"URL file not found: {urls_path}", file=sys.stderr)
        return 1

    github_handler = GitHubHandler()
    hf_handler = HFHandler()
    cache = InMemoryCache()

    emitted = 0
    for url in iter_urls(urls_path):
        source_kind = classify(url)
        if source_kind not in SUPPORTED_SOURCES:
            logging.debug("Skipping unsupported URL: %s", url)
            continue

        try:
            row = process_url(url, github_handler, hf_handler, cache)
        except Exception as exc:  # pragma: no cover - defensive safety
            logging.error("Failed to process %s: %s", url, exc)
            continue

        if not row:
            logging.warning("No data produced for %s", url)
            continue

        record = build_record(url, row.net_score, row.net_score_latency, row.name)
        print(json.dumps(record, ensure_ascii=False))
        emitted += 1

    if emitted == 0:
        logging.warning("No NDJSON records were emitted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
