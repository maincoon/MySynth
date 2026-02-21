from enum import Enum
import numpy as np


class Waveform(str, Enum):
    SINE = "sine"
    SAW = "saw"
    SQUARE = "square"


TWOPI = 2.0 * np.pi


def generate_waveform(phase: np.ndarray, waveform: Waveform) -> np.ndarray:
    if waveform == Waveform.SINE:
        return np.sin(TWOPI * phase)
    if waveform == Waveform.SAW:
        return (2.0 * phase) - 1.0
    if waveform == Waveform.SQUARE:
        return np.where(phase < 0.5, 1.0, -1.0)
    return np.sin(TWOPI * phase)
