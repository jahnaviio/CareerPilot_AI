"""India detection and city aliases. A listing is 'India' if its location text names India or a known Indian city."""
from __future__ import annotations

import re

# display name -> aliases (lowercase) that appear in postings
CITIES: dict[str, tuple[str, ...]] = {
    "Bengaluru": ("bengaluru", "bangalore", "blr"), "Hyderabad": ("hyderabad", "secunderabad", "hyd"), "Mumbai": ("mumbai", "bombay", "navi mumbai", "thane"),
    "Pune": ("pune",), "Chennai": ("chennai", "madras"), "Delhi NCR": ("delhi", "new delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad", "ncr"),
    "Kolkata": ("kolkata", "calcutta"), "Ahmedabad": ("ahmedabad",), "Visakhapatnam": ("visakhapatnam", "vizag"), "Jaipur": ("jaipur",),
    "Kochi": ("kochi", "cochin"), "Coimbatore": ("coimbatore",), "Indore": ("indore",), "Chandigarh": ("chandigarh", "mohali"),
    "Thiruvananthapuram": ("thiruvananthapuram", "trivandrum"), "Vijayawada": ("vijayawada",), "Bhubaneswar": ("bhubaneswar",), "Nagpur": ("nagpur",),
}
_INDIA = re.compile(r"\bindia\b|\bin\b$", re.I)
_ALL_ALIASES = sorted({a for v in CITIES.values() for a in v if len(a) > 3}, key=len, reverse=True)
_ALIAS_RE = re.compile(r"(?<![a-z])(" + "|".join(re.escape(a) for a in _ALL_ALIASES) + r")(?![a-z])", re.I)


def is_india(location: str) -> bool:
    loc = location or ""
    return bool(re.search(r"\bindia\b", loc, re.I) or _ALIAS_RE.search(loc))


def matches_city(location: str, city: str) -> bool:
    loc = (location or "").lower()
    return any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", loc) for a in CITIES.get(city, (city.lower(),)))
