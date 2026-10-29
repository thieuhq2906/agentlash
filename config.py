import os
import sys
import json

CONFIG_FILE = "config.json"
APP_NAME = "AgentLash"

DEFAULT_CONFIG = {
    "whip_style": "comic",          # "comic", "cyber", "classic"
    "sound_mode": "themed",         # "themed" (matching the weapon), "tom_combo", "tom_only", "random"
    "show_cursor_whip": True,       # Whip handle and tail following mouse
    "whip_animation": True,         # Whip strike slash wave
    "pow_animation": True,          # Comic POW! explosion popup
    "sound_enabled": True,          # Whip crack sound effect
    "volume": 1.0,                  # Volume factor (0.0 to 1.0)
    "custom_animation_enabled": True,# Check and use assets/custom_animation/
    "strike_speed_ms": 90,          # Time from click until the whip tip cracks (ms)
    "active": True,                 # Master toggle
    "office_mode": False,           # Chế độ Văn Phòng Yên Tĩnh: thu nhỏ = chuột, tắt tiếng
    "security_twist_enabled": True, # Security edition: show the awareness screen after N minutes of use
    "twist_minutes": 10,            # Minutes of active use before the awareness screen appears
    "config_version": 2             # 2: strike_speed_ms became click->crack delay (old default 180-220 felt laggy)
}
CONFIG_VERSION = 2

VALID_CHOICES = {
    "whip_style": ("comic", "cyber", "classic", "taser", "sword"),
    "sound_mode": ("themed", "tom_combo", "tom_only", "random"),
}

def get_base_dir():
    """Returns the directory of the running script or exe"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_bundle_dir():
    """Returns PyInstaller extraction temp dir (_MEIPASS) or script dir"""
    if hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS")
    return get_base_dir()

def get_asset_path(relative_path):
    """
    Looks for the asset first next to the .exe (user-override),
    then inside the bundled PyInstaller temp folder,
    then fallback.
    """
    # 1. External path next to .exe
    external = os.path.join(get_base_dir(), relative_path)
    if os.path.exists(external):
        return external

    # 2. Bundled internal path
    bundled = os.path.join(get_bundle_dir(), relative_path)
    if os.path.exists(bundled):
        return bundled

    return external

def _is_writable_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False

def get_data_dir():
    """Folder for config/log: next to the exe, or %APPDATA% when that is read-only (e.g. Program Files)"""
    base = get_base_dir()
    if _is_writable_dir(base):
        return base
    appdata = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
    os.makedirs(appdata, exist_ok=True)
    return appdata

def _sanitize(key, value):
    """Returns value if it has the same type as the default, otherwise None"""
    default = DEFAULT_CONFIG[key]
    if isinstance(default, bool):
        return value if isinstance(value, bool) else None
    if isinstance(default, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if key == "volume":
            return max(0.0, min(1.0, float(value)))
        if key == "strike_speed_ms":
            return int(max(40, min(1000, value)))
        return value
    if key in VALID_CHOICES:
        return value if value in VALID_CHOICES[key] else None
    return value if isinstance(value, type(default)) else None

class Config:
    def __init__(self):
        self.config_path = os.path.join(get_data_dir(), CONFIG_FILE)
        self.data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    if loaded.get("config_version", 1) < CONFIG_VERSION:
                        # Older configs only carry the old default strike speed: switch them to the new fast default
                        loaded.pop("strike_speed_ms", None)
                        loaded["config_version"] = CONFIG_VERSION
                    for key, value in loaded.items():
                        if key in DEFAULT_CONFIG:
                            value = _sanitize(key, value)
                            if value is not None:
                                self.data[key] = value
            except Exception as e:
                print(f"Error loading {self.config_path}: {e}")
        self.save()

    def save(self):
        tmp_path = self.config_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            os.replace(tmp_path, self.config_path)
        except Exception as e:
            print(f"Error saving {self.config_path}: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self.save()

config = Config()
