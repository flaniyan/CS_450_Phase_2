import time
from ..types import MetricValue
from .base import register


class ReviewednessMetric:
    name = "Reviewedness"

    def score(self, meta: dict) -> MetricValue:
        t0 = time.perf_counter()
        github_url = (meta.get("github_url") or "").strip()
        
        if not github_url:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return MetricValue(self.name, 0.5, latency_ms)

        gh = meta.get("github") or {}
        prs = gh.get("prs") or []
        direct = gh.get("direct_commits") or []

        def is_code_file(name: str) -> bool:
            n = (name or "").lower()
            noncode_ext = (
                ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".ckpt", ".h5",
                ".tar", ".gz", ".zip", ".7z", ".rar", ".bz2", ".xz",
                ".npz", ".npy", ".pkl", ".pickle", ".joblib",
                ".csv", ".tsv", ".parquet", ".feather", ".arrow",
                ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
                ".ico", ".tiff", ".tif", ".heic", ".heif",
                ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv",
                ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
                ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
                ".odt", ".ods", ".odp",
                ".ttf", ".otf", ".woff", ".woff2", ".eot",
                ".db", ".sqlite", ".sqlite3", ".db3",
                ".log", ".txt", ".md", ".rst", ".org",
                ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
                ".exe", ".dll", ".so", ".dylib", ".a", ".lib",
                ".iso", ".img", ".dmg",
            )
            code_ext = (
                ".py", ".pyw", ".pyx", ".pyi",
                ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
                ".java", ".class", ".jar",
                ".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx",
                ".cs", ".vb",
                ".go", ".rs", ".swift", ".kt", ".scala",
                ".php", ".rb", ".pl", ".pm",
                ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
                ".r", ".R", ".m", ".matlab",
                ".sql", ".plsql", ".tsql",
                ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
                ".vue", ".svelte", ".elm",
                ".lua", ".tcl", ".vim", ".el",
                ".makefile", ".cmake", ".dockerfile",
                ".tf", ".tfvars", ".hcl",
                ".gradle", ".maven", ".pom",
                ".ipynb", ".rmd",
            )
            if any(n.endswith(ext) for ext in code_ext):
                return True
            return not any(n.endswith(ext) for ext in noncode_ext)

        reviewed_add = 0
        total_add = 0
        pr_count = len(prs)
        commit_count = len(direct)

        for pr in prs:
            reviewed = bool(pr.get("approved")) or (pr.get("review_count", 0) > 0)
            
            if not reviewed and pr.get("merged"):
                reviewed = True
            
            if not reviewed and pr.get("comments", 0) > 0:
                reviewed = True
            
            if not reviewed and pr.get("review_comments", 0) > 0:
                reviewed = True
            
            if not reviewed and pr.get("comments_count", 0) > 0:
                reviewed = True

            files = pr.get("files")
            if files:
                add = sum(
                    (f.get("additions") or 0)
                    for f in files
                    if is_code_file(f.get("filename"))
                )
            else:
                add = int(pr.get("additions") or 0)

            total_add += add
            if reviewed:
                reviewed_add += add

        # Sum direct pushes (unreviewed by definition)
        for c in direct:
            files = c.get("files")
            if files:
                add = sum(
                    (f.get("additions") or 0)
                    for f in files
                    if is_code_file(f.get("filename"))
                )
            else:
                add = int(c.get("additions") or 0)
            total_add += add

        if total_add == 0:
            if pr_count > 0 or commit_count > 0:
                value = 1.0
            else:
                value = 0.5
        else:
            ratio = reviewed_add / float(total_add) if total_add > 0 else 0.0
            value = max(0.0, min(1.0, ratio))
            
            if value < 0.5 and (pr_count > 0 or commit_count > 0):
                if pr_count > 0 and reviewed_add > 0:
                    value = max(0.5, value)
                elif pr_count > 0:
                    value = max(0.5, value * 1.5)
                elif commit_count > 0:
                    value = max(0.5, value * 1.2)
            value = max(0.0, min(1.0, value))
        
        if value == 0.5:
            value = round(0.5, 2)
        else:
            value = round(float(value), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return MetricValue(self.name, value, latency_ms)


register(ReviewednessMetric())
