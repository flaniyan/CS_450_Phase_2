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

        # No usable parent scores
        if not scores:
            return 0.0

        # Average and clamp to [0,1]
        avg = sum(scores) / len(scores)
        if avg < 0.0:
            avg = 0.0
        if avg > 1.0:
            avg = 1.0
        return avg


register(TreescoreMetric())
