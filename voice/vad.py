"""Voice Activity Detection — energy-based VAD to detect when user is speaking.

Helps with automatic muting when no voice is detected.
"""

import array
import math
import struct


# Energy threshold — adjust based on mic sensitivity
_VAD_THRESHOLD = 300
_MIN_SPEECH_FRAMES = 3
_MIN_SILENCE_FRAMES = 10


class VAD:
    def __init__(self, threshold: int = _VAD_THRESHOLD):
        self.threshold = threshold
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
        self._rms_history: list[float] = []

    def _rms(self, audio_data: bytes) -> float:
        """Root mean square of raw PCM16 audio."""
        count = len(audio_data) // 2
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", audio_data[:count * 2])
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / count)

    def process(self, audio_data: bytes) -> bool:
        rms = self._rms(audio_data)
        self._rms_history.append(rms)
        if len(self._rms_history) > 50:
            self._rms_history.pop(0)
        adaptive_threshold = max(self.threshold, sum(self._rms_history) / len(self._rms_history) * 1.5)

        if rms > adaptive_threshold:
            self._speech_frames += 1
            self._silence_frames = 0
            if self._speech_frames >= _MIN_SPEECH_FRAMES:
                self._is_speaking = True
        else:
            self._silence_frames += 1
            self._speech_frames = 0
            if self._silence_frames >= _MIN_SILENCE_FRAMES:
                self._is_speaking = False

        return self._is_speaking

    @property
    def speaking(self) -> bool:
        return self._is_speaking

    def reset(self):
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
