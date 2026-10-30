"""Trek recommendations (TrekMatch score) and side-by-side comparison."""
from typing import Optional

from .data_loader import DIFFICULTY_LEVEL, get_trek, load_treks, parse_month


def recommend(difficulty: Optional[str] = None, max_days: Optional[int] = None,
              max_budget: Optional[int] = None, month=None, state: Optional[str] = None,
              top_n: int = 5) -> list:
    m = parse_month(month)
    wanted = DIFFICULTY_LEVEL.get(difficulty) if difficulty else None
    results = []
    for t in load_treks():
        if state and state.strip().lower() not in t["state"].lower():
            continue
        score = total = 0.0
        reasons = []
        if wanted:
            total += 30
            gap = abs(t["level"] - wanted)
            score += 30 * {0: 1, 1: 0.5}.get(gap, 0)
            reasons.append(f"{t['difficulty']} difficulty" + (" matches" if gap == 0 else " is close to your level"))
        if max_budget:
            total += 25
            score += 25 * (1 if t["cost_inr"] <= max_budget else max(0, 1 - (t["cost_inr"] - max_budget) / max_budget))
            reasons.append(f"approx INR {t['cost_inr']:,}" + (" is within budget" if t["cost_inr"] <= max_budget else " is above budget"))
        if max_days:
            total += 20
            score += 20 * (1 if t["duration_days"] <= max_days else max(0, 1 - (t["duration_days"] - max_days) / max_days))
            reasons.append(f"{t['duration_days']} days" + (" fits" if t["duration_days"] <= max_days else " is longer than planned"))
        if m:
            total += 25
            ok = m in t["months"]
            score += 25 if ok else 0
            reasons.append("good season for your month" if ok else f"outside best season ({t['best_season']})")
        pct = round(100 * score / total) if total else 50
        results.append({**t, "trekmatch": pct, "reasons": reasons})
    results.sort(key=lambda r: (-r["trekmatch"], r["level"], r["cost_inr"]))
    return results[:top_n]


def compare(names: list) -> dict:
    treks = [t for t in (get_trek(n) for n in names) if t]
    if len(treks) < 2:
        raise ValueError("Select at least two valid treks to compare.")
    pick = lambda fn, key: fn(treks, key=key)["name"]
    hard = lambda t: (t["level"], t["max_altitude_m"])
    return {
        "treks": treks,
        "summary": {
            "easiest": pick(min, hard), "hardest": pick(max, hard),
            "cheapest": pick(min, lambda t: t["cost_inr"]),
            "shortest": pick(min, lambda t: t["duration_days"]),
            "highest": pick(max, lambda t: t["max_altitude_m"]),
        },
    }
