import sys
import subprocess
import re
import time
from pathlib import Path


def _ps(cmd: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return str(e)


def wifi_bt_control(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")
    target = params.get("target", "wifi").strip().lower()

    if player:
        player.write_log(f"[WiFi/BT] {action}")

    try:
        if target == "wifi":
            if action in ("list", "scan", "networks"):
                output = _ps(
                    "Get-WmiObject -Class MSFT_NetAdapter -Namespace root/StandardCimv2 "
                    "| Where-Object {$_.Name -like '*Wi-Fi*' -or $_.Name -like '*Wireless*'} "
                    "| Get-NetAdapter | Select-Object -ExpandProperty Name"
                )
                if not output:
                    return "No WiFi adapter found."

                netsh = _ps("netsh wlan show networks mode=Bssid")
                if "timed out" in netsh.lower():
                    return "WiFi scan timed out."
                lines = netsh.split("\n")
                networks = []
                current = {}
                for line in lines:
                    line = line.strip()
                    if line.startswith("SSID"):
                        if current:
                            networks.append(current)
                        current = {"ssid": line.split(":", 1)[1].strip()}
                    elif "Signal" in line and current:
                        current["signal"] = line.split(":", 1)[1].strip()
                    elif "Authentication" in line and current:
                        current["auth"] = line.split(":", 1)[1].strip()
                    elif "Channel" in line and current:
                        current["channel"] = line.split(":", 1)[1].strip()
                if current:
                    networks.append(current)

                if not networks:
                    return "No WiFi networks found."

                result = []
                for n in networks[:20]:
                    sig = n.get("signal", "?")
                    auth = n.get("auth", "?")
                    result.append(f"{n['ssid']} ({sig}) [{auth}]")
                return "\n".join(result)

            elif action in ("status", "state", "info"):
                output = _ps(
                    "(Get-NetAdapter -Name '*Wi-Fi*' -ErrorAction SilentlyContinue).Status"
                )
                if not output:
                    output = _ps(
                        "(Get-NetAdapter -Name '*Wireless*' -ErrorAction SilentlyContinue).Status"
                    )
                current_ssid = _ps(
                    r'(Get-WmiObject -Namespace root\wmi -Class MSNDis_Association).AssociateSSID '
                    "| ForEach-Object {[System.Text.Encoding]::ASCII.GetString($_)}"
                )
                status = output.strip() or "Disconnected"
                ssid = current_ssid.strip() if current_ssid else "Not connected"
                return f"WiFi: {status}\nConnected to: {ssid}"

            elif action in ("on", "enable", "connect"):
                _ps(
                    "Get-NetAdapter -Name '*Wi-Fi*' -ErrorAction SilentlyContinue "
                    "| Enable-NetAdapter -Confirm:$false"
                )
                time.sleep(2)
                ssid = params.get("ssid", "").strip()
                if ssid:
                    password = params.get("password", "").strip()
                    if password:
                        _ps(
                            f'netsh wlan connect name="{ssid}" key="{password}"'
                        )
                    else:
                        _ps(f'netsh wlan connect name="{ssid}"')
                    return f"Connecting to {ssid}..."
                return "WiFi enabled."

            elif action in ("off", "disable", "disconnect"):
                _ps(
                    "Get-NetAdapter -Name '*Wi-Fi*' -ErrorAction SilentlyContinue "
                    "| Disable-NetAdapter -Confirm:$false"
                )
                return "WiFi disabled."

            elif action == "forget":
                ssid = params.get("ssid", "").strip()
                if not ssid:
                    return "SSID is required."
                _ps(f'netsh wlan delete profile name="{ssid}"')
                return f"Forgot network: {ssid}"

            return (
                f"Unknown wifi action: '{action}'. "
                f"Available: list, status, on, off, connect, forget"
            )

        elif target in ("bt", "bluetooth"):
            if action in ("list", "paired", "devices"):
                output = _ps(
                    "Get-WmiObject -Class Win32_PnPEntity | "
                    "Where-Object {$_.PNPClass -eq 'Bluetooth' -or "
                    "$_.Name -like '*Bluetooth*'} | "
                    "Select-Object -ExpandProperty Name"
                )
                if not output:
                    return "No Bluetooth devices found."
                devices = [d.strip() for d in output.split("\n") if d.strip()]
                return "\n".join(devices[:20]) if devices else "No Bluetooth devices."

            elif action in ("on", "enable"):
                _ps(
                    "Get-WmiObject -Class Win32_PnPEntity | "
                    "Where-Object {$_.PNPClass -eq 'Bluetooth'} | "
                    "ForEach-Object { "
                    "$_.PNPDeviceID | Out-File -FilePath $env:TEMP\\bt_id.txt; "
                    "$_ | Enable-PnpDevice -Confirm:$false }"
                )
                return "Bluetooth enabled."

            elif action in ("off", "disable"):
                _ps(
                    "Get-WmiObject -Class Win32_PnPEntity | "
                    "Where-Object {$_.PNPClass -eq 'Bluetooth'} | "
                    "Disable-PnpDevice -Confirm:$false"
                )
                return "Bluetooth disabled."

            elif action == "status":
                output = _ps(
                    "Get-WmiObject -Class Win32_PnPEntity | "
                    "Where-Object {$_.PNPClass -eq 'Bluetooth'} | "
                    "Select-Object Name, Status, ConfigManagerErrorCode"
                )
                return output or "Bluetooth status unavailable."

            return (
                f"Unknown bluetooth action: '{action}'. "
                f"Available: list, status, on, off"
            )

        return f"Unknown target: '{target}'. Use 'wifi' or 'bluetooth'."

    except Exception as e:
        return f"wifi_bt_control failed: {e}"



