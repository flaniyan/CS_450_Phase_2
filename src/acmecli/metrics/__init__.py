from .bus_factor_metric import BusFactorMetric
from .ramp_up_metric import RampUpMetric
from .performance_claims_metric import PerformanceClaimsMetric
from .dataset_and_code_metric import DatasetAndCodeMetric
from .license_metric import LicenseMetric
from .size_metric import SizeMetric
from .code_quality_metric import CodeQualityMetric
from .dataset_quality_metric import DatasetQualityMetric
from .hf_downloads_metric import HFDownloadsMetric
from .cli_metric import CLIMetric
from .logging_env_metric import LoggingEnvMetric

# Phase-2 new metrics
from .score_dependencies import score_dependencies_with_latency
from .score_pull_requests import score_pull_requests_with_latency
from .reviewedness_metric import ReviewednessMetric
from .reproducibility_metric import ReproducibilityMetric
from .treescore_metric import TreescoreMetric
from .base import register

# Register all metrics
register(BusFactorMetric())
register(RampUpMetric())
register(PerformanceClaimsMetric())
register(DatasetAndCodeMetric())
register(LicenseMetric())
register(SizeMetric())
register(CodeQualityMetric())
register(DatasetQualityMetric())
register(HFDownloadsMetric())
register(CLIMetric())
register(LoggingEnvMetric())
register(ReviewednessMetric())
register(ReproducibilityMetric())
register(TreescoreMetric())

# Phase-2 registry for new scoring functions
REGISTRY = {
    "bus_factor": score_dependencies_with_latency,  # placeholder - use actual metric
    "ramp_up": score_dependencies_with_latency,     # placeholder - use actual metric
    "performance_claims": score_dependencies_with_latency,  # placeholder
    "dataset_code": score_dependencies_with_latency,  # placeholder
    "license": score_dependencies_with_latency,  # placeholder
    "size": score_dependencies_with_latency,  # placeholder
    "code_quality": score_dependencies_with_latency,  # placeholder
    "dataset_quality": score_dependencies_with_latency,  # placeholder
    "dependencies": score_dependencies_with_latency,
    "pull_requests": score_pull_requests_with_latency,
}
