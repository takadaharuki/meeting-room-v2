import asyncio
import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import websockets

from app.core.config import Settings, get_settings
from app.voice_agent.context_builder import VoiceAgentContext
from app.voice_agent.prompts import VOICE_AGENT_SHORT_RESPONSE_INSTRUCTIONS


class VoiceAgentResponseError(RuntimeError):
    pass


class VoiceAgentResponseClient(Protocol):
    async def generate_short_response(self, context: VoiceAgentContext) -> str:
        pass


class OpenAIRealtimeVoiceAgentClient:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate_short_response(self, context: VoiceAgentContext) -> str:
        api_key = self.settings.openai_api_key
        if not api_key:
            raise VoiceAgentResponseError("OPENAI_API_KEY is not set")

        timeout_sec = self.settings.voice_agent_realtime_timeout_ms / 1000
        try:
            async with asyncio.timeout(timeout_sec):
                return await self._generate_short_response(context, api_key)
        except VoiceAgentResponseError:
            raise
        except TimeoutError as exc:
            raise VoiceAgentResponseError(
                "OpenAI voice agent response timed out "
                f"after {self.settings.voice_agent_realtime_timeout_ms}ms"
            ) from exc
        except Exception as exc:
            raise VoiceAgentResponseError("OpenAI voice agent response failed") from exc

    async def generate_audio_response(
        self,
        context: VoiceAgentContext,
        on_audio_delta: Callable[[str], Awaitable[None]],
    ) -> str:
        api_key = self.settings.openai_api_key
        if not api_key:
            raise VoiceAgentResponseError("OPENAI_API_KEY is not set")

        timeout_sec = self.settings.voice_agent_realtime_timeout_ms / 1000
        try:
            async with asyncio.timeout(timeout_sec):
                return await self._generate_audio_response(
                    context,
                    api_key,
                    on_audio_delta,
                )
        except VoiceAgentResponseError:
            raise
        except TimeoutError as exc:
            raise VoiceAgentResponseError(
                "OpenAI voice agent audio response timed out "
                f"after {self.settings.voice_agent_realtime_timeout_ms}ms"
            ) from exc
        except Exception as exc:
            raise VoiceAgentResponseError(
                "OpenAI voice agent audio response failed"
            ) from exc

    async def _generate_short_response(
        self,
        context: VoiceAgentContext,
        api_key: str,
    ) -> str:
        chunks: list[str] = []
        async with websockets.connect(
            self._websocket_url(),
            additional_headers={"Authorization": f"Bearer {api_key}"},
        ) as websocket:
            use_recent_audio = self._should_send_recent_audio_to_realtime(context)
            await websocket.send(json.dumps(self._session_update_payload()))
            if use_recent_audio:
                await self._send_recent_audio_turn(websocket, context)
            else:
                await websocket.send(json.dumps(self._response_create_payload(context)))

            async for raw_message in websocket:
                event = self._parse_event(raw_message)
                event_type = event.get("type")
                if event_type == "response.output_text.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str):
                        chunks.append(delta)
                    continue
                if event_type == "response.done":
                    if chunks:
                        return "".join(chunks)
                    return self._extract_response_done_text(event)
                if event_type == "error":
                    raise VoiceAgentResponseError(self._error_message(event))

        raise VoiceAgentResponseError("OpenAI voice agent response ended unexpectedly")

    async def _generate_audio_response(
        self,
        context: VoiceAgentContext,
        api_key: str,
        on_audio_delta: Callable[[str], Awaitable[None]],
    ) -> str:
        text_chunks: list[str] = []
        transcript_chunks: list[str] = []
        async with websockets.connect(
            self._websocket_url(),
            additional_headers={"Authorization": f"Bearer {api_key}"},
        ) as websocket:
            use_recent_audio = self._should_send_recent_audio_to_realtime(context)
            await websocket.send(json.dumps(self._session_update_payload()))
            if use_recent_audio:
                await self._send_recent_audio_turn(
                    websocket,
                    context,
                    output_modalities=["audio"],
                )
            else:
                await websocket.send(
                    json.dumps(
                        self._response_create_payload(
                            context,
                            output_modalities=["audio"],
                        )
                    )
                )

            async for raw_message in websocket:
                event = self._parse_event(raw_message)
                event_type = event.get("type")
                if event_type == "response.output_audio.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str):
                        await on_audio_delta(delta)
                    continue
                if event_type == "response.output_audio_transcript.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str):
                        transcript_chunks.append(delta)
                    continue
                if event_type == "response.output_text.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str):
                        text_chunks.append(delta)
                    continue
                if event_type == "response.done":
                    if transcript_chunks:
                        return "".join(transcript_chunks)
                    if text_chunks:
                        return "".join(text_chunks)
                    return self._extract_response_done_text(event)
                if event_type == "error":
                    raise VoiceAgentResponseError(self._error_message(event))

        raise VoiceAgentResponseError(
            "OpenAI voice agent audio response ended unexpectedly"
        )

    def _websocket_url(self) -> str:
        parts = urlsplit(self.settings.openai_realtime_websocket_url)
        query_items = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key not in {"intent", "model"}
        ]
        query_items.append(("model", self.settings.voice_agent_realtime_model))
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query_items),
                parts.fragment,
            )
        )

    def _session_update_payload(self) -> dict[str, Any]:
        session: dict[str, Any] = {
            "type": "realtime",
            "model": self.settings.voice_agent_realtime_model,
            "instructions": VOICE_AGENT_SHORT_RESPONSE_INSTRUCTIONS,
            "audio": {
                "output": {
                    "voice": self.settings.voice_agent_realtime_voice,
                    "speed": self.settings.voice_agent_realtime_speed,
                },
            },
            "reasoning": {
                "effort": self.settings.voice_agent_realtime_reasoning_effort,
            },
        }

        return {
            "type": "session.update",
            "session": session,
        }

    def _response_create_payload(
        self,
        context: VoiceAgentContext,
        *,
        output_modalities: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "response.create",
            "response": {
                "conversation": "none",
                "metadata": {
                    "kind": "voice_agent_short_response",
                    "meeting_id": context.meeting_id,
                },
                "output_modalities": output_modalities or ["text"],
                "instructions": VOICE_AGENT_SHORT_RESPONSE_INSTRUCTIONS,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": context_prompt(context),
                            }
                        ],
                    }
                ],
            },
        }

    def _audio_response_create_payload(
        self,
        context: VoiceAgentContext,
        *,
        output_modalities: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "response.create",
            "response": {
                "metadata": {
                    "kind": "voice_agent_short_response_with_recent_audio",
                    "meeting_id": context.meeting_id,
                },
                "output_modalities": output_modalities or ["text"],
                "instructions": VOICE_AGENT_SHORT_RESPONSE_INSTRUCTIONS,
            },
        }

    def _audio_conversation_item_create_payload(
        self,
        context: VoiceAgentContext,
    ) -> dict[str, Any]:
        full_audio = self._recent_audio_base64(context)
        content: list[dict[str, str]] = []
        if full_audio is not None:
            content.append(
                {
                    "type": "input_audio",
                    "audio": full_audio,
                }
            )
        content.append(
            {
                "type": "input_text",
                "text": context_prompt(context),
            }
        )

        return {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": content,
            },
        }

    def _recent_audio_base64(
        self,
        context: VoiceAgentContext,
    ) -> str | None:
        recent_audio = context.recent_audio_payload
        if recent_audio is None:
            return None
        audio_bytes = b"".join(chunk.pcm_s16le for chunk in recent_audio.chunks)
        if not audio_bytes:
            return None
        return base64.b64encode(audio_bytes).decode("ascii")

    def _should_send_recent_audio_to_realtime(
        self,
        context: VoiceAgentContext,
    ) -> bool:
        if not self.settings.voice_agent_recent_audio_enabled:
            return False
        if not self.settings.voice_agent_recent_audio_to_realtime_enabled:
            return False
        if context.recent_audio is None or not context.recent_audio.has_audio:
            return False
        return context.recent_audio_payload is not None

    async def _send_recent_audio_turn(
        self,
        websocket: Any,
        context: VoiceAgentContext,
        *,
        output_modalities: list[str] | None = None,
    ) -> None:
        if self._recent_audio_base64(context) is None:
            await websocket.send(
                json.dumps(
                    self._response_create_payload(
                        context,
                        output_modalities=output_modalities,
                    )
                )
            )
            return

        await websocket.send(
            json.dumps(self._audio_conversation_item_create_payload(context))
        )
        await websocket.send(
            json.dumps(
                self._audio_response_create_payload(
                    context,
                    output_modalities=output_modalities,
                )
            )
        )

    @staticmethod
    def _parse_event(raw_message: str | bytes) -> dict[str, Any]:
        try:
            event = json.loads(raw_message)
        except json.JSONDecodeError as exc:
            raise VoiceAgentResponseError("OpenAI returned non-JSON event") from exc
        if not isinstance(event, dict):
            raise VoiceAgentResponseError("OpenAI returned invalid event")
        return event

    @staticmethod
    def _extract_response_done_text(event: dict[str, Any]) -> str:
        response = event.get("response")
        if not isinstance(response, dict):
            return ""
        output = response.get("output")
        if not isinstance(output, list):
            return ""

        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text") or part.get("transcript")
                if isinstance(text, str):
                    texts.append(text)
        return "".join(texts)

    @staticmethod
    def _error_message(event: dict[str, Any]) -> str:
        error = event.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
        return "OpenAI voice agent returned an error event"


def context_prompt(context: VoiceAgentContext) -> str:
    from app.voice_agent.context_builder import VoiceAgentContextBuilder

    return VoiceAgentContextBuilder().build_prompt(context)
