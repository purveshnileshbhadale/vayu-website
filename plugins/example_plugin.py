"""Example plugin — system info as a plugin."""

import platform
import socket
import datetime


def register():
    return {
        "name": "plugin_sysinfo",
        "description": (
            "Quick system info from the plugin system: "
            "OS, hostname, IP, current time. "
            "Alternative to system_info tool."
        ),
        "parameters": {
            "info": {
                "type": "STRING",
                "description": "What to show: all | os | network | time (default: all)",
            }
        },
        "handler": _handle,
    }


def _handle(params: dict, player=None) -> str:
    info = params.get("info", "all").strip().lower()
    parts = []

    if info in ("all", "os"):
        parts.append(f"OS: {platform.system()} {platform.release()}")

    if info in ("all", "network"):
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            parts.append(f"Host: {hostname} ({ip})")
        except Exception:
            parts.append("Host: unknown")

    if info in ("all", "time"):
        now = datetime.datetime.now()
        parts.append(now.strftime("%A, %B %d — %I:%M %p"))

    return "\n".join(parts) if parts else "No info selected."
