"""Customised packing checklist."""
from .data_loader import get_trek, parse_month


def packing_list(name: str, month=None) -> dict:
    t = get_trek(name)
    if not t:
        raise LookupError(f"Unknown trek: {name}")
    m = parse_month(month) or (t["months"][0] if t["months"] else None)
    alt, days = t["max_altitude_m"], t["duration_days"]
    cold = alt >= 3000 or m in (11, 12, 1, 2, 3)
    wet = m in (6, 7, 8, 9)
    L = {
        "Essentials": ["Trekking backpack with rain cover", "Water bottles (2 L total)", "Headlamp + spare batteries", "Sunglasses, sunscreen, cap", "Trekking poles", "Power bank"],
        "Clothing": ["Quick-dry t-shirts", "Trek pants", "Fleece or insulated jacket", "Windproof jacket", "Socks (extra pairs)"],
        "Footwear": ["Trekking shoes with good grip", "Camp sandals"],
        "Health": ["Personal medicines", "First-aid kit", "ORS and energy snacks", "Toilet paper, hand sanitiser"],
        "Documents": ["Photo ID (original + copy)", "Permits / booking confirmation", "Emergency contact details"],
    }
    if cold:
        L["Clothing"] += ["Thermal base layers", "Down/heavy jacket", "Woollen cap, gloves, neck gaiter"]
    if wet:
        L["Essentials"] += ["Poncho or rain jacket", "Waterproof bags for electronics"]
        L["Health"].append("Leech/insect repellent")
    if alt >= 3500 or (m in (12, 1, 2) and alt >= 2500):
        L["Footwear"] += ["Waterproof boots", "Gaiters"]
    if m in (12, 1, 2, 3) and alt >= 3000:
        L["Essentials"].append("Microspikes (check with operator)")
    if alt >= 4000:
        L["Health"].append("Ask your doctor about altitude-sickness medication")
    if days > 1:
        L["Essentials"] += ["Sleeping bag rated for night temperatures", "Trekking towel"]
    return {"trek": t["name"], "month": m, "checklist": L}
