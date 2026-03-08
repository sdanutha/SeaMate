/**
 * Minimal WebSocket wrapper — connects to /ws (no session).
 */
export class ChatSocket {
  constructor(handlers = {}) {
    this.handlers = handlers;
    this.ws = null;
    this.ready = false;
  }

  connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws`);
    this.ws.onopen = () => { this.ready = true; };

    this.ws.onmessage = ({ data }) => {
      const msg = JSON.parse(data);
      const h = this.handlers;
      switch (msg.type) {
        case "status":      h.onStatus?.(msg.content);    break;
        case "agent_start": h.onAgentStart?.();            break;
        case "agent_end":   h.onAgentEnd?.();              break;
        case "token":       h.onToken?.(msg.content);      break;
        case "error":       h.onError?.(msg.content);      break;
      }
    };

    this.ws.onclose = () => {
      this.ready = false;
      this.handlers.onDisconnect?.();
    };
    this.ws.onerror = () => {
      this.handlers.onError?.("WebSocket error");
    };
  }

  sendMessage(text) {
    if (!this.ready) return;
    this.ws.send(JSON.stringify({ type: "message", message: text }));
  }

  disconnect() {
    this.ws?.close();
    this.ready = false;
  }
}
