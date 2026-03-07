export class AgentSocket {
  constructor(agentId, { onToken, onStart, onEnd, onStatus, onError } = {}) {
    this.agentId = agentId;
    this.callbacks = { onToken, onStart, onEnd, onStatus, onError };
    this.ws = null;
    this.ready = false;
  }

  connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${location.host}/ws/${this.agentId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => { this.ready = true; };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      switch (msg.type) {
        case "status":      this.callbacks.onStatus?.(msg.content); break;
        case "token":       this.callbacks.onToken?.(msg.content);  break;
        case "agent_start": this.callbacks.onStart?.(msg.agent);    break;
        case "agent_end":   this.callbacks.onEnd?.();               break;
        case "error":       this.callbacks.onError?.(msg.content);  break;
      }
    };

    this.ws.onclose = () => { this.ready = false; };
    this.ws.onerror = () => { this.callbacks.onError?.("WebSocket error"); };
  }

  send(message) {
    if (!this.ready) return false;
    this.ws.send(JSON.stringify({ message }));
    return true;
  }

  disconnect() {
    this.ws?.close();
    this.ready = false;
  }
}
