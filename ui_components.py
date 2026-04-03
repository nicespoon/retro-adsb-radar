import pygame
import time
import math
from typing import List, Optional, Tuple

import config
from data_models import Aircraft
import utils

class RadarScope:
    """Radar display component"""
    def __init__(self, screen: pygame.Surface, center_x: int, center_y: int, radius: int):
        self.screen = screen
        self.center_x = center_x
        self.center_y = center_y
        self.radius = radius
        self.font = utils.load_font(config.RADAR_FONT_SIZE)

    def lat_lon_to_screen(self, lat: float, lon: float) -> Optional[Tuple[int, int]]:
        """Convert lat/lon to screen coordinates"""
        lat_km = (lat - config.LAT) * 111
        lon_km = (lon - config.LON) * 111 * math.cos(math.radians(config.LAT))
        range_km = config.RADIUS_NM * 1.852
        x = self.center_x + (lon_km / range_km) * self.radius
        y = self.center_y - (lat_km / range_km) * self.radius

        dx, dy = x - self.center_x, y - self.center_y
        if dx*dx + dy*dy <= self.radius*self.radius:
            return int(x), int(y)
        return None

    def draw_aircraft(self, aircraft: Aircraft, x: int, y: int, colour: tuple):
        """Draw aircraft symbol with direction indicator"""
        pygame.draw.circle(self.screen, colour, (x, y), 5, 0)
        if aircraft.track > 0:
            track_rad = math.radians(aircraft.track)
            min_length, max_length, max_speed = config.TRAIL_MIN_LENGTH, config.TRAIL_MAX_LENGTH, config.TRAIL_MAX_SPEED
            trail_length = min_length + (max_length - min_length) * min(aircraft.speed, max_speed) / max_speed
            trail_x = x - trail_length * math.sin(track_rad)
            trail_y = y + trail_length * math.cos(track_rad)
            pygame.draw.line(self.screen, colour, (int(trail_x), int(trail_y)), (x, y), 2)
        
        text = self.font.render(aircraft.callsign, True, colour)
        self.screen.blit(text, (x + 8, y - 12))

    def draw(self, aircraft_list: List[Aircraft]):
        """Draw the complete radar scope"""
        for ring in range(1, 4):
            ring_radius = int((ring / 3) * self.radius)
            pygame.draw.circle(self.screen, config.DIM_GREEN, (self.center_x, self.center_y), ring_radius, 2)
            range_nm = int((ring / 3) * config.RADIUS_NM)
            text = self.font.render(f"{range_nm}NM", True, config.DIM_GREEN)
            self.screen.blit(text, (self.center_x + ring_radius - 20, self.center_y + 5))

        pygame.draw.line(self.screen, config.DIM_GREEN, (self.center_x - self.radius, self.center_y), (self.center_x + self.radius, self.center_y), 2)
        pygame.draw.line(self.screen, config.DIM_GREEN, (self.center_x, self.center_y - self.radius), (self.center_x, self.center_y + self.radius), 2)
        pygame.draw.circle(self.screen, config.BRIGHT_GREEN, (self.center_x, self.center_y), self.radius, 3)

        blink_state = int(time.time() * 2) % 2
        for aircraft in aircraft_list:
            pos = self.lat_lon_to_screen(aircraft.lat, aircraft.lon)
            if pos:
                x, y = pos
                if aircraft.is_military:
                    if not config.BLINK_MILITARY or blink_state:
                        self.draw_aircraft(aircraft, x, y, config.RED)
                else:
                    self.draw_aircraft(aircraft, x, y, config.BRIGHT_GREEN)

class DataTable:
    """Aircraft data table component"""
    def __init__(self, screen: pygame.Surface, x: int, y: int, width: int, height: int):
        self.screen = screen
        self.rect = pygame.Rect(x, y, width, height)
        self.font = utils.load_font(config.TABLE_FONT_SIZE)

    def draw(self, aircraft_list: List[Aircraft], status: str, last_update: float):
        """Draw aircraft data table"""
        pygame.draw.rect(self.screen, config.BRIGHT_GREEN, self.rect, 3)
        title = self.font.render("AIRCRAFT DATA", True, config.AMBER)
        title_rect = title.get_rect(centerx=self.rect.centerx, y=self.rect.y + 10)
        self.screen.blit(title, title_rect)

        headers_y = self.rect.y + 40
        headers = ["CALLSIGN", "TYPE", "  ALT", "SPD", "TRK"]
        # headers = ["CALLSIGN", "   ALT", "SPD", "TYPE", "TRK"]
        # headers = ["CALLSIGN", "   ALT", "SPD", "DIST", "TRK"]
        total_width = self.rect.width - 40
        col_widths = [0.30, 0.20, 0.20, 0.15, 0.15]
        # col_widths = [0.25, 0.25, 0.15, 0.2, 0.15]        
        col_positions = []
        current_x = self.rect.x + 20
        for i, width_ratio in enumerate(col_widths):
            width = int(total_width * width_ratio)
            col_positions.append(current_x)
            text = self.font.render(headers[i], True, config.AMBER)
            self.screen.blit(text, (current_x, headers_y))
            current_x += width

        pygame.draw.line(self.screen, config.DIM_GREEN, (self.rect.x + 8, headers_y + config.TABLE_FONT_SIZE), (self.rect.right - 8, headers_y + config.TABLE_FONT_SIZE), 2)

        sorted_aircraft = sorted(aircraft_list, key=lambda a: a.distance)
        start_y = headers_y + 30
        for i, aircraft in enumerate(sorted_aircraft[:config.MAX_TABLE_ROWS]):
            y_pos = start_y + i * config.TABLE_FONT_SIZE
            colour = config.RED if aircraft.is_military else config.BRIGHT_GREEN
            columns = [
                f"{aircraft.callsign:<7}",
                f"{(aircraft.type or 'N/A'):<4}",
                f"{aircraft.altitude:>5}" if isinstance(aircraft.altitude, int) and aircraft.altitude > 0 else "  N/A",
                # f"{aircraft.altitude:>5}" if isinstance(aircraft.altitude, int) and aircraft.altitude > 0 else "   N/A",
                f"{aircraft.speed:>3}" if aircraft.speed > 0 else "N/A",
                # f"{(aircraft.type or 'N/A'):<4}",
                # f"{aircraft.distance:>4.1f}" if aircraft.distance > 0 else "N/A ",
                f"{aircraft.track:>3.0f}°" if aircraft.track > 0 else "N/A"
            ]
            for j, value in enumerate(columns):
                text = self.font.render(str(value), True, colour)
                self.screen.blit(text, (col_positions[j], y_pos))

        military_count = sum(1 for a in aircraft_list if a.is_military)
        elapsed = time.time() - last_update
        countdown = max(0, config.FETCH_INTERVAL - elapsed)
        # countdown_text = f"{int(countdown):02d}S" if countdown > 0 else "UPDATING"
        status_info = [
            f"STATUS: {status}",
            f"CONTACTS: {len(aircraft_list)} ({military_count} MIL)",
            f"RANGE: {config.RADIUS_NM}NM",
            f"REFRESH: {config.FETCH_INTERVAL}S",
            # f"NEXT UPDATE: {countdown_text}"
        ]
        status_y = self.rect.bottom - 4 * config.TABLE_FONT_SIZE - 10
        for i, info in enumerate(status_info):
            colour = config.YELLOW if "UPDATING" in info else config.BRIGHT_GREEN
            text = self.font.render(info, True, colour)
            self.screen.blit(text, (self.rect.x + 20, status_y + i * config.TABLE_FONT_SIZE))
