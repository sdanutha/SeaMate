export class SessionSocket {
  constructor(sessionId, handlers = {}) {
    this.sessionId = sessionId;
    this.handlers = handlers;
    this.ws = null;
    this.ready = false;
  }

  connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${proto}://${location.host}/ws/${this.sessionId}`);
    this.ws.onopen = () => { this.ready = true; };

    this.ws.onmessage = ({ data }) => {
      const msg = JSON.parse(data);
      const h = this.handlers;
      switch (msg.type) {
        case "status":         h.onStatus?.(msg.content);                              break;
        case "user":           h.onUser?.(msg.content);                                break;
        case "agent_start":    h.onAgentStart?.();                                     break;
        case "agent_end":      h.onAgentEnd?.();                                       break;
        case "token":          h.onToken?.(msg.content);                               break;
        case "subagent_start": h.onSubagentStart?.(msg.name);                          break;
        case "subagent_token": h.onSubagentToken?.(msg.name, msg.content);             break;
        case "subagent_end":   h.onSubagentEnd?.(msg.name);                            break;
        case "tool_start":     h.onToolStart?.(msg.tool, msg.args, msg.subagent);      break;
        case "tool_end":       h.onToolEnd?.(msg.tool, msg.result, msg.subagent);      break;
        case "interrupt":      h.onInterrupt?.(msg.interrupt_id, msg.tool, msg.args);  break;
        case "error":          h.onError?.(msg.content);                               break;
      }
    };

    this.ws.onclose = () => { this.ready = false; this.handlers.onDisconnect?.(); };
    this.ws.onerror = () => { this.handlers.onError?.("WebSocket error"); };
  }

  sendMessage(text) {
    if (!this.ready) return;
    this.ws.send(JSON.stringify({ type: "message", message: text }));
  }

  sendDecision(interruptId, decision = "approve") {
    if (!this.ready) return;
    this.ws.send(JSON.stringify({ type: "decision", interrupt_id: interruptId, decision }));
  }

  disconnect() { this.ws?.close(); this.ready = false; }
}
