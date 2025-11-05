from .base import register


class TreescoreMetric:
    name = "Treescore"

    def score(self, meta: dict) -> float:
        parents = (
            meta.get("parents")
            or (meta.get("lineage") or {}).get("parents")
            or meta.get("lineage_parents")
            or []
        )

        # Pull numeric scores
        scores = []
        for p in parents:
            try:
                s = float(p.get("score"))
            except Exception:
                continue
            if 0.0 <= s <= 1.0:
                scores.append(s)

        # More lenient: if no usable parent scores but parents exist, give baseline score
        if not scores:
            # If parents array exists but has no scores, give baseline score for having lineage info
            if parents and len(parents) > 0:
                return 0.5  # Baseline score for having parent lineage info even without scores
            return -1.0  # Only return -1 if truly no parent data

        # Average and clamp to [0,1]
        avg = sum(scores) / len(scores)
        if avg < 0.0:
            avg = 0.0
        if avg > 1.0:
            avg = 1.0
        return avg


register(TreescoreMetric())
