"""Loads and normalises the trek dataset (Pandas)."""
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional, Union

import pandas as pd

DATA_PATH = Path(os.getenv("TREK_DATA", Path(__file__).resolve().parent.parent / "data" / "treks.csv"))
DIFFICULTY_LEVEL = {"Easy": 1, "Moderate": 2, "Difficult": 3}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def parse_month(value: Union[str, int, None]) -> Optional[int]:
    """Accepts 1-12 or a month name/abbreviation. Returns None if blank/invalid."""
    if value in (None, ""):
        return None
    try:
        n = int(value)
        return n if 1 <= n <= 12 else None
    except (TypeError, ValueError):
        key = str(value).strip()[:3].lower()
        return MONTHS.index(key) + 1 if key in MONTHS else None


def season_months(season: str) -> set:
    """'Mar-Jun;Sep-Nov' -> {3,4,5,6,9,10,11}. Handles year wrap (Dec-Apr)."""
    months = set()
    for part in str(season).split(";"):
        a, _, b = part.partition("-")
        start, end = parse_month(a), parse_month(b or a)
        if not start or not end:
            continue
        m = start
        while True:
            months.add(m)
            if m == end:
                break
            m = m % 12 + 1
    return months


@lru_cache(maxsize=1)
def load_treks() -> list:
    df = pd.read_csv(DATA_PATH)
    treks = []
    for row in df.to_dict(orient="records"):
        row["highlights"] = [h.strip() for h in str(row["highlights"]).split(";") if h.strip()]
        row["level"] = DIFFICULTY_LEVEL.get(row["difficulty"], 2)
        row["months"] = sorted(season_months(row["best_season"]))
        for k in ("duration_days", "max_altitude_m", "cost_inr"):
            row[k] = int(row[k])
        treks.append(row)
    return treks


def get_trek(name: str) -> Optional[dict]:
    key = (name or "").strip().lower()
    return next((t for t in load_treks() if t["name"].lower() == key), None)
