from threading import Lock
import numpy as np

from .voice import Voice
from .vco import Waveform


class PolySynth:
    def __init__(self, polyphony: int = 16, sample_rate: int = 48000, waveform: str = "saw", pitch_bend_range: float = 2.0) -> None:
        self.polyphony = polyphony
        self.sample_rate = sample_rate
        self.waveform = Waveform(waveform)
        self.voices = [Voice() for _ in range(polyphony)]
        self._clock = 0
        self._lock = Lock()
        # pitch bend (in semitones) applied to all voices; default +/-2 semitones
        self.pitch_bend_range = float(pitch_bend_range)
        self.pitch_bend_semitones = 0.0
        self.attack_seconds = 0.01
        self.decay_seconds = 0.35

    def set_pitch_bend_raw(self, raw: int) -> None:
        """raw: -8192..+8191 (mido pitchwheel) -> semitone offset"""
        n = max(-8192, min(8191, int(raw))) / 8192.0
        with self._lock:
            self.pitch_bend_semitones = n * self.pitch_bend_range

    def set_pitch_bend_semitones(self, semitones: float) -> None:
        with self._lock:
            self.pitch_bend_semitones = float(semitones)

    def set_waveform(self, waveform: str) -> None:
        with self._lock:
            self.waveform = Waveform(waveform)

    def set_attack_seconds(self, value: float) -> None:
        with self._lock:
            self.attack_seconds = float(max(0.0, value))

    def set_decay_seconds(self, value: float) -> None:
        with self._lock:
            self.decay_seconds = float(max(0.001, value))

    def note_on(self, note: int, velocity: int) -> None:
        with self._lock:
            self._clock += 1
            for voice in self.voices:
                if voice.active and voice.note == note:
                    voice.note_on(note, velocity, self._clock)
                    return

            for voice in self.voices:
                if not voice.active:
                    voice.note_on(note, velocity, self._clock)
                    return

            oldest = min(self.voices, key=lambda v: v.started_at)
            oldest.note_on(note, velocity, self._clock)

    def note_off(self, note: int) -> None:
        with self._lock:
            for voice in self.voices:
                if voice.active and voice.note == note:
                    voice.note_off()

    def all_notes_off(self) -> None:
        with self._lock:
            for voice in self.voices:
                voice.note_off()

    def render(self, frames: int) -> np.ndarray:
        with self._lock:
            mix = np.zeros(frames, dtype=np.float32)
            for voice in self.voices:
                mix += voice.render(
                    frames,
                    self.sample_rate,
                    self.waveform,
                    pitch_offset_semitones=self.pitch_bend_semitones,
                    attack_seconds=self.attack_seconds,
                    decay_seconds=self.decay_seconds,
                )

        mix = np.clip(mix, -1.0, 1.0)
        stereo = np.column_stack((mix, mix))
        return stereo.astype(np.float32)
