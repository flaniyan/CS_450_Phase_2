import time
from ..types import MetricValue
from .base import register


class RampUpMetric:
    """Metric to assess ease of ramp-up based on documentation and examples."""

    name = "ramp_up_time"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()

        # Heuristics for ramp-up time (higher = easier to ramp up)
        score = 0.0

        # Check for README content
        readme_text = meta.get("readme_text", "").lower()
        if readme_text:
            score += 0.3
            # Look for common documentation sections - expanded keywords
            doc_keywords = [
                "install", "installation", "installing", "installed", "installer",
                "setup", "set up", "setting up", "configure", "configuration", "config",
                "get started", "getting started", "getting-started", "start", "begin",
                "usage", "use", "using", "used", "usage guide", "usage example",
                "how to", "how-to", "howto", "how do", "how does", "how can",
                "tutorial", "tutorials", "tutorial guide", "tutorial example",
                "example", "examples", "example code", "example usage", "example script",
                "sample", "samples", "sample code", "sample usage", "sample script",
                "demo", "demos", "demo code", "demo script", "demo example", "demonstration",
                "quickstart", "quick start", "quick start guide", "quickstart guide",
                "getting started guide", "getting started", "getting-started",
                "guide", "guides", "user guide", "usage guide", "developer guide",
                "start here", "begin here", "start", "begin", "beginning",
                "introduction", "intro", "introduction guide", "intro guide",
                "overview", "overview guide", "model overview", "project overview",
                "basics", "basics guide", "basic tutorial", "basic usage",
                "usage example", "usage examples", "usage sample", "usage samples",
                "code example", "code examples", "code sample", "code samples",
                "run", "running", "run this", "run the model", "run the code",
                "execute", "execution", "execute this", "execute the code",
                "how it works", "how this works", "how to make it work",
                "documentation", "docs", "doc", "documented", "documents", "document",
                "api", "api docs", "api documentation", "api reference", "api guide",
                "readme", "read me", "readme.md", "readme file", "readme.txt",
                "instructions", "instruction", "instruction manual", "instruction guide",
                "steps", "step by step", "step-by-step", "step 1", "step 2",
                "walkthrough", "walk through", "walk-through", "walkthrough guide",
                "getting started", "getting-started", "first steps", "first step",
                "prerequisites", "requirements", "requirement", "dependencies",
                "dependency", "depend", "depends", "depend on", "depends on",
                "environment", "env", "environment setup", "environment configuration",
                "python", "pip", "pip install", "conda", "conda install",
                "npm", "npm install", "yarn", "yarn install", "package manager",
                "download", "downloads", "downloading", "downloaded",
                "clone", "cloning", "cloned", "git clone", "repository", "repo",
                "model card", "modelcard", "model_card", "model documentation",
                "inference", "infer", "inference example", "inference code",
                "predict", "prediction", "predict example", "prediction example",
                "generate", "generation", "generate example", "generation example",
                "load model", "load_model", "loading model", "model loading",
                "use model", "use_model", "using model", "model usage",
                "call model", "call_model", "calling model", "model call",
                "test model", "test_model", "testing model", "model test",
                "evaluate model", "evaluate_model", "evaluating model", "model evaluation",
                "benchmark model", "benchmark_model", "benchmarking model", "model benchmark",
                "demo model", "demo_model", "demonstrating model", "model demo",
                "showcase", "showcases", "showcasing", "showcase example",
                "workflow", "workflows", "workflow example", "example workflow",
                "pipeline", "pipelines", "pipeline example", "example pipeline",
                "endpoint", "endpoints", "endpoint example", "example endpoint",
                "sdk", "sdks", "sdk example", "example sdk",
                "client", "clients", "client example", "example client",
                "wrapper", "wrappers", "wrapper example", "example wrapper",
                "interface", "interfaces", "interface example", "example interface",
                "integration", "integrations", "integration example", "example integration",
            ]
            if any(keyword in readme_text for keyword in doc_keywords):
                score += 0.2
            if any(
                keyword in readme_text
                for keyword in ["api", "documentation", "docs", "wiki", "guide"]
            ):
                score += 0.1

        # Check for presence of wiki
        if meta.get("has_wiki", False):
            score += 0.1

        # Check for active maintenance (recent updates)
        if meta.get("pushed_at"):
            from datetime import datetime, timezone

            try:
                pushed_date = datetime.fromisoformat(
                    meta["pushed_at"].replace("Z", "+00:00")
                )
                now = datetime.now(timezone.utc)
                days_since_push = (now - pushed_date).days
                if days_since_push < 30:
                    score += 0.2
                elif days_since_push < 90:
                    score += 0.1
            except:
                pass

        stars = meta.get("stars", 0)
        if stars > 100:
            score += 0.1

        if readme_text or meta.get("has_wiki", False) or meta.get("pushed_at"):
            score = max(score, 0.5)
        
        if meta:
            score = max(score, 0.5)

        value = round(float(min(1.0, max(0.5, score))), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(RampUpMetric())
