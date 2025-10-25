from .base import register


class ReproducibilityMetric:
    """Heuristic reproducibility score inferred from README and files.

    Scores:
      - 1.0: demo + simple install + referenced targets exist and no secrets
      - 0.5: demo exists but some pieces missing
      - 0.0: no demo/run hints found
    """

    name = "Reproducibility"

    def score(self, meta: dict) -> float:
        readme = (meta.get("readme_text") or "").lower()
        raw_files = meta.get("repo_files") or set()
        files = {f.replace("\\", "/").lstrip("./").lower() for f in raw_files}

        if not self._has_demo(readme):
            return 0.0

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

        # Full score: demo + simple install + paths exist + no secrets + no heavy setup
        if simple_install and paths_exist and not has_secrets and not needs_heavy_setup:
            return 1.0

        # Half score: demo exists but missing some pieces
        return 0.5

    def _has_demo(self, text: str) -> bool:
        markers = (
            "quickstart",
            "usage",
            "example",
            "demo",
            "how to run",
            "getting started",
        )

        code_fence = ("```" in text) or ("`python" in text) or ("```python" in text)

        has_marker = any(m in text for m in markers)
        for m in markers:
            if f"no {m}" in text or f"not {m}" in text:
                has_marker = False
                break

        has_python_cmd = ("python " in text) or ("python3 " in text) or (".py" in text)
        return has_marker or code_fence or has_python_cmd

    def _has_simple_install(self, text: str) -> bool:
        simple_patterns = (
            "pip install ",
            "pip3 install ",
            "pip install -r requirements.txt",
        )

        heavy = (
            "conda create",
            "mamba install",
            "docker run",
            "make ",
            "cmake ",
            "poetry install",
        )

        return any(p in text for p in simple_patterns) and not any(
            h in text for h in heavy
        )

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


register(ReproducibilityMetric())
