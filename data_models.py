from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import config
from utils import calculate_distance_bearing

@dataclass
class Aircraft:
    """Aircraft data from tar1090"""
    hex_code: str
    callsign: str
    lat: float
    lon: float
    altitude: int
    speed: int
    track: float
    distance: float
    bearing: float
    type: str
    is_military: bool = False

    @staticmethod
    def from_dict(data: dict) -> Optional[Aircraft]:
        """Create an Aircraft object from a dictionary."""
        if 'lat' not in data or 'lon' not in data:
            return None
        lat, lon = data['lat'], data['lon']
        distance, bearing = calculate_distance_bearing(config.LAT, config.LON, lat, lon)
        if distance > config.RADIUS_NM:
            return None
        speed = int(data.get('gs', 0) or 0)
        if speed < 15:
            return None 
        hex_code = data['hex'].lower()
        mil_prefixes = tuple(prefix.lower() for prefix in config.MIL_PREFIX_LIST)
        is_military = hex_code.startswith(mil_prefixes)
        return Aircraft(
            hex_code=hex_code,
            callsign=data.get('flight', 'UNKNOWN').strip()[:8],
            lat=lat, lon=lon,
            altitude=data.get('alt_baro', 0) or 0,
            speed=speed,
            # speed=int(data.get('gs', 0) or 0),
            track=data.get('track', 0) or 0,
            type=data.get('t'),
            distance=distance, bearing=bearing,
            is_military=is_military
        )
