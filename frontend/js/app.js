import { AgentSocket } from "./ws.js";

// ── State ────────────────────────────────────────────────────────────────────
let activeAgent = null;
let socket = null;
let streamingBubble = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const output      = document.getElementById("output");
const msgInput    = document.getElementById("msg-input");
const sendBtn     = document.getElementById("send-btn");
const agentLabel  = document.getElementById("agent-label");
const agentHeader = document.getElementById("agent-header");
const sidebar     = document.getElementById("sidebar");
const mainPanel   = document.getElementById("main");
const emptyState  = document.getElementById("empty-state");

// ── Sidebar ──────────────────────────────────────────────────────────────────
async function loadSidebar() {
  const res = await fetch("/api/agents/");
  const groups = await res.json();

  sidebar.innerHTML = "";

  // Group "0" — home item
  const homeGroup = document.createElement("div");
  homeGroup.className = "sidebar-group";
  homeGroup.innerHTML = `
    <div class="sidebar-group-label">0</div>
    <div class="sidebar-item" data-id="__home">
      <div class="dot online"></div>
      <span class="item-name">home</span>
    </div>`;
  sidebar.appendChild(homeGroup);

  for (const [groupName, agents] of Object.entries(groups)) {
    const groupEl = document.createElement("div");
    groupEl.className = "sidebar-group";

    groupEl.innerHTML = `<div class="sidebar-group-label">${groupName}</div>`;

    agents.forEach((agent) => {
      const item = document.createElement("div");
      item.className = "sidebar-item";
      item.dataset.id = agent.id;
      item.innerHTML = `
        <div class="dot online"></div>
        <span class="item-name">${agent.name}</span>`;
      item.addEventListener("click", () => selectAgent(agent));
      groupEl.appendChild(item);
    });

    sidebar.appendChild(groupEl);
  }
}

// ── Select agent ─────────────────────────────────────────────────────────────
function selectAgent(agent) {
  if (activeAgent?.id === agent.id) return;

  // Disconnect old socket
  socket?.disconnect();

  activeAgent = agent;
  streamingBubble = null;

  // UI
  document.querySelectorAll(".sidebar-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.id === agent.id)
  );

  agentHeader.innerHTML = `
    <div class="dot online"></div>
    <span class="agent-title">${agent.name}</span>
    <span class="agent-meta">· ${agent.model ?? "langchain"}</span>`;

  agentLabel.textContent = agent.name;

  emptyState.style.display = "none";
  output.style.display = "flex";
  output.innerHTML = "";

  sendBtn.disabled = true;

  // Connect WebSocket
  socket = new AgentSocket(agent.id, {
    onStatus: (msg) => {
      appendMsg("status", msg);
      sendBtn.disabled = false;
      msgInput.focus();
    },
    onStart: () => {
      streamingBubble = createStreamingBubble(agent.name);
    },
    onToken: (token) => {
      if (streamingBubble) {
        // Remove cursor from previous position, append token
        streamingBubble.classList.remove("cursor");
        streamingBubble.textContent += token;
        streamingBubble.classList.add("cursor");
        output.scrollTop = output.scrollHeight;
      }
    },
    onEnd: () => {
      streamingBubble?.classList.remove("cursor");
      streamingBubble = null;
      sendBtn.disabled = false;
    },
    onError: (err) => {
      appendMsg("error", `Error: ${err}`);
      sendBtn.disabled = false;
    },
  });

  socket.connect();
}

// ── Send message ─────────────────────────────────────────────────────────────
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || !socket) return;

  msgInput.value = "";
  sendBtn.disabled = true;
  socket.send(text);
}

sendBtn.addEventListener("click", sendMessage);
msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ── Message helpers ───────────────────────────────────────────────────────────
function ts() {
  return new Date().toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function appendMsg(type, content) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${type}`;

  if (type !== "status") {
    const meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = ts();
    wrap.appendChild(meta);
  }

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = content;
  wrap.appendChild(bubble);

  output.appendChild(wrap);
  output.scrollTop = output.scrollHeight;
  return bubble;
}

function createStreamingBubble(agentName) {
  const wrap = document.createElement("div");
  wrap.className = "msg agent";

  const meta = document.createElement("div");
  meta.className = "msg-meta";
  meta.textContent = `${agentName} · ${ts()}`;
  wrap.appendChild(meta);

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble cursor";
  wrap.appendChild(bubble);

  output.appendChild(wrap);
  output.scrollTop = output.scrollHeight;
  return bubble;
}

// ── Init ─────────────────────────────────────────────────────────────────────
output.style.display = "none";
loadSidebar();
