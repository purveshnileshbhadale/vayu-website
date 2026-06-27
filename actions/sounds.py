import sys
import threading
import time

_SOUND_ENABLED = True


def set_sound_enabled(enabled: bool):
    global _SOUND_ENABLED
    _SOUND_ENABLED = enabled


def is_sound_enabled() -> bool:
    return _SOUND_ENABLED


def _beep(freq: int, duration: int):
    if not _SOUND_ENABLED:
        return
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(freq, duration)
        else:
            print("\a", end="", flush=True)
    except Exception:
        pass


def play_startup():
    threading.Thread(target=lambda: (_beep(880, 100), time.sleep(0.08), _beep(1320, 150)), daemon=True).start()


def play_listening():
    threading.Thread(target=lambda: _beep(660, 60), daemon=True).start()


def play_done():
    threading.Thread(target=lambda: (_beep(880, 80), time.sleep(0.06), _beep(1100, 100)), daemon=True).start()


def play_error():
    threading.Thread(target=lambda: (_beep(220, 200), time.sleep(0.1), _beep(180, 300)), daemon=True).start()


def play_mute():
    threading.Thread(target=lambda: _beep(440, 50), daemon=True).start()


def play_unmute():
    threading.Thread(target=lambda: (_beep(660, 50), time.sleep(0.05), _beep(880, 50)), daemon=True).start()
