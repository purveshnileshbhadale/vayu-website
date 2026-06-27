import sys
from pathlib import Path


APP_NAME = "VAYU"


def _get_script_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    if main_py.exists():
        return f'"{sys.executable}" "{main_py}"'
    return ""


def auto_start_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def set_auto_start(enable: bool) -> str:
    if sys.platform != "win32":
        return "Auto-start is only supported on Windows."

    path = _get_script_path()
    if not path:
        return "Could not determine script path."

    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, path)
            winreg.CloseKey(key)
            return "VAYU will now start automatically on boot."
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            return "VAYU auto-start disabled."
    except Exception as e:
        return f"Failed to set auto-start: {e}"
