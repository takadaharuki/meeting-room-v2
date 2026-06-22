export type SessionStartedEvent = {
  type: "session.started";
  meeting_id: string;
  soniox_model: string;
  sample_rate: number;
  frame_ms: number;
  server_timestamp_ms: number;
};

export type SessionEndedEvent = {
  type: "session.ended";
  meeting_id: string;
  reason: string;
  server_timestamp_ms: number;
};

export type TranscriptionErrorEvent = {
  type: "transcription.error";
  meeting_id: string;
  message: string;
  server_timestamp_ms: number;
};

export type TranscriptEvent = {
  type: "transcript.delta" | "transcript.final";
  meeting_id: string;
  segment_id: string;
  speaker_label: string | null;
  text: string;
  is_final: boolean;
  start_ms?: number | null;
  end_ms?: number | null;
  server_timestamp_ms: number;
};

export type ViewerEvent =
  | SessionStartedEvent
  | SessionEndedEvent
  | TranscriptionErrorEvent
  | TranscriptEvent;

export function parseViewerEvent(value: unknown): ViewerEvent | null {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null;
  }

  switch (value.type) {
    case "session.started":
    case "session.ended":
    case "transcription.error":
    case "transcript.delta":
    case "transcript.final":
      return value as ViewerEvent;
    default:
      return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
