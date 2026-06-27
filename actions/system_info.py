import subprocess
import platform
import socket
import datetime
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _bytes_to_gb(b: int) -> str:
    return f"{b / (1024**3):.1f} GB"


def system_info(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "datetime").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[Info] {action}")

    try:
        if action in ("time", "datetime", "date"):
            now = datetime.datetime.now()
            if action == "time":
                return f"The time is {now.strftime('%I:%M %p').lstrip('0')}."
            if action == "date":
                return f"Today is {now.strftime('%A, %B %d, %Y')}."
            return f"It is {now.strftime('%A, %B %d, %Y — %I:%M %p')}."

        if action in ("uptime", "system_uptime"):
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"],
                    capture_output=True, text=True, timeout=10
                )
                boot_str = result.stdout.strip()
                if boot_str:
                    boot = datetime.datetime.strptime(boot_str.split(".")[0],
                                                      "%Y%m%d%H%M%S")
                    uptime = datetime.datetime.now() - boot
                    days = uptime.days
                    hours = uptime.seconds // 3600
                    mins = (uptime.seconds // 60) % 60
                    return f"System uptime: {days}d {hours}h {mins}m."
            return "Uptime info not available."

        if action in ("os", "os_info"):
            os_name = platform.system()
            os_ver = platform.version()
            return f"Running {os_name} (build {os_ver})."

        if action in ("ip", "ip_address", "network"):
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return f"Hostname: {hostname}, Local IP: {local_ip}."

        if action in ("location", "geo"):
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Invoke-WebRequest -Uri 'https://ipapi.co/json/' -TimeoutSec 5).Content "
                     "| ConvertFrom-Json | Select-Object city,region,country,ip"],
                    capture_output=True, text=True, timeout=10
                )
                data = result.stdout.strip()
                if data:
                    return f"Location: {data}"
            except Exception:
                pass
            return "Could not determine location."

        if action in ("cpu", "cpu_usage"):
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average "
                     "| Select-Object -ExpandProperty Average"],
                    capture_output=True, text=True, timeout=10
                )
                cpu = result.stdout.strip()
                return f"CPU usage: {cpu}%" if cpu else "CPU info not available."
            return "CPU info only available on Windows."

        if action in ("ram", "memory"):
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_OperatingSystem | "
                     "Select-Object @{N='Total';E={[math]::Round($_.TotalVisibleMemorySize/1MB,1)}},"
                     "@{N='Free';E={[math]::Round($_.FreePhysicalMemory/1MB,1)}}"],
                    capture_output=True, text=True, timeout=10
                )
                ram = result.stdout.strip()
                return f"RAM: {ram}" if ram else "RAM info not available."
            return "RAM info only available on Windows."

        if action == "all":
            parts = []
            now = datetime.datetime.now()
            parts.append(now.strftime("%A, %B %d, %Y — %I:%M %p"))
            parts.append(f"OS: {platform.system()} {platform.release()}")
            try:
                hostname = socket.gethostname()
                parts.append(f"Host: {hostname} ({socket.gethostbyname(hostname)})")
            except Exception:
                pass
            return "\n".join(parts)

        return (
            f"Unknown info action: '{action}'. "
            f"Available: time, date, datetime, uptime, os, ip, location, cpu, ram, all"
        )

    except Exception as e:
        return f"system_info failed: {e}"
