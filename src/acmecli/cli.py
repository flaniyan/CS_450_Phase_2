import sys
from pathlib import Path
import logging
import os
import json
import concurrent.futures
from .types import ReportRow
from .reporter import write_ndjson
from .metrics.base import REGISTRY
from .github_handler import GitHubHandler
from .hf_handler import HFHandler
from .cache import InMemoryCache
from .scoring import compute_net_score

def setup_logging():
    log_file = os.environ.get("LOG_FILE")
    raw_level = os.environ.get("LOG_LEVEL", "0")
    try:
        log_level = int(raw_level)
    except ValueError:
        log_level = 0

    level_map = {
        0: logging.CRITICAL + 1,
        1: logging.INFO,
        2: logging.DEBUG,
    }
    level = level_map.get(log_level, logging.ERROR)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch()
        handler = logging.FileHandler(log_path, encoding="utf-8")
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    if log_level == 0:
        handler.setLevel(logging.CRITICAL + 1)
    else:
        handler.setLevel(level)
    root_logger.addHandler(handler)

def classify(url: str) -> str:
    u = url.strip().lower()
    if "huggingface.co/datasets/" in u:
        return "DATASET"
    if "github.com/" in u:
        return "MODEL_GITHUB"
    if "huggingface.co/" in u:
        return "MODEL_HF"
    return "CODE"



def extract_urls(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(',') if part.strip()]

def process_url(url: str, github_handler, hf_handler, cache):
    if classify(url) == "MODEL_GITHUB":
        repo_name = url.split("/")[-1]
        meta = github_handler.fetch_meta(url)
    elif classify(url) == "MODEL_HF":
        repo_name = url.split("/")[-1]
        meta = hf_handler.fetch_meta(url)
    else:
        return None

    if not meta:
        return None

    results = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_metric = {
            executor.submit(m.score, meta): m.name for m in REGISTRY
        }
        for future in concurrent.futures.as_completed(future_to_metric):
            metric_name = future_to_metric[future]
            try:
                mv = future.result()
                results[metric_name] = mv
            except Exception as e:
                logging.error(f"Error computing metric {metric_name}: {e}")
                # Create a default MetricValue for failed metrics
                from .types import MetricValue
                results[metric_name] = MetricValue(metric_name, 0.0, 0)
    
    net_score, net_score_latency = compute_net_score(results)
    
    # Helper function to safely get metric values
    def get_metric_value(name, default=0.0):
        metric = results.get(name)
        return metric.value if metric else default
    
    def get_metric_latency(name, default=0):
        metric = results.get(name)
        return metric.latency_ms if metric else default
    
    # Handle size_score specially since it returns a dict
    size_result = results.get('size_score')
    size_score_value = size_result.value if size_result else {
        'raspberry_pi': 0.0, 'jetson_nano': 0.0, 'desktop_pc': 0.0, 'aws_server': 0.0
    }
    
    return ReportRow(
        name=repo_name,
        category="MODEL",
        net_score=net_score,
        net_score_latency=net_score_latency,
        ramp_up_time=get_metric_value('ramp_up_time'),
        ramp_up_time_latency=get_metric_latency('ramp_up_time'),
        bus_factor=get_metric_value('bus_factor'),
        bus_factor_latency=get_metric_latency('bus_factor'),
        performance_claims=get_metric_value('performance_claims'),
        performance_claims_latency=get_metric_latency('performance_claims'),
        license=get_metric_value('license'),
        license_latency=get_metric_latency('license'),
        size_score=size_score_value,
        size_score_latency=get_metric_latency('size_score'),
        dataset_and_code_score=get_metric_value('dataset_and_code_score'),
        dataset_and_code_score_latency=get_metric_latency('dataset_and_code_score'),
        dataset_quality=get_metric_value('dataset_quality'),
        dataset_quality_latency=get_metric_latency('dataset_quality'),
        code_quality=get_metric_value('code_quality'),
        code_quality_latency=get_metric_latency('code_quality'),
    )

def main(argv: list[str]) -> int:
    setup_logging()
    if len(argv) < 2:
        print("Usage: run score <URL_FILE>")
        return 1
    _, url_file = argv
    github_handler = GitHubHandler()
    hf_handler = HFHandler()
    cache = InMemoryCache()
    lines = Path(url_file).read_text(encoding="utf-8").splitlines()
    for raw in lines:
        for url in extract_urls(raw):
            kind = classify(url)
            logging.debug("Classified URL %s as %s", url, kind)
            if kind not in {"MODEL_GITHUB", "MODEL_HF"}:
                logging.debug("Skipping unsupported URL: %s", url)
                continue
            logging.info("Processing URL: %s", url)
            row = process_url(url, github_handler, hf_handler, cache)
            if row:
                logging.info("Emitted report for %s", row.name)
                write_ndjson(row)
            else:
                logging.debug("No report produced for %s", url)
    return 0