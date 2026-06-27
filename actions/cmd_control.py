import subprocess
import sys
import time
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def cmd_control(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "run").strip().lower()
    command = params.get("command", "").strip()
    shell = params.get("shell", "powershell").strip().lower()

    if not command and action == "run":
        return "No command provided."

    if player:
        player.write_log(f"[CMD] {action}  {command[:80]}")

    try:
        if action == "run":
            if shell == "cmd":
                proc = subprocess.run(
                    ["cmd", "/c", command],
                    capture_output=True, text=True, timeout=30
                )
            elif shell == "powershell_admin":
                ps_script = (
                    f'Start-Process powershell -Verb RunAs -ArgumentList '
                    f'"-NoProfile -Command {command.replace(chr(34), chr(39))}"'
                )
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True, text=True, timeout=15
                )
                return f"Admin command launched: {command[:100]}"
            else:
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    capture_output=True, text=True, timeout=30
                )

            output = (proc.stdout + proc.stderr).strip()
            if len(output) > 500:
                output = output[:500] + "\n...(truncated)"
            return output or f"Command completed (no output): {command[:80]}"

        elif action == "run_as_admin":
            script = (
                f'Start-Process -FilePath "{command.split()[0]}" '
                f'-Verb RunAs -ArgumentList "{chr(34)}{chr(34).join(command.split()[1:])}{chr(34)}"'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True, timeout=15
            )
            return f"Launched as admin: {command[:100]}"

        elif action == "python":
            proc = subprocess.run(
                [sys.executable, "-c", command],
                capture_output=True, text=True, timeout=30
            )
            output = (proc.stdout + proc.stderr).strip()
            return output or "Python executed."

        elif action == "list_processes":
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Select-Object -First 20 Name,CPU,PM | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=15
            )
            return proc.stdout.strip() or proc.stderr.strip()

        elif action == "kill_process":
            name = params.get("process_name", "").strip()
            if not name:
                return "No process name provided."
            proc = subprocess.run(
                ["taskkill", "/F", "/IM", name],
                capture_output=True, text=True, timeout=10
            )
            return proc.stdout.strip() or f"Killed: {name}"

        elif action == "system_info":
            info = []
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-ComputerInfo | Select-Object WindowsVersion,OsArchitecture,TotalPhysicalMemory,OsName"],
                capture_output=True, text=True, timeout=15
            )
            info.append(proc.stdout.strip())
            proc2 = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize/1MB, 1)"],
                capture_output=True, text=True, timeout=10
            )
            info.append(f"RAM GB: {proc2.stdout.strip()}")
            return "\n".join(info)

        return f"Unknown cmd_control action: {action}"

    except subprocess.TimeoutExpired:
        return "Command timed out (30s limit)."
    except Exception as e:
        return f"cmd_control failed: {e}"
