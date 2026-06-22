import { parseViewerEvent, type TranscriptEvent, type ViewerEvent } from "./events";

type ConnectionStatus = "connecting" | "connected" | "closed" | "error";

type ViewerState = {
  status: ConnectionStatus;
  meetingId: string | null;
  model: string | null;
  error: string | null;
  segments: Map<string, TranscriptEvent>;
  order: string[];
};

const viewerWsUrl =
  import.meta.env.VITE_VIEWER_WS_URL ?? "ws://localhost:8000/ws/viewer";

export function mountExperimentalViewer(root: HTMLElement): void {
  const state: ViewerState = {
    status: "connecting",
    meetingId: null,
    model: null,
    error: null,
    segments: new Map(),
    order: [],
  };

  root.innerHTML = layout();
  render(state);

  const socket = new WebSocket(viewerWsUrl);

  socket.addEventListener("open", () => {
    state.status = "connected";
    render(state);
  });

  socket.addEventListener("close", () => {
    state.status = "closed";
    render(state);
  });

  socket.addEventListener("error", () => {
    state.status = "error";
    state.error = "viewer websocket connection failed";
    render(state);
  });

  socket.addEventListener("message", (message) => {
    const event = parseMessage(message.data);
    if (event === null) {
      return;
    }
    applyEvent(state, event);
    render(state);
  });
}

function parseMessage(data: unknown): ViewerEvent | null {
  if (typeof data !== "string") {
    return null;
  }
  try {
    return parseViewerEvent(JSON.parse(data));
  } catch {
    return null;
  }
}

function applyEvent(state: ViewerState, event: ViewerEvent): void {
  if ("meeting_id" in event) {
    state.meetingId = event.meeting_id;
  }

  if (event.type === "session.started") {
    state.model = event.soniox_model;
    state.error = null;
    return;
  }

  if (event.type === "transcription.error") {
    state.error = event.message;
    return;
  }

  if (event.type === "transcript.delta" || event.type === "transcript.final") {
    if (!state.segments.has(event.segment_id)) {
      state.order.push(event.segment_id);
    }
    state.segments.set(event.segment_id, event);
  }
}

function render(state: ViewerState): void {
  setText("status-value", statusLabel(state.status));
  setText("meeting-value", state.meetingId ?? "waiting");
  setText("model-value", state.model ?? "waiting");
  setText("error-value", state.error ?? "");

  const transcript = document.querySelector<HTMLDivElement>("#transcript");
  if (transcript === null) {
    return;
  }

  const segments = state.order
    .map((id) => state.segments.get(id))
    .filter((event): event is TranscriptEvent => event !== undefined);

  if (segments.length === 0) {
    transcript.innerHTML = `<p class="empty">Waiting for speech...</p>`;
    return;
  }

  transcript.innerHTML = segments.map(renderSegment).join("");
  transcript.scrollTop = transcript.scrollHeight;
}

function renderSegment(event: TranscriptEvent): string {
  const speaker = event.speaker_label === null ? "Speaker ?" : `Speaker ${event.speaker_label}`;
  const finalClass = event.is_final ? "final" : "delta";
  const status = event.is_final ? "final" : "live";
  return `
    <section class="segment ${finalClass}">
      <div class="speaker">${escapeHtml(speaker)}</div>
      <p>${escapeHtml(event.text)}</p>
      <span>${status}</span>
    </section>
  `;
}

function setText(id: string, value: string): void {
  const element = document.querySelector<HTMLElement>(`#${id}`);
  if (element !== null) {
    element.textContent = value;
  }
}

function statusLabel(status: ConnectionStatus): string {
  switch (status) {
    case "connecting":
      return "connecting";
    case "connected":
      return "connected";
    case "closed":
      return "closed";
    case "error":
      return "error";
  }
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function layout(): string {
  return `
    <div class="viewer-shell">
      <header>
        <h1>Meeting Room Viewer</h1>
        <dl>
          <div><dt>Status</dt><dd id="status-value">connecting</dd></div>
          <div><dt>Meeting</dt><dd id="meeting-value">waiting</dd></div>
          <div><dt>Model</dt><dd id="model-value">waiting</dd></div>
        </dl>
      </header>
      <p id="error-value" class="error"></p>
      <div id="transcript" class="transcript" aria-live="polite"></div>
    </div>
  `;
}
