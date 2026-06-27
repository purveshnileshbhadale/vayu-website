import sys
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta


_timers: dict[str, dict] = {}
_timer_lock = threading.Lock()
_timer_counter = 0


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _notify(message: str):
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f'New-BurntToastNotification -Text "{message}"'],
            capture_output=True, timeout=5
        )
    except Exception:
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f'[System.Windows.MessageBox]::Show("{message}","VAYU Timer")'],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    try:
        import winsound
        for freq in [800, 1000, 1200]:
            winsound.Beep(freq, 200)
            time.sleep(0.1)
    except Exception:
        pass


def _timer_worker(timer_id: str, duration_s: float, message: str, is_alarm: bool):
    time.sleep(duration_s)
    with _timer_lock:
        if timer_id not in _timers:
            return
        del _timers[timer_id]

    label = "Alarm" if is_alarm else "Timer"
    msg = f"{label}: {message}" if message else f"{label} done!"
    print(f"[Timer] {msg}")
    _notify(msg)


def timer_alarm(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    global _timer_counter

    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[Timer] {action}")

    try:
        if action in ("timer", "start", "countdown"):
            duration = params.get("duration", "").strip()
            message = params.get("message", "Timer finished!").strip()

            if not duration:
                return "Duration is required (e.g. '5m', '30s', '1h')."

            seconds = 0
            duration_lower = duration.lower()
            if duration_lower.endswith("s"):
                seconds = int(duration_lower[:-1])
            elif duration_lower.endswith("m"):
                seconds = int(duration_lower[:-1]) * 60
            elif duration_lower.endswith("h"):
                seconds = int(duration_lower[:-1]) * 3600
            else:
                try:
                    seconds = int(duration)
                except ValueError:
                    return f"Invalid duration: {duration}. Use e.g. '5m', '30s', '2h'."

            if seconds < 1:
                return "Duration must be at least 1 second."
            if seconds > 86400:
                return "Maximum duration is 24 hours."

            with _timer_lock:
                _timer_counter += 1
                timer_id = f"timer_{_timer_counter}"
                end_time = datetime.now() + timedelta(seconds=seconds)
                _timers[timer_id] = {
                    "end": end_time,
                    "message": message,
                    "duration": seconds,
                }

            t = threading.Thread(
                target=_timer_worker,
                args=(timer_id, seconds, message, False),
                daemon=True
            )
            t.start()

            if seconds >= 60:
                mins = seconds // 60
                secs = seconds % 60
                time_str = f"{mins}m {secs}s" if secs else f"{mins}m"
            else:
                time_str = f"{seconds}s"

            return f"Timer set for {time_str}. Ends at {end_time.strftime('%I:%M:%S %p')}."

        elif action in ("alarm", "set_alarm"):
            time_str = params.get("time", "").strip()
            message = params.get("message", "Alarm!").strip()

            if not time_str:
                return "Time is required (e.g. '14:30' or '2:30 PM')."

            now = datetime.now()
            try:
                alarm_time = datetime.strptime(time_str, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )
            except ValueError:
                try:
                    alarm_time = datetime.strptime(time_str, "%I:%M %p").replace(
                        year=now.year, month=now.month, day=now.day
                    )
                except ValueError:
                    return f"Invalid time format: {time_str}. Use '14:30' or '2:30 PM'."

            if alarm_time <= now:
                alarm_time += timedelta(days=1)

            seconds = (alarm_time - now).total_seconds()

            with _timer_lock:
                _timer_counter += 1
                timer_id = f"alarm_{_timer_counter}"
                _timers[timer_id] = {
                    "end": alarm_time,
                    "message": message,
                    "duration": seconds,
                }

            t = threading.Thread(
                target=_timer_worker,
                args=(timer_id, seconds, message, True),
                daemon=True
            )
            t.start()

            return f"Alarm set for {alarm_time.strftime('%I:%M %p')}."

        elif action in ("list", "status"):
            with _timer_lock:
                if not _timers:
                    return "No active timers or alarms."
                now = datetime.now()
                lines = []
                for tid, info in _timers.items():
                    remaining = (info["end"] - now).total_seconds()
                    if remaining > 0:
                        mins = int(remaining // 60)
                        secs = int(remaining % 60)
                        tag = "ALARM" if tid.startswith("alarm") else "TIMER"
                        lines.append(
                            f"{tag} {tid}: {info['message'][:40]} — "
                            f"ends {info['end'].strftime('%I:%M:%S %p')} "
                            f"({mins}m {secs}s remaining)"
                        )
                return "\n".join(lines) if lines else "No active timers."

        elif action in ("cancel", "stop", "remove"):
            timer_id = params.get("timer_id", "").strip()
            if not timer_id:
                return "timer_id is required. Use 'list' to see active timers."

            with _timer_lock:
                if timer_id in _timers:
                    del _timers[timer_id]
                    return f"Cancelled: {timer_id}"
            return f"Timer not found: {timer_id}"

        elif action in ("cancel_all", "stop_all", "clear"):
            with _timer_lock:
                count = len(_timers)
                _timers.clear()
            return f"Cancelled {count} timer(s)."

        return (
            f"Unknown action: '{action}'. "
            f"Available: timer, alarm, list, cancel, cancel_all"
        )

    except Exception as e:
        return f"timer_alarm failed: {e}"
