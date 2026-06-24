# Speaker Verification Evaluation

This experiment compares SpeechBrain ECAPA-TDNN and WeSpeaker CAM++ against the
same microphone audio segments.

The experiment is evaluation-only. It does not automatically change speaker
mapping.

Mapped speakers are logged with `expected_participant_id`. Unassigned Soniox
clusters are scored against every available participant profile with no expected
label.

Results are written as JSONL under `results/`.

