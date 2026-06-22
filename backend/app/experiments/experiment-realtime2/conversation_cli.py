from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, TextIO

BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from audio_output import Pcm16AudioPlayer  # noqa: E402
from prompts import CONVERSATION_AGENT_INSTRUCTIONS  # noqa: E402
from realtime2_client import Realtime2ConversationClient, Realtime2Event  # noqa: E402

from app.core.config import get_settings  # noqa: E402

EXPERIMENT_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = EXPERIMENT_DIR / "results"


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nstopped")


async def run() -> None:
    args = parse_args()
    settings = get_settings()
    output = open_output(args.output)

    print_startup(settings=settings, output_path=args.output)
    try:
        async with Realtime2ConversationClient(
            settings=settings,
            instructions=args.instructions.read_text(encoding="utf-8")
            if args.instructions
            else CONVERSATION_AGENT_INSTRUCTIONS,
        ) as client:
            with Pcm16AudioPlayer(
                sample_rate=settings.openai_realtime_output_sample_rate
            ) as player:
                await conversation_loop(client=client, player=player, output=output)
    finally:
        if output is not None:
            output.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instructions", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def open_output(path: Path | None) -> TextIO | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8")


async def conversation_loop(
    *,
    client: Realtime2ConversationClient,
    player: Pcm16AudioPlayer,
    output: TextIO | None,
) -> None:
    while True:
        user_text = await asyncio.to_thread(input, "\nYou> ")
        user_text = user_text.strip()
        if not user_text:
            continue
        if user_text in {":q", ":quit", "exit"}:
            break

        write_jsonl(output, {"type": "user.input", "text": user_text})
        await client.create_audio_response(user_text)
        print("AI> ", end="", flush=True)

        async for event in client.events_until_response_done():
            handle_event(event=event, player=player, output=output)

        print("", flush=True)


def handle_event(
    *,
    event: Realtime2Event,
    player: Pcm16AudioPlayer,
    output: TextIO | None,
) -> None:
    if event.kind == "audio_delta":
        player.write(event.payload["bytes"])
        return

    if event.kind == "transcript_delta":
        text = str(event.payload["text"])
        print(text, end="", flush=True)
        write_jsonl(output, {"type": "assistant.transcript.delta", "text": text})
        return

    if event.kind == "transcript_done":
        write_jsonl(output, {"type": "assistant.transcript.done"})
        return

    if event.kind == "response_done":
        write_jsonl(output, {"type": "assistant.response.done"})
        return

    if event.kind == "error":
        print(f"\n[realtime error] {event.payload}", file=sys.stderr)
        write_jsonl(output, {"type": "error", "payload": event.payload})


def write_jsonl(output: TextIO | None, payload: dict[str, Any]) -> None:
    if output is None:
        return
    line = {
        "server_timestamp_ms": int(time.time() * 1000),
        **payload,
    }
    output.write(json.dumps(line, ensure_ascii=False) + "\n")
    output.flush()


def print_startup(*, settings: Any, output_path: Path | None) -> None:
    print("Realtime2 conversation experiment")
    print(f"  model: {settings.openai_realtime_model}")
    print(f"  voice: {settings.openai_realtime_voice}")
    print(f"  reasoning_effort: {settings.openai_realtime_reasoning_effort}")
    print(f"  output_sample_rate: {settings.openai_realtime_output_sample_rate}")
    print(f"  output: {output_path or '(none)'}")
    print("  quit: :q")


if __name__ == "__main__":
    main()
