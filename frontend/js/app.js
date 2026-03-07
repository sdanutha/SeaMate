import { SessionSocket } from "./ws.js";

// ── State ─────────────────────────────────────────────────────────────────────
let socket = null;
let activeSessionId = null;
let streamingBubble = null;      // main orchestrator bubble
let subagentBubbles = {};        // name → bubble element
let activeSubagents = new Set(); // currently running subagents
let sending = false;

// ── DOM ───────────────────────────────────────────────────────────────────────
const output        = document.getElementById("output");
const msgInput      = document.getElementById("msg-input");
const sendBtn       = document.getElementById("send-btn");
const agentLabel    = document.getElementById("agent-label");
const headerTitle   = document.getElementById("header-title");
const headerMeta    = document.getElementById("header-meta");
const headerDot     = document.getElementById("header-dot");
const connStatus    = document.getElementById("conn-status");
const agentsList    = document.getElementById("agents-list");
const sessionsList  = document.getElementById("sessions-list");
const newSessionBtn = document.getElementById("new-session-btn");
const emptyState    = document.getElementById("empty-state");

// ── Helpers ───────────────────────────────────────────────────────────────────
const ts = () =>
  new Date().toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function scrollBottom() { output.scrollTop = output.scrollHeight; }

function setConnected(ok) {
  connStatus.textContent = ok ? "live" : "offline";
  connStatus.className   = `status ${ok ? "online" : "offline"}`;
  headerDot.className    = `dot ${ok ? "online" : ""}`;
}

function setInputEnabled(enabled) {
  msgInput.disabled = !enabled;
  sendBtn.disabled  = !enabled;
  if (enabled) msgInput.focus();
}

// ── Agents sidebar ────────────────────────────────────────────────────────────
async function loadAgents() {
  try {
    const res = await fetch("/api/agents/");
    const groups = await res.json();
    agentsList.innerHTML = "";

    for (const [groupName, agents] of Object.entries(groups)) {
      const label = document.createElement("div");
      label.className = "sidebar-sublabel";
      label.textContent = groupName.toUpperCase();
      agentsList.appendChild(label);

      agents.forEach((agent) => {
        const item = document.createElement("div");
        item.className = `sidebar-item agent-item ${agent.role}`;
        item.dataset.id = agent.id;
        item.innerHTML = `<div class="dot ${agent.role === "orchestrator" ? "online" : ""}"></div>
                          <span class="item-name">${agent.name}</span>
                          <span class="agent-badge">${agent.role === "orchestrator" ? "" : "sub"}</span>`;
        agentsList.appendChild(item);
      });
    }
  } catch (_) {}
}

function markSubagentActive(name, active) {
  const el = agentsList.querySelector(`[data-id="${name}"]`);
  if (!el) return;
  el.classList.toggle("running", active);
  el.querySelector(".dot")?.classList.toggle("busy", active);
  el.querySelector(".dot")?.classList.toggle("online", !active);
}

// ── Sessions sidebar ──────────────────────────────────────────────────────────
async function loadSessions() {
  try {
    const res = await fetch("/api/sessions/");
    const sessions = await res.json();
    sessionsList.innerHTML = "";

    if (sessions.length === 0) {
      sessionsList.innerHTML = `<div class="sessions-empty">no sessions yet</div>`;
      return;
    }

    sessions.forEach((s) => appendSessionItem(s));
  } catch (_) {}
}

function appendSessionItem(session, prepend = false) {
  const existing = sessionsList.querySelector(`[data-sid="${session.id}"]`);
  if (existing) { existing.querySelector(".session-title").textContent = session.title; return; }

  const el = document.createElement("div");
  el.className = "sidebar-item session-item";
  el.dataset.sid = session.id;
  el.innerHTML = `
    <div class="dot"></div>
    <span class="session-title item-name">${session.title}</span>
    <button class="session-del" title="Delete">×</button>`;

  el.addEventListener("click", (e) => {
    if (e.target.classList.contains("session-del")) return;
    selectSession(session.id, session.title);
  });
  el.querySelector(".session-del").addEventListener("click", (e) => {
    e.stopPropagation();
    deleteSession(session.id, el);
  });

  if (prepend) sessionsList.prepend(el);
  else         sessionsList.appendChild(el);
}

function setActiveSessionItem(sessionId) {
  sessionsList.querySelectorAll(".session-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.sid === sessionId)
  );
}

async function deleteSession(sessionId, el) {
  await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
  el.remove();
  if (activeSessionId === sessionId) {
    socket?.disconnect();
    activeSessionId = null;
    output.innerHTML = `<div id="empty-state"><span>no session selected</span><span class="hint">pick a session or press + to start</span></div>`;
    setInputEnabled(false);
    setConnected(false);
  }
}

// ── Select / open session ─────────────────────────────────────────────────────
function selectSession(sessionId, title = "session") {
  if (activeSessionId === sessionId) return;

  socket?.disconnect();
  activeSessionId = sessionId;
  streamingBubble = null;
  subagentBubbles = {};
  activeSubagents.clear();
  sending = false;

  headerTitle.textContent = title;
  headerMeta.textContent  = "· seamate orchestrator";
  agentLabel.textContent  = "seamate";
  setActiveSessionItem(sessionId);
  setConnected(false);
  setInputEnabled(false);

  // Clear output
  output.innerHTML = "";

  socket = new SessionSocket(sessionId, {
    onStatus: (msg) => {
      setConnected(true);
      appendStatus(msg);
      setInputEnabled(true);
    },
    onDisconnect: () => setConnected(false),
    onError: (err) => {
      appendError(err);
      setInputEnabled(true);
      sending = false;
    },

    // ── Main orchestrator tokens ──────────────────────────────
    onAgentStart: () => {
      streamingBubble = createStreamBubble("seamate", "agent");
    },
    onToken: (content) => {
      if (!streamingBubble) streamingBubble = createStreamBubble("seamate", "agent");
      appendToken(streamingBubble, content);
    },
    onAgentEnd: () => {
      finalizeStreamBubble(streamingBubble);
      streamingBubble = null;
      sending = false;
      setInputEnabled(true);
    },

    // ── Subagent tokens ───────────────────────────────────────
    onSubagentStart: (name) => {
      activeSubagents.add(name);
      markSubagentActive(name, true);
      subagentBubbles[name] = createStreamBubble(name, "subagent");
    },
    onSubagentToken: (name, content) => {
      if (!subagentBubbles[name]) subagentBubbles[name] = createStreamBubble(name, "subagent");
      appendToken(subagentBubbles[name], content);
    },
    onSubagentEnd: (name) => {
      finalizeStreamBubble(subagentBubbles[name]);
      delete subagentBubbles[name];
      activeSubagents.delete(name);
      markSubagentActive(name, false);
    },

    // ── Tool calls ────────────────────────────────────────────
    onToolStart: (tool, args) => appendToolCard(tool, args),
    onToolEnd:   (tool, result) => updateToolCard(tool, result),

    // ── Human-in-the-loop ─────────────────────────────────────
    onInterrupt: (interruptId, tool, args) => {
      appendInterruptCard(interruptId, tool, args);
      sending = false;
      setInputEnabled(false);
    },
  });

  socket.connect();
}

// ── New session ───────────────────────────────────────────────────────────────
newSessionBtn.addEventListener("click", async () => {
  const res  = await fetch("/api/sessions/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "New session" }) });
  const sess = await res.json();
  appendSessionItem(sess, true);
  selectSession(sess.id, sess.title);
});

// ── Send ──────────────────────────────────────────────────────────────────────
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || !socket?.ready || sending) return;
  sending = true;
  msgInput.value = "";
  setInputEnabled(false);
  socket.sendMessage(text);
}

sendBtn.addEventListener("click", sendMessage);
msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ── Message builders ──────────────────────────────────────────────────────────
function appendStatus(text) {
  const el = document.createElement("div");
  el.className = "msg status";
  el.innerHTML = `<div class="msg-bubble">${text}</div>`;
  output.appendChild(el); scrollBottom();
}

function appendError(text) {
  const el = document.createElement("div");
  el.className = "msg error";
  el.innerHTML = `<div class="msg-meta">${ts()}</div><div class="msg-bubble">⚠ ${text}</div>`;
  output.appendChild(el); scrollBottom();
}

function createStreamBubble(label, type) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${type}`;
  wrap.innerHTML = `<div class="msg-meta">${label} · ${ts()}</div><div class="msg-bubble cursor"></div>`;
  output.appendChild(wrap); scrollBottom();
  return wrap.querySelector(".msg-bubble");
}

function appendToken(bubble, content) {
  bubble.classList.remove("cursor");
  bubble._raw = (bubble._raw || "") + content;
  bubble.innerHTML = marked.parse(bubble._raw);
  bubble.classList.add("cursor");
  scrollBottom();
}

function finalizeStreamBubble(bubble) {
  if (!bubble) return;
  bubble.classList.remove("cursor");
  if (bubble._raw) bubble.innerHTML = marked.parse(bubble._raw);
}

// ── Tool card ─────────────────────────────────────────────────────────────────
const _toolCards = {};

function appendToolCard(tool, args) {
  const card = document.createElement("div");
  card.className = "tool-card";
  card.dataset.tool = tool;
  const argsStr = JSON.stringify(args, null, 2);
  card.innerHTML = `
    <div class="tool-header" onclick="this.parentElement.classList.toggle('open')">
      <span class="tool-icon">⚙</span>
      <span class="tool-name">${tool}</span>
      <span class="tool-chevron">▶</span>
    </div>
    <div class="tool-body">
      <pre class="tool-args">${escHtml(argsStr)}</pre>
      <div class="tool-result pending">running...</div>
    </div>`;
  output.appendChild(card);
  _toolCards[tool] = card;
  scrollBottom();
}

function updateToolCard(tool, result) {
  const card = _toolCards[tool];
  if (!card) return;
  const resultEl = card.querySelector(".tool-result");
  resultEl.className = "tool-result done";
  resultEl.textContent = result;
  card.classList.add("open");
  delete _toolCards[tool];
  scrollBottom();
}

// ── Interrupt card ────────────────────────────────────────────────────────────
function appendInterruptCard(interruptId, tool, args) {
  const card = document.createElement("div");
  card.className = "interrupt-card";
  const argsStr = JSON.stringify(args, null, 2);
  card.innerHTML = `
    <div class="interrupt-title">⚠ Approval required: <strong>${tool}</strong></div>
    <pre class="interrupt-args">${escHtml(argsStr)}</pre>
    <div class="interrupt-actions">
      <button class="approve-btn">Approve</button>
      <button class="reject-btn">Reject</button>
    </div>`;

  card.querySelector(".approve-btn").addEventListener("click", () => {
    socket.sendDecision(interruptId, "approve");
    card.classList.add("resolved");
    card.querySelector(".interrupt-actions").innerHTML = `<span class="resolved-label">✓ Approved</span>`;
    setInputEnabled(false);
    sending = true;
  });
  card.querySelector(".reject-btn").addEventListener("click", () => {
    socket.sendDecision(interruptId, "reject");
    card.classList.add("resolved");
    card.querySelector(".interrupt-actions").innerHTML = `<span class="resolved-label rejected">✗ Rejected</span>`;
    setInputEnabled(true);
    sending = false;
  });

  output.appendChild(card); scrollBottom();
}

function escHtml(str) {
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Init ──────────────────────────────────────────────────────────────────────
marked.setOptions({ breaks: true, gfm: true });
loadAgents();
loadSessions();
