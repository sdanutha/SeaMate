import { ChatSocket } from "./ws.js";

// ── State ─────────────────────────────────────────────────────────────────────
let socket = null;
let streamingBubble = null;
let sending = false;

// ── DOM ───────────────────────────────────────────────────────────────────────
const output     = document.getElementById("output");
const msgInput   = document.getElementById("msg-input");
const sendBtn    = document.getElementById("send-btn");
const connStatus = document.getElementById("conn-status");
const agentsList = document.getElementById("agents-list");

// ── Helpers ───────────────────────────────────────────────────────────────────
const ts = () =>
  new Date().toLocaleTimeString("th-TH", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

function scrollBottom() { output.scrollTop = output.scrollHeight; }

function setConnected(ok) {
  connStatus.textContent = ok ? "LIVE" : "OFFLINE";
  connStatus.className   = `status ${ok ? "online" : "offline"}`;
}

function setInputEnabled(enabled) {
  msgInput.disabled = !enabled;
  sendBtn.disabled  = !enabled;
  if (enabled) msgInput.focus();
}

// ── Load agents sidebar ───────────────────────────────────────────────────────
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
        item.innerHTML = `<div class="dot online"></div>
          <span class="item-name">${agent.name}</span>
          <span class="agent-badge">${agent.role === "orchestrator" ? "" : "sub"}</span>`;
        agentsList.appendChild(item);
      });
    }
  } catch (_) {}
}

// ── Message builders ──────────────────────────────────────────────────────────
function appendStatus(text) {
  const el = document.createElement("div");
  el.className = "msg status";
  el.innerHTML = `<div class="msg-bubble">${text}</div>`;
  output.appendChild(el);
  scrollBottom();
}

function appendError(text) {
  const el = document.createElement("div");
  el.className = "msg error";
  el.innerHTML = `<div class="msg-meta">${ts()}</div><div class="msg-bubble">${text}</div>`;
  output.appendChild(el);
  scrollBottom();
}

function createStreamBubble(label, type) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${type}`;
  wrap.innerHTML = `<div class="msg-meta">${label} · ${ts()}</div><div class="msg-bubble cursor"></div>`;
  output.appendChild(wrap);
  scrollBottom();
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

// ── Send ──────────────────────────────────────────────────────────────────────
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || !socket?.ready || sending) return;
  sending = true;
  msgInput.value = "";
  setInputEnabled(false);

  // Show user message
  const userWrap = document.createElement("div");
  userWrap.className = "msg user";
  userWrap.innerHTML = `<div class="msg-meta">you · ${ts()}</div><div class="msg-bubble">${marked.parse(text)}</div>`;
  output.appendChild(userWrap);
  scrollBottom();

  socket.sendMessage(text);
}

sendBtn.addEventListener("click", sendMessage);
msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ── Connect WebSocket ─────────────────────────────────────────────────────────
function connectChat() {
  socket = new ChatSocket({
    onStatus: (msg) => {
      setConnected(true);
      setInputEnabled(true);
      appendStatus(msg);
    },
    onDisconnect: () => {
      setConnected(false);
      setInputEnabled(false);
    },
    onError: (err) => {
      appendError(err);
      setInputEnabled(true);
      sending = false;
    },
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
  });

  socket.connect();
}

// ── Theme toggle ──────────────────────────────────────────────────────────────
const themeToggle = document.getElementById("theme-toggle");
const _THEME_KEY  = "seamate-theme";

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.textContent = theme === "dark" ? "☀" : "🌙";
  themeToggle.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  localStorage.setItem(_THEME_KEY, theme);
}

applyTheme(localStorage.getItem(_THEME_KEY) || "dark");

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
});

// ── Init ──────────────────────────────────────────────────────────────────────
marked.setOptions({ breaks: true, gfm: true });
loadAgents();
connectChat();
