import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import sys
from pathlib import Path
from typing import TextIO

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.audio.mic_capture import microphone_pcm_frames
from app.core.config import Settings, get_settings
from app.soniox.client import SonioxRealtimeClient, TranscriptEvent
from app.viewer import viewer_hub


def current_timestamp_ms() -> int:
    import time

    return time.time_ns() // 1_000_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_viewer_transcription())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/viewer")
async def viewer_websocket(websocket: WebSocket) -> None:
    await viewer_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await viewer_hub.disconnect(websocket)


async def run_viewer_transcription() -> None:
    settings = get_settings()
    await viewer_hub.broadcast(
        {
            "type": "session.started",
            "meeting_id": settings.meeting_id,
            "soniox_model": settings.soniox_model,
            "sample_rate": settings.audio_sample_rate,
            "frame_ms": settings.audio_frame_ms,
            "server_timestamp_ms": current_timestamp_ms(),
        }
    )

    try:
        client = SonioxRealtimeClient(settings=settings)
        audio_frames = microphone_pcm_frames(
            sample_rate=settings.audio_sample_rate,
            channels=settings.audio_channels,
            frame_ms=settings.audio_frame_ms,
            device=settings.audio_input_device,
        )
        async for event in client.transcribe(audio_frames):
            await viewer_hub.broadcast(event.as_dict())
    except asyncio.CancelledError:
        await viewer_hub.broadcast(
            {
                "type": "session.ended",
                "meeting_id": settings.meeting_id,
                "reason": "shutdown",
                "server_timestamp_ms": current_timestamp_ms(),
            }
        )
        raise
    except Exception as exc:
        await viewer_hub.broadcast(
            {
                "type": "transcription.error",
                "meeting_id": settings.meeting_id,
                "message": str(exc),
                "server_timestamp_ms": current_timestamp_ms(),
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream the local microphone to Soniox and print transcripts.",
    )
    parser.add_argument(
        "--format",
        choices=("pretty", "jsonl"),
        default="pretty",
        help="Console output format. 'pretty' prints Speaker N lines.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path for normalized transcript JSONL logs.",
    )
    return parser.parse_args()


async def run_soniox_console(
    *,
    console_format: str,
    output_path: Path | None,
) -> None:
    settings = get_settings()
    print_startup_settings(settings=settings, output_path=output_path)

    client = SonioxRealtimeClient(settings=settings)
    audio_frames = microphone_pcm_frames(
        sample_rate=settings.audio_sample_rate,
        channels=settings.audio_channels,
        frame_ms=settings.audio_frame_ms,
        device=settings.audio_input_device,
    )

    output_file: TextIO | None = None
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_file = output_path.open("w", encoding="utf-8")

    try:
        async for event in client.transcribe(audio_frames):
            line = json.dumps(event.as_dict(), ensure_ascii=False)
            if console_format == "jsonl":
                print(line, flush=True)
            else:
                print(format_pretty_event(event), flush=True)
            if output_file is not None:
                output_file.write(line + "\n")
                output_file.flush()
    finally:
        if output_file is not None:
            output_file.close()


def print_startup_settings(
    *,
    settings: Settings,
    output_path: Path | None,
) -> None:
    input_device = (
        str(settings.audio_input_device)
        if settings.audio_input_device is not None
        else "default"
    )
    output = str(output_path) if output_path is not None else "none"
    print("Starting meeting-room-v2 microphone transcription", file=sys.stderr)
    print(f"  meeting_id: {settings.meeting_id}", file=sys.stderr)
    print(f"  soniox_model: {settings.soniox_model}", file=sys.stderr)
    print(f"  sample_rate: {settings.audio_sample_rate}", file=sys.stderr)
    print(f"  frame_ms: {settings.audio_frame_ms}", file=sys.stderr)
    print(f"  input_device: {input_device}", file=sys.stderr)
    print(f"  jsonl_output: {output}", file=sys.stderr)
    print("Press Ctrl+C to stop.", file=sys.stderr)


def format_pretty_event(event: TranscriptEvent) -> str:
    speaker = f"Speaker {event.speaker_label}" if event.speaker_label else "Speaker ?"
    status = "final" if event.is_final else "delta"
    return f"[{status}] {speaker}: {event.text}"


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(
            run_soniox_console(
                console_format=args.format,
                output_path=args.output,
            )
        )
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
