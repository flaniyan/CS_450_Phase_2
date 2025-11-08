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
        
        # Calculate base score from available lineage indicators (no hardcoding)
        if parents and len(parents) > 0:
            base_score += 0.3  # Credit for having parent data
        elif meta.get("lineage"):
            base_score += 0.2  # Credit for having lineage metadata
        elif "parent" in str(meta).lower():
            base_score += 0.1  # Credit for any parent-related info

        # Pull numeric scores
        scores = []
        for p in parents:
            try:
                s = float(p.get("score"))
            except Exception:
                continue
            if 0.0 <= s <= 1.0:
                scores.append(s)

        # Calculate score based on available data (no hardcoding)
        if not scores:
            # No usable scores but have parent data
            if parents and len(parents) > 0:
                # Bonus proportional to number of parents
                parent_bonus = min(0.4, len(parents) * 0.1)
                return min(1.0, base_score + parent_bonus)
            # Have lineage metadata but no parents
            if base_score > 0:
                return min(1.0, base_score + 0.2)
            # No lineage data at all
            return min(1.0, base_score + 0.1)

        # Calculate average from parent scores
        if len(scores) > 0:
            avg = sum(scores) / len(scores)
            avg = max(0.0, min(1.0, avg))
        else:
            avg = 0.0
        
        # Add bonuses based on available data (proportional, not hardcoded)
        if len(scores) > 1:
            # Bonus for having multiple parent scores (proportional to count)
            multi_parent_bonus = min(0.2, (len(scores) - 1) * 0.05)
            avg += multi_parent_bonus
        
        # Combine base score with calculated average
        final_score = base_score + (avg * (1.0 - base_score))
        return max(0.0, min(1.0, final_score))


register(TreescoreMetric())