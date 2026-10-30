"""Template-based itinerary generator. Day-by-day stages are generic; confirm real stages with your operator."""
from typing import Optional

from .data_loader import get_trek, parse_month


def plan(name: str, days: Optional[int] = None, month=None, group_size: int = 1) -> dict:
    t = get_trek(name)
    if not t:
        raise LookupError(f"Unknown trek: {name}")
    n = days or t["duration_days"]
    m = parse_month(month)
    hl = t["highlights"] or ["scenic trail"]
    itinerary = []
    if n == 1:
        itinerary.append({"day": 1, "title": "Day hike", "detail": f"Start at first light, reach the top, return the same day. Look out for: {hl[0]}."})
    else:
        itinerary.append({"day": 1, "title": "Reach base & prepare", "detail": "Travel to the base village, check gear, brief with guide, rest early."})
        mid = n - 2
        for i in range(mid):
            frac = (i + 1) / (mid + 1)
            h = hl[i % len(hl)]
            if frac <= 0.4:
                d = "Gentle ascent; keep a slow pace to let your body adjust."
            elif frac <= 0.8:
                d = f"Main climbing day. Highlight: {h}."
            else:
                d = f"Approach the high point. Highlight: {h}."
            itinerary.append({"day": i + 2, "title": f"Trek stage {i + 1}", "detail": d})
        itinerary.append({"day": n, "title": "Descent & departure", "detail": "Descend to the road-head and travel onward. Keep a buffer day before flights/trains."})
    warnings = []
    if n < t["duration_days"]:
        warnings.append(f"{t['name']} normally takes {t['duration_days']} days; {n} days may be rushed.")
    if m and m not in t["months"]:
        warnings.append(f"Your month is outside the usual best season ({t['best_season']}).")
    if t["max_altitude_m"] >= 3000:
        warnings.append("Altitude above 3000 m: build in acclimatisation and watch for AMS symptoms.")
    pp = round(t["cost_inr"] * n / t["duration_days"])
    return {"trek": t["name"], "state": t["state"], "days": n, "difficulty": t["difficulty"],
            "itinerary": itinerary, "warnings": warnings,
            "budget": {"per_person_inr": pp, "group_size": group_size, "total_inr": pp * group_size,
                       "note": "Indicative operator-package estimate; verify current prices."}}
