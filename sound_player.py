import os
import array
import wave
import random
import ctypes
from ctypes import wintypes
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

# ---------- low-latency PCM playback (waveOut) ----------
# MCI "mpegvideo" goes through DirectShow and adds a noticeable delay between click and sound.
# waveOut plays PCM straight from memory with far less latency, so it is used for every .wav it can read.
WAVE_MAPPER = 0xFFFFFFFF
CALLBACK_NULL = 0
VOICES_PER_FORMAT = 6  # round-robin voices so rapid cracks overlap instead of cutting each other off

class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD),
                ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]

class WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD), ("dwBytesRecorded", wintypes.DWORD),
                ("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]

HWAVEOUT = ctypes.c_void_p
winmm.waveOutOpen.argtypes = [ctypes.POINTER(HWAVEOUT), wintypes.UINT, ctypes.POINTER(WAVEFORMATEX),
                              ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
for _fn in ("waveOutPrepareHeader", "waveOutUnprepareHeader", "waveOutWrite"):
    getattr(winmm, _fn).argtypes = [HWAVEOUT, ctypes.POINTER(WAVEHDR), wintypes.UINT]
winmm.waveOutReset.argtypes = [HWAVEOUT]
winmm.waveOutClose.argtypes = [HWAVEOUT]
winmm.waveOutSetVolume.argtypes = [HWAVEOUT, wintypes.DWORD]

class PcmClip:
    """A whole .wav file decoded into memory, leading silence trimmed (silence = extra delay after the click)"""
    def __init__(self, path):
        with wave.open(path, "rb") as w:
            self.channels, self.width, self.rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            frames = w.readframes(w.getnframes())
        if self.width != 2:
            raise ValueError("only 16-bit PCM")
        samples = array.array("h", frames)
        peak = max((abs(x) for x in samples), default=0)
        start = next((i for i, x in enumerate(samples) if abs(x) > peak * 0.02), 0)
        start -= start % self.channels
        self.buffer = ctypes.create_string_buffer(samples[start:].tobytes())
        self.length = len(self.buffer) - 1  # create_string_buffer adds a trailing NUL
        self.format_key = (self.channels, self.rate)

class WaveVoices:
    """A few open waveOut devices for one PCM format, used round-robin"""
    def __init__(self, channels, rate):
        fmt = WAVEFORMATEX(1, channels, rate, rate * channels * 2, channels * 2, 16, 0)
        self.handles, self.headers = [], []
        for _ in range(VOICES_PER_FORMAT):
            h = HWAVEOUT()
            if winmm.waveOutOpen(ctypes.byref(h), WAVE_MAPPER, ctypes.byref(fmt), 0, 0, CALLBACK_NULL) == 0:
                self.handles.append(h)
                self.headers.append(None)
        self.index = 0

    @property
    def ok(self):
        return bool(self.handles)

    def play(self, clip, volume):
        i = self.index
        self.index = (i + 1) % len(self.handles)
        h = self.handles[i]
        winmm.waveOutReset(h)  # stop whatever this voice was still playing
        if self.headers[i] is not None:
            winmm.waveOutUnprepareHeader(h, ctypes.byref(self.headers[i]), ctypes.sizeof(WAVEHDR))
        hdr = WAVEHDR()
        hdr.lpData = ctypes.cast(clip.buffer, ctypes.c_void_p)
        hdr.dwBufferLength = clip.length
        self.headers[i] = hdr  # must stay alive while the device uses it
        level = int(max(0.0, min(1.0, volume)) * 0xFFFF)
        winmm.waveOutSetVolume(h, level | (level << 16))
        if winmm.waveOutPrepareHeader(h, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR)) != 0:
            return False
        return winmm.waveOutWrite(h, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR)) == 0

    def close(self):
        for h, hdr in zip(self.handles, self.headers):
            winmm.waveOutReset(h)
            if hdr is not None:
                winmm.waveOutUnprepareHeader(h, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            winmm.waveOutClose(h)
        self.handles, self.headers = [], []

class SoundPlayer:
    def __init__(self):
        self.pools = {}
        self.clips = {}         # path -> PcmClip, or None when the file can't go through waveOut
        self.voices = {}        # (channels, rate) -> WaveVoices
        self.asset_paths = {}   # filename -> resolved path (avoids disk checks on every click)
        self.custom_sounds = []
        self.custom_mtime = None

    def get_sound_path(self, filename):
        path = self.asset_paths.get(filename)
        if path is None:
            path = get_asset_path(os.path.join("assets", "sounds", filename))
            if os.path.exists(path):
                self.asset_paths[filename] = path
        return path

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
        if sound_mode == "tom_combo":
            sound_path = self.get_sound_path("whip_tom_combo.wav")
        elif sound_mode == "tom_only":
            sound_path = self.get_sound_path("tom_scream.wav")
        elif sound_mode == "random":
            opts = [self.get_sound_path(f"whip_{s}.wav") for s in ("comic", "cyber", "classic", "taser", "sword")]
            opts += [self.get_sound_path("whip_tom_combo.wav"), self.get_sound_path("tom_scream.wav")]
            valid_opts = [o for o in opts if os.path.exists(o)]
            sound_path = random.choice(valid_opts) if valid_opts else None
        else: # "themed"
            sound_path = self.get_sound_path(f"whip_{style}.wav")
            if not os.path.exists(sound_path):
                if style == "taser":
                    sound_path = self.get_sound_path("whip_cyber.wav")
                elif style == "sword":
                    sound_path = self.get_sound_path("whip_classic.wav")

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

    def get_clip(self, path):
        if path not in self.clips:
            clip = None
            if path.lower().endswith(".wav"):
                try:
                    clip = PcmClip(path)
                    if clip.format_key not in self.voices:
                        self.voices[clip.format_key] = WaveVoices(*clip.format_key)
                    if not self.voices[clip.format_key].ok:
                        clip = None
                except Exception as e:
                    print(f"waveOut cannot play {path}, using MCI: {e}")
                    clip = None
            self.clips[path] = clip
        return self.clips[path]

    def preload(self):
        """Decodes the sounds up front so the first click has no loading delay"""
        for style in ("comic", "cyber", "classic", "taser", "sword"):
            path = self.pick_sound(style)
            if path and self.get_clip(path) is None:
                self.get_pool(path)

    def play_crack(self, style=None):
        if config.get("office_mode", False) or not config.get("sound_enabled", True):
            return

        if style is None:
            style = config.get("whip_style", "comic")

        sound_path = self.pick_sound(style)
        if not sound_path:
            return

        try:
            clip = self.get_clip(sound_path)
            if clip is not None and self.voices[clip.format_key].play(clip, config.get("volume", 1.0)):
                return
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
        for voices in self.voices.values():
            voices.close()
        self.voices.clear()
        self.clips.clear()

sound_player = SoundPlayer()
