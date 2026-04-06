import math
import pygame
from typing import Optional, Tuple

import config

_font_cache = {}

def calculate_distance_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """Calculate distance in nautical miles and bearing in degrees"""
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat, dlon = lat2_rad - lat1_rad, lon2_rad - lon1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    distance_km = 2 * math.asin(math.sqrt(a)) * 6371
    distance_nm = distance_km * 0.539957
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return distance_nm, bearing

def check_pygame_modules():
    """Verify essential Pygame modules are available"""
    print("\nChecking Pygame module support...")
    pygame.init()
    print(f"Video: {'Supported' if pygame.display.get_init() else '❌ Not available - install libsdl2-2.0-0'}")
    print(f"Font: {'Supported' if pygame.font.get_init() else '❌ Not available - install libsdl2-ttf-2.0-0'}")
    print(f"Image: {'Supported' if pygame.image.get_extended() else '❌ Not available - install libsdl2-image-2.0-0'}")

def load_background(path: str) -> Optional[pygame.Surface]:
    """Load and scale background image if it exists"""
    try:
        print(f"\nLoading background image from {path}...")
        bg = pygame.image.load(path)
        print("Background image loaded successfully")
        if bg.get_size() != (config.SCREEN_WIDTH, config.SCREEN_HEIGHT):
            print(f"Warning: Resizing background from {bg.get_size()} to display resolution")
            bg = pygame.transform.scale(bg, (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        return bg
    except (pygame.error, FileNotFoundError) as e:
        print(f"Warning: Couldn't load background image: {e}")
        return None

def load_font(size: int) -> pygame.font.Font:
    """Load font with fallback, using a managed cache."""
    if size in _font_cache:
        return _font_cache[size]
        
    try:
        font = pygame.font.Font(config.FONT_PATH, size)
        print(f"Loaded font {config.FONT_PATH} at size {size}")
    except (pygame.error, FileNotFoundError):
        print(f"Warning: Could not load {config.FONT_PATH}, falling back to default font")
        font = pygame.font.Font(None, size)
    
    _font_cache[size] = font
    return font
