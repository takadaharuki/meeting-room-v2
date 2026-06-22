import argparse
import audioop
import json
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings


EXPERIMENTS_DIR = Path(__file__).resolve().parent
DEFAULT_SCENARIO = EXPERIMENTS_DIR / "scenarios" / "four_speakers_short_overlap.json"
DEFAULT_OUTPUT_DIR = EXPERIMENTS_DIR / "generated"


class TtsExperimentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Speaker:
    id: str
    name: str
    voice: str
    speed: float
    instructions: str


@dataclass(frozen=True, slots=True)
class Utterance:
    speaker: str
    start_ms: int
    text: str


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    sample_rate: int
    speakers: dict[str, Speaker]
    utterances: list[Utterance]


def main() -> None:
    args = parse_args()
    scenario = load_scenario(args.scenario)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    utterance_paths = []
    for index, utterance in enumerate(scenario.utterances, start=1):
        speaker = scenario.speakers[utterance.speaker]
        path = args.output_dir / f"{scenario.id}_{index:02d}_{speaker.id}.wav"
        create_tts_wav(path=path, speaker=speaker, text=utterance.text)
        utterance_paths.append((utterance, path))
        print(f"generated {path}")

    mixed_path = args.output_dir / f"{scenario.id}.wav"
    mix_utterances(
        scenario=scenario,
        utterance_paths=utterance_paths,
        output_path=mixed_path,
    )
    print(f"mixed {mixed_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        type=Path,
        default=DEFAULT_SCENARIO,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    return parser.parse_args()


def load_scenario(path: Path) -> Scenario:
    raw = json.loads(path.read_text(encoding="utf-8"))
    speakers = {
        item["id"]: Speaker(
            id=item["id"],
            name=item["name"],
            voice=item["voice"],
            speed=float(item.get("speed", 1.0)),
            instructions=item.get("instructions", ""),
        )
        for item in raw["speakers"]
    }
    utterances = [
        Utterance(
            speaker=item["speaker"],
            start_ms=int(item["start_ms"]),
            text=item["text"],
        )
        for item in raw["utterances"]
    ]
    return Scenario(
        id=raw["id"],
        sample_rate=int(raw["sample_rate"]),
        speakers=speakers,
        utterances=utterances,
    )


def create_tts_wav(*, path: Path, speaker: Speaker, text: str) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise TtsExperimentError("OPENAI_API_KEY is not set")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise TtsExperimentError("OpenAI TTS generation requires 'openai'.") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.audio.speech.create(
        model=settings.openai_tts_model,
        voice=speaker.voice,
        input=text,
        instructions=speaker.instructions,
        speed=speaker.speed,
        response_format="wav",
    )
    path.write_bytes(response.read())


def mix_utterances(
    *,
    scenario: Scenario,
    utterance_paths: list[tuple[Utterance, Path]],
    output_path: Path,
) -> None:
    output = bytearray()
    sample_width = 2
    channels = 1

    for utterance, path in utterance_paths:
        pcm = read_normalized_pcm(
            path=path,
            target_sample_rate=scenario.sample_rate,
            target_channels=channels,
            target_sample_width=sample_width,
        )
        start_byte = ms_to_byte_offset(
            utterance.start_ms,
            sample_rate=scenario.sample_rate,
            channels=channels,
            sample_width=sample_width,
        )
        end_byte = start_byte + len(pcm)
        if len(output) < end_byte:
            output.extend(bytes(end_byte - len(output)))

        current = bytes(output[start_byte:end_byte])
        mixed = audioop.add(current, pcm, sample_width)
        output[start_byte:end_byte] = mixed

    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(scenario.sample_rate)
        wav.writeframes(bytes(output))


def read_normalized_pcm(
    *,
    path: Path,
    target_sample_rate: int,
    target_channels: int,
    target_sample_width: int,
) -> bytes:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        pcm = wav.readframes(wav.getnframes())

    if sample_width != target_sample_width:
        pcm = audioop.lin2lin(pcm, sample_width, target_sample_width)
        sample_width = target_sample_width

    if channels == 2 and target_channels == 1:
        pcm = audioop.tomono(pcm, sample_width, 0.5, 0.5)
        channels = 1
    elif channels != target_channels:
        raise TtsExperimentError(
            f"Unsupported channel conversion: {channels} -> {target_channels}"
        )

    if sample_rate != target_sample_rate:
        pcm, _ = audioop.ratecv(
            pcm,
            sample_width,
            target_channels,
            sample_rate,
            target_sample_rate,
            None,
        )

    return pcm


def ms_to_byte_offset(
    ms: int,
    *,
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> int:
    frame = int(sample_rate * ms / 1000)
    return frame * channels * sample_width


if __name__ == "__main__":
    main()
