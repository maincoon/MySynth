import numpy as np
from threading import Lock

from .mixer import StaticMixer
from .rdverb import Rdverb


class AudioEngine:
    def __init__(
        self,
        synth,
        sample_rate: int = 48000,
        block_size: int = 256,
        external_inputs: list | None = None,
        mixer: StaticMixer | None = None,
        rdverb: Rdverb | None = None,
    ) -> None:
        self.synth = synth
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.external_inputs = external_inputs or []
        self.mixer = mixer or StaticMixer()
        self.rdverb = rdverb or Rdverb(sample_rate=sample_rate)
        self._stream = None
        self._lock = Lock()
        self._last_mono = np.zeros(self.block_size, dtype=np.float32)

    def set_rdverb_mix(self, value: float) -> None:
        self.rdverb.set_mix(value)

    def set_rdverb_feedback(self, value: float) -> None:
        self.rdverb.set_feedback(value)

    def set_rdverb_delay_ms(self, value: float) -> None:
        self.rdverb.set_delay_ms(value)

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "sounddevice is not installed. Install dependencies: pip install -r requirements.txt"
            ) from exc

        def callback(outdata, frames, time_info, status):
            if status:
                pass
            synth_audio = self.synth.render(frames)
            external_blocks = [ext.get_block(frames) for ext in self.external_inputs]
            mixed_audio = self.mixer.mix(synth_audio, external_blocks)
            wet_audio = self.rdverb.process(mixed_audio)
            outdata[:] = wet_audio
            with self._lock:
                self._last_mono = np.array(wet_audio[:, 0], copy=True)

        started_inputs = []
        try:
            for ext in self.external_inputs:
                ext.start()
                started_inputs.append(ext)
        except Exception:
            for ext in reversed(started_inputs):
                try:
                    ext.stop()
                except Exception:
                    pass
            raise

        try:
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=2,
                dtype=np.float32,
                blocksize=self.block_size,
                callback=callback,
            )
            self._stream.start()
        except Exception:
            for ext in reversed(started_inputs):
                try:
                    ext.stop()
                except Exception:
                    pass
            raise

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        for ext in self.external_inputs:
            try:
                ext.stop()
            except Exception:
                pass

    def get_last_mono_block(self) -> np.ndarray:
        with self._lock:
            if self._last_mono.size == 0:
                return np.zeros(self.block_size, dtype=np.float32)
            return np.array(self._last_mono, copy=True)
