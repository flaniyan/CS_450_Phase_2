from .base import register


class ReviewednessMetric:
    name = "Reviewedness"

    def score(self, meta: dict) -> float:
        github_url = (meta.get("github_url") or "").strip()

        if not github_url:
            return -1.0

        gh = meta.get("github") or {}
        prs = gh.get("prs") or []
        direct = gh.get("direct_commits") or []

        def is_code_file(name: str) -> bool:
            n = (name or "").lower()
            noncode_ext = (
                ".safetensors",
                ".bin",
                ".pt",
                ".pth",
                ".onnx",
                ".ckpt",
                ".h5",
                ".tar",
                ".gz",
                ".zip",
                ".7z",
                ".npz",
                ".npy",
                ".csv",
                ".tsv",
                ".parquet",
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".webp",
                ".svg",
                ".mp4",
                ".mp3",
                ".wav",
                ".flac",
                ".pdf",
                ".doc",
                ".docx",
                ".ppt",
                ".pptx",
            )
            return not any(n.endswith(ext) for ext in noncode_ext)

        reviewed_add = 0
        total_add = 0

        # Sum PR contributions
        for pr in prs:
            reviewed = bool(pr.get("approved")) or (pr.get("review_count", 0) > 0)

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
            # Direct commits are not reviewed, so reviewed_add stays 0

        # If no activity (empty github dict or no PRs/commits), return -1.0
        if not prs and not direct:
            return -1.0

        # If only non-code files (total_add == 0), all are considered reviewed
        if total_add == 0:
            return 1.0

        # Calculate ratio of reviewed additions to total additions
        ratio = reviewed_add / float(total_add)
        if ratio < 0:
            ratio = 0.0
        if ratio > 1:
            ratio = 1.0

        return ratio


register(ReviewednessMetric())
