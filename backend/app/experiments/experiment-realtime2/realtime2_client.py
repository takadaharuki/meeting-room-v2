from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import websockets

from app.core.config import Settings

RealtimeEventKind = Literal[
    "audio_delta",
    "transcript_delta",
    "transcript_done",
    "response_done",
    "error",
    "session",
]


class Realtime2Error(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Realtime2Event:
    kind: RealtimeEventKind
    payload: dict[str, Any]


class Realtime2ConversationClient:
    def __init__(self, *, settings: Settings, instructions: str) -> None:
        if not settings.openai_api_key:
            raise Realtime2Error("OPENAI_API_KEY is not set")

        self._settings = settings
        self._instructions = instructions
        self._websocket: Any | None = None

    async def __aenter__(self) -> Realtime2ConversationClient:
        self._websocket = await websockets.connect(
            self._websocket_url(),
            additional_headers={
                "Authorization": f"Bearer {self._settings.openai_api_key}",
            },
            max_size=None,
        )
        await self._update_session()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._websocket is not None:
            await self._websocket.close()
            self._websocket = None

    def _websocket_url(self) -> str:
        query = urlencode({"model": self._settings.openai_realtime_model})
        return f"{self._settings.openai_realtime_websocket_url}?{query}"

    async def _send(self, event: dict[str, Any]) -> None:
        if self._websocket is None:
            raise Realtime2Error("Realtime websocket is not connected")
        await self._websocket.send(json.dumps(event, ensure_ascii=False))

    async def _recv(self) -> dict[str, Any]:
        if self._websocket is None:
            raise Realtime2Error("Realtime websocket is not connected")
        raw = await self._websocket.recv()
        return json.loads(raw)

    async def _update_session(self) -> None:
        await self._send(
            {
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "model": self._settings.openai_realtime_model,
                    "instructions": self._instructions,
                    "audio": {
                        "output": {
                            "voice": self._settings.openai_realtime_voice,
                            "format": self._output_audio_format(),
                        }
                    },
                    "reasoning": {
                        "effort": self._settings.openai_realtime_reasoning_effort
                    },
                },
            }
        )

    async def create_audio_response(self, user_text: str) -> None:
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_text,
                        }
                    ],
                },
            }
        )
        await self._send(
            {
                "type": "response.create",
                "response": {
                    "audio": {
                        "output": {
                            "format": self._output_audio_format(),
                        }
                    },
                },
            }
        )

    def _output_audio_format(self) -> dict[str, Any]:
        return {
            "type": "audio/pcm",
            "rate": self._settings.openai_realtime_output_sample_rate,
        }

    async def events_until_response_done(self) -> AsyncIterator[Realtime2Event]:
        while True:
            event = await self._recv()
            event_type = str(event.get("type", ""))

            if event_type in {"session.created", "session.updated"}:
                yield Realtime2Event("session", event)
                continue

            if event_type in {"response.output_audio.delta", "response.audio.delta"}:
                delta = event.get("delta")
                if isinstance(delta, str):
                    yield Realtime2Event(
                        "audio_delta",
                        {
                            "bytes": base64.b64decode(delta),
                            "event": event,
                        },
                    )
                continue

            if event_type in {
                "response.output_audio_transcript.delta",
                "response.audio_transcript.delta",
            }:
                delta = event.get("delta")
                if isinstance(delta, str):
                    yield Realtime2Event(
                        "transcript_delta",
                        {
                            "text": delta,
                            "event": event,
                        },
                    )
                continue

            if event_type in {
                "response.output_audio_transcript.done",
                "response.audio_transcript.done",
            }:
                yield Realtime2Event("transcript_done", event)
                continue

            if event_type == "error":
                yield Realtime2Event("error", event)
                continue

            if event_type == "response.done":
                yield Realtime2Event("response_done", event)
                break

            await asyncio.sleep(0)
