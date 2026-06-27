import sys
import subprocess
import platform
from pathlib import Path
from datetime import datetime


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


def power_mgmt(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[Power] {action}")

    try:
        if action in ("battery", "battery_status", "power"):
            output = _ps(
                "Get-WmiObject -Class Win32_Battery | "
                "Select-Object EstimatedChargeRemaining, BatteryStatus, "
                "EstimatedRunTime, Chemistry | Format-List"
            )
            if not output or "timed out" in output.lower():
                ac_status = _ps(
                    "(Get-WmiObject -Class Win32_Battery).BatteryStatus"
                )
                if not ac_status.strip():
                    return "No battery found (desktop PC)."
                return f"Battery status: code {ac_status.strip()}"

            lines = output.split("\n")
            info = {}
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()

            pct = info.get("EstimatedChargeRemaining", "?")
            status_map = {"1": "Discharging", "2": "AC Power", "3": "Fully Charged",
                          "4": "Low", "5": "Critical", "6": "Charging",
                          "7": "Charging High", "8": "Charging Low",
                          "9": "Unknown", "10": "Partially Charged"}
            status_code = info.get("BatteryStatus", "?")
            status = status_map.get(status_code, f"Code {status_code}")
            runtime = info.get("EstimatedRunTime", "0")
            chem = info.get("Chemistry", "?")

            result = f"Battery: {pct}% | {status}"
            if runtime and runtime != "0":
                result += f" | {runtime}min remaining"

            ac_online = _ps(
                "(Get-WmiObject -Class Win32_Battery).BatteryStatus -eq 2"
            )
            if "True" in ac_online:
                result += " (plugged in)"

            return result

        elif action in ("sleep", "suspend", "standby"):
            _ps(
                "(Add-Type -AssemblyName System.Windows.Forms) -and "
                "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"
            )
            return "Putting system to sleep..."

        elif action in ("hibernate", "hybrid_sleep"):
            _ps(
                "(Add-Type -AssemblyName System.Windows.Forms) -and "
                "[System.Windows.Forms.Application]::SetSuspendState('Hibernate', $false, $false)"
            )
            return "Hibernating system..."

        elif action in ("power_plan", "plan", "power_scheme"):
            plan = params.get("plan", "").strip().lower()
            if not plan:
                output = _ps("powercfg /GetActiveScheme")
                if ":" in output:
                    current = output.split(":")[-1].strip().split("(")[0].strip()
                    return f"Current power plan: {current}"
                return "Could not determine power plan."

            plan_guid = ""
            if "balanced" in plan or "default" in plan:
                plan_guid = "381b4222-f694-41f0-9685-ff5bb260df2f"
            elif "high" in plan or "performance" in plan or "max" in plan:
                plan_guid = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
            elif "power" in plan or "saver" in plan or "low" in plan or "eco" in plan:
                plan_guid = "a1841308-3541-4fab-bc81-f71556f20b4a"
            elif "ultimate" in plan:
                plan_guid = "e9a42b02-d5df-448d-aa00-03f14749eb61"
            else:
                return f"Unknown power plan: '{plan}'. Use: balanced, high_performance, power_saver, ultimate"

            _ps(f"powercfg /SetActive {plan_guid}")
            return f"Power plan set to: {plan}"

        elif action in ("screen_off", "display_off"):
            _ps(
                "(Add-Type -AssemblyName System.Windows.Forms) -and "
                "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $true)"
            )
            return "Turning off display..."

        return (
            f"Unknown action: '{action}'. "
            f"Available: battery, sleep, hibernate, power_plan, screen_off"
        )

    except Exception as e:
        return f"power_mgmt failed: {e}"
