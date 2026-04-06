class AudioManager:
    """Manages ATC audio stream playback using a single, persistent VLC instance."""
    def __init__(self, stream_url: str = None):
        self.stream_url = stream_url
        self.player = None
        self.instance = None
        self.initialised = False

    def initialise(self) -> bool:
        """
        Initialises the VLC instance and loads the stream.
        The 'vlc' module is imported here to make it an optional dependency.
        """
        if self.initialised:
            return False  # Already initialised, no need to reinitialise
    
        if not self.stream_url:
            return False  # Can't initialise without a stream URL

        try:
            import vlc

            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            media = self.instance.media_new(self.stream_url)
            media.add_option(':network-caching=10000')
            media.add_option(':clock-jitter=0')
            media.add_option(':clock-synchro=0')
            self.player.set_media(media)
            self.initialised = True
            print("Audio manager initialised successfully")
            return True
        except ModuleNotFoundError:
            print("Error: 'python-vlc' not found. Please install it to use the audio feature.")
            return False
        except Exception as e:
            print(f"Error initialising audio. Is the VLC application installed? Details: {e}")
            self.player = None
            self.instance = None
            return False

    def toggle(self):
        """Toggles the audio stream on or off."""
        if not self.player:
            return

        if self.player.is_playing():
            self.player.stop()
            print("Audio stream stopped")
        else:
            self.player.play()
            print("Audio stream started")

    def is_playing(self) -> bool:
        """Returns True if the audio stream is currently playing."""
        if not self.player:
            return False
        return self.player.is_playing()

    def shutdown(self):
        """Stops playback and releases VLC resources cleanly."""
        if self.player:
            self.player.stop()
        if self.instance:
            self.instance.release()
        self.player = None
        self.instance = None

        if self.initialised:
            print("Audio shut down cleanly")

