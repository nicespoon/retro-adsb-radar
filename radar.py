import configparser
import math
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import pygame
import requests

# Try to import NumPy for batch operations
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Read configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Import config values from config.ini with defaults
FETCH_INTERVAL = config.getint('General', 'FETCH_INTERVAL', fallback=10)
MIL_PREFIX_LIST = [prefix.strip() for prefix in config.get('General', 'MIL_PREFIX_LIST', fallback='7CF').split(',')]
TAR1090_URL = config.get('General', 'TAR1090_URL', fallback='http://localhost/data/aircraft.json')
BLINK_MILITARY = config.getboolean('General', 'BLINK_MILITARY', fallback=True)

LAT = config.getfloat('Location', 'LAT', fallback=0.0)
LON = config.getfloat('Location', 'LON', fallback=0.0)
AREA_NAME = config.get('Location', 'AREA_NAME', fallback='UNKNOWN')
RADIUS_NM = config.getint('Location', 'RADIUS_NM', fallback=60)

STATIC_REDRAW_INTERVAL = config.getint('Performance', 'STATIC_REDRAW_INTERVAL', fallback=5)
FPS = config.getint('Performance', 'FPS', fallback=6)
ENABLE_TEXT_CACHE = config.getboolean('Performance', 'ENABLE_TEXT_CACHE', fallback=True)
ENABLE_COORDINATE_CACHE = config.getboolean('Performance', 'ENABLE_COORDINATE_CACHE', fallback=True)
ENABLE_STATIC_SURFACE_CACHE = config.getboolean('Performance', 'ENABLE_STATIC_SURFACE_CACHE', fallback=True)
MAX_TEXT_CACHE_SIZE = config.getint('Performance', 'MAX_TEXT_CACHE_SIZE', fallback=1000)
COORDINATE_CACHE_TTL = config.getfloat('Performance', 'COORDINATE_CACHE_TTL', fallback=1.0)
USE_NUMPY_BATCH_OPS = config.getboolean('Performance', 'USE_NUMPY_BATCH_OPS', fallback=True) and NUMPY_AVAILABLE

SCREEN_WIDTH = config.getint('Display', 'SCREEN_WIDTH', fallback=960)
SCREEN_HEIGHT = config.getint('Display', 'SCREEN_HEIGHT', fallback=540)
MAX_TABLE_ROWS = config.getint('Display', 'MAX_TABLE_ROWS', fallback=10)
FONT_PATH = config.get('Display', 'FONT_PATH', fallback='fonts/TerminusTTF-4.49.3.ttf')
HEADER_FONT_SIZE = config.getint('Display', 'HEADER_FONT_SIZE', fallback=32)
RADAR_FONT_SIZE = config.getint('Display', 'RADAR_FONT_SIZE', fallback=22)
TABLE_FONT_SIZE = config.getint('Display', 'TABLE_FONT_SIZE', fallback=22)
INSTRUCTION_FONT_SIZE = config.getint('Display', 'INSTRUCTION_FONT_SIZE', fallback=12)

# Colors
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
BRIGHT_GREEN = (50, 255, 50)
DIM_GREEN = (0, 180, 0)
RED = (255, 50, 50)
YELLOW = (255, 255, 0)
AMBER = (255, 191, 0)

class OptimizedTextCache:
    """Enhanced text cache with LRU eviction and better memory management"""

    def __init__(self, max_size=1000):
        self.cache = {}
        self.access_order = []
        self.max_size = max_size
        self._last_clear = time.time()

    def render(self, font: pygame.font.Font, text: str, color: tuple) -> pygame.Surface:
        if not ENABLE_TEXT_CACHE:
            return font.render(text, True, color)

        key = (text, color, font.get_height())

        if key in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]

        # Render new text
        surface = font.render(text, True, color)

        # Add to cache
        self.cache[key] = surface
        self.access_order.append(key)

        # Evict oldest if over size limit
        if len(self.cache) > self.max_size:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]

        return surface

    def clear_old(self):
        """Clear cache based on time and usage"""
        now = time.time()
        if now - self._last_clear > 300:  # 5 minutes
            # Keep only the 100 most recently used items
            if len(self.cache) > 100:
                to_keep = self.access_order[-100:]
                self.cache = {k: self.cache[k] for k in to_keep}
                self.access_order = to_keep
            self._last_clear = now

class StaticSurfaceCache:
    """Cache static radar elements to avoid redrawing"""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.radar_static = None
        self.needs_rebuild = True

    def get_radar_static(self, center_x, center_y, radius):
        if not ENABLE_STATIC_SURFACE_CACHE:
            return None

        if self.needs_rebuild or self.radar_static is None:
            self.radar_static = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.radar_static = self.radar_static.convert_alpha()
            self._draw_static_elements(self.radar_static, center_x, center_y, radius)
            self.needs_rebuild = False
        return self.radar_static

    def _draw_static_elements(self, surface, center_x, center_y, radius):
        # Range rings
        for ring in range(1, 4):
            ring_radius = int((ring / 3) * radius)
            pygame.draw.circle(surface, DIM_GREEN, (center_x, center_y), ring_radius, 2)

        # Crosshairs
        pygame.draw.line(surface, DIM_GREEN,
                        (center_x - radius, center_y),
                        (center_x + radius, center_y), 2)
        pygame.draw.line(surface, DIM_GREEN,
                        (center_x, center_y - radius),
                        (center_x, center_y + radius), 2)

        # Outer circle
        pygame.draw.circle(surface, BRIGHT_GREEN, (center_x, center_y), radius, 3)

class CoordinateCache:
    """Cache aircraft screen coordinates to avoid repeated calculations"""

    def __init__(self):
        self.cache = {}
        self.last_update = {}
        self.lat_cos_cache = math.cos(math.radians(LAT)) if LAT != 0 else 1.0
        self.range_km = RADIUS_NM * 1.852

    def get_screen_pos(self, aircraft_id, lat, lon, center_x, center_y, radius):
        if not ENABLE_COORDINATE_CACHE:
            return self._calculate_pos(lat, lon, center_x, center_y, radius)

        cache_key = aircraft_id
        current_time = time.time()

        # Check if we have recent cached coordinates
        if (cache_key in self.cache and 
            current_time - self.last_update.get(cache_key, 0) < COORDINATE_CACHE_TTL):
            return self.cache[cache_key]

        pos = self._calculate_pos(lat, lon, center_x, center_y, radius)

        # Cache result
        self.cache[cache_key] = pos
        self.last_update[cache_key] = current_time

        return pos

    def _calculate_pos(self, lat, lon, center_x, center_y, radius):
        # Calculate using pre-computed values
        lat_km = (lat - LAT) * 111
        lon_km = (lon - LON) * 111 * self.lat_cos_cache

        x = center_x + (lon_km / self.range_km) * radius
        y = center_y - (lat_km / self.range_km) * radius

        # Check if within radar circle
        dx, dy = x - center_x, y - center_y
        if dx*dx + dy*dy <= radius*radius:
            return (int(x), int(y))
        return None

class SortedAircraftManager:
    """Manage aircraft list with minimal re-sorting"""

    def __init__(self):
        self.aircraft_dict = {}
        self.sorted_list = []
        self.needs_resort = True

    def update_aircraft(self, new_aircraft_list):
        # Check if aircraft list has changed significantly
        new_dict = {a.hex_code: a for a in new_aircraft_list}

        if set(new_dict.keys()) != set(self.aircraft_dict.keys()):
            self.needs_resort = True
        else:
            # Check if distances have changed significantly
            for hex_code, aircraft in new_dict.items():
                old_aircraft = self.aircraft_dict.get(hex_code)
                if old_aircraft and abs(aircraft.distance - old_aircraft.distance) > 0.5:
                    self.needs_resort = True
                    break

        self.aircraft_dict = new_dict

        if self.needs_resort:
            self.sorted_list = sorted(new_aircraft_list, key=lambda a: a.distance)
            self.needs_resort = False

    def get_sorted_aircraft(self, max_count=None):
        if max_count:
            return self.sorted_list[:max_count]
        return self.sorted_list

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
    is_military: bool = False

def load_font(size: int) -> pygame.font.Font:
    """Load Terminus font with fallback to default pygame font"""
    try:
        return pygame.font.Font(FONT_PATH, size)
    except (pygame.error, FileNotFoundError):
        return pygame.font.Font(None, size)

def create_optimized_surface(width, height, alpha=True):
    """Create optimized pygame surface"""
    if alpha:
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        return surface.convert_alpha()
    else:
        surface = pygame.Surface((width, height))
        return surface.convert()

def calculate_distance_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """Calculate distance in nautical miles and bearing in degrees using Haversine formula"""
    # Convert to radians
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    # Distance calculation
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    distance_km = 2 * math.asin(math.sqrt(a)) * 6371  # Earth radius = 6371km
    distance_nm = distance_km * 0.539957  # Convert to nautical miles

    # Bearing calculation
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360

    return distance_nm, bearing

def batch_calculate_distances_bearings(aircraft_positions, center_lat, center_lon):
    """Calculate distances and bearings for multiple aircraft at once using NumPy"""
    if not USE_NUMPY_BATCH_OPS or not aircraft_positions:
        return []

    # Convert to numpy arrays
    lats = np.array([pos[0] for pos in aircraft_positions])
    lons = np.array([pos[1] for pos in aircraft_positions])

    # Convert to radians
    lat1_rad = np.radians(center_lat)
    lon1_rad = np.radians(center_lon)
    lat2_rad = np.radians(lats)
    lon2_rad = np.radians(lons)

    # Vectorized distance calculation
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    distances_km = 2 * np.arcsin(np.sqrt(a)) * 6371
    distances_nm = distances_km * 0.539957

    # Vectorized bearing calculation
    y = np.sin(dlon) * np.cos(lat2_rad)
    x = np.cos(lat1_rad) * np.sin(lat2_rad) - np.sin(lat1_rad) * np.cos(lat2_rad) * np.cos(dlon)
    bearings = (np.degrees(np.arctan2(y, x)) + 360) % 360

    return list(zip(distances_nm, bearings))

def parse_aircraft(data: dict) -> Optional[Aircraft]:
    """Parse tar1090 aircraft data into Aircraft object"""
    # Skip aircraft without position
    if 'lat' not in data or 'lon' not in data:
        return None

    lat, lon = data['lat'], data['lon']
    distance, bearing = calculate_distance_bearing(LAT, LON, lat, lon)

    # Skip aircraft outside our range
    if distance > RADIUS_NM:
        return None

    # Simple military detection using defined prefixes
    hex_code = data['hex'].lower()
    mil_prefixes = tuple(prefix.lower() for prefix in MIL_PREFIX_LIST)
    is_military = hex_code.startswith(mil_prefixes)

    return Aircraft(
        hex_code=hex_code,
        callsign=data.get('flight', 'UNKNOWN').strip()[:8],
        lat=lat,
        lon=lon,
        altitude=data.get('alt_baro', 0) or 0,
        speed=int(data.get('gs', 0) or 0),
        track=data.get('track', 0) or 0,
        distance=distance,
        bearing=bearing,
        is_military=is_military
    )

class RadarScope:
    """Optimized radar display component"""

    def __init__(self, screen: pygame.Surface, center_x: int, center_y: int, radius: int, text_cache: OptimizedTextCache):
        self.screen = screen
        self.center_x = center_x
        self.center_y = center_y
        self.radius = radius
        self.font = load_font(RADAR_FONT_SIZE)
        self.text_cache = text_cache
        self.coord_cache = CoordinateCache()
        self.static_cache = StaticSurfaceCache(screen.get_width(), screen.get_height())

    def draw_aircraft(self, aircraft: Aircraft, x: int, y: int, color: tuple):
        """Draw aircraft symbol with direction indicator"""
        # Main aircraft dot
        pygame.draw.circle(self.screen, color, (x, y), 5, 0)

        # Direction arrow if we have track data
        if aircraft.track > 0:
            track_rad = math.radians(aircraft.track)
            # Trailing line (behind)
            trail_length = 12
            trail_x = x - trail_length * math.sin(track_rad)
            trail_y = y + trail_length * math.cos(track_rad)
            pygame.draw.line(self.screen, color, (int(trail_x), int(trail_y)), (x, y), 2)

        # Callsign label
        text = self.text_cache.render(self.font, aircraft.callsign, color)
        self.screen.blit(text, (x + 8, y - 12))

    def draw(self, aircraft_list: List[Aircraft]):
        """Draw the complete radar scope with optimizations"""
        # Draw static elements from cache if available
        static_surface = self.static_cache.get_radar_static(self.center_x, self.center_y, self.radius)
        if static_surface:
            self.screen.blit(static_surface, (0, 0))
        else:
            # Fallback to direct drawing
            self._draw_static_elements()

        # Draw range labels (these might change based on RADIUS_NM)
        for ring in range(1, 4):
            ring_radius = int((ring / 3) * self.radius)
            range_nm = int((ring / 3) * RADIUS_NM)
            text = self.text_cache.render(self.font, f"{range_nm}NM", DIM_GREEN)
            self.screen.blit(text, (self.center_x + ring_radius - 20, self.center_y + 5))

        # Aircraft symbols with optimized coordinate calculation
        blink_state = int(time.time() * 2) % 2  # Blink every 0.5 seconds
        for aircraft in aircraft_list:
            pos = self.coord_cache.get_screen_pos(aircraft.hex_code, aircraft.lat, aircraft.lon, 
                                                self.center_x, self.center_y, self.radius)
            if pos:
                x, y = pos
                # Military aircraft optionally blink red, civilian are always green
                if aircraft.is_military:
                    if not BLINK_MILITARY or blink_state:
                        self.draw_aircraft(aircraft, x, y, RED)
                else:
                    self.draw_aircraft(aircraft, x, y, BRIGHT_GREEN)

    def _draw_static_elements(self):
        """Draw static radar elements directly (fallback)"""
        # Range rings
        for ring in range(1, 4):
            ring_radius = int((ring / 3) * self.radius)
            pygame.draw.circle(self.screen, DIM_GREEN, (self.center_x, self.center_y), ring_radius, 2)

        # Crosshairs
        pygame.draw.line(self.screen, DIM_GREEN,
                        (self.center_x - self.radius, self.center_y),
                        (self.center_x + self.radius, self.center_y), 2)
        pygame.draw.line(self.screen, DIM_GREEN,
                        (self.center_x, self.center_y - self.radius),
                        (self.center_x, self.center_y + self.radius), 2)

        # Outer circle
        pygame.draw.circle(self.screen, BRIGHT_GREEN, (self.center_x, self.center_y), self.radius, 3)

class DataTable:
    """Optimized aircraft data table component"""

    def __init__(self, screen: pygame.Surface, x: int, y: int, width: int, height: int, text_cache: OptimizedTextCache):
        self.screen = screen
        self.rect = pygame.Rect(x, y, width, height)
        self.title_font = load_font(TABLE_FONT_SIZE)
        self.data_font = load_font(TABLE_FONT_SIZE)
        self.small_font = load_font(TABLE_FONT_SIZE)
        self.text_cache = text_cache
        self.aircraft_manager = SortedAircraftManager()

    def draw(self, aircraft_list: List[Aircraft], status: str, last_update: float):
        """Draw aircraft data table with optimized sorting"""
        # Update aircraft manager (handles smart sorting)
        self.aircraft_manager.update_aircraft(aircraft_list)

        # Border
        pygame.draw.rect(self.screen, BRIGHT_GREEN, self.rect, 3)

        # Title
        title = self.text_cache.render(self.title_font, "AIRCRAFT DATA", AMBER)
        title_rect = title.get_rect(centerx=self.rect.centerx, y=self.rect.y + 12)
        self.screen.blit(title, title_rect)

        # Column headers
        headers_y = self.rect.y + 40
        headers = ["CALL", "ALT", "SPD", "DIST", "HDG"]
        col_width = self.rect.width // 5

        for i, header in enumerate(headers):
            text = self.text_cache.render(self.data_font, header, AMBER)
            self.screen.blit(text, (self.rect.x + 20 + i * col_width, headers_y))

        # Separator line
        pygame.draw.line(self.screen, DIM_GREEN,
                        (self.rect.x + 8, headers_y + 22),
                        (self.rect.right - 8, headers_y + 22), 2)

        # Aircraft data rows using optimized sorting
        sorted_aircraft = self.aircraft_manager.get_sorted_aircraft(MAX_TABLE_ROWS)
        start_y = headers_y + 30

        for i, aircraft in enumerate(sorted_aircraft):
            y_pos = start_y + i * 22
            color = RED if aircraft.is_military else BRIGHT_GREEN

            # Format data columns
            columns = [
                f"{aircraft.callsign:<8}",
                f"{aircraft.altitude:>5}" if isinstance(aircraft.altitude, int) and aircraft.altitude > 0 else "GND",
                f"{aircraft.speed:>3}" if aircraft.speed > 0 else "N/A",
                f"{aircraft.distance:>4.1f}" if aircraft.distance > 0 else "N/A ",
                f"{aircraft.track:03.0f}°" if aircraft.track > 0 else "N/A"
            ]

            for j, value in enumerate(columns):
                text = self.text_cache.render(self.small_font, str(value), color)
                self.screen.blit(text, (self.rect.x + 20 + j * col_width, y_pos))

        # Status information
        military_count = sum(1 for a in aircraft_list if a.is_military)
        elapsed = time.time() - last_update
        countdown = max(0, FETCH_INTERVAL - elapsed)
        countdown_text = f"{int(countdown):02d}S" if countdown > 0 else "UPDATING"

        status_info = [
            f"STATUS: {status}",
            f"CONTACTS: {len(aircraft_list)} ({military_count} MIL)",
            f"RANGE: {RADIUS_NM}NM",
            f"INTERVAL: {FETCH_INTERVAL}S",
            f"NEXT UPDATE: {countdown_text}"
        ]

        status_y = self.rect.bottom - 120
        for i, info in enumerate(status_info):
            color = YELLOW if "UPDATING" in info else BRIGHT_GREEN
            text = self.text_cache.render(self.small_font, info, color)
            self.screen.blit(text, (self.rect.x + 20, status_y + i * 20))

class AircraftTracker:
    """Handles fetching aircraft data from tar1090"""

    def __init__(self):
        self.aircraft: List[Aircraft] = []
        self.status = "INITIALISING"
        self.last_update = time.time()
        self.running = True

    def fetch_data(self) -> List[Aircraft]:
        """Fetch aircraft from local tar1090"""
        try:
            response = requests.get(TAR1090_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            aircraft_list = []
            for aircraft_data in data.get('aircraft', []):
                aircraft = parse_aircraft(aircraft_data)
                if aircraft:
                    aircraft_list.append(aircraft)

            return aircraft_list

        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return []

    def update_loop(self):
        """Background thread to fetch data periodically"""
        while self.running:
            self.status = "SCANNING"
            self.last_update = time.time()

            aircraft = self.fetch_data()
            if aircraft:
                self.aircraft = aircraft
                self.status = "ACTIVE"
            else:
                self.status = "NO CONTACTS"

            time.sleep(FETCH_INTERVAL)

    def start(self):
        """Start the background data fetching"""
        thread = threading.Thread(target=self.update_loop, daemon=True)
        thread.start()

def create_scanlines(width: int, height: int) -> pygame.Surface:
    """Create CRT-style scanline overlay"""
    surface = create_optimized_surface(width, height, True)
    for y in range(0, height, 4):
        pygame.draw.line(surface, (0, 0, 0, 30), (0, y), (width, y))
    return surface

def main():
    """Main application loop with optimizations"""
    pygame.init()
    pygame.mixer.quit()  # Disable all audio to save resources

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption(f"{AREA_NAME} ADS-B RADAR")
    clock = pygame.time.Clock()
    frame_count = 0

    # Initialize optimized text cache
    text_cache = OptimizedTextCache(MAX_TEXT_CACHE_SIZE)

    # Load fonts
    header_font = load_font(HEADER_FONT_SIZE)
    instruction_font = load_font(INSTRUCTION_FONT_SIZE)
    title_font = load_font(RADAR_FONT_SIZE)

    # Create scanline overlay using optimized surface
    scanlines = create_scanlines(SCREEN_WIDTH, SCREEN_HEIGHT)

    # Pre-render static text elements
    radar_size = min(SCREEN_HEIGHT - 120, SCREEN_WIDTH // 2 - 50) // 2
    static_radar_title = text_cache.render(title_font, "◄ ADS-B RADAR SCOPE ►", AMBER)
    static_radar_title_rect = static_radar_title.get_rect(centerx=SCREEN_WIDTH//4, y=SCREEN_HEIGHT//2 - radar_size)
    static_instructions = text_cache.render(instruction_font, "PRESS Q OR ESC TO QUIT", DIM_GREEN)
    static_instructions_rect = (15, SCREEN_HEIGHT - 30)

    # Create optimized components
    radar = RadarScope(screen, SCREEN_WIDTH // 4, SCREEN_HEIGHT // 2 + 30, radar_size, text_cache)
    table = DataTable(screen, SCREEN_WIDTH // 2 + 20, 80,
                     SCREEN_WIDTH // 2 - 30, SCREEN_HEIGHT - 100, text_cache)

    # Start aircraft tracker
    tracker = AircraftTracker()
    tracker.start()

    print(f"Radar system initialized with optimizations:")
    print(f"  - Text Cache: {'Enabled' if ENABLE_TEXT_CACHE else 'Disabled'}")
    print(f"  - Coordinate Cache: {'Enabled' if ENABLE_COORDINATE_CACHE else 'Disabled'}")
    print(f"  - Static Surface Cache: {'Enabled' if ENABLE_STATIC_SURFACE_CACHE else 'Disabled'}")
    print(f"  - NumPy Batch Operations: {'Enabled' if USE_NUMPY_BATCH_OPS else 'Disabled'}")

    # Main loop
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE)
            ):
                running = False

        # Clear screen
        screen.fill(BLACK)
        frame_count += 1

        # Periodic cache cleanup
        if frame_count % 300 == 0:  # Every 300 frames (~1 minute at 6 FPS)
            text_cache.clear_old()

        # Header (updates every frame for time)
        current_time = datetime.now().strftime("%H:%M:%S")
        header_text = f"{AREA_NAME} {LAT}°, {LON}° - {current_time}"
        header = text_cache.render(header_font, header_text, AMBER)
        header_rect = header.get_rect(centerx=SCREEN_WIDTH // 2, y=15)
        screen.blit(header, header_rect)

        # Static text elements
        screen.blit(static_radar_title, static_radar_title_rect)
        screen.blit(static_instructions, static_instructions_rect)

        # Components
        radar.draw(tracker.aircraft)
        table.draw(tracker.aircraft, tracker.status, tracker.last_update)

        # Scanline effect (reduced frequency)
        if frame_count % STATIC_REDRAW_INTERVAL == 0:
            screen.blit(scanlines, (0, 0))

        pygame.display.flip()
        clock.tick(FPS)

    tracker.running = False
    pygame.quit()

if __name__ == "__main__":
    main()
