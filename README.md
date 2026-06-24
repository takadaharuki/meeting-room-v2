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
VOICE_AGENT_BARGE_IN_ENABLED=true
VOICE_AGENT_BARGE_IN_MIN_CHARS=2
SPEAKER_INTRO_WINDOW_MS=8000
```

Flow:

```text
Mac mic -> Soniox transcript/turn-end -> silence trigger -> gpt-realtime-2 audio -> Mac speaker
```

The agent response is not sent to the experimental viewer. Because Mac speaker
audio can be picked up by Soniox, triggers are muted while the agent is speaking
and for `VOICE_AGENT_POST_AGENT_MUTE_MS` after speech ends.

When barge-in is enabled, a mapped human speaker producing at least
`VOICE_AGENT_BARGE_IN_MIN_CHARS` of transcript while the agent is speaking
cancels the Realtime response and aborts Mac audio playback. AI and unassigned
speaker clusters do not trigger interruption.

## Speaker Setup

The experimental viewer has `Setup` and `Live` tabs.

1. Open `Setup`.
2. Enter human participant names and the AI agent name.
3. Click `Save`.
4. For each participant, click `Start Intro`.
5. The participant self-introduces. For the AI agent, the backend plays an intro from the Mac speaker.
6. When a new Soniox speaker appears, the row changes to `Candidate`.
7. Click `Confirm` to bind that speaker label to the participant.
8. Use `Live` for the transcript view.

Unknown Soniox speaker labels are shown as unassigned and do not create new
participants automatically.

The `Live` tab also shows memory-only speaking stats per mapped participant or
unassigned speaker: final utterance count, text character count, and estimated
speech time from Soniox timestamps.
