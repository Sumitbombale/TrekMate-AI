"""Safety guidance. General information only; follow local authorities and your guide."""
from typing import Optional

from .data_loader import get_trek

BASE = {
    "general": ["Trek with a registered operator or experienced group; tell someone your route and return time.",
                "Start early, finish before dark and carry a headlamp.",
                "Turn back if weather turns bad; the summit is optional, returning is not.",
                "Check current conditions and permit rules with local forest/tourism offices before leaving.",
                "Carry offline maps and a fully charged phone/power bank."],
    "ams": ["Early AMS signs: headache, nausea, dizziness, unusual fatigue, poor sleep.",
            "Do not go higher with symptoms; rest, hydrate and descend if they worsen.",
            "Danger signs (confusion, unsteady walking, breathlessness at rest, wet cough): descend immediately and get medical help.",
            "Above ~3000 m, avoid big jumps in sleeping altitude and avoid alcohol."],
    "weather": ["Mountain weather changes quickly; layer clothing and keep rain protection handy.",
                "Avoid river crossings after heavy rain and lightning-exposed ridges."],
    "emergency": ["India's national emergency number is 112.",
                  "Inform your guide/trek leader first; they know the local rescue process.",
                  "Mobile coverage is often absent on trails; agree on a descent plan before you start."],
}


def get_safety(name: Optional[str] = None, topic: Optional[str] = None) -> dict:
    out = {k: list(v) for k, v in BASE.items()}
    if name:
        t = get_trek(name)
        if not t:
            raise LookupError(f"Unknown trek: {name}")
        specific = [f"{t['name']} reaches {t['max_altitude_m']} m and is rated {t['difficulty']}."]
        if t["max_altitude_m"] >= 5000:
            specific.append("Very high altitude: needs prior high-altitude experience and a proper acclimatisation schedule.")
        elif t["max_altitude_m"] >= 3000:
            specific.append("High altitude: take AMS precautions seriously.")
        if t["level"] == 3:
            specific.append("Strenuous trek: train for several weeks and consider a medical check-up.")
        if t["best_season"].startswith(("Dec", "Jan")):
            specific.append("Winter conditions: frostbite and hypothermia risk; use proper insulation.")
        out["trek_specific"] = specific
    if topic:
        key = topic.strip().lower()
        if key not in out:
            raise ValueError(f"Unknown topic '{topic}'. Choose from: {', '.join(out)}")
        out = {key: out[key]}
    out["disclaimer"] = "General guidance, not medical or rescue advice."
    return out
