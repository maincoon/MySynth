from dataclasses import dataclass
import numpy as np

from .attack import Attack
from .decay import Decay
from .music import midi_note_to_freq
from .vco import Waveform, generate_waveform


@dataclass
class Voice:
    note: int = -1
    velocity: int = 0
    active: bool = False
    phase: float = 0.0
    started_at: int = 0
    age_samples: int = 0
    released: bool = False

    def note_on(self, note: int, velocity: int, timestamp: int) -> None:
        self.note = note
        self.velocity = velocity
        self.active = True
        self.started_at = timestamp
        self.age_samples = 0
        self.released = False

    def note_off(self) -> None:
        self.released = True

    def render(
        self,
        frames: int,
        sample_rate: int,
        waveform: Waveform,
        pitch_offset_semitones: float = 0.0,
        attack_seconds: float = 0.01,
        decay_seconds: float = 0.35,
    ) -> np.ndarray:
        if not self.active:
            return np.zeros(frames, dtype=np.float32)

        base_freq = midi_note_to_freq(self.note)
        # apply pitch offset in semitones (pitch bend)
        freq = base_freq * (2.0 ** (pitch_offset_semitones / 12.0))
        phase_inc = freq / float(sample_rate)
        phase = (self.phase + phase_inc * np.arange(frames, dtype=np.float64)) % 1.0
        out = generate_waveform(phase, waveform)

        time_axis = (self.age_samples + np.arange(frames, dtype=np.float64)) / float(sample_rate)
        attack = Attack(attack_seconds)
        decay = Decay(decay_seconds)
        out = attack.apply(out, time_axis)
        out = decay.apply(out, time_axis, velocity_norm=(self.velocity / 127.0), start_seconds=attack_seconds)

        self.phase = (self.phase + phase_inc * frames) % 1.0
        self.age_samples += frames

        amp = (self.velocity / 127.0) * 0.12
        voice_out = (out * amp).astype(np.float32)

        min_tail = int((attack_seconds + (decay_seconds * 6.0)) * sample_rate)
        if np.max(np.abs(voice_out)) < 1e-4 and self.age_samples > min_tail:
            self.active = False
            self.released = False
            self.age_samples = 0

        return voice_out
