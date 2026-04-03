# Set SDL_AUDIODRIVER to guarantee no device is opened for audio output
import os
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import config
import utils
from audio_manager import AudioManager
from data_fetcher import AircraftTracker
from ui_components import RadarScope, DataTable

def main():
    """Main application loop"""
    print("\nStarting Retro ADS-B Radar...")
    print(f"📍 Location: {config.AREA_NAME} ({config.LAT}°, {config.LON}°)")
    print(f"📡 Range: {config.RADIUS_NM} NM")
    print(f"🖥️  Display: {config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT} at {config.FPS} FPS")

    # Initialisation
    pygame.display.init()
    pygame.font.init()
    utils.check_pygame_modules()

    # Preload all required fonts into a local dictionary
    print("\nPreloading fonts...")
    font_cache = {
        'header': utils.load_font(config.HEADER_FONT_SIZE),
        'radar': utils.load_font(config.RADAR_FONT_SIZE),
        'table': utils.load_font(config.TABLE_FONT_SIZE),
        'instruction': utils.load_font(config.INSTRUCTION_FONT_SIZE)
    }

    # Display Setup
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption(f"{config.AREA_NAME} ADS-B RADAR")
    clock = pygame.time.Clock()
    background = utils.load_background(config.BACKGROUND_PATH) if config.BACKGROUND_PATH else None
    
    # Mouse Visibility Control
    last_mouse_move = time.time()
    MOUSE_HIDE_DELAY = 3.0
    pygame.mouse.set_visible(True)

    # Create Components
    radar_size = min(config.SCREEN_HEIGHT - 120, config.SCREEN_WIDTH // 2 - 50) // 2
    radar = RadarScope(screen, config.SCREEN_WIDTH // 4, config.SCREEN_HEIGHT // 2 + 35, radar_size)
    table = DataTable(screen, config.SCREEN_WIDTH // 2 + 20, 80, config.SCREEN_WIDTH // 2 - 30, config.SCREEN_HEIGHT - 100)
    
    # Initialise Audio and Data Tracker
    audio = AudioManager(config.ATC_STREAM_URL)
    if audio.initialise() and config.ATC_AUTO_START:
        print("Auto-starting ATC audio...")
        audio.toggle()

    tracker = AircraftTracker()
    tracker.start()

    # Main Loop
    running = True
    while running:
        # Mouse Cursor Visibility
        if time.time() - last_mouse_move > MOUSE_HIDE_DELAY:
            pygame.mouse.set_visible(False)

        # Drawing
        screen.blit(background, (0, 0)) if background else screen.fill(config.BLACK)

        # Header
        current_time = datetime.now().strftime("%H:%M:%S")
        zulu_time = datetime.now(timezone.utc).strftime("%H:%M:%S")
        header_text = f"{config.AREA_NAME} - {config.LAT}°,{config.LON}° - {current_time}L / {zulu_time}Z"
        header = font_cache['header'].render(header_text, True, config.AMBER)
        header_rect = header.get_rect(centerx=config.SCREEN_WIDTH // 2, y=15)
        screen.blit(header, header_rect)

        # Radar Title
        radar_title = font_cache['radar'].render("◄ ADS-B RADAR SCOPE ►", True, config.AMBER)
        radar_title_rect = radar_title.get_rect(centerx=config.SCREEN_WIDTH//4, y=config.SCREEN_HEIGHT//2 - radar_size)
        screen.blit(radar_title, radar_title_rect)

        # Components
        radar.draw(tracker.aircraft)
        table.draw(tracker.aircraft, tracker.status, tracker.last_update)

        # Instructions with clickable areas (centered under radar scope)
        #quit_text = "Q/ESC: QUIT"
        quit_text = ""
        audio_text = f"A: ATC [{'ON' if audio.is_playing() else 'OFF'}]" if audio and audio.initialised else ""

        # Combine both texts with spacing
        instruction_text = quit_text
        if audio_text:
            instruction_text += "    " + audio_text

        instruction_surface = font_cache['instruction'].render(instruction_text, True, config.DIM_GREEN)
        # Centre the instructions under the radar scope (same centerx as radar title)
        instruction_rect = instruction_surface.get_rect(centerx=config.SCREEN_WIDTH // 4, y=config.SCREEN_HEIGHT - 55)

        # For hover/click, calculate the rects for each part
        quit_surface = font_cache['instruction'].render(quit_text, True, config.DIM_GREEN)
        quit_rect = quit_surface.get_rect()
        quit_rect.y = config.SCREEN_HEIGHT - 55
        # Place quit_rect at left of combined text
        quit_rect.x = instruction_rect.x

        if audio_text:
            audio_surface = font_cache['instruction'].render(audio_text, True, config.DIM_GREEN)
            audio_rect = audio_surface.get_rect()
            audio_rect.y = config.SCREEN_HEIGHT - 55
            # Place audio_rect after quit_rect with spacing
            audio_rect.x = quit_rect.right + font_cache['instruction'].size('    ')[0]
        else:
            audio_surface = None
            audio_rect = None
        
        # Hover effects for instructions
        mouse_pos = pygame.mouse.get_pos()
        # Default: both dim
        quit_col = config.DIM_GREEN
        audio_col = config.DIM_GREEN
        if quit_rect.collidepoint(mouse_pos):
            quit_col = config.BRIGHT_GREEN
        elif audio_rect and audio_rect.collidepoint(mouse_pos):
            audio_col = config.BRIGHT_GREEN

        # Redraw with highlight if hovered
        quit_surface = font_cache['instruction'].render(quit_text, True, quit_col)
        screen.blit(quit_surface, quit_rect)
        if audio_surface and audio_rect:
            audio_surface = font_cache['instruction'].render(audio_text, True, audio_col)
            screen.blit(audio_surface, audio_rect)

        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE)):
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_a:
                if audio: audio.toggle()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                # Check for clicks on instruction text areas
                if audio and audio_rect.collidepoint(mouse_pos):
                    audio.toggle()
                elif quit_rect.collidepoint(mouse_pos):
                    running = False
                last_mouse_move = time.time()
                pygame.mouse.set_visible(True)
            elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
                last_mouse_move = time.time()
                pygame.mouse.set_visible(True)

        # Update display
        pygame.display.flip()
        clock.tick(config.FPS)

    # Shutdown
    tracker.running = False
    if audio and audio.initialised:
        audio.shutdown()

    print("✅ Shutting down...")
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
