import asyncio
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path


class WavReplayError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WavInfo:
    path: Path
    sample_rate: int
    channels: int
    sample_width: int


def read_wav_info(path: Path) -> WavInfo:
    with wave.open(str(path), "rb") as wav:
        return WavInfo(
            path=path,
            sample_rate=wav.getframerate(),
            channels=wav.getnchannels(),
            sample_width=wav.getsampwidth(),
        )


async def wav_pcm_frames(
    path: Path,
    *,
    frame_ms: int,
) -> AsyncIterator[bytes]:
    if frame_ms <= 0:
        raise WavReplayError("frame_ms must be greater than zero")

    with wave.open(str(path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        if channels != 1:
            raise WavReplayError("Only mono WAV replay is supported")
        if sample_width != 2:
            raise WavReplayError("Only 16-bit PCM WAV replay is supported")

        frames_per_chunk = int(sample_rate * frame_ms / 1000)
        if frames_per_chunk <= 0:
            raise WavReplayError("frame size is too small")

        sleep_sec = frame_ms / 1000
        while True:
            frame = wav.readframes(frames_per_chunk)
            if not frame:
                break
            yield frame
            await asyncio.sleep(sleep_sec)
