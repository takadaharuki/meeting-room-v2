from __future__ import annotations


class AudioOutputError(RuntimeError):
    pass


class Pcm16AudioPlayer:
    def __init__(self, *, sample_rate: int) -> None:
        self._sample_rate = sample_rate
        self._stream = None

    def __enter__(self) -> Pcm16AudioPlayer:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioOutputError("Audio playback requires sounddevice.") from exc

        self._stream = sd.RawOutputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="int16",
            blocksize=0,
        )
        self._stream.start()
        return self

    def __exit__(self, *args: object) -> None:
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def write(self, pcm: bytes) -> None:
        if not pcm or self._stream is None:
            return
        self._stream.write(pcm)
