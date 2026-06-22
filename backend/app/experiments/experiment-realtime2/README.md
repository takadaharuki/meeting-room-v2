# Realtime2 Conversation Experiment

This experiment is a minimal one-to-one voice agent using only
`gpt-realtime-2` for response generation and audio output.

It is intentionally separate from production code. The first goal is to verify:

```text
terminal user text -> gpt-realtime-2 -> streamed assistant audio + console text
```

## Run

Run from `backend/`.

```bash
uv run python app/experiments/experiment-realtime2/conversation_cli.py
```

Optional JSONL log:

```bash
uv run python app/experiments/experiment-realtime2/conversation_cli.py --output app/experiments/experiment-realtime2/results/session.jsonl
```

## Notes

- This uses WebSocket because the experiment runs server-side.
- Output audio is streamed from `response.output_audio.delta` / `response.audio.delta`
  and played as 24 kHz PCM16.
- User input is text for this first experiment. Live microphone input can be added
  after the agent response path is verified.

