# Retro ADS-B Radar ✈

Aircraft radar display built with Python and Pygame. Visualises real-time aircraft positions and metadata from a local tar1090 server, with a retro interface.

![Retro ADS-B Radar Screenshot](images/screenshot.png)

## Features
- Real-time radar visualisation of aircraft within a configurable radius
- Military aircraft detection with configurable hex code prefixes and blinking effect
- Configurable font sizes and display settings
- Tabular display of aircraft data (callsign, altitude, speed, distance, track)
- Retro colour palette
- Terminus TTF fonts for an authentic look
- Default configuration is compatible with the [Hagibis Mini PC USB-C Hub](https://hagibis.com/products-p00288p1.html)

![Retro ADS-B Radar Running on Hagibis Mini PC USB-C Hub](images/hagibis_display.jpg)

## Quick Start

1. **Hardware setup:**
   - Connect your ADS-B USB dongle (e.g. RTL-SDR) to a Raspberry Pi or similar single-board computer.
   - Attach a suitable 1090 MHz antenna to the dongle.
   - Ensure the dongle is running software that provides ADS-B data in JSON format, such as [tar1090](https://github.com/wiedehopf/tar1090).
   - Connect your Raspberry Pi to your display, such as the Hagibis Mini PC USB-C Hub, with an HDMI cable.

2. **Software setup:**
   - Clone the repository:
     ```
     git clone https://github.com/nicespoon/retro-adsb-radar.git
     cd retro-adsb-radar
     ```
   - Install dependencies:
     ```
     pip install -r requirements.txt
     ```
   - Configure the application:
     - Copy `config.ini.example` to `config.ini`.
     - Edit `config.ini` to set the `TAR1090URL` to your tar1090 data source URL (default: `http://localhost/data/aircraft.json`).
     - Adjust location and display settings as needed.

3. **Run the radar UI:**
   ```bash
   python3 radar.py
   ```
   *Note:* On some systems, you may need to use `python` instead of `python3`.
5. **Quit:** Press `Q` or `ESC` in the radar window.

## Configuration
The application is configured via `config.ini`. Copy `config.ini.example` to `config.ini` and adjust as needed:

```ini
[General]
FETCH_INTERVAL = 10                # Data fetch interval (seconds)
MIL_PREFIX_LIST = 7CF              # Comma-separated list of military aircraft hex prefixes (e.g. 7CF,AE,43C)
TAR1090_URL = http://localhost/tar1090/data/aircraft.json  # tar1090 data source URL
BLINK_MILITARY = true              # Toggle blinking effect for military aircraft (true/false)

[Location]
LAT = -31.9522                     # Radar centre latitude
LON = 115.8614                     # Radar centre longitude
AREA_NAME = PERTH                  # Displayed area name
RADIUS_NM = 60                     # Radar range (nautical miles)

[Display]
SCREEN_WIDTH = 960                 # Window width (pixels)
SCREEN_HEIGHT = 640                # Window height (pixels)
FPS = 6                            # Frames per second
MAX_TABLE_ROWS = 10                # Maximum number of aircraft to show in the table
FONT_PATH = fonts/TerminusTTF-4.49.3.ttf  # Path to TTF font
BACKGROUND_PATH =                  # Optional path to background image
HEADER_FONT_SIZE = 32              # Font size for the header text
RADAR_FONT_SIZE = 22              # Font size for radar labels and callsigns
TABLE_FONT_SIZE = 22              # Font size for the data table
INSTRUCTION_FONT_SIZE = 12         # Font size for instruction text
```

### Key Configuration Options

- **Military Aircraft Detection**
  - `MIL_PREFIX_LIST`: Comma-separated list of hex code prefixes. Example: `7CF,AE,43C` will highlight aircraft whose hex codes start with any of these prefixes.
  - `BLINK_MILITARY`: Set to `false` to show military aircraft in solid red without blinking.

- **Display Customization**
  - `SCREEN_WIDTH` and `SCREEN_HEIGHT`: Default 960x640 recommended for best display.
  - Font sizes can be adjusted individually with `HEADER_FONT_SIZE`, `RADAR_FONT_SIZE`, `TABLE_FONT_SIZE`, and `INSTRUCTION_FONT_SIZE`.
  - `MAX_TABLE_ROWS`: Controls how many aircraft are shown in the data table.
  - `BACKGROUND_PATH`: Optional path to a background image. The image will be scaled to match the display resolution.

- **Data Source**
  - `TAR1090_URL`: URL of your tar1090 instance. Default is `http://localhost/tar1090/data/aircraft.json`.
  - `FETCH_INTERVAL`: How often to update aircraft data (in seconds).

## License
- The project code is licensed under the MIT License (see `LICENSE`).
- Fonts used in this project are licensed under the SIL Open Font License Version 1.1.  
  See font license files in the `fonts/` directory for details.
