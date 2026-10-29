import os
import random
import ctypes
from config import config, get_asset_path, get_base_dir

SND_ASYNC = 0x0001
SND_NODEFAULT = 0x0002
SND_FILENAME = 0x00020000

SOUND_EXTS = (".wav", ".mp3")
CHANNELS_PER_SOUND = 4  # Round-robin MCI devices so rapid clicks overlap instead of cutting each other off

winmm = ctypes.windll.winmm

def mci(command):
    """Sends an MCI command string, returns 0 on success or the MCI error code"""
    return winmm.mciSendStringW(command, None, 0, None)

class SoundChannelPool:
    """A few pre-opened MCI devices for one file, played round-robin"""
    _next_id = 0

    def __init__(self, path):
        self.path = path
        self.aliases = []
        self.index = 0
        self.volume = None
        for _ in range(CHANNELS_PER_SOUND):
            SoundChannelPool._next_id += 1
            alias = f"roida_snd{SoundChannelPool._next_id}"
            if mci(f'open "{path}" type mpegvideo alias {alias}') == 0:
                self.aliases.append(alias)
            else:
                break

    @property
    def ok(self):
        return bool(self.aliases)

    def play(self, volume):
        alias = self.aliases[self.index]
        self.index = (self.index + 1) % len(self.aliases)
        level = int(max(0.0, min(1.0, volume)) * 1000)
        mci(f"setaudio {alias} volume to {level}")
        return mci(f"play {alias} from 0") == 0

    def close(self):
        for alias in self.aliases:
            mci(f"close {alias}")
        self.aliases = []

class SoundPlayer:
    def __init__(self):
        self.pools = {}
        self.custom_sounds = []
        self.custom_mtime = None

    def get_sound_path(self, filename):
        return get_asset_path(os.path.join("assets", "sounds", filename))

    def custom_sounds_dir(self):
        return os.path.join(get_base_dir(), "assets", "custom_sounds")

    def refresh_custom_sounds(self):
        """Re-scans assets/custom_sounds/ only when the folder changed"""
        folder = self.custom_sounds_dir()
        try:
            mtime = os.stat(folder).st_mtime
        except OSError:
            self.custom_sounds = []
            self.custom_mtime = None
            return
        if mtime == self.custom_mtime:
            return
        self.custom_mtime = mtime
        self.custom_sounds = sorted(
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in SOUND_EXTS
        )

    def pick_sound(self, style):
        # 1. Custom user override: any .wav/.mp3 in assets/custom_sounds/ (or legacy assets/sounds/custom.wav)
        self.refresh_custom_sounds()
        if self.custom_sounds:
            return random.choice(self.custom_sounds)
        legacy_custom = self.get_sound_path("custom.wav")
        if os.path.exists(legacy_custom):
            return legacy_custom

        sound_mode = config.get("sound_mode", "themed")
        if sound_mode == "random":
            opts = [self.get_sound_path(f"whip_{s}.wav") for s in ("comic", "cyber", "classic")]
            valid_opts = [o for o in opts if os.path.exists(o)]
            sound_path = random.choice(valid_opts) if valid_opts else None
        else: # "themed"
            sound_path = self.get_sound_path(f"whip_{style}.wav")

        # Fallback
        if not sound_path or not os.path.exists(sound_path):
            sound_path = self.get_sound_path("whip_comic.wav")
        return sound_path if os.path.exists(sound_path) else None

    def get_pool(self, path):
        pool = self.pools.get(path)
        if pool is None:
            pool = SoundChannelPool(path)
            self.pools[path] = pool
        return pool

    def preload(self):
        """Opens the default sounds up front so the first click has no loading delay"""
        for style in ("comic", "cyber", "classic"):
            path = self.pick_sound(style)
            if path:
                self.get_pool(path)

    def play_crack(self, style=None):
        if not config.get("sound_enabled", True):
            return

        if style is None:
            style = config.get("whip_style", "comic")

        sound_path = self.pick_sound(style)
        if not sound_path:
            return

        try:
            pool = self.get_pool(sound_path)
            if pool.ok and pool.play(config.get("volume", 1.0)):
                return
            # MCI unavailable for this file: fall back to PlaySound (no overlap, no volume)
            winmm.PlaySoundW(sound_path, None, SND_FILENAME | SND_ASYNC | SND_NODEFAULT)
        except Exception as e:
            print(f"Error playing sound: {e}")

    def close(self):
        for pool in self.pools.values():
            pool.close()
        self.pools.clear()

sound_player = SoundPlayer()
