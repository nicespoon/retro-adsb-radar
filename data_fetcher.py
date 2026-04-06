import requests
import threading
import time
from typing import List

import config
from data_models import Aircraft

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
            print(f"Fetching aircraft data from {config.TAR1090_URL}...")
            response = requests.get(config.TAR1090_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            aircraft_list = []
            for ac_data in data.get('aircraft', []):
                ac = Aircraft.from_dict(ac_data)
                if ac:
                    aircraft_list.append(ac)
            print(f"Found {len(aircraft_list)} aircraft within {config.RADIUS_NM}NM range")
            return aircraft_list
        except requests.RequestException as e:
            print(f"Error: Couldn't fetch aircraft data: {e}")
            return []

    def update_loop(self):
        """Background thread to fetch data periodically"""
        while self.running:
            self.status = "SCANNING"
            self.last_update = time.time()
            self.aircraft = self.fetch_data()
            self.status = "ACTIVE" if self.aircraft else "NO CONTACTS"
            time.sleep(config.FETCH_INTERVAL)

    def start(self):
        """Start the background data fetching"""
        thread = threading.Thread(target=self.update_loop, daemon=True)
        thread.start()
