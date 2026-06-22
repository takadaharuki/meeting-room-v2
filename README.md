# meeting-room-v2

## Voice Agent

The production voice agent is disabled by default. To enable the initial
facilitation experiment, set:

```env
VOICE_AGENT_ENABLED=true
VOICE_AGENT_SILENCE_MS=1500
VOICE_AGENT_COOLDOWN_MS=15000
VOICE_AGENT_POST_AGENT_MUTE_MS=5000
VOICE_AGENT_MIN_TRANSCRIPT_CHARS=8
```

Flow:

```text
Mac mic -> Soniox transcript/turn-end -> silence trigger -> gpt-realtime-2 audio -> Mac speaker
```

The agent response is not sent to the experimental viewer. Because Mac speaker
audio can be picked up by Soniox, triggers are muted while the agent is speaking
and for `VOICE_AGENT_POST_AGENT_MUTE_MS` after speech ends.
