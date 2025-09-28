from dataclasses import dataclass, asdict
from typing import Protocol, Iterable, TypedDict, Literal, Optional, Dict

Category = Literal["MODEL", "DATASET", "CODE"]
Source   = Literal["GITHUB", "HUGGINGFACE", "LOCAL"]

@dataclass(frozen=True)
class TargetSpec:
    url: str
    source: Source
    name: str
    category: Category
    revision: Optional[str] = None  # commit/tag if known

class Signals(TypedDict, total=False):
    readme_text: str
    license_name: str
    contributors: Dict[str, int]
    stars: int
    downloads: int

@dataclass(frozen=True)
class MetricValue:
    name: str              # e.g. "ramp_up_time"
    value: float           # [0,1]
    latency_ms: int

@dataclass(frozen=True)
class ReportRow:
    # Required NDJSON fields + per-metric latencies (values are stubs for now)
    name: str
    category: Category
    net_score: float
    net_score_latency: int
    ramp_up_time: float
    ramp_up_time_latency: int
    bus_factor: float
    bus_factor_latency: int
    performance_claims: float
    performance_claims_latency: int
    license: float
    license_latency: int
    size_score: Dict[str, float]     # {raspberry_pi, jetson_nano, desktop_pc, aws_server}
    size_score_latency: int
    dataset_and_code_score: float
    dataset_and_code_score_latency: int
    dataset_quality: float
    dataset_quality_latency: int
    code_quality: float
    code_quality_latency: int

class SourceHandler(Protocol):
    def resolve_revision(self, url: str) -> str: ...
    def fetch_meta(self, spec: TargetSpec) -> dict: ...
    def stream_files(self, spec: TargetSpec, patterns: list[str]) -> Iterable[tuple[str, bytes]]: ...

class Cache(Protocol):
    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, data: bytes, etag: str | None = None) -> None: ...

class Metric(Protocol):
    name: str
    def collect(self, spec: TargetSpec, handler: SourceHandler, cache: Cache) -> Signals: ...
    def score(self, signals: Signals) -> MetricValue: ...
