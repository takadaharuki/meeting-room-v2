# ROOM_REALTIME_PROTOCOL.md

## Purpose

This document defines the initial real-time protocol for `meeting-room-v2`.

The first version is intentionally small. It covers only the backend-to-viewer transcript events produced from Soniox real-time speech-to-text with speaker diarization.

## Scope

The initial runtime shape is:

```text
Mac room microphone
  -> backend audio capture
  -> Soniox realtime WebSocket
  -> backend normalized transcript events
  -> frontend viewer
```

Raw Soniox payloads are not part of the frontend protocol. The backend normalizes Soniox tokens into project-owned events before broadcasting them.

## Non-Goals

- iPhone device clients.
- Browser microphone capture.
- Raw audio recording storage.
- Raw Soniox event forwarding to the frontend.
- Participant identity confirmation.
- Visual features, face images, raw video, or meeting video.
- Device-based active speaker estimation.

## Common Fields

All backend-to-viewer events include:

```text
type
meeting_id
segment_id
text
speaker_label
is_final
server_timestamp_ms
```

`server_timestamp_ms` is the backend wall-clock time in milliseconds when the normalized event is emitted.

`speaker_label` is the provider-derived diarization label, such as `"1"` or `"2"`. It is not a participant identity. A later assignment flow may map it to a participant, but the mapping must remain editable.

## transcript.delta

Partial transcript for a segment.

```json
{
  "type": "transcript.delta",
  "meeting_id": "meeting_001",
  "segment_id": "seg_000001",
  "speaker_label": "1",
  "text": "今日の議題は",
  "is_final": false,
  "start_ms": 1200,
  "end_ms": 2400,
  "server_timestamp_ms": 1710000000000
}
```

Fields:

```text
type: "transcript.delta"
meeting_id: meeting/session id
segment_id: backend-assigned stable segment id
speaker_label: Soniox speaker label normalized as a string
text: partial text for this segment
is_final: false
start_ms: optional audio-relative start time from provider
end_ms: optional audio-relative end time from provider
server_timestamp_ms: backend emission time
```

The frontend should replace the current display for the same `segment_id` when a newer `transcript.delta` arrives.

## transcript.final

Final transcript for a segment.

```json
{
  "type": "transcript.final",
  "meeting_id": "meeting_001",
  "segment_id": "seg_000001",
  "speaker_label": "1",
  "text": "今日の議題は予算についてです。",
  "is_final": true,
  "start_ms": 1200,
  "end_ms": 4300,
  "server_timestamp_ms": 1710000001200
}
```

Fields:

```text
type: "transcript.final"
meeting_id: meeting/session id
segment_id: backend-assigned stable segment id
speaker_label: Soniox speaker label normalized as a string
text: final text for this segment
is_final: true
start_ms: optional audio-relative start time from provider
end_ms: optional audio-relative end time from provider
server_timestamp_ms: backend emission time
```

When `transcript.final` arrives, the frontend should replace any existing delta for the same `segment_id` and mark the segment as final.

## Speaker Label Rules

- `speaker_label` comes from Soniox diarization output.
- The label must be treated as a temporary speaker cluster, not as identity proof.
- The label is represented as a string even if the provider returns a number.
- Unknown speaker labels should be represented as `null` only if Soniox does not provide a label.
- Participant assignment is outside this initial protocol.

## Raw Provider Payloads

The frontend protocol must not depend on raw Soniox payload shape.

If raw provider debugging becomes necessary later, add a separate development-only event that includes only safe metadata, not audio and not full provider payloads.
