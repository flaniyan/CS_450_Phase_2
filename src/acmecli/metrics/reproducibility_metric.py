import time
from ..types import MetricValue
from .base import register


class ReproducibilityMetric:
    """Heuristic reproducibility score inferred from README and files.

    Scores:
      - 1.0: demo + simple install + referenced targets exist and no secrets
      - 0.5: demo exists but some pieces missing
      - 0.0: no demo/run hints found
    """

    name = "Reproducibility"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        readme = (meta.get("readme_text") or "").lower()
        raw_files = meta.get("repo_files") or set()
        files = {f.replace("\\", "/").lstrip("./").lower() for f in raw_files}

        has_demo = self._has_demo(readme)

        # Per spec: 0 = no code/doesn't run, 0.5 = runs with debugging, 1.0 = runs with no changes/debugging
        if not has_demo:
            # No demonstration code found - model cannot be run using only included code
            value = 0.0
        else:
            # Demo code exists - check if it runs without changes/debugging
            simple_install = self._has_simple_install(readme)
            _, referenced_paths = self._extract_run_target(readme)

            def _path_matches(ref: str) -> bool:
                ref_norm = ref.replace("\\", "/").lstrip("./").lower()
                return any(f.endswith(ref_norm) or f == ref_norm for f in files)

            paths_exist = True
            if referenced_paths:
                paths_exist = all(_path_matches(ref) for ref in referenced_paths)

            has_secrets = self._mentions_secrets(readme)
            needs_heavy_setup = self._needs_heavy_setup(readme)

            # If all conditions are met, it runs with no changes/debugging (1.0)
            # Otherwise, it runs but requires debugging (0.5)
            if (
                simple_install
                and paths_exist
                and not has_secrets
                and not needs_heavy_setup
            ):
                value = 1.0
            else:
                value = 0.5

        value = round(float(value), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)

    def _has_demo(self, text: str) -> bool:
        markers = (
            "quickstart",
            "quick start",
            "quick start guide",
            "quickstart guide",
            "getting started",
            "getting started guide",
            "get started",
            "get started guide",
            "usage",
            "use",
            "usage guide",
            "usage example",
            "usage examples",
            "how to",
            "how-to",
            "howto",
            "how to use",
            "how to run",
            "how to execute",
            "how to use this",
            "how to run this",
            "how to test",
            "how to test this",
            "example",
            "examples",
            "example code",
            "example usage",
            "example usage code",
            "sample",
            "samples",
            "sample code",
            "sample usage",
            "demo",
            "demos",
            "demo code",
            "demo script",
            "demo example",
            "demo usage",
            "demonstration",
            "demonstration code",
            "demonstration script",
            "tutorial",
            "tutorials",
            "tutorial code",
            "tutorial example",
            "guide",
            "guides",
            "user guide",
            "usage guide",
            "developer guide",
            "walkthrough",
            "walk through",
            "walkthrough guide",
            "run",
            "running",
            "run this",
            "run the model",
            "run the code",
            "execute",
            "execution",
            "execute this",
            "execute the code",
            "how it works",
            "how this works",
            "how to make it work",
            "basic usage",
            "basic example",
            "basic demo",
            "basic tutorial",
            "code example",
            "code examples",
            "code sample",
            "code samples",
            "usage example",
            "usage examples",
            "usage sample",
            "installation",
            "install",
            "install guide",
            "installation guide",
            "setup",
            "setup guide",
            "setup instructions",
            "setup example",
            "start here",
            "begin here",
            "start",
            "begin",
            "introduction",
            "intro",
            "introduction guide",
            "overview",
            "overview guide",
            "model overview",
            "basics",
            "basics guide",
            "basic tutorial",
            "python example",
            "python code",
            "python script",
            "python usage",
            "python demo",
            "python tutorial",
            "python guide",
            "inference",
            "infer",
            "inference example",
            "inference code",
            "inference script",
            "run inference",
            "inference demo",
            "predict",
            "prediction",
            "predict example",
            "prediction example",
            "generate",
            "generation",
            "generate example",
            "generation example",
            "test",
            "testing",
            "test example",
            "test code",
            "test script",
            "try",
            "try this",
            "try it",
            "try the model",
            "notebook",
            "notebooks",
            "jupyter notebook",
            "colab notebook",
            "colab",
            "google colab",
            "colab example",
            "script",
            "scripts",
            "example script",
            "demo script",
            "code snippet",
            "code snippets",
            "snippet",
            "snippets",
            "workflow",
            "workflows",
            "example workflow",
            "recipe",
            "recipes",
            "example recipe",
            "playground",
            "playground example",
            "interactive demo",
            "interactive example",
            "interactive tutorial",
            "hands-on",
            "hands on",
            "hands-on example",
            "practical example",
            "practical guide",
            "real-world",
            "real world",
            "real-world example",
            "use case",
            "use cases",
            "use case example",
            "application",
            "applications",
            "application example",
            "implementation",
            "implementations",
            "implementation example",
            "integration",
            "integrations",
            "integration example",
            "deployment",
            "deploy",
            "deployment example",
            "production",
            "production example",
            "production usage",
            "model card",
            "modelcard",
            "model_card",
            "inference",
            "infer",
            "inference example",
            "inference code",
            "predict",
            "prediction",
            "predict example",
            "prediction example",
            "generate",
            "generation",
            "generate example",
            "generation example",
            "load model",
            "load_model",
            "loading model",
            "model loading",
            "use model",
            "use_model",
            "using model",
            "model usage",
            "call model",
            "call_model",
            "calling model",
            "model call",
            "run model",
            "run_model",
            "running model",
            "model run",
            "test model",
            "test_model",
            "testing model",
            "model test",
            "evaluate model",
            "evaluate_model",
            "evaluating model",
            "model evaluation",
            "benchmark model",
            "benchmark_model",
            "benchmarking model",
            "model benchmark",
            "demo model",
            "demo_model",
            "demonstrating model",
            "model demo",
            "showcase",
            "showcases",
            "showcasing",
            "showcase example",
            "sample output",
            "sample_output",
            "sample outputs",
            "example output",
            "output example",
            "output_example",
            "output examples",
            "result",
            "results",
            "result example",
            "example result",
            "usage",
            "usages",
            "usage pattern",
            "usage patterns",
            "workflow",
            "workflows",
            "workflow example",
            "example workflow",
            "pipeline",
            "pipelines",
            "pipeline example",
            "example pipeline",
            "endpoint",
            "endpoints",
            "endpoint example",
            "example endpoint",
            "api",
            "apis",
            "api example",
            "example api",
            "api usage",
            "sdk",
            "sdks",
            "sdk example",
            "example sdk",
            "client",
            "clients",
            "client example",
            "example client",
            "wrapper",
            "wrappers",
            "wrapper example",
            "example wrapper",
            "interface",
            "interfaces",
            "interface example",
            "example interface",
            "integration",
            "integrations",
            "integration example",
            "example integration",
        )

        code_fence = (
            ("```" in text)
            or ("`python" in text)
            or ("```python" in text)
            or ("```py" in text)
            or ("```python3" in text)
        )

        has_marker = any(m in text for m in markers)
        # Only exclude if explicitly negative
        for m in markers:
            if f"no {m}" in text or f"not {m}" in text or f"without {m}" in text:
                has_marker = False
                break

        has_python_cmd = (
            ("python " in text)
            or ("python3 " in text)
            or (".py" in text)
            or ("python -m" in text)
            or ("python -c" in text)
            or ("python.exe" in text)
            or ("python3.exe" in text)
            or ("from " in text and "import " in text)
            or (
                "import " in text
                and ("torch" in text or "tensorflow" in text or "transformers" in text)
            )
        )
        has_code_block = (
            code_fence
            or ("<code>" in text)
            or ("code block" in text)
            or ("```" in text)
            or ("<pre>" in text)
            or ("<script>" in text)
            or ("code:" in text)
            or ("code example:" in text)
        )
        has_notebook = (
            ".ipynb" in text
            or "jupyter notebook" in text
            or "colab notebook" in text
            or "google colab" in text
        )
        return has_marker or has_code_block or has_python_cmd or has_notebook

    def _has_simple_install(self, text: str) -> bool:
        simple_patterns = (
            "pip install ",
            "pip3 install ",
            "pip install -r",
            "pip install -e",
            "pip install -r requirements.txt",
            "pip install -r requirements",
            "pip install",
            "pip3 install",
            "pip install --user",
            "python -m pip install",
            "python -m pip install -r",
            "python3 -m pip install",
            "python3 -m pip install -r",
            "easy_install",
            "easy_install ",
            "easy_install -m",
            "python setup.py install",
            "python setup.py",
            "python setup.py --user",
            "python3 setup.py install",
            "python3 setup.py",
            "pipenv install",
            "pipenv sync",
            "pipenv install --dev",
            "venv",
            "virtualenv",
            "python -m venv",
            "python3 -m venv",
            "python -m virtualenv",
            "python3 -m virtualenv",
            "source activate",
            "source venv/bin/activate",
            "conda install",
            "conda env",
            "conda create",
            "conda activate",
            "environment.yml",
            "environment.yaml",
            "requirements.txt",
            "requirements",
            "requirements-dev.txt",
            "requirements-dev",
            "pip freeze",
            "pip list",
            "pip show",
            "npm install",
            "npm install --save",
            "yarn install",
            "gem install",
            "bundle install",
            "go get",
            "go install",
            "cargo install",
            "cargo build",
            "mvn install",
            "mvn compile",
            "gradle install",
            "gradle build",
        )

        # Only consider truly heavy if it's the only option
        heavy = (
            "conda create",
            "mamba create",
            "mamba install",
            "docker build",
            "docker compose",
            "docker-compose",
            "make install",
            "make build",
            "cmake build",
            "poetry build",
            "poetry install --no-dev",
        )

        has_simple = any(p in text for p in simple_patterns)
        has_heavy_only = any(h in text for h in heavy) and not has_simple
        # Be lenient: if there's any simple pattern, give credit
        return has_simple and not has_heavy_only

    def _extract_run_target(self, text: str):
        referenced = []
        run_cmd = None

        for line in text.splitlines():
            ln = line.strip()
            if ln.startswith("python ") or ln.startswith("python3 "):
                run_cmd = ln
                parts = ln.split()
                if len(parts) >= 2 and parts[1].endswith(".py"):
                    referenced.append(parts[1])

            if "examples/" in ln or "demo/" in ln or "scripts/" in ln:
                for token in ln.replace("(", " ").replace(")", " ").split():
                    if token.endswith(".py") and (
                        "/examples/" in token
                        or "/demo/" in token
                        or "/scripts/" in token
                    ):
                        referenced.append(token)

        return run_cmd, list(set(referenced))

    def _mentions_secrets(self, text: str) -> bool:
        secrets = (
            "api_key",
            "hf_token",
            "huggingface-cli login",
            "export ",
            "setx ",
            "aws_access_key_id",
            "gcloud auth",
            "az login",
        )

        return any(s in text for s in secrets)

    def _needs_heavy_setup(self, text: str) -> bool:
        gpu = ("cuda", "cudnn", "nvidia-smi")
        datasets = (
            "datasets load_dataset",
            "wget ",
            "curl http",
            "kaggle datasets",
            "unzip ",
            "tar -x",
        )

        return any(x in text for x in gpu + datasets)

    def _has_any_code_indicators(self, text: str, files: set) -> bool:
        code_extensions = (
            ".py",
            ".js",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".ipynb",
            ".ts",
            ".tsx",
            ".jsx",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".sh",
            ".bash",
            ".r",
            ".m",
            ".sql",
            ".html",
            ".css",
            ".vue",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".md",
            ".txt",
            ".rst",
            ".org",
            ".xml",
            ".csv",
            ".tsv",
        )
        code_keywords = (
            "import",
            "from",
            "def",
            "function",
            "class",
            "module",
            "package",
            "require",
            "include",
            "using",
            "namespace",
            "public",
            "private",
            "const",
            "let",
            "var",
            "return",
            "if",
            "else",
            "for",
            "while",
            "try",
            "except",
            "catch",
            "finally",
            "async",
            "await",
            "promise",
            "code",
            "script",
            "program",
            "programming",
            "software",
            "library",
            "framework",
            "api",
            "sdk",
            "tool",
            "toolkit",
            "utility",
            "helper",
            "model",
            "train",
            "training",
            "inference",
            "predict",
            "generate",
            "example",
            "demo",
            "tutorial",
            "usage",
            "guide",
            "documentation",
        )
        code_patterns = (
            "```",
            "<code>",
            "code:",
            "code example",
            "code block",
            "python",
            "javascript",
            "typescript",
            "java",
            "c++",
            "c#",
            "programming",
            "script",
            "library",
            "framework",
            "api",
            "function",
            "method",
            "variable",
            "constant",
            "parameter",
            "github",
            "repository",
            "repo",
            "git",
            "version control",
            "install",
            "setup",
            "configure",
            "run",
            "execute",
            "test",
        )

        has_code_ext = any(ext in text for ext in code_extensions)
        has_code_keyword = any(kw in text for kw in code_keywords)
        has_code_pattern = any(pattern in text for pattern in code_patterns)
        has_code_file = any(f.endswith(code_extensions) for f in files)
        has_imports = (
            "import " in text
            or "from " in text
            or "require(" in text
            or "include " in text
        )
        has_github = (
            "github" in text or "git" in text or "repository" in text or "repo" in text
        )

        return (
            has_code_ext
            or has_code_keyword
            or has_code_pattern
            or has_code_file
            or has_imports
            or has_github
        )


register(ReproducibilityMetric())
