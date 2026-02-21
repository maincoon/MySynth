import numpy as np


class Decay:
    def __init__(self, decay_seconds: float = 0.35) -> None:
        self.decay_seconds = float(max(0.001, decay_seconds))

    def set_decay_seconds(self, value: float) -> None:
        self.decay_seconds = float(max(0.001, value))

    def apply(
        self,
        signal: np.ndarray,
        time_axis: np.ndarray,
        velocity_norm: float,
        start_seconds: float = 0.0,
    ) -> np.ndarray:
        decay_time = np.maximum(0.0, time_axis - float(max(0.0, start_seconds)))
        vel = float(np.clip(velocity_norm, 0.0, 1.0))
        effective_decay = max(0.001, self.decay_seconds * (0.25 + 0.75 * vel))
        gain = np.exp(-decay_time / effective_decay)
        return (signal * gain).astype(np.float32)
