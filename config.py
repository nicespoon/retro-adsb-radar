import configparser
import os


def _get_str(section: str, option: str, fallback: str = '') -> str:
	value = config.get(section, option, fallback=fallback)
	return value.strip().strip('"').strip("'")

# Configuration Loading
config = configparser.ConfigParser()
script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.ini")
config.read(config_path)

# General Settings
FETCH_INTERVAL = config.getint('General', 'FETCH_INTERVAL', fallback=10)
MIL_PREFIX_LIST = [prefix.strip() for prefix in _get_str('General', 'MIL_PREFIX_LIST', fallback='7CF').split(',')]
TAR1090_URL = _get_str('General', 'TAR1090_URL', fallback='http://localhost/data/aircraft.json')
BLINK_MILITARY = config.getboolean('General', 'BLINK_MILITARY', fallback=True)

# Audio Settings
ATC_STREAM_URL = _get_str('Audio', 'ATC_STREAM_URL', fallback='')
ATC_AUTO_START = config.getboolean('Audio', 'AUTO_START', fallback=False)
MQTT_BROKER = _get_str('Audio', 'MQTT_BROKER', fallback='')
MQTT_PORT = config.getint('Audio', 'MQTT_PORT', fallback=1883)
MQTT_USER = _get_str('Audio', 'MQTT_USER', fallback='')
MQTT_PASSWORD = _get_str('Audio', 'MQTT_PASSWORD', fallback='')
COMMAND_TOPIC = _get_str('Audio', 'COMMAND_TOPIC', fallback='')
STATE_TOPIC = _get_str('Audio', 'STATE_TOPIC', fallback='')
MQTT_CONFIG = {
	'broker': MQTT_BROKER,
	'port': MQTT_PORT,
	'user': MQTT_USER,
	'password': MQTT_PASSWORD,
	'command_topic': COMMAND_TOPIC,
	'state_topic': STATE_TOPIC,
}

# Location Settings
LAT = config.getfloat('Location', 'LAT', fallback=0.0)
LON = config.getfloat('Location', 'LON', fallback=0.0)
AREA_NAME = _get_str('Location', 'AREA_NAME', fallback='UNKNOWN')
RADIUS_NM = config.getint('Location', 'RADIUS_NM', fallback=60)

# Display Settings
SCREEN_WIDTH = config.getint('Display', 'SCREEN_WIDTH', fallback=960)
SCREEN_HEIGHT = config.getint('Display', 'SCREEN_HEIGHT', fallback=640)
FPS = config.getint('Display', 'FPS', fallback=6)
MAX_TABLE_ROWS = config.getint('Display', 'MAX_TABLE_ROWS', fallback=10)
FONT_PATH = _get_str('Display', 'FONT_PATH', fallback='fonts/TerminusTTF-4.49.3.ttf')
BACKGROUND_PATH = _get_str('Display', 'BACKGROUND_PATH', fallback='')
TRAIL_MIN_LENGTH = config.getint('Display', 'TRAIL_MIN_LENGTH', fallback=8)
TRAIL_MAX_LENGTH = config.getint('Display', 'TRAIL_MAX_LENGTH', fallback=25)
TRAIL_MAX_SPEED = config.getint('Display', 'TRAIL_MAX_SPEED', fallback=500)
HEADER_FONT_SIZE = config.getint('Display', 'HEADER_FONT_SIZE', fallback=32)
RADAR_FONT_SIZE = config.getint('Display', 'RADAR_FONT_SIZE', fallback=28)
TABLE_FONT_SIZE = config.getint('Display', 'TABLE_FONT_SIZE', fallback=28)
INSTRUCTION_FONT_SIZE = config.getint('Display', 'INSTRUCTION_FONT_SIZE', fallback=28)

# Colours
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
BRIGHT_GREEN = (50, 255, 50)
DIM_GREEN = (0, 180, 0)
RED = (255, 50, 50)
YELLOW = (255, 255, 0)
AMBER = (255, 191, 0)
