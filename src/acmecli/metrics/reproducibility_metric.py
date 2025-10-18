from .base import register


class ReproducibilityMetric:
    name = "Reproducibility"

    def score(self, meta: dict) -> float:
        """
        meta expected keys (extend your fetcher to provide):
          - readme_text: str  (normalized model card/README)
          - repo_files: set[str]  (all paths in repo zip or tree)
        """
        readme = (meta.get("readme_text") or "").lower()
        # Normalize repo file paths for case- and separator-insensitive matching
        raw_files = meta.get("repo_files") or set()
        files = {f.replace("\\", "/").lstrip("./").lower() for f in raw_files}

        # No demo section / code blocks? -> 0.0
        if not _has_demo(readme):
            return 0.0

        # Check for simple install and runnable script present
        simple_install = _has_simple_install(readme)
        run_cmd, referenced_paths = _extract_run_target(readme)

        # consider a referenced path present if any repo file endswith
        # the referenced token
        def _path_matches(ref: str) -> bool:
            ref_norm = ref.replace("\\", "/").lstrip("./").lower()
            return any(f.endswith(ref_norm) or f == ref_norm for f in files)

        if referenced_paths:
            paths_exist = all(
                _path_matches(p) for p in referenced_paths
            )
        else:
            paths_exist = True

        requires_secrets = _mentions_secrets(readme)
        needs_heavy_setup = _needs_heavy_setup(readme)

        # OOB (1.0): demo + simple install + run target exists + no secrets/heavy setup
        if (
            simple_install
            and paths_exist
            and not requires_secrets
            and not needs_heavy_setup
        ):
            return 1.0

        # Agent (0.5): demo exists but something likely breaks OOB
        return 0.5


def _has_demo(text: str) -> bool:
    # headings or phrases that usually signal runnable demos
    markers = (
        "quickstart",
        "usage",
        "example",
        "demo",
        "how to run",
        "getting started",
    )

    # Allow either explicit demo/usage markers OR presence of python commands
    # or .py references
    code_fences = (
        "```" in text
        or "`python" in text
        or "```python" in text
    )

    # Don't count markers prefixed with simple negations like 'no demo' or 'not demo'
    has_marker = any(m in text for m in markers)
    for m in markers:
        if f"no {m}" in text or f"not {m}" in text:
            has_marker = False
            break
    has_python_cmd = ("python " in text) or ("python3 " in text) or (".py" in text)

    return has_marker or code_fences or has_python_cmd


def _has_simple_install(text: str) -> bool:
    # allow simple pip installs; avoid long env managers/makefiles
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

    return any(p in text for p in simple_patterns) and not any(h in text for h in heavy)


def _extract_run_target(text: str):
    """Very light heuristic: find 'python <path>.py' or 'python -m <mod>' lines and
    return path(s).
    """

    referenced = []
    run_cmd = None

    for line in text.splitlines():
        ln = line.strip()

        # match 'python', 'python3', or common shell prompts like '$ python'
        if (
            ln.startswith("python ")
            or ln.startswith("python3 ")
            or ln.startswith("$ python")
            or ln.startswith("$ python3")
        ):
            run_cmd = ln
            parts = ln.split()
            if len(parts) >= 2 and parts[1].endswith(".py"):
                referenced.append(parts[1])

        if "examples/" in ln or "demo/" in ln or "scripts/" in ln:
            # collect obvious referenced script paths
            for token in ln.replace("(", " ").replace(")", " ").split():
                if token.endswith(".py") and (
                    "/examples/" in token
                    or "/demo/" in token
                    or "/scripts/" in token
                ):
                    referenced.append(token)

    return run_cmd, list(set(referenced))


def _mentions_secrets(text: str) -> bool:
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


def _needs_heavy_setup(text: str) -> bool:
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

