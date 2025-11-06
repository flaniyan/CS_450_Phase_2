# Why the Lenient Baseline Scoring Logic Was Wrong

## The Problem

The original implementation had **lenient baseline scoring** that gave artificial credit (0.3, 0.4, 0.5) even when there was no actual review activity. This violated the core purpose of a "reviewedness" metric, which should measure **actual code review coverage**, not just the presence of a GitHub repository.

---

## Specific Issues with the Old Logic

### 1. **Issue: Giving credit for no activity**

**Test:** `test_no_activity_returns_minus1`

```python
meta = {"github_url": "https://github.com/u/r", "github": {}}
assert m.score(meta) == -1.0
```

**Old Code:**

```python
if not prs and not direct:
    if github_url:
        return 0.3  # ❌ Baseline score for having GitHub repo
    return -1.0
```

**Problem:** Returned `0.3` even when there's **zero activity** (no PRs, no commits). The metric should return `-1.0` to indicate "cannot compute" when there's nothing to review.

**Fix:** Return `-1.0` when there's no activity, regardless of whether a GitHub URL exists.

---

### 2. **Issue: Wrong score for non-code files**

**Test:** `test_only_non_code_files_returns_one`

```python
# PR with only .safetensors file (non-code)
meta = {
    "github_url": "...",
    "github": {
        "prs": [{
            "merged": True,
            "approved": True,
            "files": [{"filename": "weights/model.safetensors", "additions": 100}]
        }]
    }
}
assert m.score(meta) == 1.0  # All non-code files are "reviewed" by default
```

**Old Code:**

```python
if total_add == 0:  # No code additions (only non-code files)
    if prs or direct:
        return 0.4  # ❌ Wrong! Should be 1.0
```

**Problem:**

- When only non-code files exist (like `.safetensors`, `.bin`), `total_add = 0` (no code additions)
- The metric should return `1.0` because **all non-code files are considered "reviewed"** (they don't need code review)
- But old code returned `0.4`, giving partial credit instead of full credit

**Fix:** Return `1.0` when `total_add == 0` because if there's no code to review, it's 100% "reviewed" by default.

---

### 3. **Issue: Giving partial credit for unreviewed PRs**

**Test:** `test_reviewed_and_unreviewed_ratio`

```python
# PR 1: 100 additions, approved ✓
# PR 2: 50 additions, NOT approved ✗
meta = {
    "github_url": "...",
    "github": {
        "prs": [
            {"merged": True, "approved": True, "files": [{"filename": "src/a.py", "additions": 100}]},
            {"merged": True, "approved": False, "files": [{"filename": "src/b.py", "additions": 50}]}
        ]
    }
}
# Expected: 100 reviewed / 150 total = 0.666...
assert math.isclose(score, 100 / 150, rel_tol=1e-6)
```

**Old Code:**

```python
for pr in prs:
    reviewed = bool(pr.get("approved"))
    # ...
    if reviewed:
        reviewed_add += add
    elif is_merged:
        reviewed_add += add * 0.5  # ❌ Partial credit for merged but not approved
```

**Problem:**

- PR 2 is merged but **not approved** (no review)
- Old code gave it 50% credit: `reviewed_add = 100 + (50 * 0.5) = 125`
- Ratio: `125 / 150 = 0.833...` ❌
- **Correct ratio:** `100 / 150 = 0.666...` ✓

**Fix:** Only count additions as "reviewed" if the PR is actually approved. Don't give partial credit for merged-but-unreviewed PRs.

---

### 4. **Issue: Baseline score for unreviewed commits**

**Test:** `test_direct_commits_unreviewed`

```python
meta = {
    "github_url": "...",
    "github": {
        "direct_commits": [
            {"files": [{"filename": "src/c.py", "additions": 30}]}
        ]
    }
}
assert m.score(meta) == 0.0  # Direct commits are unreviewed by definition
```

**Old Code:**

```python
# Direct commits are added to total_add but not reviewed_add
# So ratio = 0 / 30 = 0.0

if ratio == 0.0 and (prs or direct):
    merged_prs = [pr for pr in prs if pr.get("merged")]
    if merged_prs:
        return 0.5  # ❌ Wrong baseline
    return 0.5  # ❌ Wrong baseline
```

**Problem:**

- Direct commits are **unreviewed by definition** (pushed directly to main/master)
- Ratio should be `0.0` (0% reviewed)
- But old code returned `0.5` as a "baseline
- This hides the fact that the codebase has unreviewed commits

**Fix:** Return the actual ratio (0.0) when there are only unreviewed commits. Don't give artificial baseline scores.

---

## Core Principle

**Reviewedness metric should measure:**

```
reviewed_code_additions / total_code_additions
```

**Not:**

- "Does this repo exist on GitHub?" → Baseline 0.3
- "Are there any PRs/commits?" → Baseline 0.4
- "Are there merged PRs?" → Baseline 0.5

**The metric should be strict:**

- ✅ No activity → `-1.0` (cannot compute)
- ✅ Only non-code files → `1.0` (nothing to review = 100% reviewed)
- ✅ Actual ratio → `reviewed / total` (no fake baselines)
- ✅ Only unreviewed → `0.0` (not 0.5)

---

## Summary

The lenient baseline scoring was **hiding poor review practices** by giving artificial credit. The fixed version now:

1. ✅ Returns `-1.0` when there's no activity (can't compute)
2. ✅ Returns `1.0` when only non-code files exist (nothing to review = fully reviewed)
3. ✅ Returns the **actual ratio** of reviewed to total code additions
4. ✅ Returns `0.0` when all code is unreviewed (no fake baselines)

This makes the metric **honest and accurate** for measuring actual code review coverage.
