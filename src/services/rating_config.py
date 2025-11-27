"""
Configuration constants for rating system.
All thresholds and defaults are configurable via environment variables.
"""
import os
from typing import List

# Ingestibility threshold - minimum score required for model ingestion
INGESTIBILITY_THRESHOLD = float(os.getenv("RATING_INGESTIBILITY_THRESHOLD", "0.5"))

# Default score value when metric cannot be computed
DEFAULT_SCORE = float(os.getenv("RATING_DEFAULT_SCORE", "0.0"))

# Default category when category cannot be determined
DEFAULT_CATEGORY = os.getenv("RATING_DEFAULT_CATEGORY", "unknown")

# Default size scores when size metric cannot be computed
DEFAULT_SIZE_SCORES = {
    "raspberry_pi": float(os.getenv("RATING_DEFAULT_SIZE_RASPBERRY_PI", "0.0")),
    "jetson_nano": float(os.getenv("RATING_DEFAULT_SIZE_JETSON_NANO", "0.0")),
    "desktop_pc": float(os.getenv("RATING_DEFAULT_SIZE_DESKTOP_PC", "0.0")),
    "aws_server": float(os.getenv("RATING_DEFAULT_SIZE_AWS_SERVER", "0.0")),
}

# Model versions to try when version is not specified
DEFAULT_MODEL_VERSIONS: List[str] = os.getenv(
    "RATING_DEFAULT_MODEL_VERSIONS", "1.0.0,main,latest"
).split(",")

# Rounding precision for scores
SCORE_PRECISION = int(os.getenv("RATING_SCORE_PRECISION", "2"))



