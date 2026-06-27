import sys
import time
from pathlib import Path

try:
    import win32gui
    import win32con
    import win32api
    import win32process
    _WIN32 = True
except ImportError:
    _WIN32 = False


def window_manager(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if not _WIN32:
        return "pywin32 not installed. Run: pip install pywin32"

    if player:
        player.write_log(f"[Window] {action}")

    try:
        if action == "list":
            windows = []
            top_windows = []

            def enum_cb(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd)
                if not title or len(title) < 2:
                    return
                rect = win32gui.GetWindowRect(hwnd)
                tid, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    exe = win32process.GetModuleFileNameEx(win32api.GetCurrentProcess(), pid)
                    exe_name = Path(exe).name if exe else "?"
                except Exception:
                    exe_name = "?"
                windows.append(f"{title} | PID:{pid} | {exe_name} | rect:{rect}")

            win32gui.EnumWindows(enum_cb, None)
            if not windows:
                return "No visible windows found."

            lines = windows[:30]
            result = "\n".join(lines)
            if len(windows) > 30:
                result += f"\n... and {len(windows) - 30} more"
            return result

        elif action == "focus":
            title = params.get("title", "").strip()
            if not title:
                return "Window title is required."
            hwnd = win32gui.FindWindow(None, title)
            if not hwnd:
                def find_cb(hwnd, data):
                    t = win32gui.GetWindowText(hwnd)
                    if title.lower() in t.lower() and win32gui.IsWindowVisible(hwnd):
                        data.append(hwnd)
                matches = []
                win32gui.EnumWindows(find_cb, matches)
                hwnd = matches[0] if matches else None
            if not hwnd:
                return f"Window not found: {title}"
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return f"Focused: {win32gui.GetWindowText(hwnd)[:80]}"

        elif action == "minimize":
            title = params.get("title", "").strip()
            if title:
                hwnd = _find_window(title)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    return f"Minimized: {title}"
                return f"Window not found: {title}"
            win32gui.ShowWindow(win32gui.GetForegroundWindow(), win32con.SW_MINIMIZE)
            return "Minimized active window."

        elif action == "maximize":
            title = params.get("title", "").strip()
            if title:
                hwnd = _find_window(title)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                    return f"Maximized: {title}"
                return f"Window not found: {title}"
            win32gui.ShowWindow(win32gui.GetForegroundWindow(), win32con.SW_MAXIMIZE)
            return "Maximized active window."

        elif action == "restore":
            title = params.get("title", "").strip()
            if title:
                hwnd = _find_window(title)
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    return f"Restored: {title}"
                return f"Window not found: {title}"
            win32gui.ShowWindow(win32gui.GetForegroundWindow(), win32con.SW_RESTORE)
            return "Restored active window."

        elif action in ("move", "resize", "move_resize"):
            title = params.get("title", "").strip()
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            w = int(params.get("width", 800))
            h = int(params.get("height", 600))

            if title:
                hwnd = _find_window(title)
                if not hwnd:
                    return f"Window not found: {title}"
            else:
                hwnd = win32gui.GetForegroundWindow()

            win32gui.SetWindowPos(hwnd, 0, x, y, w, h,
                                  win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW)
            return f"Moved/resized window to ({x},{y}) {w}x{h}."

        elif action == "close":
            title = params.get("title", "").strip()
            if title:
                hwnd = _find_window(title)
                if hwnd:
                    win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    return f"Closed: {title}"
                return f"Window not found: {title}"
            win32gui.SendMessage(win32gui.GetForegroundWindow(), win32con.WM_CLOSE, 0, 0)
            return "Closed active window."

        elif action == "active":
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return f"Active window: {title} | PID: {pid} | rect: {rect}"

        return (
            f"Unknown action: '{action}'. "
            f"Available: list, focus, minimize, maximize, restore, move, resize, close, active"
        )

    except Exception as e:
        return f"window_manager failed: {e}"


def _find_window(title: str):
    hwnd = win32gui.FindWindow(None, title)
    if hwnd:
        return hwnd

    def find_cb(hwnd, data):
        t = win32gui.GetWindowText(hwnd)
        if title.lower() in t.lower() and win32gui.IsWindowVisible(hwnd):
            data.append(hwnd)

    matches = []
    win32gui.EnumWindows(find_cb, matches)
    return matches[0] if matches else None
