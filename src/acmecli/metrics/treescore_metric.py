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

        base_score = 0.0

        if parents and len(parents) > 0:
            base_score += 0.4
        elif meta.get("lineage"):
            base_score += 0.3
        elif "parent" in str(meta).lower():
            base_score += 0.2

        scores = []
        for p in parents:
            try:
                s = float(p.get("score"))
            except Exception:
                continue
            if 0.0 <= s <= 1.0:
                scores.append(s)

        if not scores:
            if parents and len(parents) > 0:
                parent_bonus = min(0.3, len(parents) * 0.15)
                final = base_score + parent_bonus
                return min(1.0, max(0.5, final))
            if base_score > 0:
                final = base_score + 0.3
                return min(1.0, max(0.5, final))
            return 0.5

        if len(scores) > 0:
            avg = sum(scores) / len(scores)
            avg = max(0.0, min(1.0, avg))
        else:
            avg = 0.0

        if len(scores) > 1:
            multi_parent_bonus = min(0.2, (len(scores) - 1) * 0.05)
            avg += multi_parent_bonus

        final_score = base_score + (avg * (1.0 - base_score))
        return max(0.5, min(1.0, final_score))


register(TreescoreMetric())
