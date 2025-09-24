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

SCREEN_WIDTH = config.getint('Display', 'SCREEN_WIDTH', fallback=960)
SCREEN_HEIGHT = config.getint('Display', 'SCREEN_HEIGHT', fallback=540)
FPS = config.getint('Display', 'FPS', fallback=6)
MAX_TABLE_ROWS = config.getint('Display', 'MAX_TABLE_ROWS', fallback=10)
FONT_PATH = config.get('Display', 'FONT_PATH', fallback='fonts/TerminusTTF-4.49.3.ttf')
HEADER_FONT_SIZE = config.getint('Display', 'HEADER_FONT_SIZE', fallback=32)
RADAR_FONT_SIZE = config.getint('Display', 'RADAR_FONT_SIZE', fallback=22)
TABLE_FONT_SIZE = config.getint('Display', 'TABLE_FONT_SIZE', fallback=22)
INSTRUCTION_FONT_SIZE = config.getint('Display', 'INSTRUCTION_FONT_SIZE', fallback=12)

# Colours
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
BRIGHT_GREEN = (50, 255, 50)
DIM_GREEN = (0, 180, 0)
RED = (255, 50, 50)
YELLOW = (255, 255, 0)
AMBER = (255, 191, 0)

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
    """Radar display component"""

    def __init__(self, screen: pygame.Surface, center_x: int, center_y: int, radius: int):
        self.screen = screen
        self.center_x = center_x
        self.center_y = center_y
        self.radius = radius
        self.font = load_font(RADAR_FONT_SIZE)

    def lat_lon_to_screen(self, lat: float, lon: float) -> Optional[Tuple[int, int]]:
        """Convert lat/lon to screen coordinates"""
        # Simple flat projection
        lat_km = (lat - LAT) * 111
        lon_km = (lon - LON) * 111 * math.cos(math.radians(LAT))
        range_km = RADIUS_NM * 1.852

        x = self.center_x + (lon_km / range_km) * self.radius
        y = self.center_y - (lat_km / range_km) * self.radius

        # Check if point is within radar circle
        dx, dy = x - self.center_x, y - self.center_y
        if dx*dx + dy*dy <= self.radius*self.radius:
            return int(x), int(y)
        return None

    def draw_aircraft(self, aircraft: Aircraft, x: int, y: int, colour: tuple):
        """Draw aircraft symbol with direction indicator"""
        # Main aircraft dot
        pygame.draw.circle(self.screen, colour, (x, y), 5, 0)

        # Direction arrow if we have track data
        if aircraft.track > 0:
            track_rad = math.radians(aircraft.track)
            line_length = 15

            # Trailing line (behind)
            trail_length = 12
            trail_x = x - trail_length * math.sin(track_rad)
            trail_y = y + trail_length * math.cos(track_rad)
            pygame.draw.line(self.screen, colour, (int(trail_x), int(trail_y)), (x, y), 2)

        # Callsign label
        text = self.font.render(aircraft.callsign, True, colour)
        self.screen.blit(text, (x + 8, y - 12))

    def draw(self, aircraft_list: List[Aircraft]):
        """Draw the complete radar scope"""
        # Range rings
        for ring in range(1, 4):
            ring_radius = int((ring / 3) * self.radius)
            pygame.draw.circle(self.screen, DIM_GREEN, (self.center_x, self.center_y), ring_radius, 2)

            # Range labels
            range_nm = int((ring / 3) * RADIUS_NM)
            text = self.font.render(f"{range_nm}NM", True, DIM_GREEN)
            self.screen.blit(text, (self.center_x + ring_radius - 20, self.center_y + 5))

        # Crosshairs
        pygame.draw.line(self.screen, DIM_GREEN, 
                        (self.center_x - self.radius, self.center_y),
                        (self.center_x + self.radius, self.center_y), 2)
        pygame.draw.line(self.screen, DIM_GREEN,
                        (self.center_x, self.center_y - self.radius),
                        (self.center_x, self.center_y + self.radius), 2)

        # Outer circle
        pygame.draw.circle(self.screen, BRIGHT_GREEN, (self.center_x, self.center_y), self.radius, 3)

        # Aircraft symbols
        blink_state = int(time.time() * 2) % 2  # Blink every 0.5 seconds

        for aircraft in aircraft_list:
            pos = self.lat_lon_to_screen(aircraft.lat, aircraft.lon)
            if pos:
                x, y = pos
                # Military aircraft optionally blink red, civilian are always green
                if aircraft.is_military:
                    if not BLINK_MILITARY or blink_state:
                        self.draw_aircraft(aircraft, x, y, RED)
                else:
                    self.draw_aircraft(aircraft, x, y, BRIGHT_GREEN)

class DataTable:
    """Aircraft data table component"""

    def __init__(self, screen: pygame.Surface, x: int, y: int, width: int, height: int):
        self.screen = screen
        self.rect = pygame.Rect(x, y, width, height)
        self.title_font = load_font(TABLE_FONT_SIZE)
        self.data_font = load_font(TABLE_FONT_SIZE)
        self.small_font = load_font(TABLE_FONT_SIZE)

    def draw(self, aircraft_list: List[Aircraft], status: str, last_update: float):
        """Draw aircraft data table"""
        # Border
        pygame.draw.rect(self.screen, BRIGHT_GREEN, self.rect, 3)

        # Title
        title = self.title_font.render("AIRCRAFT DATA", True, AMBER)
        title_rect = title.get_rect(centerx=self.rect.centerx, y=self.rect.y + 10)
        self.screen.blit(title, title_rect)

        # Column headers
        headers_y = self.rect.y + 40
        headers = ["CALL", "   ALT", "SPD", "DIST", "HDG"]
        
        # Calculate column widths based on content
        total_width = self.rect.width - 40  # Account for padding
        col_widths = [0.25, 0.25, 0.15, 0.2, 0.15]  # Proportions of total width
        col_positions = []
        current_x = self.rect.x + 20
        
        for i, width_ratio in enumerate(col_widths):
            width = int(total_width * width_ratio)
            col_positions.append(current_x)
            text = self.data_font.render(headers[i], True, AMBER)
            self.screen.blit(text, (current_x, headers_y))
            current_x += width

        # Separator line
        pygame.draw.line(self.screen, DIM_GREEN,
                        (self.rect.x + 8, headers_y + TABLE_FONT_SIZE),
                        (self.rect.right - 8, headers_y + TABLE_FONT_SIZE), 2)

        # Aircraft data rows
        sorted_aircraft = sorted(aircraft_list, key=lambda a: a.distance)
        start_y = headers_y + 30

        for i, aircraft in enumerate(sorted_aircraft[:MAX_TABLE_ROWS]):  # Show up to MAX_TABLE_ROWS aircraft
            y_pos = start_y + i * TABLE_FONT_SIZE
            colour = RED if aircraft.is_military else BRIGHT_GREEN

            # Format data columns
            columns = [
                f"{aircraft.callsign:<8}",
                f"{aircraft.altitude:>6}" if isinstance(aircraft.altitude, int) and aircraft.altitude > 0 else "  N/A",
                f"{aircraft.speed:>3}" if aircraft.speed > 0 else "N/A",
                f"{aircraft.distance:>4.1f}" if aircraft.distance > 0 else "N/A ",
                f"{aircraft.track:>3.0f}°" if aircraft.track > 0 else "N/A"
            ]

            for j, value in enumerate(columns):
                text = self.small_font.render(str(value), True, colour)
                self.screen.blit(text, (col_positions[j], y_pos))

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

        status_y = self.rect.bottom - 5 * TABLE_FONT_SIZE - 10
        for i, info in enumerate(status_info):
            colour = YELLOW if "UPDATING" in info else BRIGHT_GREEN
            text = self.small_font.render(info, True, colour)
            self.screen.blit(text, (self.rect.x + 20, status_y + i * TABLE_FONT_SIZE))

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
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(0, height, 4):
        pygame.draw.line(surface, (0, 0, 0, 30), (0, y), (width, y))
    return surface

def main():
    """Main application loop"""
    pygame.init()
    pygame.mixer.quit()  # Disable all audio to save resources
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption(f"{AREA_NAME} ADS-B RADAR")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    # Load fonts
    header_font = load_font(HEADER_FONT_SIZE)
    instruction_font = load_font(INSTRUCTION_FONT_SIZE)
    
    # Create scanline overlay
    scanlines = create_scanlines(SCREEN_WIDTH, SCREEN_HEIGHT)

    # Create components
    radar_size = min(SCREEN_HEIGHT - 120, SCREEN_WIDTH // 2 - 50) // 2
    radar = RadarScope(screen, SCREEN_WIDTH // 4, SCREEN_HEIGHT // 2 + 35, radar_size)

    table = DataTable(screen, SCREEN_WIDTH // 2 + 20, 80, 
                     SCREEN_WIDTH // 2 - 30, SCREEN_HEIGHT - 100)

    # Start aircraft tracker
    tracker = AircraftTracker()
    tracker.start()

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

        # Header
        current_time = datetime.now().strftime("%H:%M:%S")
        header_text = f"{AREA_NAME} {LAT}°, {LON}° - {current_time}"
        header = header_font.render(header_text, True, AMBER)
        header_rect = header.get_rect(centerx=SCREEN_WIDTH // 2, y=15)
        screen.blit(header, header_rect)

        # Radar title
        title_font = load_font(RADAR_FONT_SIZE)
        radar_title = title_font.render("◄ ADS-B RADAR SCOPE ►", True, AMBER)
        radar_title_rect = radar_title.get_rect(centerx=SCREEN_WIDTH//4, y=SCREEN_HEIGHT//2 - radar_size)
        screen.blit(radar_title, radar_title_rect)

        # Components
        radar.draw(tracker.aircraft)
        table.draw(tracker.aircraft, tracker.status, tracker.last_update)

        # Instructions
        instructions = instruction_font.render("PRESS Q OR ESC TO QUIT", True, DIM_GREEN)
        screen.blit(instructions, (15, SCREEN_HEIGHT - 30))

        # Scanline effect
        screen.blit(scanlines, (0, 0))

        pygame.display.flip()
        clock.tick(FPS)

    tracker.running = False
    pygame.quit()

if __name__ == "__main__":
    main()