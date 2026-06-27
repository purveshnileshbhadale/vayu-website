import sys
import time
import threading
import wave
import io
from pathlib import Path
from datetime import datetime

try:
    import sounddevice as sd
    _SD = True
except ImportError:
    _SD = False


_recording: list | None = None
_recording_thread: threading.Thread | None = None
_recording_start: float = 0.0
_recording_samplerate: int = 16000
_recording_lock = threading.Lock()


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _record_worker(samplerate: int, channels: int, duration: float | None):
    global _recording, _recording_start
    my_buffer = []

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[AudioRecorder] {status}")
        my_buffer.append(indata.copy())

    try:
        with sd.InputStream(samplerate=samplerate, channels=channels,
                            callback=callback, dtype="int16"):
            if duration:
                time.sleep(duration)
            else:
                while True:
                    with _recording_lock:
                        if _recording is None:
                            break
                    time.sleep(0.05)
    except Exception as e:
        print(f"[AudioRecorder] Record error: {e}")

    with _recording_lock:
        if _recording is not None:
            import numpy as np
            _recording = np.concatenate(my_buffer) if my_buffer else np.array([], dtype="int16")


def audio_recorder(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    global _recording, _recording_thread, _recording_start

    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if not _SD:
        return "sounddevice not installed. Run: pip install sounddevice numpy"

    if player:
        player.write_log(f"[AudioRec] {action}")

    try:
        if action in ("start", "record", "begin"):
            with _recording_lock:
                if _recording is not None:
                    return "Already recording. Stop first or check status."

                duration = params.get("duration")
                if duration:
                    duration = float(duration)
                samplerate = int(params.get("samplerate", 16000))
                channels = int(params.get("channels", 1))
                _recording = []
                _recording_start = time.time()

            _recording_thread = threading.Thread(
                target=_record_worker,
                args=(samplerate, channels, duration),
                daemon=True
            )
            _recording_thread.start()

            if duration:
                return f"Recording for {duration}s..."
            return "Recording started (will continue until stopped)."

        elif action in ("stop", "save", "finish"):
            with _recording_lock:
                if _recording is None:
                    return "No active recording."
                data = _recording
                sr = _recording_samplerate
                _recording = None

            if _recording_thread:
                _recording_thread.join(timeout=3)

            elapsed = time.time() - _recording_start
            if data is None or (hasattr(data, '__len__') and len(data) == 0):
                return "No audio data captured."

            import numpy as np
            if isinstance(data, list) and data:
                data = np.concatenate(data) if len(data) > 1 else data[0]

            output_path = params.get("save_path", "").strip()
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = str(_get_base_dir() / f"recording_{timestamp}.wav")

            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                if isinstance(data, np.ndarray):
                    wf.writeframes(data.tobytes())
                else:
                    wf.writeframes(bytes(data))

            return f"Recording saved: {output_path} ({elapsed:.1f}s)"

        elif action in ("status", "check"):
            with _recording_lock:
                if _recording is None:
                    return "No active recording."
                elapsed = time.time() - _recording_start
                return f"Recording in progress ({elapsed:.0f}s elapsed)."

        elif action in ("devices", "list_devices"):
            devices = sd.query_devices()
            lines = []
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    lines.append(f"{i}: {dev['name']} (in:{dev['max_input_channels']}ch, {int(dev['default_samplerate'])}Hz)")
            return "\n".join(lines) if lines else "No input devices found."

        return (
            f"Unknown action: '{action}'. "
            f"Available: start, stop, status, devices"
        )

    except Exception as e:
        return f"audio_recorder failed: {e}"
