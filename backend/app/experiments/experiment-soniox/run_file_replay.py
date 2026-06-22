import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from file_replay import read_wav_info, wav_pcm_frames  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.soniox.client import SonioxRealtimeClient, TranscriptEvent  # noqa: E402

EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_WAV = EXPERIMENTS_DIR / "generated" / "four_speakers_short_overlap.wav"
DEFAULT_RESULTS_DIR = EXPERIMENTS_DIR / "results"


def main() -> None:
    asyncio.run(run())


async def run() -> None:
    args = parse_args()
    DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = args.output or DEFAULT_RESULTS_DIR / f"{args.wav.stem}.jsonl"

    info = read_wav_info(args.wav)
    settings = get_settings().model_copy(
        update={
            "audio_sample_rate": info.sample_rate,
            "audio_channels": info.channels,
            "audio_format": "pcm_s16le",
        }
    )
    client = SonioxRealtimeClient(settings=settings)
    frames = wav_pcm_frames(args.wav, frame_ms=args.frame_ms)

    with result_path.open("w", encoding="utf-8") as output:
        async for event in client.transcribe(frames):
            if not isinstance(event, TranscriptEvent):
                continue
            payload = event.as_dict()
            line = json.dumps(payload, ensure_ascii=False)
            print(line, flush=True)
            output.write(line + "\n")

    print(f"saved {result_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", type=Path, default=DEFAULT_WAV)
    parser.add_argument("--frame-ms", type=int, default=100)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
