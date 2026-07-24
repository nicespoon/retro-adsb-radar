import threading
from typing import Optional


class AudioManager:
    """Manages ATC audio either locally via VLC or remotely via MQTT."""

    def __init__(self, stream_url: str = None, mqtt_config: Optional[dict] = None):
        self.stream_url = stream_url
        self.mqtt_config = mqtt_config or {}
        self.backend = None
        self.player = None
        self.instance = None
        self.client = None
        self._mqtt_module = None
        self._mqtt_connected = False
        self._mqtt_muted: Optional[bool] = None
        self._state_lock = threading.Lock()
        self.initialised = False

    def initialise(self) -> bool:
        """Initialise the configured audio backend."""
        if self.initialised:
            return False

        if self._mqtt_enabled():
            return self._initialise_mqtt()

        if self.stream_url:
            return self._initialise_vlc()

        return False

    def _mqtt_enabled(self) -> bool:
        return all(
            [
                self.mqtt_config.get('broker'),
                self.mqtt_config.get('command_topic'),
                self.mqtt_config.get('state_topic'),
            ]
        )

    def _initialise_vlc(self) -> bool:
        try:
            import vlc

            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            media = self.instance.media_new(self.stream_url)
            media.add_option(':network-caching=10000')
            media.add_option(':clock-jitter=0')
            media.add_option(':clock-synchro=0')
            self.player.set_media(media)
            self.backend = 'vlc'
            self.initialised = True
            print("Audio manager initialised successfully (VLC)")
            return True
        except ModuleNotFoundError:
            print("Error: 'python-vlc' not found. Please install it to use the audio feature.")
            return False
        except Exception as e:
            print(f"Error initialising audio. Is the VLC application installed? Details: {e}")
            self.player = None
            self.instance = None
            return False

    def _initialise_mqtt(self) -> bool:
        try:
            import paho.mqtt.client as mqtt
        except ModuleNotFoundError:
            print("Error: 'paho-mqtt' not found. Please install it to use MQTT audio control.")
            return False

        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            print("Error: paho-mqtt v2.0.0+ is required. Please run 'pip install --upgrade paho-mqtt'")
            return False

        try:
            if self.mqtt_config.get('user'):
                self.client.username_pw_set(
                    self.mqtt_config.get('user'),
                    self.mqtt_config.get('password') or None,
                )

            self.client.on_connect = self._on_mqtt_connect
            self.client.on_disconnect = self._on_mqtt_disconnect
            self.client.on_message = self._on_mqtt_message
            self.client.connect_async(self.mqtt_config['broker'], self.mqtt_config['port'], keepalive=60)
            self.client.loop_start()

            self._mqtt_module = mqtt
            self.backend = 'mqtt'
            self.initialised = True
            print("Audio manager initialised successfully (MQTT)")
            return True
        except Exception as e:
            self.client = None
            print(f"Error initialising MQTT audio control: {e}")
            return False

    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        self._mqtt_connected = True
        state_topic = self.mqtt_config.get('state_topic')
        if state_topic:
            client.subscribe(state_topic)
        print(f"MQTT audio control connected to {self.mqtt_config.get('broker')}:{self.mqtt_config.get('port')}")

    def _on_mqtt_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        self._mqtt_connected = False
        print(f"MQTT audio control disconnected: {reason_code}")

    def _on_mqtt_message(self, client, userdata, message):
        try:
            payload = message.payload.decode('utf-8', errors='ignore').strip().upper()
            muted = self._payload_to_bool(payload)
            if muted is None:
                print(f"Ignoring unrecognised MQTT state payload: {payload}")
                return

            with self._state_lock:
                self._mqtt_muted = muted
        except Exception as e:
            print(f"MQTT Message Error: {e}")

    def _payload_to_bool(self, payload: str) -> Optional[bool]:
        if payload in {'ON', 'TRUE', '1', 'MUTED'}:
            return True
        if payload in {'OFF', 'FALSE', '0', 'UNMUTED'}:
            return False
        return None

    def toggle(self):
        """Toggle the configured audio backend."""
        if self.backend == 'mqtt':
            self._toggle_mqtt()
            return

        if not self.player:
            return

        if self.player.is_playing():
            self.player.stop()
            print("Audio stream stopped")
        else:
            self.player.play()
            print("Audio stream started")

    def _toggle_mqtt(self):
        if not self.client or not self._mqtt_module:
            return

        with self._state_lock:
            target_muted = not self._mqtt_muted if self._mqtt_muted is not None else False
            self._mqtt_muted = target_muted

        payload = 'ON' if target_muted else 'OFF'
        result = self.client.publish(self.mqtt_config['command_topic'], payload, qos=1)
        if result.rc != self._mqtt_module.MQTT_ERR_SUCCESS:
            print(f"Failed to publish MQTT audio command: {result.rc}")
            return

        print(f"Remote audio mute {'enabled' if target_muted else 'disabled'}")

    def is_playing(self) -> bool:
        """Return True when audio should be shown as active in the UI."""
        if self.backend == 'mqtt':
            with self._state_lock:
                return self._mqtt_muted is False

        if not self.player:
            return False
        return self.player.is_playing()

    def status_label(self) -> str:
        """Return a short UI label for the current audio state."""
        if self.backend == 'mqtt':
            with self._state_lock:
                if self._mqtt_muted is None:
                    return 'SYNC'
                return 'OFF' if self._mqtt_muted else 'ON'

        return 'ON' if self.is_playing() else 'OFF'

    def shutdown(self):
        """Stop playback and release backend resources cleanly."""
        if self.player:
            self.player.stop()
        if self.instance:
            self.instance.release()
        self.player = None
        self.instance = None

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        self.client = None
        self._mqtt_connected = False

        if self.initialised:
            print("Audio shut down cleanly")

