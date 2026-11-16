"""Approximate centres of areas in Chhatrapati Sambhajinagar. Replace with real map data later."""
from math import asin, cos, radians, sin, sqrt

AREAS = {
    "Kranti Chowk": (19.8762, 75.3433), "Cidco": (19.886, 75.364), "Garkheda": (19.857, 75.366),
    "Osmanpura": (19.875, 75.333), "Jalna Road": (19.88, 75.378), "Jawahar Colony": (19.868, 75.33),
    "Padegaon": (19.845, 75.33), "Satara Parisar": (19.8, 75.342), "Harsul": (19.918, 75.333),
    "Waluj": (19.842, 75.238),
}


def canonical_area(name):
    """'CIDCO' / 'cidco' / 'Cidco' all become 'Cidco'. Returns None if unknown."""
    for key in AREAS:
        if key.lower() == str(name).strip().lower():
            return key
    return None


def distance_km(a, b):
    """Straight-line distance between two named areas (haversine formula)."""
    (la1, lo1), (la2, lo2) = AREAS[a], AREAS[b]
    dla, dlo = radians(la2 - la1), radians(lo2 - lo1)
    h = sin(dla / 2) ** 2 + cos(radians(la1)) * cos(radians(la2)) * sin(dlo / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))