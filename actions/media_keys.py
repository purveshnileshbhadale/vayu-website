import subprocess
import sys
import platform
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

_OS = platform.system()


def media_keys(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if not _PYAUTOGUI:
        return "pyautogui is not installed. Run: pip install pyautogui"

    if player:
        player.write_log(f"[Media] {action}")

    try:
        if action in ("play", "pause", "play_pause", "toggle"):
            pyautogui.press("playpause")
            return "Toggled play/pause."

        if action in ("next", "next_track", "skip"):
            pyautogui.press("nexttrack")
            return "Skipped to next track."

        if action in ("prev", "previous", "previous_track"):
            pyautogui.press("prevtrack")
            return "Went to previous track."

        if action == "stop":
            pyautogui.press("stop")
            return "Stopped playback."

        if action in ("volume_up", "vol_up"):
            pyautogui.press("volumeup")
            return "Volume up."

        if action in ("volume_down", "vol_down"):
            pyautogui.press("volumedown")
            return "Volume down."

        if action in ("mute", "volume_mute", "toggle_mute"):
            pyautogui.press("volumemute")
            return "Toggled mute."

        return (
            f"Unknown media action: '{action}'. "
            f"Available: play, pause, next, prev, stop, volume_up, volume_down, mute"
        )

    except Exception as e:
        return f"media_keys failed: {e}"
