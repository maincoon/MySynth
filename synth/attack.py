import numpy as np


class Attack:
    def __init__(self, attack_seconds: float = 0.01) -> None:
        self.attack_seconds = float(max(0.0, attack_seconds))

    def set_attack_seconds(self, value: float) -> None:
        self.attack_seconds = float(max(0.0, value))

    def apply(self, signal: np.ndarray, time_axis: np.ndarray) -> np.ndarray:
        if self.attack_seconds <= 0.0:
            return signal
        gain = np.clip(time_axis / self.attack_seconds, 0.0, 1.0)
        return (signal * gain).astype(np.float32)
