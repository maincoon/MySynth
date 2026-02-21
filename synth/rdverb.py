import numpy as np


class Rdverb:
    def __init__(
        self,
        sample_rate: int = 48000,
        mix: float = 0.15,
        feedback: float = 0.45,
        delay_ms: float = 180.0,
    ) -> None:
        self.sample_rate = int(max(8000, sample_rate))
        self.mix = float(np.clip(mix, 0.0, 1.0))
        self.feedback = float(np.clip(feedback, 0.0, 0.97))
        self.delay_ms = float(np.clip(delay_ms, 10.0, 2000.0))
        self._guard_gain = 1.0

        max_delay_samples = int(self.sample_rate * 2.0)
        self._buf_l = np.zeros(max_delay_samples, dtype=np.float32)
        self._buf_r = np.zeros(max_delay_samples, dtype=np.float32)
        self._write_idx = 0

    def _delay_samples(self) -> int:
        return int(np.clip((self.delay_ms / 1000.0) * self.sample_rate, 1, self._buf_l.size - 1))

    def set_mix(self, value: float) -> None:
        self.mix = float(np.clip(value, 0.0, 1.0))

    def set_feedback(self, value: float) -> None:
        self.feedback = float(np.clip(value, 0.0, 0.97))

    def set_delay_ms(self, value: float) -> None:
        self.delay_ms = float(np.clip(value, 10.0, 2000.0))

    def process(self, stereo: np.ndarray) -> np.ndarray:
        if stereo.ndim != 2 or stereo.shape[1] != 2:
            raise ValueError("Expected a stereo block with shape (frames, 2)")

        frames = stereo.shape[0]
        if frames == 0 or self.mix <= 0.0:
            return stereo.astype(np.float32, copy=False)

        out = np.array(stereo, copy=True, dtype=np.float32)
        dry = 1.0 - self.mix
        delay = self._delay_samples()
        buf_len = self._buf_l.size

        for n in range(frames):
            x_l = float(stereo[n, 0])
            x_r = float(stereo[n, 1])
            read_idx = (self._write_idx - delay) % buf_len
            wet_l = float(self._buf_l[read_idx])
            wet_r = float(self._buf_r[read_idx])

            peak_level = max(abs(x_l), abs(x_r), abs(wet_l), abs(wet_r))
            if peak_level > 0.9:
                self._guard_gain = max(0.2, self._guard_gain * 0.94)
            else:
                self._guard_gain = min(1.0, self._guard_gain + 0.0025)

            safe_feedback = min(self.feedback, 0.92) * self._guard_gain
            write_l = np.tanh(x_l + (wet_l * safe_feedback))
            write_r = np.tanh(x_r + (wet_r * safe_feedback))

            self._buf_l[self._write_idx] = np.float32(write_l)
            self._buf_r[self._write_idx] = np.float32(write_r)

            out_l = np.tanh((x_l * dry) + (wet_l * self.mix))
            out_r = np.tanh((x_r * dry) + (wet_r * self.mix))
            out[n, 0] = np.float32(out_l)
            out[n, 1] = np.float32(out_r)
            self._write_idx = (self._write_idx + 1) % buf_len

        return np.clip(out, -1.0, 1.0).astype(np.float32)
