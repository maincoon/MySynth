import numpy as np


class StaticMixer:
    def __init__(self, synth_gain: float = 1.0, input_gain: float = 1.0) -> None:
        self.synth_gain = float(synth_gain)
        self.input_gain = float(input_gain)

    def mix(self, synth_stereo: np.ndarray, external_mono_blocks: list[np.ndarray]) -> np.ndarray:
        if synth_stereo.ndim != 2 or synth_stereo.shape[1] != 2:
            raise ValueError("Expected stereo block 'synth_stereo' with shape (frames, 2)")

        frames = synth_stereo.shape[0]
        external_sum = np.zeros(frames, dtype=np.float32)
        for block in external_mono_blocks:
            if block.size == frames:
                external_sum += block.astype(np.float32, copy=False)
            elif block.size > frames:
                external_sum += block[:frames].astype(np.float32, copy=False)
            else:
                padded = np.zeros(frames, dtype=np.float32)
                padded[: block.size] = block
                external_sum += padded

        external_stereo = np.column_stack((external_sum, external_sum)).astype(np.float32)
        mixed = (synth_stereo.astype(np.float32, copy=False) * self.synth_gain) + (external_stereo * self.input_gain)
        return np.clip(mixed, -1.0, 1.0).astype(np.float32)
