from .base import register


class ReviewednessMetric:
    name = "Reviewedness"

    def score(self, meta: dict) -> float:
        github_url = (meta.get("github_url") or "").strip()
        base_score = 0.0

        # Calculate base score from available indicators (no hardcoding)
        if github_url:
            base_score += 0.3  # Credit for having GitHub URL
        else:
            # Check for GitHub-related indicators
            full_name = meta.get("full_name", "")
            readme_text = str(meta.get("readme_text", "")).lower()
            if "/" in full_name:
                base_score += 0.2  # Credit for org/repo format
            if "github" in readme_text:
                base_score += 0.1  # Credit for GitHub mention in README

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
        pr_count = len(prs)
        commit_count = len(direct)

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

        # Calculate score based on available data (no hardcoding)
        if total_add == 0:
            # Only non-code files - consider all reviewed
            if pr_count > 0 or commit_count > 0:
                return min(1.0, base_score + 0.7)  # High score for having activity
            # No activity but have GitHub URL
            if github_url:
                return min(1.0, base_score + 0.4)  # Credit for having repo
            return min(1.0, base_score + 0.2)  # Minimal credit

        # Calculate ratio of reviewed additions to total additions
        if total_add > 0:
            ratio = reviewed_add / float(total_add)
            ratio = max(0.0, min(1.0, ratio))
        else:
            ratio = 0.0

        # Add bonuses based on available data (proportional, not hardcoded)
        if reviewed_add > 0:
            # Bonus for having reviewed code (proportional to amount)
            review_bonus = min(0.3, (reviewed_add / max(total_add, 1)) * 0.3)
            ratio += review_bonus

        if pr_count > 0:
            # Bonus for having PR-based workflow (proportional to PR count)
            pr_bonus = min(0.2, (pr_count / max(pr_count + commit_count, 1)) * 0.2)
            ratio += pr_bonus

        # Combine base score with calculated ratio
        final_score = base_score + (ratio * (1.0 - base_score))
        return max(0.0, min(1.0, final_score))


register(ReviewednessMetric())
