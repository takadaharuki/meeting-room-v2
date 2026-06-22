# Soniox Experiment

This directory contains development-only experiments for Soniox speaker diarization.

Production code must not import from `app.experiments`.

## Files

```text
scenarios/
  four_speakers_short_overlap.json
generated/
  generated wav files, not committed
results/
  Soniox jsonl results, not committed
generate_tts_audio.py
file_replay.py
run_file_replay.py
```

## Flow

1. Generate one mixed scenario WAV with OpenAI TTS.
2. Replay that WAV to Soniox at real-time speed.
3. Save normalized `transcript.delta` / `transcript.final` events as JSONL.

## Commands

Run from `backend/`.

```bash
uv run python app/experiments/experiment-soniox/generate_tts_audio.py
uv run python app/experiments/experiment-soniox/run_file_replay.py
```

The default scenario is `scenarios/four_speakers_short_overlap.json`.

## Notes

- OpenAI TTS output is used only to create repeatable test audio.
- Scenario `start_ms` values define natural short overlaps.
- Generated audio and Soniox result logs are not committed.
- Speaker labels from Soniox are temporary clusters, not participant identity.
