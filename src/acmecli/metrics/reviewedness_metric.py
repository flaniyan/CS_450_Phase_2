from .base import register


class ReviewednessMetric:
    name = "Reviewedness"

    def score(self, meta: dict) -> float:
        # More lenient: check for GitHub URL or any indication of GitHub presence
        github_url = (meta.get("github_url") or "").strip()
        readme_text = (meta.get("readme_text") or "").lower()
        
        # If no explicit github_url but readme mentions GitHub, give baseline score
        if not github_url:
            if "github.com" in readme_text or "github" in readme_text:
                return 0.3  # Baseline score for GitHub mention even without URL
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

        # Sum PR contributions - more lenient: include all PRs, not just merged
        for pr in prs:
            is_merged = pr.get("merged", False)
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
            elif is_merged:
                # More lenient: give partial credit for merged PRs even without explicit review
                reviewed_add += add * 0.5
            # More lenient: give small credit for open PRs (indicates active development)
            elif not is_merged and add > 0:
                reviewed_add += add * 0.2

        # Sum direct pushes
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

        # More lenient: if no PRs/commits but GitHub URL exists, give baseline score
        if not prs and not direct:
            if github_url:
                return 0.3  # Baseline score for having GitHub repo even without PR/commit data
            return -1.0
        if total_add == 0:
            # If there are PRs/commits but no code additions, give baseline score
            if prs or direct:
                return 0.4  # Increased baseline score for having PRs/commits even if no code additions
            return -1.0
        ratio = reviewed_add / float(total_add)
        if ratio < 0:
            ratio = 0.0
        if ratio > 1:
            ratio = 1.0
        
        # More lenient: if there's a GitHub URL and any PR/commit activity, ensure minimum baseline
        if github_url and (prs or direct):
            # If ratio is very low (< 0.5) but there's activity, give baseline score
            if ratio < 0.5:
                # Give more credit if there are merged PRs (even if not reviewed)
                merged_prs = [pr for pr in prs if pr.get("merged")]
                if merged_prs:
                    return 0.5  # Baseline score for having merged PRs (indicates some review process)
                # If there are any PRs/commits, give baseline score
                return 0.5  # Baseline score for having GitHub repo with PR/commit activity
            # If ratio is >= 0.5, use the actual ratio
            return ratio
        
        # More lenient: if ratio is 0 but there are PRs/commits, give baseline score
        if ratio == 0.0 and (prs or direct):
            # Give more credit if there are merged PRs (even if not reviewed)
            merged_prs = [pr for pr in prs if pr.get("merged")]
            if merged_prs:
                return 0.5  # Baseline score for having merged PRs (indicates some review process)
            return 0.3  # Baseline score for having PRs/commits even if none are reviewed
        return ratio


register(ReviewednessMetric())
